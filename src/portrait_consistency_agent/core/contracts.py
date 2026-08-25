"""Versioned, JSON-safe contracts shared by every project module.

The contracts deliberately store references and hashes, never raw image bytes,
secrets, or full face-feature vectors. Domain modules may add internal details,
but cross-module inputs and outputs must use one of these models.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTRACT_VERSION = "0.1"

SafeId = Annotated[
    str,
    Field(
        min_length=3,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
        description="Opaque local identifier; never an image payload or secret.",
    ),
]
Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Percent = Annotated[float, Field(ge=0.0, le=100.0)]
Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
RoundNumber = Annotated[int, Field(ge=1, le=3)]
ProviderStrength = Annotated[int, Field(ge=0, le=100)]
UserDelta = Annotated[int, Field(ge=-100, le=100)]


def utc_now() -> datetime:
    """Return an explicit timezone-aware timestamp for traces and persistence."""

    return datetime.now(timezone.utc)


class ContractModel(BaseModel):
    """Base rules for all persisted cross-module payloads."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    contract_version: Literal["0.1"] = CONTRACT_VERSION


class EditableFeature(str, Enum):
    """User-facing adjustment dimensions, including future SDK-only features."""

    FACE_LIFTING = "face_lifting"
    EYE_ENLARGING = "eye_enlarging"
    WHITENING = "whitening"
    SMOOTHING = "smoothing"
    EYE_DISTANCE = "eye_distance"
    MOUTH_SHAPE = "mouth_shape"
    LIPS_THICKNESS = "lips_thickness"
    NOSE_WING = "nose_wing"
    SKIN_TONE = "skin_tone"
    MAKEUP = "makeup"


class AdjustmentMode(str, Enum):
    PRESERVE_ORIGINAL = "preserve_original"
    BALANCED = "balanced"
    CONSISTENCY_FIRST = "consistency_first"


class QualityStatus(str, Enum):
    COMPARABLE = "comparable"
    REJECTED = "rejected"


class QualityFlag(str, Enum):
    NO_FACE = "no_face"
    MULTIPLE_FACES = "multiple_faces"
    BLUR = "blur"
    LOW_EXPOSURE = "low_exposure"
    OVER_EXPOSURE = "over_exposure"
    OCCLUSION = "occlusion"
    EXTREME_POSE = "extreme_pose"
    EXTREME_EXPRESSION = "extreme_expression"
    LOW_RESOLUTION = "low_resolution"


class IntentGoal(str, Enum):
    ALIGN_TO_PROFILE = "align_to_profile"
    DIAGNOSE = "diagnose"
    MANUAL_EDIT = "manual_edit"
    UNKNOWN = "unknown"


class Route(str, Enum):
    SINGLE = "single"
    BATCH = "batch"
    UNKNOWN = "unknown"


class IntentAction(str, Enum):
    DIAGNOSE = "diagnose"
    PROVIDE_PLAN = "provide_plan"
    EXECUTE = "execute"
    UNKNOWN = "unknown"


class IntentSlot(str, Enum):
    GOAL = "goal"
    ROUTE = "route"
    ACTION = "action"
    ALLOWED_FEATURES = "allowed_features"
    STYLE = "style"
    MAX_ROUNDS = "max_rounds"


class FieldSource(str, Enum):
    USER_EXPLICIT = "user_explicit"
    PROFILE_DEFAULT = "profile_default"
    PRODUCT_DEFAULT = "product_default"
    CLARIFICATION = "clarification"


class ConfirmationStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REVOKED = "revoked"


class PlanStatus(str, Enum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    EXECUTING = "executing"
    EXECUTED = "executed"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"


class ProviderRunStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


class VerificationDecision(str, Enum):
    STOP = "stop"
    REPLAN = "replan"
    RESHOOT = "reshoot"
    MANUAL_REVIEW = "manual_review"
    CLOSE = "close"


class StopReason(str, Enum):
    GOAL_MET = "goal_met"
    USER_ACCEPTED = "user_accepted"
    NO_IMPROVEMENT = "no_improvement"
    MAX_ROUNDS = "max_rounds"
    INPUT_NOT_COMPARABLE = "input_not_comparable"
    PROVIDER_UNSUPPORTED = "provider_unsupported"
    PROVIDER_FAILURE = "provider_failure"
    USER_CANCELLED = "user_cancelled"


class ReferenceProfile(ContractModel):
    """A confirmed, versioned representation of the user's reference standard."""

    profile_id: SafeId
    user_id: SafeId
    version: Annotated[int, Field(ge=1)]
    feature_snapshot_ref: SafeId
    allowed_features: list[EditableFeature] = Field(min_length=1)
    blocked_features: list[EditableFeature] = Field(default_factory=list)
    adjustment_mode: AdjustmentMode = AdjustmentMode.BALANCED
    max_rounds: RoundNumber = 3
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_constraints(self) -> ReferenceProfile:
        allowed = set(self.allowed_features)
        blocked = set(self.blocked_features)
        if len(allowed) != len(self.allowed_features):
            raise ValueError("allowed_features must not contain duplicates")
        if len(blocked) != len(self.blocked_features):
            raise ValueError("blocked_features must not contain duplicates")
        if allowed & blocked:
            raise ValueError("allowed_features and blocked_features must not overlap")
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("expires_at must be later than created_at")
        return self


class PhotoQualityResult(ContractModel):
    """Deterministic comparability result without storing a photo or landmarks."""

    photo_id: SafeId
    status: QualityStatus
    face_count: Annotated[int, Field(ge=0, le=10)]
    quality_flags: list[QualityFlag] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list, max_length=8)
    metrics: dict[str, float] = Field(default_factory=dict)
    confidence: Confidence
    analysis_version: str = Field(min_length=1, max_length=64)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_status(self) -> PhotoQualityResult:
        flags = set(self.quality_flags)
        if self.status == QualityStatus.COMPARABLE:
            if self.face_count != 1:
                raise ValueError("comparable photos must contain exactly one face")
            if {QualityFlag.NO_FACE, QualityFlag.MULTIPLE_FACES} & flags:
                raise ValueError("comparable photos cannot contain blocking face flags")
        elif not self.quality_flags and not self.reason_codes:
            raise ValueError("rejected photos need at least one flag or reason code")
        return self


class IntentFrame(ContractModel):
    """A validated interpretation of natural language and current conversation state."""

    session_id: SafeId
    turn: Annotated[int, Field(ge=1)]
    goal: IntentGoal
    route: Route
    action: IntentAction
    allowed_features: list[EditableFeature] = Field(default_factory=list)
    blocked_features: list[EditableFeature] = Field(default_factory=list)
    adjustment_mode: AdjustmentMode | None = None
    max_rounds: RoundNumber | None = None
    field_sources: dict[str, FieldSource] = Field(default_factory=dict)
    confidence: Confidence
    missing_slots: list[IntentSlot] = Field(default_factory=list)
    confirmation_status: ConfirmationStatus = ConfirmationStatus.NOT_REQUIRED
    confirmation_token: str | None = Field(default=None, min_length=8, max_length=256)
    model_provider: str | None = Field(default=None, max_length=64)
    prompt_version: str | None = Field(default=None, max_length=64)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_intent_and_confirmation(self) -> IntentFrame:
        allowed = set(self.allowed_features)
        blocked = set(self.blocked_features)
        if len(allowed) != len(self.allowed_features):
            raise ValueError("allowed_features must not contain duplicates")
        if len(blocked) != len(self.blocked_features):
            raise ValueError("blocked_features must not contain duplicates")
        if allowed & blocked:
            raise ValueError("allowed_features and blocked_features must not overlap")
        if len(set(self.missing_slots)) != len(self.missing_slots):
            raise ValueError("missing_slots must not contain duplicates")

        if self.action == IntentAction.EXECUTE:
            if self.confirmation_status not in {
                ConfirmationStatus.PENDING,
                ConfirmationStatus.CONFIRMED,
                ConfirmationStatus.REVOKED,
            }:
                raise ValueError("execute intent requires an explicit confirmation status")
            if (
                self.confirmation_status
                in {
                    ConfirmationStatus.PENDING,
                    ConfirmationStatus.CONFIRMED,
                }
                and not self.confirmation_token
            ):
                raise ValueError("execute intent requires a confirmation token")
            if self.confirmation_status == ConfirmationStatus.CONFIRMED and self.missing_slots:
                raise ValueError("confirmed execution cannot have unresolved intent slots")
        elif self.confirmation_status != ConfirmationStatus.NOT_REQUIRED:
            raise ValueError("non-execute intent cannot carry an execution confirmation status")
        elif self.confirmation_token is not None:
            raise ValueError("non-execute intent cannot carry a confirmation token")
        return self


class TencentBeautifyParams(ContractModel):
    """All V0 Tencent API parameters are explicit to avoid provider defaults."""

    face_lifting: ProviderStrength = 0
    eye_enlarging: ProviderStrength = 0
    whitening: ProviderStrength = 0
    smoothing: ProviderStrength = 0


class FeatureDelta(ContractModel):
    """A user-visible relative adjustment, distinct from provider absolute values."""

    feature: EditableFeature
    delta: UserDelta
    rationale_code: str = Field(min_length=1, max_length=64)


class EditPlan(ContractModel):
    """A bounded, provider-specific edit plan for exactly one target photo."""

    plan_id: SafeId
    session_id: SafeId
    profile_id: SafeId
    photo_id: SafeId
    iteration: RoundNumber
    provider: Literal["tencent_beautify_pic"] = "tencent_beautify_pic"
    provider_version: str = Field(min_length=1, max_length=64)
    user_deltas: list[FeatureDelta] = Field(default_factory=list, max_length=3)
    provider_absolute_params: TencentBeautifyParams
    expected_index_gain: Percent | None = None
    risk_notes: list[str] = Field(default_factory=list, max_length=5)
    status: PlanStatus = PlanStatus.PROPOSED
    confirmation_token: str | None = Field(default=None, min_length=8, max_length=256)
    planner_version: str = Field(min_length=1, max_length=64)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_plan(self) -> EditPlan:
        features = [delta.feature for delta in self.user_deltas]
        if len(set(features)) != len(features):
            raise ValueError("user_deltas must not target the same feature twice")
        if self.status in {PlanStatus.CONFIRMED, PlanStatus.EXECUTING, PlanStatus.EXECUTED}:
            if not self.confirmation_token:
                raise ValueError("confirmed/executing/executed plans require a confirmation token")
        return self


class ProviderRun(ContractModel):
    """Auditable record of one external provider attempt, without raw payloads."""

    run_id: SafeId
    plan_id: SafeId
    session_id: SafeId
    provider: Literal["tencent_beautify_pic"] = "tencent_beautify_pic"
    operation: Literal["BeautifyPic"] = "BeautifyPic"
    provider_version: str = Field(min_length=1, max_length=64)
    idempotency_key: str = Field(min_length=8, max_length=256)
    request_hash: Sha256
    status: ProviderRunStatus
    provider_request_id: str | None = Field(default=None, min_length=1, max_length=256)
    result_ref: str | None = Field(default=None, min_length=1, max_length=1024)
    latency_ms: Annotated[int, Field(ge=0)] | None = None
    estimated_cost_cny: Annotated[float, Field(ge=0.0)] | None = None
    error_code: str | None = Field(default=None, min_length=1, max_length=128)
    error_message: str | None = Field(default=None, min_length=1, max_length=512)
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_run_outcome(self) -> ProviderRun:
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at cannot be earlier than started_at")
        if self.status == ProviderRunStatus.SUCCEEDED:
            if not self.provider_request_id or not self.result_ref or self.latency_ms is None:
                raise ValueError(
                    "successful runs require request id, result reference, and latency"
                )
        if self.status in {ProviderRunStatus.FAILED, ProviderRunStatus.TIMEOUT}:
            if not self.error_code:
                raise ValueError("failed or timeout runs require an error code")
        return self


class VerificationResult(ContractModel):
    """Deterministic post-edit assessment and the next state-machine decision."""

    verification_id: SafeId
    session_id: SafeId
    plan_id: SafeId
    before_index: Percent
    after_index: Percent
    index_delta: float
    confidence: Confidence
    decision: VerificationDecision
    stop_reason: StopReason | None = None
    verification_version: str = Field(min_length=1, max_length=64)
    result_photo_ref: str = Field(min_length=1, max_length=1024)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_delta_and_decision(self) -> VerificationResult:
        expected_delta = round(self.after_index - self.before_index, 4)
        if abs(self.index_delta - expected_delta) > 0.0001:
            raise ValueError("index_delta must equal after_index - before_index")
        if self.decision in {VerificationDecision.STOP, VerificationDecision.CLOSE}:
            if self.stop_reason is None:
                raise ValueError("stop and close decisions require a stop reason")
        return self
