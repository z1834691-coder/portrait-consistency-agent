"""Tencent ImageModeration adapter for the pre-processing safety gate."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final

from portrait_consistency_agent.core.contracts import (
    ContentSafetyEvidence,
    ContentSafetyStatus,
)
from portrait_consistency_agent.core.settings import AppSettings

MAX_BASE64_BYTES: Final[int] = 10 * 1024 * 1024
MODERATION_API_VERSION: Final[str] = "2020-12-29"
MODERATION_OPERATION: Final[str] = "ImageModeration"


class ContentSafetyCredentialsMissingError(RuntimeError):
    """Raised before a network call when Tencent credentials are absent."""


class TencentContentSafetyApiError(RuntimeError):
    """A safe provider failure suitable for a trace/error summary."""

    def __init__(self, error_code: str, message: str, request_id: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.request_id = request_id


def safe_error_trace(exception: BaseException) -> dict[str, object]:
    """Return the minimum safe provider error facts for a trace.

    Tencent's SDK error body can contain request-specific detail.  The UI and
    the local ledger therefore keep only the stable exception type, Tencent's
    error code, and its request id when available.  The image, credentials,
    and raw SDK message never enter this projection.
    """

    payload: dict[str, object] = {"error_type": type(exception).__name__}
    if isinstance(exception, TencentContentSafetyApiError):
        payload["error_code"] = exception.error_code
        payload["provider_request_id"] = exception.request_id
    return payload


def safe_error_message(exception: BaseException) -> str:
    """Create a user-readable error without exposing image or credential data."""

    if isinstance(exception, TencentContentSafetyApiError):
        request_id = exception.request_id or "未返回"
        return (
            "Tencent ImageModeration 调用失败。"
            f"错误码：{exception.error_code}；RequestId：{request_id}。"
            "请保留这两项回执用于排查，系统不会继续放行本次照片。"
        )
    return str(exception)


@dataclass(frozen=True)
class TencentImageModerationResponse:
    request_id: str
    suggestion: str
    label: str | None
    sub_label: str | None
    score: float | None


@dataclass(frozen=True)
class ContentSafetyDecision:
    status: ContentSafetyStatus
    evidence: ContentSafetyEvidence
    reason_code: str


def _sdk_error_code(exception: object) -> str:
    get_code = getattr(exception, "get_code", None)
    code = get_code() if callable(get_code) else None
    return str(code or "TENCENT_SDK_ERROR")


def _as_base64(image: bytes | str) -> str:
    if isinstance(image, bytes):
        if not image:
            raise ValueError("image bytes must not be empty")
        encoded = base64.b64encode(image).decode("ascii")
    else:
        encoded = image.strip()
        if not encoded:
            raise ValueError("image base64 must not be empty")
    if len(encoded.encode("ascii")) > MAX_BASE64_BYTES:
        raise ValueError("image base64 exceeds Tencent ImageModeration's 10MB limit")
    return encoded


class TencentImageModerationClient:
    """V0 synchronous safety adapter; it never stores the image payload."""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    @staticmethod
    def build_base64_request(
        image: bytes | str,
        *,
        biz_type: str = "",
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "FileContent": _as_base64(image),
            "Type": "IMAGE",
        }
        if biz_type.strip():
            payload["BizType"] = biz_type.strip()
        return payload

    def moderate_base64(
        self,
        image: bytes | str,
    ) -> TencentImageModerationResponse:
        if not self.settings.has_tencent_credentials:
            raise ContentSafetyCredentialsMissingError(
                "Tencent credentials are absent. Configure both "
                "TENCENT_SECRET_ID and TENCENT_SECRET_KEY in local .env or Streamlit "
                "Cloud App Settings → Secrets before a live ImageModeration call."
            )
        try:
            from tencentcloud.common import credential
            from tencentcloud.common.exception.tencent_cloud_sdk_exception import (
                TencentCloudSDKException,
            )
            from tencentcloud.common.profile.client_profile import ClientProfile
            from tencentcloud.common.profile.http_profile import HttpProfile
            from tencentcloud.ims.v20201229 import ims_client, models
        except ImportError as exc:  # pragma: no cover - dependency test covers normal path
            raise TencentContentSafetyApiError(
                "SDK_MISSING",
                "Tencent IMS SDK is not installed in the current environment.",
            ) from exc

        try:
            credentials = credential.Credential(
                self.settings.tencent_secret_id.get_secret_value(),  # type: ignore[union-attr]
                self.settings.tencent_secret_key.get_secret_value(),  # type: ignore[union-attr]
            )
            http_profile = HttpProfile()
            http_profile.endpoint = self.settings.tencent_moderation_endpoint
            client_profile = ClientProfile()
            client_profile.httpProfile = http_profile
            client = ims_client.ImsClient(
                credentials,
                self.settings.tencent_region,
                client_profile,
            )
            request = models.ImageModerationRequest()
            request.from_json_string(
                json.dumps(
                    self.build_base64_request(
                        image,
                        biz_type=self.settings.tencent_moderation_biz_type,
                    )
                )
            )
            response = client.ImageModeration(request)
        except TencentCloudSDKException as exc:
            error_code = _sdk_error_code(exc)
            request_id = getattr(exc, "get_request_id", lambda: None)()
            raise TencentContentSafetyApiError(
                error_code or "TENCENT_SDK_ERROR",
                "Tencent ImageModeration request failed. See the receipt for "
                "request_id/error_code.",
                request_id=request_id,
            ) from exc

        request_id = getattr(response, "RequestId", None)
        suggestion = getattr(response, "Suggestion", None)
        if not request_id:
            raise TencentContentSafetyApiError(
                "MISSING_REQUEST_ID",
                "Tencent returned no RequestId; the safety result cannot be audited.",
            )
        if not suggestion:
            raise TencentContentSafetyApiError(
                "MISSING_SUGGESTION",
                "Tencent returned no ImageModeration suggestion.",
                request_id=request_id,
            )
        score = getattr(response, "Score", None)
        return TencentImageModerationResponse(
            request_id=request_id,
            suggestion=str(suggestion),
            label=getattr(response, "Label", None) or None,
            sub_label=getattr(response, "SubLabel", None) or None,
            score=float(score) if score is not None else None,
        )


def build_content_safety_decision(
    response: TencentImageModerationResponse,
    *,
    receipt_ref: str,
    policy_version: str = "content-safety-v0",
) -> ContentSafetyDecision:
    """Map Pass to allow; hold Review/Block as blocked until a human policy exists."""

    suggestion = response.suggestion.strip().lower()
    if suggestion == "pass":
        status = ContentSafetyStatus.PASSED
        reason_code = "content_safety_provider_passed"
    elif suggestion == "review":
        status = ContentSafetyStatus.BLOCKED
        reason_code = "content_safety_review_required"
    else:
        status = ContentSafetyStatus.BLOCKED
        reason_code = "content_safety_provider_blocked"
    evidence = ContentSafetyEvidence(
        provider="tencent_ims",
        operation=MODERATION_OPERATION,
        provider_version=MODERATION_API_VERSION,
        policy_version=policy_version,
        receipt_ref=receipt_ref,
        provider_request_id=response.request_id,
        evaluated_at=datetime.now(timezone.utc),
    )
    return ContentSafetyDecision(status=status, evidence=evidence, reason_code=reason_code)
