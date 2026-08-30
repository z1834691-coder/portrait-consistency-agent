"""Versioned, JSON-safe contracts shared by every project module.

Contract v0.4 implements the product rules frozen on 2026-08-28.  Contracts
carry facts and versioned policy snapshots; they never carry raw image bytes,
secrets, signed URLs, hidden reasoning, or an uncalibrated consistency score.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTRACT_VERSION = "0.4"

SafeId = Annotated[
    str,
    Field(
        min_length=3,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
        description="Opaque identifier; never an image payload, path, or secret.",
    ),
]
AuditedKnowledgeRef = Annotated[
    str,
    Field(
        min_length=7,
        max_length=384,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*#[A-Za-z0-9][A-Za-z0-9_-]*@[A-Za-z0-9._-]+$",
        description=(
            "Reviewed knowledge source/chunk/version reference; never a URL or raw content."
        ),
    ),
]
Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
Probability = Annotated[float, Field(ge=0.0, le=1.0)]
PositiveInt = Annotated[int, Field(ge=1)]
NonNegativeInt = Annotated[int, Field(ge=0)]
ProviderStrength = Annotated[int, Field(ge=0, le=100)]


def utc_now() -> datetime:
    """Return an explicit timezone-aware timestamp for persistence and traces."""

    return datetime.now(timezone.utc)


class ContractModel(BaseModel):
    """Base rules for all persisted cross-module payloads."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    contract_version: Literal["0.4"] = CONTRACT_VERSION


class EditableFeature(str, Enum):
    """Product feature vocabulary; execution still depends on a Provider Card."""

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


class PreserveAttribute(str, Enum):
    SKIN_TONE = "skin_tone"
    MAKEUP = "makeup"
    EXPRESSION = "expression"
    BACKGROUND = "background"
    HAIR = "hair"
    BODY = "body"


class AdjustmentMode(str, Enum):
    PRESERVE_ORIGINAL = "preserve_original"
    BALANCED = "balanced"
    CONSISTENCY_FIRST = "consistency_first"


class ProfileStatus(str, Enum):
    ACTIVE = "active"
    GEOMETRY_ONLY = "geometry_only"
    SUPERSEDED = "superseded"
    DELETED = "deleted"


class MeasurementStatus(str, Enum):
    MEASURED = "measured"
    ESTIMATED = "estimated"
    UNAVAILABLE = "unavailable"


class MeasurementUnit(str, Enum):
    NORMALIZED_RATIO = "normalized_ratio"
    ANGLE_DEGREES = "angle_degrees"
    NORMALIZED_POSITION = "normalized_position"
    CATEGORICAL_CODE = "categorical_code"


class AnchorStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    DELETE_PENDING = "delete_pending"
    DELETED = "deleted"


class CapabilityMode(str, Enum):
    EXECUTABLE = "executable"
    SUGGESTION_ONLY = "suggestion_only"
    UNSUPPORTED = "unsupported"


class PhotoRole(str, Enum):
    REFERENCE = "reference"
    TARGET = "target"
    RESULT = "result"


class SubjectMatchStatus(str, Enum):
    NOT_APPLICABLE = "not_applicable"
    MATCH = "match"
    UNCERTAIN = "uncertain"
    NO_MATCH = "no_match"


class ContentSafetyStatus(str, Enum):
    NOT_EVALUATED = "not_evaluated"
    PASSED = "passed"
    BLOCKED = "blocked"


class IsolationStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    USER_SELECTION_REQUIRED = "user_selection_required"
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class QualityRoute(str, Enum):
    SAFETY_CHECK_REQUIRED = "safety_check_required"
    REJECT_REUPLOAD = "reject_reupload"
    WARN_CONTINUE = "warn_continue"
    CONTINUE = "continue"
    SELECT_FACE = "select_face"
    ISOLATION_PENDING = "isolation_pending"
    REQUIRE_USER_CROP = "require_user_crop"
    SUBJECT_CONFIRMATION_REQUIRED = "subject_confirmation_required"


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
    HEAVY_FILTER = "heavy_filter"
    FACE_INCOMPLETE = "face_incomplete"
    PROVIDER_UNSUPPORTED_INPUT = "provider_unsupported_input"


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


class TargetScope(str, Enum):
    CURRENT_PHOTO = "current_photo"
    CURRENT_BATCH = "current_batch"
    UNKNOWN = "unknown"


class ReferenceSource(str, Enum):
    EXISTING_PROFILE = "existing_profile"
    NEW_UPLOAD = "new_upload"
    FIRST_BATCH_PHOTO = "first_batch_photo"
    UNKNOWN = "unknown"


class OutputPreference(str, Enum):
    REPORT = "report"
    MANUAL_PARAMETERS = "manual_parameters"
    EDITED_IMAGES = "edited_images"


class ExecutionPriority(str, Enum):
    MINIMAL_CHANGE = "minimal_change"
    CONSISTENCY = "consistency"
    SPEED = "speed"
    COST = "cost"
    BALANCED = "balanced"


class BatchFailurePolicy(str, Enum):
    CONTINUE_VALID = "continue_valid"
    STOP_ALL = "stop_all"
    ASK_BEFORE_CONTINUING = "ask_before_continuing"


class PreferenceMemoryRequest(str, Enum):
    NONE = "none"
    REQUESTED = "requested"
    CONFIRMED = "confirmed"
    DECLINED = "declined"


class IntentSlot(str, Enum):
    GOAL = "goal"
    ROUTE = "route"
    ACTION = "action"
    TARGET_SCOPE = "target_scope"
    REFERENCE_SOURCE = "reference_source"
    OUTPUT_PREFERENCES = "output_preferences"
    ALLOWED_FEATURES = "allowed_features"
    BLOCKED_FEATURES = "blocked_features"
    PRESERVE_ATTRIBUTES = "preserve_attributes"
    ADJUSTMENT_MODE = "adjustment_mode"
    PRIORITY = "priority"
    REQUESTED_MAX_ROUNDS = "requested_max_rounds"
    BATCH_FAILURE_POLICY = "batch_failure_policy"
    CONFIRMATION_SCOPE = "confirmation_scope"


class FieldSource(str, Enum):
    USER_EXPLICIT = "user_explicit"
    PROFILE_DEFAULT = "profile_default"
    PRODUCT_DEFAULT = "product_default"
    CLARIFICATION = "clarification"


class ParserMode(str, Enum):
    LLM = "llm"
    TEMPLATE_FALLBACK = "template_fallback"
    USER_STRUCTURED_INPUT = "user_structured_input"


class ConfirmationStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REVOKED = "revoked"
    EXPIRED = "expired"


class PlanStatus(str, Enum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    EXECUTING = "executing"
    EXECUTED = "executed"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ChangeDirection(str, Enum):
    INCREASE = "increase"
    DECREASE = "decrease"
    PRESERVE = "preserve"
    UNKNOWN = "unknown"


class ProviderRunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class ErrorPhase(str, Enum):
    PREFLIGHT = "preflight"
    SIGNING = "signing"
    NETWORK = "network"
    PROVIDER = "provider"
    RESULT_DECODE = "result_decode"
    PERSISTENCE = "persistence"
    UNKNOWN = "unknown"


class ErrorCategory(str, Enum):
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    NETWORK = "network"
    PROVIDER_5XX = "provider_5xx"
    INVALID_PARAMETER = "invalid_parameter"
    AUTHORIZATION = "authorization"
    CONTENT_SAFETY = "content_safety"
    UNSUPPORTED_INPUT = "unsupported_input"
    MISSING_RESULT = "missing_result"
    LOCAL_VALIDATION = "local_validation"
    UNKNOWN = "unknown"


class ArtifactDeleteStatus(str, Enum):
    ACTIVE = "active"
    DELETE_PENDING = "delete_pending"
    DELETED = "deleted"
    DELETE_FAILED = "delete_failed"


class ComparisonTrend(str, Enum):
    IMPROVED = "improved"
    NO_CHANGE = "no_change"
    WORSENED = "worsened"
    UNVERIFIABLE = "unverifiable"


class VerificationStrategy(str, Enum):
    """A bounded way to gather post-edit evidence.

    The enum is a strategy proposal vocabulary, not permission to make a
    network call.  State/consent policy and the concrete adapter still decide
    whether the proposed strategy can run.
    """

    LOCAL_GEOMETRY = "local_geometry"
    EXTERNAL_SUBJECT_MATCH = "external_subject_match"
    HYBRID = "hybrid"
    MANUAL_VISUAL_REVIEW = "manual_visual_review"


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
    RESULT_WORSENED = "result_worsened"
    INPUT_NOT_COMPARABLE = "input_not_comparable"
    PROVIDER_UNSUPPORTED = "provider_unsupported"
    PROVIDER_FAILURE = "provider_failure"
    SAFETY_BLOCK = "safety_block"
    USER_CANCELLED = "user_cancelled"
    USER_DISSATISFIED = "user_dissatisfied"


class FeedbackStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNKNOWN = "unknown"
    NOT_PROVIDED = "not_provided"


class FeedbackLabelSource(str, Enum):
    HUMAN_GOLD = "human_gold"
    USER_EXPLICIT = "user_explicit"
    INTERACTION_WEAK = "interaction_weak"
    SYNTHETIC = "synthetic"
    NOT_APPLICABLE = "not_applicable"


class FeedbackEvidenceStrength(str, Enum):
    """How much a feedback signal can support a product inference."""

    STRONG_INTENT = "strong_intent"
    STRONG_FEEDBACK = "strong_feedback"
    WEAK_BEHAVIOR = "weak_behavior"
    UNKNOWN = "unknown"


class FeedbackSignal(str, Enum):
    """The observable signal, kept separate from satisfaction status."""

    NONE = "none"
    LIKE = "like"
    DISLIKE = "dislike"
    TEXT_COMMENT = "text_comment"
    FOLLOW_UP_REQUEST = "follow_up_request"
    FIRST_PROMPT = "first_prompt"
    NEW_SESSION = "new_session"
    SESSION_EXIT = "session_exit"
    INACTIVITY = "inactivity"


class ProductEventType(str, Enum):
    """Redacted operational events that feed the future product dashboard."""

    SESSION_STARTED = "session_started"
    PROFILE_CREATED = "profile_created"
    INTENT_SUBMITTED = "intent_submitted"
    DIAGNOSIS_SHOWN = "diagnosis_shown"
    PLAN_SHOWN = "plan_shown"
    EXECUTION_CONFIRMED = "execution_confirmed"
    PROVIDER_SUCCEEDED = "provider_succeeded"
    VERIFICATION_COMPLETED = "verification_completed"
    FEEDBACK_LIKED = "feedback_liked"
    FEEDBACK_DISLIKED = "feedback_disliked"
    USER_COMMENTED = "user_commented"
    FOLLOW_UP_REQUESTED = "follow_up_requested"
    REUPLOAD_REQUIRED = "reupload_required"
    SESSION_EXITED = "session_exited"
    INACTIVITY_TIMEOUT = "inactivity_timeout"
    DATA_DELETION_REQUESTED = "data_deletion_requested"
    DATA_DELETED = "data_deleted"


class InteractionStage(str, Enum):
    ONBOARDING = "onboarding"
    PROFILE = "profile"
    QUALITY_GATE = "quality_gate"
    SUBJECT_GATE = "subject_gate"
    DIAGNOSIS = "diagnosis"
    PLAN = "plan"
    CONFIRMATION = "confirmation"
    EXECUTION = "execution"
    VERIFICATION = "verification"
    DATA_LIFECYCLE = "data_lifecycle"
    UNKNOWN = "unknown"


class InteractionOutcome(str, Enum):
    """A path outcome, deliberately not a satisfaction label."""

    UNKNOWN = "unknown"
    CONTINUED = "continued"
    COMPLETED = "completed"
    PATH_ABANDONED = "path_abandoned"


class NormalizedFeature(ContractModel):
    """One interpretable profile measurement, never a raw landmark vector."""

    feature_code: str = Field(min_length=1, max_length=96)
    value: float | str | None = None
    unit: MeasurementUnit
    status: MeasurementStatus
    confidence: Confidence | None = None

    @model_validator(mode="after")
    def validate_measurement(self) -> NormalizedFeature:
        if self.status == MeasurementStatus.UNAVAILABLE and self.value is not None:
            raise ValueError("unavailable features cannot carry a measured value")
        if self.status != MeasurementStatus.UNAVAILABLE and self.value is None:
            raise ValueError("measured or estimated features require a value")
        if self.status != MeasurementStatus.UNAVAILABLE and self.confidence is None:
            raise ValueError("measured or estimated features require confidence")
        return self


class DataRetentionPolicySnapshot(ContractModel):
    """The user-facing retention and deletion promise attached to an anchor."""

    policy_id: SafeId
    policy_version: str = Field(min_length=1, max_length=64)
    anchor_retention_days: PositiveInt
    reminder_days_before_expiry: list[PositiveInt] = Field(min_length=1, max_length=8)
    primary_delete_sla_hours: PositiveInt
    backup_delete_sla_days: PositiveInt

    @model_validator(mode="after")
    def validate_retention_policy(self) -> DataRetentionPolicySnapshot:
        if len(self.reminder_days_before_expiry) != len(set(self.reminder_days_before_expiry)):
            raise ValueError("expiry reminders must not contain duplicates")
        if any(day >= self.anchor_retention_days for day in self.reminder_days_before_expiry):
            raise ValueError("expiry reminders must occur before the retention deadline")
        return self


class SubjectAnchorMetadata(ContractModel):
    """Metadata for an encrypted, separately consented six-month subject anchor.

    ``anchor_ref`` is an opaque reference to encrypted storage.  It never contains
    an embedding, a key, a photo path, or a vendor face-library identifier.
    """

    anchor_ref: SafeId | None = None
    consent_record_ref: SafeId
    status: AnchorStatus
    created_at: datetime
    expires_at: datetime | None = None
    retention_policy: DataRetentionPolicySnapshot
    access_policy_version: str = Field(min_length=1, max_length=64)
    deletion_requested_at: datetime | None = None
    access_revoked_at: datetime | None = None
    primary_delete_due_at: datetime | None = None
    backup_delete_due_at: datetime | None = None
    deleted_at: datetime | None = None
    deletion_audit_ref: SafeId | None = None

    @model_validator(mode="after")
    def validate_anchor_lifecycle(self) -> SubjectAnchorMetadata:
        if self.status == AnchorStatus.ACTIVE:
            if self.anchor_ref is None or self.expires_at is None:
                raise ValueError("active subject anchors require an opaque ref and expiry")
            if self.expires_at <= self.created_at:
                raise ValueError("subject anchor expiry must be after creation")
        if self.status == AnchorStatus.DELETE_PENDING:
            required = (
                self.deletion_requested_at,
                self.access_revoked_at,
                self.primary_delete_due_at,
                self.backup_delete_due_at,
            )
            if any(value is None for value in required):
                raise ValueError(
                    "pending deletion requires request, access-revocation, and SLA deadlines"
                )
            assert self.deletion_requested_at is not None
            assert self.access_revoked_at is not None
            assert self.primary_delete_due_at is not None
            assert self.backup_delete_due_at is not None
            if self.access_revoked_at < self.deletion_requested_at:
                raise ValueError("anchor access cannot be revoked before deletion is requested")
            if self.primary_delete_due_at < self.deletion_requested_at:
                raise ValueError("primary deletion due time must follow the request")
            if self.backup_delete_due_at < self.primary_delete_due_at:
                raise ValueError("backup deletion due time must not precede primary deletion")
        if self.status == AnchorStatus.DELETED:
            if self.deleted_at is None or self.deletion_audit_ref is None:
                raise ValueError("deleted subject anchors require deletion evidence")
        return self


class ProviderFeatureMapping(ContractModel):
    feature: EditableFeature
    capability_mode: CapabilityMode
    provider_card_id: SafeId
    provider_card_version: str = Field(min_length=1, max_length=64)
    provider_parameter: str | None = Field(default=None, max_length=96)


class ReferenceProfile(ContractModel):
    """Confirmed long-term facial geometry standard without the reference photo."""

    profile_id: SafeId
    user_id: SafeId
    version: PositiveInt
    status: ProfileStatus = ProfileStatus.ACTIVE
    feature_snapshot_ref: SafeId
    normalized_features: list[NormalizedFeature] = Field(default_factory=list, max_length=128)
    reference_quality_result_id: SafeId
    allowed_features: list[EditableFeature] = Field(default_factory=list)
    blocked_features: list[EditableFeature] = Field(default_factory=list)
    preserve_attributes: list[PreserveAttribute] = Field(default_factory=list)
    adjustment_mode: AdjustmentMode = AdjustmentMode.BALANCED
    provider_mappings: list[ProviderFeatureMapping] = Field(default_factory=list)
    subject_anchor: SubjectAnchorMetadata | None = None
    profile_schema_version: str = Field(min_length=1, max_length=64)
    extractor_version: str = Field(min_length=1, max_length=64)
    canonicalization_version: str = Field(min_length=1, max_length=64)
    consent_policy_version: str = Field(min_length=1, max_length=64)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_profile(self) -> ReferenceProfile:
        allowed = set(self.allowed_features)
        blocked = set(self.blocked_features)
        if len(allowed) != len(self.allowed_features):
            raise ValueError("allowed_features must not contain duplicates")
        if len(blocked) != len(self.blocked_features):
            raise ValueError("blocked_features must not contain duplicates")
        if allowed & blocked:
            raise ValueError("allowed_features and blocked_features must not overlap")
        codes = [feature.feature_code for feature in self.normalized_features]
        if len(codes) != len(set(codes)):
            raise ValueError("normalized_features must have unique feature_code values")
        if self.status == ProfileStatus.GEOMETRY_ONLY and self.subject_anchor is not None:
            if self.subject_anchor.status in {
                AnchorStatus.ACTIVE,
                AnchorStatus.DELETE_PENDING,
            }:
                raise ValueError(
                    "geometry-only profiles cannot retain an active or pending-deletion "
                    "subject anchor"
                )
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")
        return self


class QualityRoutingPolicySnapshot(ContractModel):
    """Versioned thresholds; values are configurable and not contract type limits."""

    policy_id: SafeId
    policy_version: str = Field(min_length=1, max_length=64)
    reject_at_or_below: Confidence
    continue_at_or_above: Confidence

    @model_validator(mode="after")
    def validate_threshold_order(self) -> QualityRoutingPolicySnapshot:
        if self.reject_at_or_below >= self.continue_at_or_above:
            raise ValueError("reject threshold must be lower than continue threshold")
        return self


class ContentSafetyEvidence(ContractModel):
    """Auditable evidence for a completed safety check, without image payloads."""

    provider: str = Field(min_length=1, max_length=64)
    operation: str = Field(min_length=1, max_length=96)
    provider_version: str = Field(min_length=1, max_length=64)
    policy_version: str = Field(min_length=1, max_length=64)
    receipt_ref: SafeId
    provider_request_id: str | None = Field(default=None, min_length=1, max_length=256)
    evaluated_at: datetime


class SubjectMatchEvidence(ContractModel):
    """Versioned raw 1:1 match evidence; a provider score is not a probability."""

    provider: str = Field(min_length=1, max_length=64)
    operation: str = Field(min_length=1, max_length=96)
    model_version: str = Field(min_length=1, max_length=64)
    threshold_policy_version: str = Field(min_length=1, max_length=64)
    receipt_ref: SafeId
    provider_request_id: str | None = Field(default=None, min_length=1, max_length=256)
    raw_score: float | None = None
    raw_score_min: float | None = None
    raw_score_max: float | None = None
    calibrated: bool = False
    evaluated_at: datetime

    @model_validator(mode="after")
    def validate_raw_score_scale(self) -> SubjectMatchEvidence:
        scale = (self.raw_score_min, self.raw_score_max)
        if self.raw_score is None:
            if any(value is not None for value in scale):
                raise ValueError("a raw score scale requires a raw score")
            return self
        if any(value is None for value in scale):
            raise ValueError("raw subject-match scores require their documented scale")
        assert self.raw_score_min is not None and self.raw_score_max is not None
        if self.raw_score_min >= self.raw_score_max:
            raise ValueError("raw subject-match score scale must be ordered")
        if not self.raw_score_min <= self.raw_score <= self.raw_score_max:
            raise ValueError("raw subject-match score must stay inside its documented scale")
        return self


class PhotoQualityResult(ContractModel):
    """Deterministic content, subject, quality, editability, and face-routing result."""

    quality_result_id: SafeId
    session_id: SafeId
    photo_id: SafeId
    photo_sha256: Sha256
    photo_role: PhotoRole
    face_count: Annotated[int, Field(ge=0, le=20)]
    selected_face_ref: SafeId | None = None
    prepared_artifact_ref: SafeId | None = None
    isolation_status: IsolationStatus = IsolationStatus.NOT_REQUIRED
    subject_match_status: SubjectMatchStatus
    subject_match_confidence: Confidence | None = None
    subject_match_evidence: SubjectMatchEvidence | None = None
    quality_confidence: Confidence
    editability_confidence: Confidence
    content_safety_status: ContentSafetyStatus = ContentSafetyStatus.NOT_EVALUATED
    content_safety_evidence: ContentSafetyEvidence | None = None
    quality_flags: list[QualityFlag] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list, max_length=16)
    metrics: dict[str, float] = Field(default_factory=dict)
    route: QualityRoute
    routing_policy: QualityRoutingPolicySnapshot
    analysis_version: str = Field(min_length=1, max_length=64)
    provider_card_id: SafeId
    provider_card_version: str = Field(min_length=1, max_length=64)
    created_at: datetime = Field(default_factory=utc_now)

    def _expected_route(self) -> QualityRoute:
        if self.content_safety_status == ContentSafetyStatus.BLOCKED or self.face_count == 0:
            return QualityRoute.REJECT_REUPLOAD
        if self.content_safety_status == ContentSafetyStatus.NOT_EVALUATED:
            return QualityRoute.SAFETY_CHECK_REQUIRED
        if self.face_count > 1:
            if self.selected_face_ref is None:
                return QualityRoute.SELECT_FACE
            if self.isolation_status == IsolationStatus.FAILED:
                return QualityRoute.REQUIRE_USER_CROP
            if self.isolation_status != IsolationStatus.SUCCEEDED:
                return QualityRoute.ISOLATION_PENDING
        if self.photo_role != PhotoRole.REFERENCE:
            if self.subject_match_status == SubjectMatchStatus.NO_MATCH:
                return QualityRoute.REJECT_REUPLOAD
            if self.subject_match_status == SubjectMatchStatus.UNCERTAIN:
                return QualityRoute.SUBJECT_CONFIRMATION_REQUIRED
        strictest_confidence = min(self.quality_confidence, self.editability_confidence)
        if strictest_confidence <= self.routing_policy.reject_at_or_below:
            return QualityRoute.REJECT_REUPLOAD
        if strictest_confidence < self.routing_policy.continue_at_or_above:
            return QualityRoute.WARN_CONTINUE
        return QualityRoute.CONTINUE

    @model_validator(mode="after")
    def validate_quality_route(self) -> PhotoQualityResult:
        if self.content_safety_status == ContentSafetyStatus.NOT_EVALUATED:
            if self.content_safety_evidence is not None:
                raise ValueError("not-evaluated safety status cannot carry completed evidence")
        elif self.content_safety_evidence is None:
            raise ValueError("completed safety decisions require an auditable evidence snapshot")
        if self.photo_role == PhotoRole.REFERENCE:
            if self.subject_match_status != SubjectMatchStatus.NOT_APPLICABLE:
                raise ValueError("reference photos must use subject_match_status=not_applicable")
            if self.subject_match_confidence is not None or self.subject_match_evidence is not None:
                raise ValueError("reference photos cannot carry a target subject-match result")
        elif self.subject_match_status == SubjectMatchStatus.NOT_APPLICABLE:
            raise ValueError("target/result photos require an independent subject match result")
        elif self.subject_match_evidence is None:
            raise ValueError("target/result subject-match decisions require auditable evidence")
        elif self.subject_match_evidence.calibrated:
            if self.subject_match_confidence is None:
                raise ValueError("calibrated subject-match evidence requires calibrated confidence")
        elif self.subject_match_confidence is not None:
            raise ValueError("uncalibrated provider scores cannot masquerade as confidence")
        if self.face_count == 1 and self.isolation_status != IsolationStatus.NOT_REQUIRED:
            raise ValueError("single-face photos do not require face isolation")
        if self.route != self._expected_route():
            raise ValueError(
                f"route must be the most restrictive result: {self._expected_route().value}"
            )
        if self.route != QualityRoute.CONTINUE and not self.reason_codes and not self.quality_flags:
            raise ValueError("non-continue routes require an explainable reason or quality flag")
        return self


class ConfirmationScope(ContractModel):
    """Bounded authorization for one photo/batch and one plan family."""

    scope_id: SafeId
    target_refs: list[SafeId] = Field(min_length=1)
    allowed_features: list[EditableFeature] = Field(default_factory=list)
    max_provider_rounds: PositiveInt
    whitening_allowed: bool = False
    smoothing_allowed: bool = False
    budget_limit_cny: Annotated[float, Field(ge=0.0)] | None = None
    safety_policy_id: SafeId
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime

    @model_validator(mode="after")
    def validate_scope(self) -> ConfirmationScope:
        if len(self.target_refs) != len(set(self.target_refs)):
            raise ValueError("confirmation target_refs must not contain duplicates")
        if len(self.allowed_features) != len(set(self.allowed_features)):
            raise ValueError("confirmation allowed_features must not contain duplicates")
        if self.expires_at <= self.created_at:
            raise ValueError("confirmation scope must expire after it is created")
        if self.whitening_allowed and EditableFeature.WHITENING not in self.allowed_features:
            raise ValueError("whitening permission requires whitening in allowed_features")
        if self.smoothing_allowed and EditableFeature.SMOOTHING not in self.allowed_features:
            raise ValueError("smoothing permission requires smoothing in allowed_features")
        return self


class IntentFrame(ContractModel):
    """Structured user goal and constraints; never workflow state or a tool receipt."""

    intent_id: SafeId
    session_id: SafeId
    turn: PositiveInt
    supersedes_intent_id: SafeId | None = None
    goal: IntentGoal
    route: Route
    action: IntentAction
    target_scope: TargetScope
    reference_source: ReferenceSource
    target_refs: list[SafeId] = Field(default_factory=list)
    output_preferences: list[OutputPreference] = Field(default_factory=list)
    allowed_features: list[EditableFeature] = Field(default_factory=list)
    blocked_features: list[EditableFeature] = Field(default_factory=list)
    preserve_attributes: list[PreserveAttribute] = Field(default_factory=list)
    adjustment_mode: AdjustmentMode | None = None
    priority: ExecutionPriority = ExecutionPriority.BALANCED
    requested_max_rounds: PositiveInt | None = None
    batch_failure_policy: BatchFailurePolicy = BatchFailurePolicy.CONTINUE_VALID
    preference_memory_request: PreferenceMemoryRequest = PreferenceMemoryRequest.NONE
    field_sources: dict[str, FieldSource] = Field(default_factory=dict)
    slot_confidence: dict[str, Confidence] = Field(default_factory=dict)
    intent_confidence: Confidence
    missing_slots: list[IntentSlot] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list, max_length=16)
    confirmation_status: ConfirmationStatus = ConfirmationStatus.NOT_REQUIRED
    confirmation_scope: ConfirmationScope | None = None
    confirmation_ref: SafeId | None = None
    parser_mode: ParserMode
    model_provider: str | None = Field(default=None, max_length=64)
    model_version: str | None = Field(default=None, max_length=64)
    prompt_version: str | None = Field(default=None, max_length=64)
    user_text_sha256: Sha256 | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_intent(self) -> IntentFrame:
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
            if OutputPreference.EDITED_IMAGES not in self.output_preferences:
                raise ValueError("execute intent must request edited_images")
            if self.confirmation_status not in {
                ConfirmationStatus.PENDING,
                ConfirmationStatus.CONFIRMED,
                ConfirmationStatus.REVOKED,
                ConfirmationStatus.EXPIRED,
            }:
                raise ValueError("execute intent requires an explicit confirmation state")
            if self.confirmation_status in {
                ConfirmationStatus.PENDING,
                ConfirmationStatus.CONFIRMED,
            } and (self.confirmation_scope is None or self.confirmation_ref is None):
                raise ValueError(
                    "pending/confirmed execution requires a bounded confirmation scope"
                )
            if self.confirmation_status == ConfirmationStatus.CONFIRMED and self.missing_slots:
                raise ValueError("confirmed execution cannot have unresolved intent slots")
        elif self.confirmation_status != ConfirmationStatus.NOT_REQUIRED:
            raise ValueError("non-execute intent cannot carry execution confirmation")
        elif self.confirmation_scope is not None or self.confirmation_ref is not None:
            raise ValueError("non-execute intent cannot carry an execution scope")
        if self.parser_mode == ParserMode.LLM and not self.model_provider:
            raise ValueError("LLM-parsed intent requires model_provider")
        return self


class TencentBeautifyParams(ContractModel):
    """All current Tencent API parameters are explicit and limited to 0..100."""

    face_lifting: ProviderStrength = 0
    eye_enlarging: ProviderStrength = 0
    whitening: ProviderStrength = 0
    smoothing: ProviderStrength = 0


class FeatureDifference(ContractModel):
    feature_code: str = Field(min_length=1, max_length=96)
    reference_value: float | None = None
    observed_value: float | None = None
    normalized_gap: Annotated[float, Field(ge=0.0)] | None = None
    measurement_confidence: Confidence
    editable: bool
    reason_codes: list[str] = Field(default_factory=list, max_length=8)


class ExecutableChange(ContractModel):
    feature: EditableFeature
    provider_parameter: str = Field(min_length=1, max_length=96)
    user_delta: int
    current_absolute: ProviderStrength
    proposed_absolute: ProviderStrength
    expected_direction: ChangeDirection
    rationale_codes: list[str] = Field(min_length=1, max_length=8)


class SuggestionOnlyChange(ContractModel):
    feature: EditableFeature
    user_delta: int | None = None
    instruction: str = Field(min_length=1, max_length=512)
    reason_codes: list[str] = Field(min_length=1, max_length=8)


class PlanConstraintsSnapshot(ContractModel):
    allowed_features: list[EditableFeature] = Field(default_factory=list)
    blocked_features: list[EditableFeature] = Field(default_factory=list)
    preserve_attributes: list[PreserveAttribute] = Field(default_factory=list)
    adjustment_mode: AdjustmentMode

    @model_validator(mode="after")
    def validate_constraints(self) -> PlanConstraintsSnapshot:
        if set(self.allowed_features) & set(self.blocked_features):
            raise ValueError("plan allowed and blocked features must not overlap")
        return self


class SafetyPolicySnapshot(ContractModel):
    """Values come from configuration; changing them does not change contract types."""

    policy_id: SafeId
    policy_version: str = Field(min_length=1, max_length=64)
    max_provider_rounds: PositiveInt
    stop_after_no_improvement_rounds: PositiveInt
    max_attempts_per_plan: PositiveInt
    max_cost_cny: Annotated[float, Field(ge=0.0)] | None = None


class EditPlan(ContractModel):
    """Immutable pre-edit plan for exactly one target photo."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    plan_id: SafeId
    revision: PositiveInt
    parent_plan_id: SafeId | None = None
    session_id: SafeId
    profile_id: SafeId
    profile_version: PositiveInt
    photo_id: SafeId
    photo_sha256: Sha256
    intent_id: SafeId
    quality_result_id: SafeId
    iteration: PositiveInt
    provider: Literal["tencent_beautify_pic"] = "tencent_beautify_pic"
    provider_api_version: str = Field(min_length=1, max_length=64)
    provider_card_id: SafeId
    provider_card_version: str = Field(min_length=1, max_length=64)
    knowledge_refs: list[AuditedKnowledgeRef] = Field(default_factory=list, max_length=16)
    baseline_feature_differences: list[FeatureDifference] = Field(default_factory=list)
    executable_changes: list[ExecutableChange] = Field(default_factory=list)
    suggestion_only_changes: list[SuggestionOnlyChange] = Field(default_factory=list)
    provider_absolute_params: TencentBeautifyParams
    constraints_snapshot: PlanConstraintsSnapshot
    safety_policy: SafetyPolicySnapshot
    risk_notes: list[str] = Field(default_factory=list, max_length=16)
    requires_confirmation: bool = True
    confirmation_ref: SafeId | None = None
    confirmation_scope_hash: Sha256 | None = None
    status: PlanStatus = PlanStatus.PROPOSED
    planner_version: str = Field(min_length=1, max_length=64)
    mapping_policy_version: str = Field(min_length=1, max_length=64)
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime | None = None
    superseded_reason: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def validate_plan(self) -> EditPlan:
        features = [change.feature for change in self.executable_changes]
        if len(features) != len(set(features)):
            raise ValueError("executable_changes cannot target the same feature twice")
        if len(self.knowledge_refs) != len(set(self.knowledge_refs)):
            raise ValueError("knowledge_refs must not contain duplicates")
        allowed = set(self.constraints_snapshot.allowed_features)
        blocked = set(self.constraints_snapshot.blocked_features)
        if any(feature not in allowed or feature in blocked for feature in features):
            raise ValueError("executable changes must remain inside the constraint snapshot")
        tencent_parameter_map = {
            EditableFeature.FACE_LIFTING: ("FaceLifting", "face_lifting"),
            EditableFeature.EYE_ENLARGING: ("EyeEnlarging", "eye_enlarging"),
            EditableFeature.WHITENING: ("Whitening", "whitening"),
            EditableFeature.SMOOTHING: ("Smoothing", "smoothing"),
        }
        for change in self.executable_changes:
            mapping = tencent_parameter_map.get(change.feature)
            if mapping is None:
                raise ValueError("current Tencent execution only accepts Provider Card features")
            expected_parameter, params_field = mapping
            if change.provider_parameter != expected_parameter:
                raise ValueError("executable change does not match the Provider Card parameter")
            if change.proposed_absolute != getattr(self.provider_absolute_params, params_field):
                raise ValueError("planned absolute value must match the provider request snapshot")
        if self.provider_absolute_params.whitening > 0 and EditableFeature.WHITENING not in allowed:
            raise ValueError("non-zero whitening requires explicit permission")
        if self.provider_absolute_params.smoothing > 0 and EditableFeature.SMOOTHING not in allowed:
            raise ValueError("non-zero smoothing requires explicit permission")
        if self.iteration > self.safety_policy.max_provider_rounds:
            raise ValueError("iteration exceeds the applied configurable safety policy")
        if self.executable_changes and not self.requires_confirmation:
            raise ValueError("external executable changes always require user confirmation")
        if self.status in {PlanStatus.CONFIRMED, PlanStatus.EXECUTING, PlanStatus.EXECUTED}:
            if self.confirmation_ref is None or self.confirmation_scope_hash is None:
                raise ValueError("confirmed/executing/executed plans require bounded confirmation")
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("plan expiry must be later than creation")
        if self.status == PlanStatus.SUPERSEDED and not self.superseded_reason:
            raise ValueError("superseded plans require a reason")
        return self


class ProviderErrorDetail(ContractModel):
    phase: ErrorPhase
    category: ErrorCategory
    provider_code: str = Field(min_length=1, max_length=128)
    safe_message: str = Field(min_length=1, max_length=512)
    retryable: bool
    retry_after_ms: NonNegativeInt | None = None


class ArtifactLifecycle(ContractModel):
    expires_at: datetime
    delete_status: ArtifactDeleteStatus = ArtifactDeleteStatus.ACTIVE
    deleted_at: datetime | None = None

    @model_validator(mode="after")
    def validate_deletion(self) -> ArtifactLifecycle:
        if self.delete_status == ArtifactDeleteStatus.DELETED and self.deleted_at is None:
            raise ValueError("deleted artifacts require deleted_at")
        return self


class ProviderRun(ContractModel):
    """Immutable factual receipt for exactly one external provider attempt."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    run_id: SafeId
    trace_id: SafeId
    plan_id: SafeId
    plan_revision: PositiveInt
    session_id: SafeId
    photo_id: SafeId
    attempt_number: PositiveInt
    retry_group_id: SafeId | None = None
    parent_run_id: SafeId | None = None
    provider: Literal["tencent_beautify_pic"] = "tencent_beautify_pic"
    operation: Literal["BeautifyPic"] = "BeautifyPic"
    provider_api_version: str = Field(min_length=1, max_length=64)
    region: str = Field(min_length=1, max_length=64)
    endpoint: str = Field(min_length=1, max_length=255)
    provider_card_id: SafeId
    provider_card_version: str = Field(min_length=1, max_length=64)
    idempotency_key: SafeId
    request_hash: Sha256
    request_params: TencentBeautifyParams
    input_artifact_ref: SafeId
    input_artifact_sha256: Sha256
    confirmation_ref: SafeId
    confirmation_scope_hash: Sha256
    consent_policy_version: str = Field(min_length=1, max_length=64)
    status: ProviderRunStatus
    provider_request_id: str | None = Field(default=None, min_length=1, max_length=256)
    result_artifact_ref: str | None = Field(default=None, min_length=1, max_length=1024)
    result_artifact_sha256: Sha256 | None = None
    artifact_lifecycle: ArtifactLifecycle | None = None
    queued_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    queue_latency_ms: NonNegativeInt | None = None
    network_latency_ms: NonNegativeInt | None = None
    total_latency_ms: NonNegativeInt | None = None
    estimated_cost_cny: Annotated[float, Field(ge=0.0)] | None = None
    actual_cost_cny: Annotated[float, Field(ge=0.0)] | None = None
    budget_policy_version: str | None = Field(default=None, max_length=64)
    error: ProviderErrorDetail | None = None

    @model_validator(mode="after")
    def validate_run(self) -> ProviderRun:
        if self.started_at and self.queued_at and self.started_at < self.queued_at:
            raise ValueError("started_at cannot be earlier than queued_at")
        if self.completed_at and self.started_at and self.completed_at < self.started_at:
            raise ValueError("completed_at cannot be earlier than started_at")
        if self.status == ProviderRunStatus.SUCCEEDED:
            required = (
                self.provider_request_id,
                self.result_artifact_ref,
                self.result_artifact_sha256,
                self.artifact_lifecycle,
                self.started_at,
                self.completed_at,
                self.total_latency_ms,
            )
            if any(value is None for value in required):
                raise ValueError("successful runs require a complete provider and artifact receipt")
            if self.error is not None:
                raise ValueError("successful runs cannot carry an error")
        if self.status in {ProviderRunStatus.FAILED, ProviderRunStatus.TIMEOUT}:
            if self.error is None or self.completed_at is None:
                raise ValueError("failed/timeout runs require error details and completion time")
        return self


class FeatureComparison(ContractModel):
    feature_code: str = Field(min_length=1, max_length=96)
    before_gap: Annotated[float, Field(ge=0.0)] | None = None
    after_gap: Annotated[float, Field(ge=0.0)] | None = None
    trend: ComparisonTrend
    measurement_confidence: Confidence

    @model_validator(mode="after")
    def validate_measurement_availability(self) -> FeatureComparison:
        if self.before_gap is None or self.after_gap is None:
            if self.trend != ComparisonTrend.UNVERIFIABLE:
                raise ValueError("missing measurements require an unverifiable trend")
        elif self.trend == ComparisonTrend.UNVERIFIABLE:
            raise ValueError("available measurements require a measured trend")
        return self


class VerificationStrategyProposal(ContractModel):
    """A constrained strategy suggestion before any verification tool runs.

    This is intentionally separate from :class:`VerificationResult`: a
    proposal records what the Agent suggested, while the result records what
    the verifier actually measured.  It never proves that an external tool was
    called and it cannot grant permission by itself.
    """

    proposal_id: SafeId
    selected_strategy: VerificationStrategy
    allowed_strategies: list[VerificationStrategy] = Field(min_length=1, max_length=8)
    reason_codes: list[str] = Field(min_length=1, max_length=8)
    knowledge_refs: list[AuditedKnowledgeRef] = Field(default_factory=list, max_length=16)
    data_outbound: bool = False
    additional_consent_required: bool = False
    selector_mode: Literal["deterministic_baseline_v0", "llm_proposed"] = (
        "deterministic_baseline_v0"
    )
    selector_version: str = Field(min_length=1, max_length=64)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_strategy_proposal(self) -> VerificationStrategyProposal:
        if len(self.allowed_strategies) != len(set(self.allowed_strategies)):
            raise ValueError("allowed_strategies must not contain duplicates")
        if len(self.knowledge_refs) != len(set(self.knowledge_refs)):
            raise ValueError("knowledge_refs must not contain duplicates")
        if self.selected_strategy not in self.allowed_strategies:
            raise ValueError("selected strategy must be inside the allowed strategy set")
        outbound_strategy = self.selected_strategy in {
            VerificationStrategy.EXTERNAL_SUBJECT_MATCH,
            VerificationStrategy.HYBRID,
        }
        if outbound_strategy and not self.data_outbound:
            raise ValueError("external or hybrid verification must declare data_outbound")
        if self.data_outbound and not self.additional_consent_required:
            raise ValueError("outbound verification requires additional consent")
        if not outbound_strategy and self.data_outbound:
            raise ValueError("local or manual verification cannot declare data_outbound")
        return self


class UserFeedback(ContractModel):
    """A user-level feedback fact, separate from behavioral telemetry.

    An explicit first prompt is strong evidence of intent, for example, but it
    remains ``status=unknown`` because it says nothing about satisfaction.
    """

    status: FeedbackStatus = FeedbackStatus.NOT_PROVIDED
    label_source: FeedbackLabelSource = FeedbackLabelSource.NOT_APPLICABLE
    explicit: bool = False
    signal: FeedbackSignal = FeedbackSignal.NONE
    evidence_strength: FeedbackEvidenceStrength = FeedbackEvidenceStrength.UNKNOWN
    reason_codes: list[str] = Field(default_factory=list, max_length=8)
    recorded_at: datetime | None = None

    @model_validator(mode="after")
    def validate_feedback(self) -> UserFeedback:
        if self.status in {FeedbackStatus.ACCEPTED, FeedbackStatus.REJECTED}:
            if (
                not self.explicit
                or self.label_source
                not in {FeedbackLabelSource.HUMAN_GOLD, FeedbackLabelSource.USER_EXPLICIT}
                or self.evidence_strength != FeedbackEvidenceStrength.STRONG_FEEDBACK
            ):
                raise ValueError("accept/reject must be explicit strong human feedback")
        if self.label_source == FeedbackLabelSource.INTERACTION_WEAK and self.explicit:
            raise ValueError("interaction weak labels cannot be marked explicit")
        if self.evidence_strength == FeedbackEvidenceStrength.WEAK_BEHAVIOR and self.explicit:
            raise ValueError("weak behavioral evidence cannot be marked explicit")
        if self.signal in {
            FeedbackSignal.FIRST_PROMPT,
            FeedbackSignal.NEW_SESSION,
            FeedbackSignal.SESSION_EXIT,
            FeedbackSignal.INACTIVITY,
        } and self.status in {FeedbackStatus.ACCEPTED, FeedbackStatus.REJECTED}:
            raise ValueError(
                "intent, continuation, exit, and inactivity signals are not satisfaction labels"
            )
        if (
            self.status == FeedbackStatus.NOT_PROVIDED
            and self.label_source != FeedbackLabelSource.NOT_APPLICABLE
        ):
            raise ValueError("not-provided feedback cannot claim a label source")
        return self


class ProductEvent(ContractModel):
    """Redacted event for operational analysis, retention, and the local dashboard.

    This is deliberately not a seventh image-processing contract and not a
    training dataset row. It records that a product event occurred without raw
    text, face geometry, photos, embeddings, or provider request payloads.
    """

    event_id: SafeId
    session_id: SafeId
    anonymous_user_id: SafeId
    event_type: ProductEventType
    stage: InteractionStage
    evidence_strength: FeedbackEvidenceStrength
    outcome: InteractionOutcome = InteractionOutcome.UNKNOWN
    related_contract_ref: SafeId | None = None
    reason_codes: list[str] = Field(default_factory=list, max_length=8)
    occurred_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_product_event(self) -> ProductEvent:
        weak_events = {
            ProductEventType.SESSION_EXITED,
            ProductEventType.INACTIVITY_TIMEOUT,
            ProductEventType.REUPLOAD_REQUIRED,
        }
        if (
            self.event_type in weak_events
            and self.evidence_strength == FeedbackEvidenceStrength.STRONG_FEEDBACK
        ):
            raise ValueError(
                "exit, inactivity, and reupload events cannot be strong satisfaction feedback"
            )
        if self.event_type == ProductEventType.INTENT_SUBMITTED:
            if self.evidence_strength != FeedbackEvidenceStrength.STRONG_INTENT:
                raise ValueError("an intentionally submitted prompt must be strong intent evidence")
        return self


class CalibratedAcceptance(ContractModel):
    """Optional future output; V0 policy forbids populating this model."""

    probability: Probability
    model_version: str = Field(min_length=1, max_length=64)
    dataset_version: str = Field(min_length=1, max_length=64)
    calibration_version: str = Field(min_length=1, max_length=64)
    evaluation_report_ref: SafeId


class ManualReviewRequest(ContractModel):
    reviewer: Literal["project_developer"] = "project_developer"
    reason_codes: list[str] = Field(min_length=1, max_length=8)
    original_image_access_authorized: bool = False
    original_image_authorization_ref: SafeId | None = None

    @model_validator(mode="after")
    def validate_review_authorization(self) -> ManualReviewRequest:
        if self.original_image_access_authorized and self.original_image_authorization_ref is None:
            raise ValueError("original-image review requires a separate authorization ref")
        if not self.original_image_access_authorized and self.original_image_authorization_ref:
            raise ValueError("authorization ref cannot exist without original-image access")
        return self


class VerificationResult(ContractModel):
    """Measured post-edit result and deterministic next state; no uncalibrated score."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    verification_id: SafeId
    session_id: SafeId
    profile_id: SafeId
    profile_version: PositiveInt
    photo_id: SafeId
    plan_id: SafeId
    plan_revision: PositiveInt
    provider_run_id: SafeId
    verification_strategy: VerificationStrategy = VerificationStrategy.LOCAL_GEOMETRY
    strategy_proposal_ref: SafeId | None = None
    strategy_reason_codes: list[str] = Field(default_factory=list, max_length=8)
    knowledge_refs: list[AuditedKnowledgeRef] = Field(default_factory=list, max_length=16)
    data_outbound: bool = False
    additional_consent_required: bool = False
    verification_run_refs: list[SafeId] = Field(default_factory=list, max_length=8)
    verification_artifact_refs: list[SafeId] = Field(default_factory=list, max_length=8)
    plan_family_id: SafeId | None = None
    previous_verification_id: SafeId | None = None
    cumulative_improvement: bool = False
    target_evidence_sufficient: bool = False
    preserved_attributes_verified: bool = False
    feature_comparisons: list[FeatureComparison] = Field(default_factory=list)
    overall_trend: ComparisonTrend
    result_quality_flags: list[QualityFlag] = Field(default_factory=list)
    prohibited_attribute_changed: bool = False
    result_artifact_available: bool
    round_number: PositiveInt
    no_improvement_streak: NonNegativeInt
    safety_policy: SafetyPolicySnapshot
    user_feedback: UserFeedback = Field(default_factory=UserFeedback)
    calibrated_acceptance: CalibratedAcceptance | None = None
    decision: VerificationDecision
    stop_reason: StopReason | None = None
    reason_codes: list[str] = Field(default_factory=list, max_length=16)
    result_artifact_ref: str = Field(min_length=1, max_length=1024)
    last_known_good_artifact_ref: str | None = Field(default=None, max_length=1024)
    rollback_reason: str | None = Field(default=None, max_length=256)
    manual_review: ManualReviewRequest | None = None
    verifier_version: str = Field(min_length=1, max_length=64)
    extractor_version: str = Field(min_length=1, max_length=64)
    threshold_policy_version: str = Field(min_length=1, max_length=64)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_verification(self) -> VerificationResult:
        outbound_strategy = self.verification_strategy in {
            VerificationStrategy.EXTERNAL_SUBJECT_MATCH,
            VerificationStrategy.HYBRID,
        }
        if outbound_strategy and not self.data_outbound:
            raise ValueError("external or hybrid verification must declare data_outbound")
        if self.data_outbound and not self.additional_consent_required:
            raise ValueError("outbound verification requires additional consent")
        if not outbound_strategy and self.data_outbound:
            raise ValueError("local or manual verification cannot declare data_outbound")
        if self.verification_run_refs and (
            self.verification_strategy == VerificationStrategy.LOCAL_GEOMETRY
        ):
            raise ValueError("local verification cannot claim an external verification run")
        if self.target_evidence_sufficient and self.overall_trend not in {
            ComparisonTrend.IMPROVED,
            ComparisonTrend.NO_CHANGE,
        }:
            raise ValueError(
                "target evidence can be sufficient only when trend is improved or unchanged"
            )
        if self.round_number > self.safety_policy.max_provider_rounds:
            raise ValueError("round_number exceeds the applied safety policy")
        policy_exhausted = (
            self.round_number >= self.safety_policy.max_provider_rounds
            or self.no_improvement_streak >= self.safety_policy.stop_after_no_improvement_rounds
        )
        if self.decision == VerificationDecision.REPLAN and policy_exhausted:
            raise ValueError("replan is forbidden after the configured stop policy fires")
        if self.decision in {VerificationDecision.STOP, VerificationDecision.CLOSE}:
            if self.stop_reason is None:
                raise ValueError("stop/close decisions require a stop reason")
        if self.stop_reason == StopReason.USER_ACCEPTED:
            if self.user_feedback.status != FeedbackStatus.ACCEPTED:
                raise ValueError("user_accepted stop requires explicit accepted feedback")
        if self.stop_reason == StopReason.GOAL_MET:
            if (
                self.calibrated_acceptance is None
                and self.user_feedback.status != FeedbackStatus.ACCEPTED
                and not self.target_evidence_sufficient
            ):
                raise ValueError(
                    "goal_met requires calibrated evidence, explicit user acceptance, or "
                    "structured target evidence"
                )
        if (
            not self.result_artifact_available or self.prohibited_attribute_changed
        ) and self.decision in {VerificationDecision.STOP, VerificationDecision.CLOSE}:
            raise ValueError("missing/unsafe result artifacts cannot be accepted as STOP/CLOSE")
        if self.overall_trend == ComparisonTrend.WORSENED and self.decision in {
            VerificationDecision.STOP,
            VerificationDecision.CLOSE,
        }:
            if self.last_known_good_artifact_ref is None or self.rollback_reason is None:
                raise ValueError("worsened results require a last-known-good fallback")
        if self.decision == VerificationDecision.MANUAL_REVIEW and self.manual_review is None:
            raise ValueError("manual review decisions require an explicit developer review request")
        if self.decision != VerificationDecision.MANUAL_REVIEW and self.manual_review is not None:
            raise ValueError("manual review details only belong to MANUAL_REVIEW decisions")
        return self
