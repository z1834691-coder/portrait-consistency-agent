"""Explicit opt-in smoke runner for Tencent BeautifyPic.

Without --allow-live this script never reads an image or calls Tencent. With
--allow-live it only uses a user-authorized local image and redacts all image
payloads and credentials from its JSON output. It no longer writes a result to
``storage/results``: current V0 policy keeps result bytes only in the live
process that requested them.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from portrait_consistency_agent.core.contracts import (
    ArtifactLifecycle,
    ErrorCategory,
    ErrorPhase,
    ProviderErrorDetail,
    ProviderRun,
    ProviderRunStatus,
    TencentBeautifyParams,
)
from portrait_consistency_agent.core.policies import build_v0_execution_policy
from portrait_consistency_agent.core.settings import AppSettings
from portrait_consistency_agent.services.tencent_beautify import (
    TencentBeautifyApiError,
    TencentBeautifyClient,
    TencentCredentialsMissingError,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAX_BASE64_BYTES = 5 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Explicit opt-in Tencent BeautifyPic smoke runner")
    parser.add_argument(
        "--allow-live", action="store_true", help="Required before any Tencent call"
    )
    parser.add_argument("--image", type=Path, help="A local, user-authorized image for a live call")
    parser.add_argument("--face-lifting", type=int, default=0)
    parser.add_argument("--eye-enlarging", type=int, default=0)
    parser.add_argument("--whitening", type=int, default=0)
    parser.add_argument("--smoothing", type=int, default=0)
    return parser.parse_args()


def print_status(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def fail_before_network(reason: str, *, exit_code: int) -> int:
    print_status({"status": "not_run", "reason": reason, "network_called": False})
    return exit_code


def load_authorized_image(image_path: Path) -> tuple[bytes, str]:
    if image_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError("Only PNG, JPG, JPEG, and BMP are supported by this V0 smoke script")
    if not image_path.is_file():
        raise ValueError("Image path does not exist or is not a file")
    image_bytes = image_path.read_bytes()
    image_base64 = base64.b64encode(image_bytes).decode("ascii")
    if len(image_base64.encode("ascii")) > MAX_BASE64_BYTES:
        raise ValueError("Base64 image exceeds Tencent's documented 5 MB limit")
    return image_bytes, image_base64


def build_request_hash(image_bytes: bytes, params: TencentBeautifyParams) -> str:
    material = hashlib.sha256(image_bytes).hexdigest() + params.model_dump_json()
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def main() -> int:
    args = parse_args()
    settings = AppSettings()
    params = TencentBeautifyParams(
        face_lifting=args.face_lifting,
        eye_enlarging=args.eye_enlarging,
        whitening=args.whitening,
        smoothing=args.smoothing,
    )

    if not args.allow_live:
        return fail_before_network(
            "Pass --allow-live only after configuring local credentials "
            "and choosing an authorized image.",
            exit_code=0,
        )
    if not settings.has_tencent_credentials:
        return fail_before_network(
            "Tencent credentials are missing. Configure both values in local .env; "
            "do not paste them into chat.",
            exit_code=2,
        )
    if args.image is None:
        return fail_before_network("--image is required for a live request.", exit_code=2)

    try:
        image_bytes, image_base64 = load_authorized_image(args.image)
    except ValueError as exc:
        return fail_before_network(str(exc), exit_code=2)

    run_id = f"run_{uuid.uuid4().hex}"
    idempotency_key = f"idem_{uuid.uuid4().hex}"
    started_at = utc_now()
    started_clock = time.perf_counter()
    request_hash = build_request_hash(image_bytes, params)
    input_artifact_sha256 = hashlib.sha256(image_bytes).hexdigest()
    confirmation_scope_hash = hashlib.sha256(
        json.dumps(
            {
                "input_artifact_sha256": input_artifact_sha256,
                "params": params.model_dump(mode="json"),
                "purpose": "explicit_cli_smoke",
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    client = TencentBeautifyClient(settings)

    try:
        response = client.beautify_base64(image_base64, params)
        if not response.result_image_base64:
            raise TencentBeautifyApiError(
                "UNEXPECTED_RESULT_TYPE",
                "V0 expects a base64 result image from Tencent.",
                request_id=response.request_id,
            )
        result_bytes = base64.b64decode(response.result_image_base64, validate=True)
        latency_ms = round((time.perf_counter() - started_clock) * 1000)
        completed_at = utc_now()
        execution_policy = build_v0_execution_policy()
        provider_run = ProviderRun(
            run_id=run_id,
            trace_id=f"trace_{run_id.removeprefix('run_')}",
            plan_id="smoke_plan_001",
            plan_revision=1,
            session_id="smoke_session_001",
            photo_id=f"photo_{input_artifact_sha256[:16]}",
            attempt_number=1,
            provider_api_version="2019-12-13",
            region=settings.tencent_region,
            endpoint=settings.tencent_beautify_endpoint,
            provider_card_id="tencent-beautify-pic-2019-12-13",
            provider_card_version="reviewed_2026-08-27",
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            request_params=params,
            input_artifact_ref=f"authorized_photo_{input_artifact_sha256[:16]}",
            input_artifact_sha256=input_artifact_sha256,
            confirmation_ref="authorized_cli_smoke",
            confirmation_scope_hash=confirmation_scope_hash,
            consent_policy_version="cli-smoke-v1",
            status=ProviderRunStatus.SUCCEEDED,
            provider_request_id=response.request_id,
            result_artifact_ref=f"memory_only_smoke_{response.request_id}",
            result_artifact_sha256=hashlib.sha256(result_bytes).hexdigest(),
            artifact_lifecycle=ArtifactLifecycle(
                expires_at=completed_at
                + timedelta(minutes=execution_policy.result_memory_ttl_minutes)
            ),
            network_latency_ms=latency_ms,
            total_latency_ms=latency_ms,
            started_at=started_at,
            completed_at=completed_at,
        )
        print_status({"status": "succeeded", "provider_run": provider_run.model_dump(mode="json")})
        return 0
    except (TencentCredentialsMissingError, TencentBeautifyApiError, ValueError) as exc:
        latency_ms = round((time.perf_counter() - started_clock) * 1000)
        request_id = exc.request_id if isinstance(exc, TencentBeautifyApiError) else None
        error_code = (
            exc.error_code if isinstance(exc, TencentBeautifyApiError) else "LOCAL_VALIDATION_ERROR"
        )
        completed_at = utc_now()
        provider_run = ProviderRun(
            run_id=run_id,
            trace_id=f"trace_{run_id.removeprefix('run_')}",
            plan_id="smoke_plan_001",
            plan_revision=1,
            session_id="smoke_session_001",
            photo_id=f"photo_{input_artifact_sha256[:16]}",
            attempt_number=1,
            provider_api_version="2019-12-13",
            region=settings.tencent_region,
            endpoint=settings.tencent_beautify_endpoint,
            provider_card_id="tencent-beautify-pic-2019-12-13",
            provider_card_version="reviewed_2026-08-27",
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            request_params=params,
            input_artifact_ref=f"authorized_photo_{input_artifact_sha256[:16]}",
            input_artifact_sha256=input_artifact_sha256,
            confirmation_ref="authorized_cli_smoke",
            confirmation_scope_hash=confirmation_scope_hash,
            consent_policy_version="cli-smoke-v1",
            status=ProviderRunStatus.FAILED,
            provider_request_id=request_id,
            network_latency_ms=latency_ms,
            total_latency_ms=latency_ms,
            error=ProviderErrorDetail(
                phase=(
                    ErrorPhase.PREFLIGHT
                    if error_code == "LOCAL_VALIDATION_ERROR"
                    else ErrorPhase.PROVIDER
                ),
                category=(
                    ErrorCategory.LOCAL_VALIDATION
                    if error_code == "LOCAL_VALIDATION_ERROR"
                    else ErrorCategory.UNKNOWN
                ),
                provider_code=error_code,
                safe_message="Tencent smoke request failed; inspect the redacted error category.",
                retryable=False,
            ),
            started_at=started_at,
            completed_at=completed_at,
        )
        print_status({"status": "failed", "provider_run": provider_run.model_dump(mode="json")})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
