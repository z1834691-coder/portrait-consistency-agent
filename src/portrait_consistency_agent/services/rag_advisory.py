"""Bounded RAG consumer for 8A/8C and future tool-routing seams.

This module is deliberately an *advisory* bridge.  It turns a persisted
P0-B retrieval result into explicit direct/reference/conflict evidence groups,
records a safe bad case when it cannot answer, and leaves execution authority
with the existing state machine, consent policy, Provider Card and Adapter.

It does not accept image bytes, raw user text, embeddings, secrets, or a
Provider receipt; it never creates parameters, calls an external tool, or
marks a tool as authorized.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from portrait_consistency_agent.core.contracts import (
    EditableFeature,
    IntentFrame,
    ReferenceProfile,
)
from portrait_consistency_agent.core.rag_contracts import (
    EvidenceRelation,
    RagAdvisoryDecision,
    RagAdvisoryRoute,
    RagBadCaseDiagnosis,
    RagBadCaseRecord,
    RagQuery,
    RagStage,
    RetrievalRoute,
)
from portrait_consistency_agent.services.rag_p0a import build_plan_edit_query
from portrait_consistency_agent.services.rag_p0b import RagP0BHybridRetriever, RagP0BRun
from portrait_consistency_agent.storage.knowledge_store import LocalKnowledgeStore

RAG_ADVISORY_VERSION = "rag-advisory-v0.1"


@dataclass(frozen=True)
class RagAdvisoryRun:
    """One replayable retrieval-plus-consumer decision, with no execution side effect."""

    decision: RagAdvisoryDecision
    retrieval: RagP0BRun
    bad_case: RagBadCaseRecord | None
    trace: tuple[dict[str, object], ...]


def build_plan_advisory_query(
    *,
    query_id: str,
    intent: IntentFrame,
    profile: ReferenceProfile,
    face_count: int = 1,
) -> RagQuery:
    """Build an 8A capability query from already validated contracts only."""

    allowed = list(intent.allowed_features or profile.allowed_features)
    return build_plan_edit_query(
        query_id=query_id,
        requested_features=allowed,
        allowed_features=allowed,
        preserve_constraints=intent.preserve_attributes or profile.preserve_attributes,
        face_count=face_count,
        # This means an existing, user-consented execution flow may be
        # considered later.  It is not an authorization created by RAG.
        outbound_allowed=True,
    )


def build_verification_strategy_advisory_query(
    *,
    query_id: str,
    profile_version: int,
    round_number: int,
) -> RagQuery:
    """Ask only what reviewed knowledge says about a verification strategy.

    The query itself explicitly forbids outbound image use.  P0-C can surface
    CompareFace's limitation as evidence but cannot call it or change 8C's
    baseline allow-list.
    """

    return RagQuery(
        query_id=query_id,
        stage=RagStage.VERIFICATION_STRATEGY,
        provider_candidates=["tencent_cloud"],
        operation_candidates=["CompareFace"],
        profile_version=profile_version,
        round_number=round_number,
        outbound_allowed=False,
        adapter_required=False,
        verification_route="strategy_selection",
        intent_slots_present=["profile_version", "round_number", "verification_scope"],
    )


def build_failure_routing_advisory_query(
    *,
    query_id: str,
    provider: str,
    operation: str,
    provider_error_category: str,
) -> RagQuery:
    """Build a future failure-route lookup without leaking Provider error payloads."""

    return RagQuery(
        query_id=query_id,
        stage=RagStage.FAILURE_ROUTING,
        provider_candidates=[provider],
        operation_candidates=[operation],
        previous_provider_error_category=provider_error_category,
        outbound_allowed=False,
        adapter_required=False,
        intent_slots_present=["provider", "operation", "safe_error_category"],
    )


class RagAdvisoryService:
    """Translate RAG evidence into a safe, non-authorizing product decision."""

    def __init__(self, *, store: LocalKnowledgeStore, retriever: RagP0BHybridRetriever) -> None:
        self.store = store
        self.retriever = retriever

    def advise(
        self,
        *,
        query: RagQuery,
        existing_baseline_available: bool,
        advice_id: str | None = None,
    ) -> RagAdvisoryRun:
        """Retrieve reviewed knowledge and choose a *non-execution* next route.

        A retriever miss never becomes an LLM guess.  It either stops the
        RAG-dependent branch with ``不知道`` or falls back only to an already
        configured, independently gated Provider Card baseline.
        """

        retrieval = self.retriever.retrieve(query)
        result = retrieval.result
        direct = [
            evidence
            for evidence in result.evidences
            if evidence.relation == EvidenceRelation.DIRECT_EVIDENCE and evidence.adopted
        ]
        reference = [
            evidence
            for evidence in result.evidences
            if evidence.relation == EvidenceRelation.REFERENCE_CONTEXT
        ]
        conflicts = [
            evidence
            for evidence in result.evidences
            if evidence.relation == EvidenceRelation.CONFLICT_EVIDENCE
        ]
        direct_refs = [evidence.knowledge_ref for evidence in direct]
        reference_refs = [evidence.knowledge_ref for evidence in reference]
        conflict_refs = [evidence.knowledge_ref for evidence in conflicts]
        direct_features = _unique_features(direct)

        bad_case = self._bad_case_for(retrieval)
        if bad_case is not None:
            self.store.record_bad_case(bad_case)

        if result.route == RetrievalRoute.CONFLICT_BLOCKED:
            advisory_route = RagAdvisoryRoute.CONFLICT_BLOCKED
            proposal_allowed = False
            baseline_may_continue = False
            next_steps = ["manual_review", "manual_suggestion", "stop"]
            reason_codes = [*result.reason_codes, "CONFLICT_REQUIRES_NONEXECUTION_REVIEW"]
        elif result.route == RetrievalRoute.EVIDENCE_FOUND:
            advisory_route = RagAdvisoryRoute.ADVISORY_AVAILABLE
            proposal_allowed = True
            baseline_may_continue = False
            next_steps = ["use_existing_baseline", "manual_suggestion", "stop"]
            reason_codes = [*result.reason_codes, "RAG_ADVISORY_ONLY"]
        elif result.route == RetrievalRoute.MANUAL_SUGGESTION:
            advisory_route = RagAdvisoryRoute.MANUAL_SUGGESTION_ONLY
            proposal_allowed = True
            baseline_may_continue = False
            next_steps = ["manual_suggestion", "stop"]
            reason_codes = [*result.reason_codes, "NO_AUTOMATIC_NEW_CAPABILITY"]
        elif existing_baseline_available:
            advisory_route = RagAdvisoryRoute.BASELINE_DEGRADED
            proposal_allowed = False
            baseline_may_continue = True
            next_steps = ["use_existing_baseline", "manual_suggestion", "stop"]
            reason_codes = [*result.reason_codes, "RAG_BRANCH_STOPPED_BASELINE_UNCHANGED"]
        else:
            advisory_route = RagAdvisoryRoute.UNKNOWN_STOPPED
            proposal_allowed = False
            baseline_may_continue = False
            next_steps = ["manual_suggestion", "stop"]
            reason_codes = [*result.reason_codes, "RAG_UNKNOWN_DO_NOT_INVENT"]

        decision = RagAdvisoryDecision(
            advice_id=advice_id or f"rag_advice_{uuid.uuid4().hex}",
            query_id=query.query_id,
            stage=query.stage,
            retrieval_route=result.route,
            advisory_route=advisory_route,
            direct_evidence_refs=direct_refs,
            reference_information_refs=reference_refs,
            conflict_information_refs=conflict_refs,
            direct_features=direct_features,
            proposal_allowed=proposal_allowed,
            existing_baseline_may_continue=baseline_may_continue,
            # The Literal[False] contract makes this boundary impossible to
            # change by RAG output or an LLM completion.
            execution_authorized=False,
            non_execution_next_steps=next_steps,
            bad_case_ref=bad_case.bad_case_id if bad_case is not None else None,
            reason_codes=list(dict.fromkeys(reason_codes)),
        )
        trace = [
            *retrieval.trace,
            {
                "step": "rag_consumer_classification",
                "version": RAG_ADVISORY_VERSION,
                "query_id": query.query_id,
                "stage": query.stage.value,
                "retrieval_route": result.route.value,
                "advisory_route": decision.advisory_route.value,
                "direct_evidence_refs": decision.direct_evidence_refs,
                "reference_information_refs": decision.reference_information_refs,
                "conflict_information_refs": decision.conflict_information_refs,
                "execution_authorized": False,
                "existing_baseline_may_continue": decision.existing_baseline_may_continue,
                "bad_case_ref": decision.bad_case_ref,
                "external_calls": 0,
            },
        ]
        self.store.record_advisory_run(decision=decision, trace=trace)
        return RagAdvisoryRun(
            decision=decision,
            retrieval=retrieval,
            bad_case=bad_case,
            trace=tuple(trace),
        )

    @staticmethod
    def _bad_case_for(retrieval: RagP0BRun) -> RagBadCaseRecord | None:
        """Translate a controlled retrieval failure into a diagnosable safe fact."""

        result = retrieval.result
        diagnosis: RagBadCaseDiagnosis | None = None
        if result.route == RetrievalRoute.CONFLICT_BLOCKED:
            diagnosis = RagBadCaseDiagnosis.HARD_FACT_CONFLICT
        elif result.route == RetrievalRoute.INDEX_UNAVAILABLE:
            diagnosis = RagBadCaseDiagnosis.INDEX_UNAVAILABLE
        elif result.route == RetrievalRoute.QUERY_UNDERSPECIFIED:
            diagnosis = RagBadCaseDiagnosis.MISSING_CRITICAL_SLOTS
        elif result.route == RetrievalRoute.BASELINE_FALLBACK:
            if "NO_ACTIVE_KNOWLEDGE" in result.reason_codes:
                diagnosis = RagBadCaseDiagnosis.NO_ACTIVE_KNOWLEDGE
            elif "RETRIEVER_MISS_SUSPECT" in result.reason_codes:
                diagnosis = RagBadCaseDiagnosis.RETRIEVER_EMPTY
            else:
                diagnosis = RagBadCaseDiagnosis.RERANKER_NO_DIRECT_EVIDENCE
        if diagnosis is None:
            return None
        return RagBadCaseRecord(
            bad_case_id=f"rag_badcase_{uuid.uuid4().hex}",
            query_id=result.query_id,
            query_sha256=result.query_sha256,
            stage=_stage_from_run(retrieval),
            retrieval_route=result.route,
            diagnosis=diagnosis,
            metadata_candidate_count=retrieval.metadata_candidate_count,
            sparse_candidate_count=retrieval.sparse_candidate_count,
            dense_candidate_count=retrieval.dense_candidate_count,
            fused_candidate_count=retrieval.fused_candidate_count,
            evidence_refs=[evidence.knowledge_ref for evidence in result.evidences],
            reason_codes=result.reason_codes,
        )


def _stage_from_run(run: RagP0BRun) -> RagStage:
    """Read the already validated stage from the first safe trace event."""

    stage_value = str(run.trace[0]["stage"])
    return RagStage(stage_value)


def _unique_features(evidences: list[object]) -> list[EditableFeature]:
    features: list[EditableFeature] = []
    for evidence in evidences:
        # ``KnowledgeEvidence`` is intentionally kept structural here so this
        # helper cannot inspect source text or user data.
        for feature in getattr(evidence, "feature_codes", []):
            if feature not in features:
                features.append(feature)
    return features
