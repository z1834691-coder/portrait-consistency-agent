"""Explicit opt-in smoke runner for Tencent ImageModeration.

The default path never reads image bytes or calls Tencent.  The live path is
only for one user-authorized local image and prints a deliberately redacted
receipt: no Base64, credentials, file name, label detail, or raw image data.
It verifies the provider gate, not the correctness of a complete safety policy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from portrait_consistency_agent.core.settings import AppSettings
from portrait_consistency_agent.services.tencent_safety import (
    ContentSafetyCredentialsMissingError,
    TencentContentSafetyApiError,
    TencentImageModerationClient,
    build_content_safety_decision,
)


def print_status(payload: dict[str, object]) -> None:
    """Write only a JSON-safe, non-sensitive smoke receipt."""

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def fail_before_network(reason: str, *, exit_code: int) -> int:
    print_status({"status": "not_run", "reason": reason, "network_called": False})
    return exit_code


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Explicit opt-in Tencent ImageModeration smoke runner"
    )
    parser.add_argument(
        "--allow-live", action="store_true", help="Required before any Tencent call"
    )
    parser.add_argument("--image", type=Path, help="Authorized local image")
    return parser.parse_args()


def load_image(path: Path) -> bytes:
    if not path.is_file():
        raise ValueError("Image path does not exist or is not a file")
    return path.read_bytes()


def main() -> int:
    args = parse_args()
    if not args.allow_live:
        return fail_before_network(
            "Pass --allow-live only after configuring credentials and choosing an "
            "authorized image.",
            exit_code=0,
        )
    settings = AppSettings()
    if not settings.has_tencent_credentials:
        return fail_before_network(
            "Tencent credentials are missing. Configure both values in local .env; "
            "do not paste them into chat.",
            exit_code=2,
        )
    if args.image is None:
        return fail_before_network("--image is required for a live request.", exit_code=2)

    try:
        image_bytes = load_image(args.image)
    except ValueError as exc:
        return fail_before_network(str(exc), exit_code=2)

    image_sha256 = hashlib.sha256(image_bytes).hexdigest()
    client = TencentImageModerationClient(settings)
    try:
        response = client.moderate_base64(image_bytes)
        decision = build_content_safety_decision(
            response,
            receipt_ref=f"safety_smoke_{image_sha256[:16]}",
        )
    except (ContentSafetyCredentialsMissingError, TencentContentSafetyApiError, ValueError) as exc:
        error_payload: dict[str, object] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
        if isinstance(exc, TencentContentSafetyApiError):
            error_payload.update({"error_code": exc.error_code, "request_id": exc.request_id})
        print_status(
            {
                "status": "failed",
                "network_called": True,
                "image_sha256": image_sha256,
                "error": error_payload,
            }
        )
        return 1

    print_status(
        {
            "status": "succeeded",
            "network_called": True,
            "image_sha256": image_sha256,
            "content_safety": {
                "status": decision.status.value,
                "reason_code": decision.reason_code,
                "provider": decision.evidence.provider,
                "operation": decision.evidence.operation,
                "provider_version": decision.evidence.provider_version,
                "provider_request_id": decision.evidence.provider_request_id,
            },
            "warning": (
                "This verifies one provider receipt only; it does not prove complete "
                "content-safety coverage."
            ),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
