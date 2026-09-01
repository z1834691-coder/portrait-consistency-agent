"""Tencent CompareFace adapter for current-session same-person routing.

The adapter returns the provider's raw comparison score and model version.  It
never labels that raw score as a probability and it never persists an image or
an embedding.  Classification into ``match / uncertain / no_match`` is a
versioned, replaceable policy outside the SDK call.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final

from pydantic import BaseModel, Field, model_validator

from portrait_consistency_agent.core.contracts import (
    SubjectMatchEvidence,
    SubjectMatchStatus,
)
from portrait_consistency_agent.core.settings import AppSettings

MAX_BASE64_BYTES: Final[int] = 5_242_880
COMPARE_FACE_API_VERSION: Final[str] = "2018-03-01"
COMPARE_FACE_OPERATION: Final[str] = "CompareFace"


class SubjectMatchCredentialsMissingError(RuntimeError):
    """Raised before a network call when the Tencent credential pair is absent."""


class TencentSubjectApiError(RuntimeError):
    """A safe provider failure suitable for a trace/error summary."""

    def __init__(self, error_code: str, message: str, request_id: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.request_id = request_id


class SubjectMatchPolicy(BaseModel):
    """Configurable V0 routing thresholds for Tencent model 3.0 raw scores."""

    policy_id: str = Field(default="subject_match_v0", min_length=1, max_length=64)
    policy_version: str = Field(default="2026-08-27", min_length=1, max_length=64)
    model_version: str = Field(default="3.0", min_length=1, max_length=16)
    raw_score_min: float = Field(default=0.0, ge=0.0, le=100.0)
    raw_score_max: float = Field(default=100.0, ge=0.0, le=100.0)
    uncertain_at_or_above: float = Field(default=50.0, ge=0.0, le=100.0)
    match_at_or_above: float = Field(default=70.0, ge=0.0, le=100.0)

    @classmethod
    def v0(cls) -> SubjectMatchPolicy:
        return cls()

    @model_validator(mode="after")
    def validate_thresholds(self) -> SubjectMatchPolicy:
        if self.raw_score_min >= self.raw_score_max:
            raise ValueError("raw subject-match score scale must be ordered")
        if not self.raw_score_min <= self.uncertain_at_or_above <= self.match_at_or_above:
            raise ValueError("subject-match thresholds must be ordered inside the score scale")
        return self

    def classify(self, raw_score: float) -> SubjectMatchStatus:
        if not self.raw_score_min <= raw_score <= self.raw_score_max:
            raise ValueError("Tencent CompareFace raw score is outside the documented 0..100 scale")
        if raw_score >= self.match_at_or_above:
            return SubjectMatchStatus.MATCH
        if raw_score >= self.uncertain_at_or_above:
            return SubjectMatchStatus.UNCERTAIN
        return SubjectMatchStatus.NO_MATCH


@dataclass(frozen=True)
class TencentCompareFaceResponse:
    request_id: str
    raw_score: float
    face_model_version: str


@dataclass(frozen=True)
class SubjectMatchDecision:
    status: SubjectMatchStatus
    evidence: SubjectMatchEvidence
    reason_code: str


def _sdk_error_code(exception: object) -> str:
    get_code = getattr(exception, "get_code", None)
    code = get_code() if callable(get_code) else None
    return str(code or "TENCENT_SDK_ERROR")


def _as_base64(value: bytes | str, *, name: str) -> str:
    if isinstance(value, bytes):
        if not value:
            raise ValueError(f"{name} image bytes must not be empty")
        encoded = base64.b64encode(value).decode("ascii")
    else:
        encoded = value.strip()
        if not encoded:
            raise ValueError(f"{name} image base64 must not be empty")
    if len(encoded.encode("ascii")) > MAX_BASE64_BYTES:
        raise ValueError(f"{name} image base64 exceeds Tencent's 5MB limit")
    return encoded


class TencentCompareFaceClient:
    """The only V0 external path for current-session subject matching."""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    @staticmethod
    def build_base64_request(
        image_a: bytes | str,
        image_b: bytes | str,
        *,
        policy: SubjectMatchPolicy | None = None,
    ) -> dict[str, object]:
        policy = policy or SubjectMatchPolicy.v0()
        return {
            "ImageA": _as_base64(image_a, name="ImageA"),
            "ImageB": _as_base64(image_b, name="ImageB"),
            "FaceModelVersion": policy.model_version,
            "QualityControl": 0,
            "NeedRotateDetection": 0,
        }

    def compare_base64(
        self,
        image_a: bytes | str,
        image_b: bytes | str,
        *,
        policy: SubjectMatchPolicy | None = None,
    ) -> TencentCompareFaceResponse:
        """Call Tencent and return only its factual request/score receipt."""

        policy = policy or SubjectMatchPolicy.v0()
        if not self.settings.has_tencent_credentials:
            raise SubjectMatchCredentialsMissingError(
                "Tencent credentials are absent. Configure both "
                "TENCENT_SECRET_ID and TENCENT_SECRET_KEY in local .env or Streamlit "
                "Cloud App Settings → Secrets before a live CompareFace call."
            )

        try:
            from tencentcloud.common import credential
            from tencentcloud.common.exception.tencent_cloud_sdk_exception import (
                TencentCloudSDKException,
            )
            from tencentcloud.common.profile.client_profile import ClientProfile
            from tencentcloud.common.profile.http_profile import HttpProfile
            from tencentcloud.iai.v20180301 import iai_client, models
        except ImportError as exc:  # pragma: no cover - dependency test covers normal path
            raise TencentSubjectApiError(
                "SDK_MISSING",
                "Tencent IAI SDK is not installed in the current environment.",
            ) from exc

        try:
            credentials = credential.Credential(
                self.settings.tencent_secret_id.get_secret_value(),  # type: ignore[union-attr]
                self.settings.tencent_secret_key.get_secret_value(),  # type: ignore[union-attr]
            )
            http_profile = HttpProfile()
            http_profile.endpoint = self.settings.tencent_subject_endpoint
            client_profile = ClientProfile()
            client_profile.httpProfile = http_profile
            client = iai_client.IaiClient(
                credentials,
                self.settings.tencent_region,
                client_profile,
            )
            request = models.CompareFaceRequest()
            request.from_json_string(
                json.dumps(self.build_base64_request(image_a, image_b, policy=policy))
            )
            response = client.CompareFace(request)
        except TencentCloudSDKException as exc:
            error_code = _sdk_error_code(exc)
            request_id = getattr(exc, "get_request_id", lambda: None)()
            raise TencentSubjectApiError(
                error_code or "TENCENT_SDK_ERROR",
                "Tencent CompareFace request failed. See the receipt for request_id/error_code.",
                request_id=request_id,
            ) from exc

        request_id = getattr(response, "RequestId", None)
        raw_score = getattr(response, "Score", None)
        face_model_version = getattr(response, "FaceModelVersion", None) or policy.model_version
        if not request_id:
            raise TencentSubjectApiError(
                "MISSING_REQUEST_ID",
                "Tencent returned no RequestId; the match result cannot be audited.",
            )
        if raw_score is None:
            raise TencentSubjectApiError(
                "MISSING_SCORE",
                "Tencent returned no CompareFace score.",
                request_id=request_id,
            )
        try:
            parsed_score = float(raw_score)
        except (TypeError, ValueError) as exc:
            raise TencentSubjectApiError(
                "INVALID_SCORE",
                "Tencent returned an unreadable CompareFace score.",
                request_id=request_id,
            ) from exc
        if not policy.raw_score_min <= parsed_score <= policy.raw_score_max:
            raise TencentSubjectApiError(
                "INVALID_SCORE_SCALE",
                "Tencent returned a score outside the configured raw score scale.",
                request_id=request_id,
            )
        return TencentCompareFaceResponse(
            request_id=request_id,
            raw_score=parsed_score,
            face_model_version=str(face_model_version),
        )


def build_subject_match_decision(
    response: TencentCompareFaceResponse,
    *,
    receipt_ref: str,
    policy: SubjectMatchPolicy | None = None,
) -> SubjectMatchDecision:
    """Convert raw provider evidence to a separately auditable route decision."""

    policy = policy or SubjectMatchPolicy.v0()
    status = policy.classify(response.raw_score)
    reason_code = {
        SubjectMatchStatus.MATCH: "subject_match_provider_threshold_met",
        SubjectMatchStatus.UNCERTAIN: "subject_match_provider_threshold_uncertain",
        SubjectMatchStatus.NO_MATCH: "subject_match_provider_threshold_not_met",
    }[status]
    evidence = SubjectMatchEvidence(
        provider="tencent_iai",
        operation=COMPARE_FACE_OPERATION,
        model_version=response.face_model_version,
        threshold_policy_version=policy.policy_version,
        receipt_ref=receipt_ref,
        provider_request_id=response.request_id,
        raw_score=response.raw_score,
        raw_score_min=policy.raw_score_min,
        raw_score_max=policy.raw_score_max,
        calibrated=False,
        evaluated_at=datetime.now(timezone.utc),
    )
    return SubjectMatchDecision(status=status, evidence=evidence, reason_code=reason_code)
