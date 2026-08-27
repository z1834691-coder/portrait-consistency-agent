"""Explicit opt-in smoke runner for Tencent CompareFace.

The default path never reads image bytes or calls Tencent.  The live path is
only for two user-authorized local images and prints hashes/metadata plus the
provider receipt; it never prints Base64 or credentials.  This script validates
the current-session adapter, not a calibrated identity probability or a full
content-safety/product flow.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from portrait_consistency_agent.core.contracts import PhotoRole
from portrait_consistency_agent.core.settings import AppSettings
from portrait_consistency_agent.services.photo_quality import analyze_photo_bytes
from portrait_consistency_agent.services.tencent_subject import (
    SubjectMatchCredentialsMissingError,
    SubjectMatchPolicy,
    TencentCompareFaceClient,
    TencentSubjectApiError,
    build_subject_match_decision,
)


def print_status(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def fail_before_network(reason: str, *, exit_code: int) -> int:
    print_status({"status": "not_run", "reason": reason, "network_called": False})
    return exit_code


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Explicit opt-in Tencent CompareFace smoke runner")
    parser.add_argument(
        "--allow-live", action="store_true", help="Required before any Tencent call"
    )
    parser.add_argument("--reference", type=Path, help="Authorized local reference image")
    parser.add_argument("--target", type=Path, help="Authorized local target image")
    return parser.parse_args()


def load_image(path: Path) -> bytes:
    if not path.is_file():
        raise ValueError(f"Image path does not exist or is not a file: {path}")
    return path.read_bytes()


def main() -> int:
    args = parse_args()
    if not args.allow_live:
        return fail_before_network(
            "Pass --allow-live only after configuring credentials and choosing "
            "two authorized images.",
            exit_code=0,
        )
    settings = AppSettings()
    if not settings.has_tencent_credentials:
        return fail_before_network(
            "Tencent credentials are missing. Configure both values in local .env; "
            "do not paste them into chat.",
            exit_code=2,
        )
    if args.reference is None or args.target is None:
        return fail_before_network(
            "--reference and --target are required for a live request.", exit_code=2
        )

    try:
        reference_bytes = load_image(args.reference)
        target_bytes = load_image(args.target)
        reference_observation = analyze_photo_bytes(
            reference_bytes,
            photo_id="smoke_reference",
            photo_role=PhotoRole.REFERENCE,
        )
        target_observation = analyze_photo_bytes(
            target_bytes,
            photo_id="smoke_target",
            photo_role=PhotoRole.TARGET,
        )
    except ValueError as exc:
        return fail_before_network(str(exc), exit_code=2)

    observations = {
        "reference": reference_observation.public_projection(),
        "target": target_observation.public_projection(),
    }
    for label, observation in (
        ("reference", reference_observation),
        ("target", target_observation),
    ):
        if observation.face_count != 1:
            return fail_before_network(
                f"{label} must contain exactly one detectable face before CompareFace; "
                f"reasons={list(observation.reason_codes)}",
                exit_code=2,
            )

    client = TencentCompareFaceClient(settings)
    try:
        response = client.compare_base64(
            reference_bytes, target_bytes, policy=SubjectMatchPolicy.v0()
        )
        decision = build_subject_match_decision(
            response,
            receipt_ref="compare_face_smoke_receipt",
        )
    except (SubjectMatchCredentialsMissingError, TencentSubjectApiError, ValueError) as exc:
        error_payload = {"type": type(exc).__name__, "message": str(exc)}
        if isinstance(exc, TencentSubjectApiError):
            error_payload.update({"error_code": exc.error_code, "request_id": exc.request_id})
        print_status(
            {
                "status": "failed",
                "network_called": True,
                "quality": observations,
                "error": error_payload,
            }
        )
        return 1

    print_status(
        {
            "status": "succeeded",
            "network_called": True,
            "quality": observations,
            "subject_match": {
                "status": decision.status.value,
                "reason_code": decision.reason_code,
                "evidence": decision.evidence.model_dump(mode="json"),
            },
            "warning": "Provider raw score is not a calibrated probability and is not a "
            "V0 user-facing score.",
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
