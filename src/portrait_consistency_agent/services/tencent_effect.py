"""Candidate Tencent Effect SDK capability card and a safe adapter shell.

This module is deliberately *not* a Tencent SDK integration.  The Effect SDK
route is a client/Web/PC/mobile candidate, while the current project only has a
verified Tencent BeautifyPic REST adapter.  Until a licensed package, exact
platform API, static-image behavior, pricing, privacy terms, and a real smoke
receipt are verified, this module may only prepare a redacted request envelope
and explain why live execution is blocked.

The shell never imports a vendor SDK, reads image bytes, accepts Base64, stores
keys, or makes a network call.  That makes it useful for testing the future
Provider Card/Adapter/permission/budget boundary without creating a hidden
outbound path.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from portrait_consistency_agent.services.provider_cards import load_tencent_effect_card

EFFECT_CARD_ID = "tencent-effect-sdk-candidate"
EFFECT_CARD_VERSION = "candidate_2026-08-30"
EFFECT_OPERATION = "EffectSDK"


class EffectPlatform(str, Enum):
    """Surfaces that must be verified independently for the candidate SDK."""

    WEB = "web"
    PC = "pc"
    MOBILE = "mobile"


class EffectLicenseStatus(str, Enum):
    """Vendor license states used by the deterministic live gate."""

    NOT_OBTAINED = "not_obtained"
    PENDING_VENDOR_CONFIRMATION = "pending_vendor_confirmation"
    TEST_ACTIVE = "test_active"
    PRODUCTION_ACTIVE = "production_active"
    EXPIRED = "expired"


class EffectCardReviewStatus(str, Enum):
    CANDIDATE = "candidate"


class EffectParameterStatus(str, Enum):
    DOCUMENTED_CANDIDATE = "documented_candidate"
    CANDIDATE_PARAMETER_GROUP = "candidate_parameter_group"
    DOCUMENTED_FEATURE_NO_STATIC_MAPPING = "documented_feature_no_static_mapping"
    NOT_VERIFIED = "not_verified"


class EffectStaticExecutionStatus(str, Enum):
    PENDING_VERIFICATION = "pending_verification"
    NOT_PROMISED = "not_promised"


class EffectStaticImageStatus(str, Enum):
    """Whether official material documents a static-image path for a surface.

    This is deliberately separate from a project live receipt.  A document can
    show a browser tutorial without proving that this project has a License,
    the needed parameter, or an integrated runtime.
    """

    DOCUMENTED_NOT_LIVE_VERIFIED = "documented_not_live_verified"
    NOT_DOCUMENTED_FOR_THIS_SPIKE = "not_documented_for_this_spike"


class EffectBatchStatus(str, Enum):
    """Batch facts may not be inferred from a single-image tutorial."""

    NOT_DOCUMENTED_IN_REVIEWED_SOURCES = "not_documented_in_reviewed_sources"


class EffectCardParameter(BaseModel):
    """One candidate feature mapping; it is not an executable mapping yet."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    feature_code: str = Field(min_length=2, max_length=96)
    provider_parameter: str | None = Field(default=None, min_length=2, max_length=128)
    documented_range: tuple[float, float] | None = None
    documentation_status: EffectParameterStatus
    static_image_execution_status: EffectStaticExecutionStatus
    source_scope: str = Field(min_length=8, max_length=160)
    execution_mapping_status: Literal["not_verified_for_current_static_surface", "not_promised"]
    notes: str = Field(min_length=8, max_length=512)

    @model_validator(mode="after")
    def validate_range(self) -> EffectCardParameter:
        if self.documented_range is not None:
            lower, upper = self.documented_range
            if lower >= upper:
                raise ValueError("documented parameter range must be ordered")
        if self.documentation_status == EffectParameterStatus.NOT_VERIFIED:
            if self.provider_parameter is not None or self.documented_range is not None:
                raise ValueError("unverified parameters cannot carry a provider key or range")
            if self.static_image_execution_status != EffectStaticExecutionStatus.NOT_PROMISED:
                raise ValueError("unverified parameters must be not_promised for static execution")
            if self.execution_mapping_status != "not_promised":
                raise ValueError("unverified parameters must not claim a current static mapping")
        if self.documentation_status == EffectParameterStatus.DOCUMENTED_FEATURE_NO_STATIC_MAPPING:
            if (
                self.static_image_execution_status
                != EffectStaticExecutionStatus.PENDING_VERIFICATION
            ):
                raise ValueError("documented feature groups remain pending for static execution")
        return self


class EffectPlatformCapability(BaseModel):
    """A platform-level candidate status; all runtime capabilities stay pending."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: Literal["candidate"]
    static_image_status: EffectStaticImageStatus
    batch_status: EffectBatchStatus
    license_status: EffectLicenseStatus
    official_evidence: list[str] = Field(min_length=1, max_length=8)


class EffectLicenseGate(BaseModel):
    """Non-secret License facts required before a real SDK call."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: EffectLicenseStatus
    test_license_obtained: bool
    production_license_obtained: bool
    required_before_live: bool = True
    open_questions: list[str] = Field(min_length=1, max_length=12)


class EffectPermissionBudgetGate(BaseModel):
    """Card-level defaults; per-request checks live in :class:`EffectGateInput`."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    live_allowed_by_default: Literal[False]
    required_checks: list[str] = Field(min_length=1, max_length=24)
    provider_permission_status: Literal["not_requested"]
    pricing_status: Literal["pending_vendor_quote"]
    estimated_cost_cny_per_image: float | None = Field(default=None, ge=0.0)
    plan_budget_cny: float | None = Field(default=None, ge=0.0)


class EffectDataBoundary(BaseModel):
    """Explicitly unknown vendor data behavior, never treated as local by default."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    processing_mode_candidate: Literal["platform_specific_not_assumed"]
    image_outbound_status: Literal["unknown_pending_license_privacy_review"]
    vendor_retention_status: Literal["unknown_pending_vendor_terms"]
    telemetry_status: Literal["unknown_pending_vendor_terms"]
    android_ios_face_photo_evidence: str = Field(min_length=16, max_length=320)
    web_image_processing_evidence: str = Field(min_length=16, max_length=320)
    region_evidence: str = Field(min_length=16, max_length=320)
    must_not_assume_local_processing: Literal[True]
    must_not_send_user_photo_in_shell: Literal[True]


class EffectBatchCapability(BaseModel):
    """Batch facts deliberately remain pending until an actual surface is tested."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: EffectBatchStatus
    max_images: int | None = Field(default=None, ge=1)
    per_image_plan_required: Literal[True]
    same_parameter_reuse_allowed: Literal[False]


class TencentEffectCapabilityCard(BaseModel):
    """Typed projection of ``data/provider_cards/tencent_effect_sdk.json``."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    card_id: Literal["tencent-effect-sdk-candidate"]
    provider: Literal["tencent_cloud"]
    operation: Literal["EffectSDK"]
    api_version: str = Field(min_length=1, max_length=96)
    card_version: Literal["candidate_2026-08-30"]
    review_status: EffectCardReviewStatus
    reviewed_at: str = Field(min_length=10, max_length=32)
    integration_kind: Literal["client_sdk"]
    endpoint: None = None
    platforms: dict[EffectPlatform, EffectPlatformCapability]
    parameters: list[EffectCardParameter] = Field(min_length=1, max_length=64)
    batch: EffectBatchCapability
    license: EffectLicenseGate
    permission_budget_gate: EffectPermissionBudgetGate
    data_boundary: EffectDataBoundary
    safety_boundary: dict[str, object]
    evidence_review: dict[str, object]
    source: dict[str, str]

    @model_validator(mode="after")
    def validate_card(self) -> TencentEffectCapabilityCard:
        if self.review_status != EffectCardReviewStatus.CANDIDATE:
            raise ValueError("Tencent Effect SDK remains candidate until all admission gates pass")
        expected = set(EffectPlatform)
        if set(self.platforms) != expected:
            raise ValueError("candidate card must state web, pc, and mobile surfaces")
        features = [parameter.feature_code for parameter in self.parameters]
        if len(features) != len(set(features)):
            raise ValueError("candidate card parameter feature codes must be unique")
        return self


class EffectGateInput(BaseModel):
    """Per-request evidence needed to even consider a future live SDK call."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    allow_live: bool = False
    platform: EffectPlatform
    license_status: EffectLicenseStatus = EffectLicenseStatus.PENDING_VENDOR_CONFIRMATION
    provider_permission_granted: bool = False
    user_image_consent: bool = False
    outbound_data_approved: bool = False
    region_approved: bool = False
    adapter_ready: bool = False
    static_image_smoke_passed: bool = False
    estimated_cost_cny: float | None = Field(default=None, ge=0.0)
    plan_budget_cny: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def validate_cost_pair(self) -> EffectGateInput:
        if self.estimated_cost_cny is not None and self.plan_budget_cny is not None:
            if self.estimated_cost_cny > self.plan_budget_cny:
                # The decision method also returns a safe reason code.  This
                # validator only guards an impossible negative/contradictory
                # pair from silently reaching an adapter.
                return self
        return self


class EffectGateDecision(BaseModel):
    """Deterministic, user-safe explanation of why a live call is allowed/blocked."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    allowed: bool
    reason_codes: list[str] = Field(min_length=1, max_length=24)
    card_id: str = Field(min_length=3, max_length=128)
    card_version: str = Field(min_length=1, max_length=64)


class TencentEffectRequest(BaseModel):
    """A redacted future request envelope; it intentionally carries no image."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    request_ref: str = Field(
        min_length=3,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
    )
    input_artifact_ref: str = Field(
        min_length=3,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
    )
    platform: EffectPlatform
    parameters: dict[str, float] = Field(min_length=1, max_length=64)
    batch_size: int = Field(default=1, ge=1, le=100)
    card_id: Literal["tencent-effect-sdk-candidate"] = EFFECT_CARD_ID
    card_version: Literal["candidate_2026-08-30"] = EFFECT_CARD_VERSION
    request_mode: Literal["candidate_shell"] = "candidate_shell"

    @field_validator("parameters")
    @classmethod
    def reject_non_finite_values(cls, values: dict[str, float]) -> dict[str, float]:
        for key, value in values.items():
            if not key.strip():
                raise ValueError("parameter names must not be empty")
            if isinstance(value, bool):
                raise ValueError("parameter values must be numeric, not boolean")
            if not math.isfinite(float(value)):
                raise ValueError("parameter values must be finite")
        return values


class EffectDryRunResult(BaseModel):
    """Safe shell output suitable for an offline Trace or dashboard preview."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: Literal["blocked"]
    request_ref: str
    platform: EffectPlatform
    batch_size: int
    parameter_names: list[str] = Field(min_length=1, max_length=64)
    gate: EffectGateDecision
    trace: list[dict[str, object]] = Field(min_length=1, max_length=12)


class TencentEffectNotReadyError(RuntimeError):
    """Raised instead of making a live request while the candidate gate is open."""

    def __init__(self, decision: EffectGateDecision) -> None:
        self.decision = decision
        super().__init__(
            "Tencent Effect SDK candidate is not live-ready: " + ", ".join(decision.reason_codes)
        )


def load_typed_tencent_effect_card() -> TencentEffectCapabilityCard:
    """Load and strictly validate the candidate card with no network access."""

    return TencentEffectCapabilityCard.model_validate(load_tencent_effect_card())


def evaluate_effect_gate(
    gate: EffectGateInput,
    *,
    card: TencentEffectCapabilityCard | None = None,
) -> EffectGateDecision:
    """Evaluate all deterministic live prerequisites in a stable order.

    A returned ``allowed=True`` would mean prerequisites are present, not that
    this shell can execute.  The current candidate card always remains
    ``review_status=candidate`` and the current adapter remains not-ready, so a
    live call is still impossible until a future product gate changes both.
    """

    card = card or load_typed_tencent_effect_card()
    reasons: list[str] = []
    platform = card.platforms.get(gate.platform)
    if platform is None:
        reasons.append("platform_not_in_candidate_card")
    elif platform.license_status not in {
        EffectLicenseStatus.TEST_ACTIVE,
        EffectLicenseStatus.PRODUCTION_ACTIVE,
    }:
        reasons.append("platform_license_not_active")
    if card.review_status != EffectCardReviewStatus.CANDIDATE:
        reasons.append("card_not_reviewed_active")
    else:
        reasons.append("card_candidate_not_admitted")
    if not gate.allow_live:
        reasons.append("allow_live_not_explicit")
    if gate.license_status not in {
        EffectLicenseStatus.TEST_ACTIVE,
        EffectLicenseStatus.PRODUCTION_ACTIVE,
    }:
        reasons.append("request_license_not_active")
    if not gate.provider_permission_granted:
        reasons.append("provider_permission_missing")
    if not gate.user_image_consent:
        reasons.append("user_image_consent_missing")
    if not gate.outbound_data_approved:
        reasons.append("outbound_data_not_approved")
    if not gate.region_approved:
        reasons.append("region_not_approved")
    if gate.estimated_cost_cny is None:
        reasons.append("estimated_cost_unknown")
    if gate.plan_budget_cny is None:
        reasons.append("plan_budget_not_set")
    elif gate.estimated_cost_cny is not None and gate.estimated_cost_cny > gate.plan_budget_cny:
        reasons.append("budget_exceeded")
    if not gate.adapter_ready:
        reasons.append("adapter_shell_not_live")
    if not gate.static_image_smoke_passed:
        reasons.append("static_image_smoke_not_passed")
    return EffectGateDecision(
        allowed=not reasons,
        reason_codes=reasons or ["all_prerequisites_present"],
        card_id=card.card_id,
        card_version=card.card_version,
    )


class TencentEffectAdapter:
    """Non-network candidate adapter for planning and gate demonstrations."""

    def __init__(self, card: TencentEffectCapabilityCard | None = None) -> None:
        self.card = card or load_typed_tencent_effect_card()

    def prepare_request(
        self,
        *,
        request_ref: str,
        input_artifact_ref: str,
        platform: EffectPlatform,
        parameters: Mapping[str, float],
        batch_size: int = 1,
    ) -> TencentEffectRequest:
        """Create a future request envelope without reading an image.

        The feature keys are checked against the candidate Card and candidate
        ranges.  A successful preparation is *not* an execution permission;
        the returned mode remains ``candidate_shell``.
        """

        known = {parameter.feature_code: parameter for parameter in self.card.parameters}
        unknown = sorted(set(parameters) - set(known))
        if unknown:
            raise ValueError("candidate card does not list feature(s): " + ", ".join(unknown))
        normalized: dict[str, float] = {}
        for feature, raw_value in parameters.items():
            if isinstance(raw_value, bool):
                raise ValueError("candidate parameter values must be numeric, not boolean")
            value = float(raw_value)
            if not math.isfinite(value):
                raise ValueError("candidate parameter values must be finite")
            spec = known[feature]
            if spec.documented_range is None:
                raise ValueError(f"candidate parameter is not range-verified: {feature}")
            lower, upper = spec.documented_range
            if not lower <= value <= upper:
                raise ValueError(f"candidate parameter is outside its documented range: {feature}")
            if spec.provider_parameter in {None, "pending_exact_api_key"}:
                raise ValueError(f"candidate provider key is not verified: {feature}")
            normalized[feature] = value
        return TencentEffectRequest(
            request_ref=request_ref,
            input_artifact_ref=input_artifact_ref,
            platform=platform,
            parameters=normalized,
            batch_size=batch_size,
        )

    # Alias used by future Tool Registry wiring; kept explicit for readability.
    build_request = prepare_request

    def dry_run(
        self,
        request: TencentEffectRequest,
        *,
        gate: EffectGateInput | None = None,
    ) -> EffectDryRunResult:
        """Return a safe blocked result for an offline adapter smoke test."""

        gate = gate or EffectGateInput(platform=request.platform)
        decision = evaluate_effect_gate(gate, card=self.card)
        trace = [
            {
                "step": "candidate_card_loaded",
                "card_id": self.card.card_id,
                "card_version": self.card.card_version,
                "review_status": self.card.review_status.value,
            },
            {
                "step": "request_envelope_validated",
                "platform": request.platform.value,
                "batch_size": request.batch_size,
                "parameter_names": sorted(request.parameters),
            },
            {
                "step": "live_gate_evaluated",
                "allowed": decision.allowed,
                "reason_codes": decision.reason_codes,
            },
            {
                "step": "network_call",
                "status": "not_attempted",
                "reason": "candidate_adapter_has_no_vendor_sdk_or_network_path",
            },
        ]
        return EffectDryRunResult(
            status="blocked",
            request_ref=request.request_ref,
            platform=request.platform,
            batch_size=request.batch_size,
            parameter_names=sorted(request.parameters),
            gate=decision,
            trace=trace,
        )

    def execute(
        self,
        request: TencentEffectRequest,
        *,
        gate: EffectGateInput | None = None,
    ) -> None:
        """Refuse every call until a future admitted adapter replaces this shell."""

        result = self.dry_run(request, gate=gate)
        reasons = list(result.gate.reason_codes)
        if "adapter_shell_not_live" not in reasons:
            reasons.append("adapter_shell_not_live")
        decision = result.gate.model_copy(update={"allowed": False, "reason_codes": reasons})
        raise TencentEffectNotReadyError(decision)
