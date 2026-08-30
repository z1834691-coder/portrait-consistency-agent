"""Contracts for the local, governed RAG P0-A knowledge slice.

These are intentionally separate from the six portrait-processing contracts in
``core.contracts``.  They describe reviewed *tool knowledge*, never a user
photo, face vector, secret, raw user sentence, or a provider receipt.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from portrait_consistency_agent.core.contracts import (
    EditableFeature,
    PreserveAttribute,
    SafeId,
    Sha256,
)

RAG_CONTRACT_VERSION = "rag-p0.1"

# A knowledge reference deliberately has a stricter, more trace-friendly shape
# than a URL.  It points only to a locally reviewed source/chunk/version; it
# never carries a raw document, a user photo, a user sentence, or a secret.
KnowledgeReference = Annotated[
    str,
    Field(
        min_length=7,
        max_length=384,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*#[A-Za-z0-9][A-Za-z0-9_-]*@[A-Za-z0-9._-]+$",
    ),
]


def utc_now() -> datetime:
    """Return an explicit timezone-aware timestamp for RAG audit records."""

    return datetime.now(timezone.utc)


class RagContractModel(BaseModel):
    """Strict JSON-safe base model for knowledge and retrieval facts."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    rag_contract_version: Literal["rag-p0.1"] = RAG_CONTRACT_VERSION


class KnowledgeSourceType(str, Enum):
    PROVIDER_CARD = "provider_card"
    OFFICIAL_API = "official_api"
    OFFICIAL_SDK = "official_sdk"
    PROJECT_POLICY = "project_policy"
    VERIFIED_RECEIPT = "verified_receipt"
    AUDITED_BAD_CASE = "audited_bad_case"


class KnowledgeLifecycleStatus(str, Enum):
    CANDIDATE = "candidate"
    REVIEWED_ACTIVE = "reviewed_active"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    WITHDRAWN = "withdrawn"
    CONFLICTED_PENDING_REVIEW = "conflicted_pending_review"
    EXPLANATION_ONLY = "explanation_only"


class KnowledgeClaimType(str, Enum):
    CAPABILITY = "capability"
    PARAMETER = "parameter"
    LIMITATION = "limitation"
    INPUT_REQUIREMENT = "input_requirement"
    FAILURE_POLICY = "failure_policy"
    PERMISSION = "permission"
    PRIVACY = "privacy"
    COST = "cost"
    VERIFICATION_SCOPE = "verification_scope"


class KnowledgeCapabilityStatus(str, Enum):
    EXECUTABLE = "executable"
    SUGGESTION_ONLY = "suggestion_only"
    UNSUPPORTED = "unsupported"
    NOT_APPLICABLE = "not_applicable"


class RagStage(str, Enum):
    QUALITY_GATE = "quality_gate"
    PLAN_EDIT = "plan_edit"
    VERIFICATION_STRATEGY = "verification_strategy"
    FAILURE_ROUTING = "failure_routing"


class EvidenceRelation(str, Enum):
    DIRECT_EVIDENCE = "direct_evidence"
    REFERENCE_CONTEXT = "reference_context"
    CONFLICT_EVIDENCE = "conflict_evidence"


class RetrievalRoute(str, Enum):
    EVIDENCE_FOUND = "evidence_found"
    MANUAL_SUGGESTION = "manual_suggestion"
    BASELINE_FALLBACK = "baseline_fallback"
    QUERY_UNDERSPECIFIED = "query_underspecified"
    CONFLICT_BLOCKED = "conflict_blocked"
    INDEX_UNAVAILABLE = "index_unavailable"


class RagAdvisoryRoute(str, Enum):
    """The only routes a RAG consumer may take after retrieving knowledge.

    ``ADVISORY_AVAILABLE`` means there is evidence that can inform an
    existing planner or strategy selector.  It does not grant execution.  A
    conflict always blocks execution; a miss may keep an independently
    configured, existing Provider Card baseline, but can never invent or
    expand a new capability.
    """

    ADVISORY_AVAILABLE = "advisory_available"
    MANUAL_SUGGESTION_ONLY = "manual_suggestion_only"
    BASELINE_DEGRADED = "baseline_degraded"
    UNKNOWN_STOPPED = "unknown_stopped"
    CONFLICT_BLOCKED = "conflict_blocked"


class RagBadCaseDiagnosis(str, Enum):
    """Safe diagnoses for a RAG refusal or conflict; no model self-score."""

    NO_ACTIVE_KNOWLEDGE = "no_active_knowledge"
    RETRIEVER_EMPTY = "retriever_empty"
    RERANKER_NO_DIRECT_EVIDENCE = "reranker_no_direct_evidence"
    INDEX_UNAVAILABLE = "index_unavailable"
    MISSING_CRITICAL_SLOTS = "missing_critical_slots"
    HARD_FACT_CONFLICT = "hard_fact_conflict"


class KnowledgeItem(RagContractModel):
    """One complete, reviewed source version, retained for provenance."""

    knowledge_id: SafeId
    source_type: KnowledgeSourceType
    source_title: str = Field(min_length=3, max_length=256)
    source_uris: list[str] = Field(default_factory=list, max_length=12)
    source_version: str = Field(min_length=1, max_length=96)
    authority_level: int = Field(ge=1, le=5)
    effective_from: datetime
    review_due_at: datetime
    expires_at: datetime | None = None
    lifecycle_status: KnowledgeLifecycleStatus
    provider: str = Field(min_length=1, max_length=96)
    operation: str = Field(min_length=1, max_length=128)
    region: str = Field(min_length=1, max_length=96)
    adapter_status: str = Field(min_length=1, max_length=64)
    smoke_status: str = Field(min_length=1, max_length=64)
    privacy_class: str = Field(default="tool_knowledge", min_length=1, max_length=64)
    cost_tier: str = Field(default="unknown", min_length=1, max_length=64)
    content_sha256: Sha256
    supersedes: SafeId | None = None
    conflict_group_id: SafeId | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_lifecycle_times(self) -> KnowledgeItem:
        if self.review_due_at < self.effective_from:
            raise ValueError("review_due_at must not precede effective_from")
        if self.expires_at is not None and self.expires_at <= self.effective_from:
            raise ValueError("expires_at must be after effective_from")
        if self.supersedes == self.knowledge_id:
            raise ValueError("knowledge item cannot supersede itself")
        return self


class KnowledgeChunk(RagContractModel):
    """One retrievable claim with the parent source and key context preserved."""

    chunk_id: SafeId
    knowledge_id: SafeId
    heading_path: list[str] = Field(min_length=1, max_length=8)
    claim_type: KnowledgeClaimType
    capability_status: KnowledgeCapabilityStatus
    content: str = Field(min_length=8, max_length=8000)
    keywords: list[str] = Field(min_length=1, max_length=48)
    feature_codes: list[EditableFeature] = Field(default_factory=list, max_length=16)
    applicable_stages: list[RagStage] = Field(min_length=1, max_length=4)
    requires_adapter: bool = False
    requires_outbound_image: bool = False
    content_sha256: Sha256
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_chunk_shape(self) -> KnowledgeChunk:
        if len(self.keywords) != len(set(self.keywords)):
            raise ValueError("knowledge chunk keywords must be unique")
        if len(self.feature_codes) != len(set(self.feature_codes)):
            raise ValueError("knowledge chunk feature_codes must be unique")
        if len(self.applicable_stages) != len(set(self.applicable_stages)):
            raise ValueError("knowledge chunk applicable_stages must be unique")
        return self


class RagQuery(RagContractModel):
    """Structured retrieval request; deliberately contains no user raw text."""

    query_id: SafeId
    stage: RagStage
    requested_features: list[EditableFeature] = Field(default_factory=list, max_length=16)
    allowed_features: list[EditableFeature] = Field(default_factory=list, max_length=16)
    preserve_constraints: list[PreserveAttribute] = Field(default_factory=list, max_length=16)
    provider_candidates: list[str] = Field(default_factory=list, max_length=16)
    operation_candidates: list[str] = Field(default_factory=list, max_length=16)
    region: str = Field(default="local_demo", min_length=1, max_length=96)
    photo_quality_route: str | None = Field(default=None, max_length=96)
    face_count: int | None = Field(default=None, ge=0, le=10)
    subject_match_route: str | None = Field(default=None, max_length=96)
    safety_route: str | None = Field(default=None, max_length=96)
    profile_version: int | None = Field(default=None, ge=1)
    round_number: int | None = Field(default=None, ge=1, le=10)
    outbound_allowed: bool = False
    adapter_required: bool = False
    verification_route: str | None = Field(default=None, max_length=96)
    previous_provider_error_category: str | None = Field(default=None, max_length=96)
    missing_critical_slots: list[str] = Field(default_factory=list, max_length=16)
    intent_slots_present: list[str] = Field(default_factory=list, max_length=32)
    query_version: str = Field(default="rag-query-v0.1", min_length=1, max_length=64)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_query_shape(self) -> RagQuery:
        for values, name in (
            (self.requested_features, "requested_features"),
            (self.allowed_features, "allowed_features"),
            (self.provider_candidates, "provider_candidates"),
            (self.operation_candidates, "operation_candidates"),
            (self.missing_critical_slots, "missing_critical_slots"),
            (self.intent_slots_present, "intent_slots_present"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{name} must not contain duplicates")
        return self


class KnowledgeEvidence(RagContractModel):
    """A source-backed result suitable for a compact user explanation and Trace."""

    knowledge_id: SafeId
    chunk_id: SafeId
    source_title: str = Field(min_length=3, max_length=256)
    source_version: str = Field(min_length=1, max_length=96)
    lifecycle_status: KnowledgeLifecycleStatus
    relation: EvidenceRelation
    claim_type: KnowledgeClaimType
    capability_status: KnowledgeCapabilityStatus
    feature_codes: list[EditableFeature] = Field(default_factory=list, max_length=16)
    rank: int = Field(ge=1, le=100)
    fts_score: float | None = None
    adopted: bool = False
    reason_codes: list[str] = Field(default_factory=list, max_length=16)
    user_summary: str = Field(min_length=3, max_length=400)

    @property
    def knowledge_ref(self) -> str:
        return f"{self.knowledge_id}#{self.chunk_id}@{self.source_version}"


class RagRetrievalResult(RagContractModel):
    """One bounded, governed RAG P0 retrieval outcome and safe routing reason."""

    query_id: SafeId
    query_sha256: Sha256
    route: RetrievalRoute
    reason_codes: list[str] = Field(default_factory=list, max_length=24)
    evidences: list[KnowledgeEvidence] = Field(default_factory=list, max_length=10)
    retrieval_version: str = Field(min_length=1, max_length=64)
    index_version: str = Field(min_length=1, max_length=64)
    latency_ms: int = Field(ge=0)
    created_at: datetime = Field(default_factory=utc_now)

    @property
    def knowledge_refs(self) -> list[str]:
        return [item.knowledge_ref for item in self.evidences if item.adopted]

    def user_evidence_cards(self) -> list[dict[str, str]]:
        """Return the frozen P0 compact evidence-card projection only."""

        return [
            {
                "结论": item.user_summary,
                "来源": item.source_title,
                "版本": item.source_version,
                "状态": item.capability_status.value,
            }
            for item in self.evidences
            if item.adopted
        ]


class RagBadCaseRecord(RagContractModel):
    """A redacted retrieval failure/conflict fact for later product iteration."""

    bad_case_id: SafeId
    query_id: SafeId
    query_sha256: Sha256
    stage: RagStage
    retrieval_route: RetrievalRoute
    diagnosis: RagBadCaseDiagnosis
    metadata_candidate_count: int = Field(ge=0)
    sparse_candidate_count: int = Field(ge=0)
    dense_candidate_count: int = Field(ge=0)
    fused_candidate_count: int = Field(ge=0)
    evidence_refs: list[KnowledgeReference] = Field(default_factory=list, max_length=32)
    reason_codes: list[str] = Field(default_factory=list, max_length=24)
    created_at: datetime = Field(default_factory=utc_now)


class RagAdvisoryDecision(RagContractModel):
    """A bounded consumer-facing RAG decision, never a tool authorization.

    The user or an LLM may later choose only a non-executing next path after a
    conflict (manual review, manual suggestion, or stop).  Neither can use
    this object to decide which conflicting fact should execute.
    """

    advice_id: SafeId
    query_id: SafeId
    stage: RagStage
    retrieval_route: RetrievalRoute
    advisory_route: RagAdvisoryRoute
    direct_evidence_refs: list[KnowledgeReference] = Field(default_factory=list, max_length=16)
    reference_information_refs: list[KnowledgeReference] = Field(
        default_factory=list, max_length=16
    )
    conflict_information_refs: list[KnowledgeReference] = Field(default_factory=list, max_length=32)
    direct_features: list[EditableFeature] = Field(default_factory=list, max_length=16)
    proposal_allowed: bool = False
    existing_baseline_may_continue: bool = False
    execution_authorized: Literal[False] = False
    non_execution_next_steps: list[
        Literal["manual_review", "manual_suggestion", "stop", "use_existing_baseline"]
    ] = Field(default_factory=list, max_length=4)
    bad_case_ref: SafeId | None = None
    reason_codes: list[str] = Field(default_factory=list, max_length=24)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_advisory_boundary(self) -> RagAdvisoryDecision:
        if len(self.direct_evidence_refs) != len(set(self.direct_evidence_refs)):
            raise ValueError("direct_evidence_refs must not contain duplicates")
        if len(self.reference_information_refs) != len(set(self.reference_information_refs)):
            raise ValueError("reference_information_refs must not contain duplicates")
        if len(self.conflict_information_refs) != len(set(self.conflict_information_refs)):
            raise ValueError("conflict_information_refs must not contain duplicates")
        if len(self.direct_features) != len(set(self.direct_features)):
            raise ValueError("direct_features must not contain duplicates")
        if self.advisory_route == RagAdvisoryRoute.CONFLICT_BLOCKED:
            if not self.conflict_information_refs:
                raise ValueError("conflict_blocked decisions require conflict evidence")
            if self.proposal_allowed or self.existing_baseline_may_continue:
                raise ValueError("conflict_blocked decisions cannot permit a planning path")
            invalid = set(self.non_execution_next_steps) - {
                "manual_review",
                "manual_suggestion",
                "stop",
            }
            if invalid:
                raise ValueError("conflicts only allow non-execution next paths")
        if self.advisory_route == RagAdvisoryRoute.UNKNOWN_STOPPED and self.bad_case_ref is None:
            raise ValueError("unknown_stopped decisions require a bad-case record")
        return self
