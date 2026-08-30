"""Candidate Volcengine Beauty API V2 adapter shell.

This module deliberately stops before a real provider call. Official V2
documentation now evidences the asynchronous endpoint shape, Bearer-API-Key
sample and some parameter keys; target-account entitlement, live effects,
pricing, data-processing region and retention behavior are still unverified.
The shell therefore provides typed request facts, an explicit permission/budget
preflight and a deterministic blocked receipt.

It must not be confused with the Tencent image-editing adapter: a Tencent
consent does not authorize sending a photo to Volcengine, and this candidate
card is not yet an executable capability.
"""

from __future__ import annotations

import hashlib
import math
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from portrait_consistency_agent.core.contracts import PositiveInt, Sha256
from portrait_consistency_agent.services.provider_cards import load_volc_beauty_card

VOLC_CONTRACT_VERSION = "volc-beauty-v0.1"
VOLC_PROVIDER = "volcengine"
VOLC_OPERATION = "beautify_image_v2"


class VolcBeautyAdapterError(RuntimeError):
    """Base error for the candidate adapter shell."""


class VolcBeautyExecutionBlockedError(VolcBeautyAdapterError):
    """Raised only by callers that require an executable result from the shell."""

    def __init__(self, reason_codes: tuple[str, ...], message: str) -> None:
        super().__init__(message)
        self.reason_codes = reason_codes


class VolcBeautyNotReadyError(VolcBeautyAdapterError):
    """The candidate has passed local checks in a future branch but lacks a real API."""


class VolcBeautyRequest(BaseModel):
    """Safe request metadata for a future Volcengine call.

    This contract intentionally contains an image hash and byte count, not
    image bytes, Base64, a local path or a signed URL.  ``parameter_values``
    remain non-executable until the target account, live response schema and
    actual visual effects are verified. No photo payload is present here.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    contract_version: Literal["volc-beauty-v0.1"] = VOLC_CONTRACT_VERSION
    provider: Literal["volcengine"] = VOLC_PROVIDER
    operation: Literal["beautify_image_v2"] = VOLC_OPERATION
    image_sha256: Sha256
    image_bytes_size: PositiveInt
    batch_size: int = Field(default=1, ge=1, le=100)
    parameter_values: dict[str, float] = Field(default_factory=dict, max_length=64)
    region: str = Field(default="pending_vendor_confirmation", min_length=1, max_length=96)
    parameter_schema_status: Literal["pending_vendor_confirmation", "verified"] = (
        "pending_vendor_confirmation"
    )

    @field_validator("parameter_values")
    @classmethod
    def validate_parameter_values(cls, values: dict[str, float]) -> dict[str, float]:
        for key, value in values.items():
            if not key.strip():
                raise ValueError("candidate parameter keys must not be blank")
            if not math.isfinite(value):
                raise ValueError("candidate parameter values must be finite")
        return values


class VolcBeautyGate(BaseModel):
    """All gates required before any future image could leave the process."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    allow_live: bool = False
    credentials_present: bool = False
    explicit_provider_consent: bool = False
    outbound_allowed: bool = False
    adapter_ready: bool = False
    requested_region: str = Field(
        default="pending_vendor_confirmation", min_length=1, max_length=96
    )
    estimated_cost_cny: float | None = Field(default=None, ge=0.0)
    spent_cost_cny: float = Field(default=0.0, ge=0.0)
    budget_limit_cny: float | None = Field(default=None, ge=0.0)


class VolcBeautyPreflightResult(BaseModel):
    """Redacted decision evidence; it never contains a request body or secret."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider: Literal["volcengine"] = VOLC_PROVIDER
    operation: Literal["beautify_image_v2"] = VOLC_OPERATION
    allowed: bool
    reason_codes: tuple[str, ...] = ()
    card_id: str = Field(min_length=1, max_length=128)
    card_version: str = Field(min_length=1, max_length=96)
    batch_size: int = Field(ge=1, le=100)
    estimated_cost_cny: float | None = Field(default=None, ge=0.0)
    budget_remaining_cny: float | None = Field(default=None, ge=0.0)
    network_called: Literal[False] = False
    image_sent: Literal[False] = False


class VolcBeautyRunReceipt(BaseModel):
    """A safe candidate-run receipt for offline smoke tests.

    A blocked receipt is not a provider receipt and carries no RequestId.  A
    future real implementation must create the project's factual ProviderRun
    only after an independently approved adapter, card and live smoke.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider: Literal["volcengine"] = VOLC_PROVIDER
    operation: Literal["beautify_image_v2"] = VOLC_OPERATION
    status: Literal["blocked", "not_run", "not_implemented"]
    reason_codes: tuple[str, ...] = ()
    request_sha256: Sha256 | None = None
    provider_request_id: None = None
    network_called: Literal[False] = False
    image_sent: Literal[False] = False


class CandidateImageProviderAdapter(Protocol):
    """Minimal seam shared by a future approved image-provider adapter."""

    def preflight(
        self,
        request: VolcBeautyRequest,
        gate: VolcBeautyGate,
    ) -> VolcBeautyPreflightResult: ...

    def execute(
        self,
        request: VolcBeautyRequest,
        *,
        gate: VolcBeautyGate,
        image_bytes: bytes | None = None,
    ) -> VolcBeautyRunReceipt: ...


def request_from_image_bytes(
    image_bytes: bytes,
    *,
    parameter_values: dict[str, float] | None = None,
    batch_size: int = 1,
    region: str = "pending_vendor_confirmation",
) -> VolcBeautyRequest:
    """Create safe request metadata without retaining or transmitting image bytes."""

    if not image_bytes:
        raise ValueError("image bytes must not be empty")
    return VolcBeautyRequest(
        image_sha256=hashlib.sha256(image_bytes).hexdigest(),
        image_bytes_size=len(image_bytes),
        batch_size=batch_size,
        parameter_values=parameter_values or {},
        region=region,
    )


class VolcBeautyAdapter:
    """Candidate adapter with fail-closed preflight and no network implementation."""

    def __init__(self, card: dict[str, object] | None = None) -> None:
        self.card = card or load_volc_beauty_card()

    def preflight(
        self,
        request: VolcBeautyRequest,
        gate: VolcBeautyGate,
    ) -> VolcBeautyPreflightResult:
        """Evaluate card, consent, credentials, budget and schema gates locally."""

        reason_codes: list[str] = []
        card_id = str(self.card.get("card_id", "missing-card"))
        card_version = str(self.card.get("card_version", "missing-version"))
        if self.card.get("review_status") != "reviewed_active":
            reason_codes.append("provider_card_not_active")
        admission = self.card.get("admission")
        if not isinstance(admission, dict) or admission.get("ready_for_execution") is not True:
            reason_codes.append("provider_card_not_ready")
        if not gate.adapter_ready:
            reason_codes.append("adapter_not_ready")
        if not gate.allow_live:
            reason_codes.append("allow_live_required")
        if not gate.credentials_present:
            reason_codes.append("credentials_missing")
        if not gate.explicit_provider_consent:
            reason_codes.append("provider_outbound_consent_required")
        if not gate.outbound_allowed:
            reason_codes.append("image_outbound_not_allowed")
        if (
            gate.requested_region == "pending_vendor_confirmation"
            or request.region == "pending_vendor_confirmation"
            or gate.requested_region != request.region
        ):
            reason_codes.append("provider_region_unverified")
        if request.parameter_schema_status != "verified":
            reason_codes.append("request_schema_unverified")
        batch_info = self.card.get("batch")
        if request.batch_size > 1 and (
            not isinstance(batch_info, dict) or batch_info.get("max_concurrency") is None
        ):
            reason_codes.append("batch_limit_unverified")
        if gate.budget_limit_cny is None:
            reason_codes.append("budget_limit_unconfigured")
            budget_remaining = None
        else:
            budget_remaining = max(gate.budget_limit_cny - gate.spent_cost_cny, 0.0)
            if gate.estimated_cost_cny is None:
                reason_codes.append("cost_estimate_unverified")
            elif gate.estimated_cost_cny > budget_remaining:
                reason_codes.append("budget_exceeded")
        # The candidate card itself is deliberately not ready, so this can
        # only become true after a later, explicitly approved card revision.
        allowed = not reason_codes
        return VolcBeautyPreflightResult(
            allowed=allowed,
            reason_codes=tuple(dict.fromkeys(reason_codes)),
            card_id=card_id,
            card_version=card_version,
            batch_size=request.batch_size,
            estimated_cost_cny=gate.estimated_cost_cny,
            budget_remaining_cny=budget_remaining,
        )

    def execute(
        self,
        request: VolcBeautyRequest,
        *,
        gate: VolcBeautyGate,
        image_bytes: bytes | None = None,
    ) -> VolcBeautyRunReceipt:
        """Return a blocked offline receipt; never sends image data in this candidate.

        ``image_bytes`` is accepted only as an in-memory future adapter seam.
        The method does not inspect it before preflight and never serializes it.
        Even an all-green synthetic gate cannot pass while the candidate card
        and vendor schema remain unverified.
        """

        del image_bytes  # The shell intentionally has no image/network path.
        decision = self.preflight(request, gate)
        if not decision.allowed:
            return VolcBeautyRunReceipt(
                status="blocked",
                reason_codes=decision.reason_codes,
                request_sha256=request.image_sha256,
            )
        raise VolcBeautyNotReadyError(
            "Volcengine candidate passed local gates unexpectedly; real API schema, auth and "
            "ProviderRun implementation are still required before any network call."
        )
