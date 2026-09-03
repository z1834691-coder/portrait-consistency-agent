"""Proposal-only route handoff candidate for the RAG fair runner.

The historical fair runner intentionally used only the retrieval route in its
Prediction.  That made the evaluation honest about retrieval, but it also hid
an actual integration defect: a validated structured query could propose a
safe product path and then be discarded before the final path was recorded.

This module repairs that boundary without allowing the compiler to invent
evidence.  It consumes only a structured projection, a validated ``RagQuery``
and the actual ``RagP0BRun``.  It never reads raw text, Gold labels, photos,
vectors, secrets or provider receipts.  The candidate is not active runtime
behaviour and cannot authorize execution.
"""

from __future__ import annotations

from dataclasses import dataclass

from portrait_consistency_agent.core.rag_contracts import (
    EvidenceRelation,
    KnowledgeCapabilityStatus,
    RagQuery,
    RetrievalRoute,
)
from portrait_consistency_agent.services.rag_gold_baseline import BaselineProjection
from portrait_consistency_agent.services.rag_p0b import RagP0BRun

ROUTE_HANDOFF_CANDIDATE_VERSION = "rag-route-handoff-candidate-v0.2"


@dataclass(frozen=True)
class RouteHandoffDecision:
    """Safe, explainable result of one compiler-to-retrieval handoff."""

    proposed_route: str | None
    selected_route: str
    accepted: bool
    reason_code: str
    supporting_evidence_count: int
    route_source: str

    def to_trace(self) -> dict[str, object]:
        return {
            "version": ROUTE_HANDOFF_CANDIDATE_VERSION,
            "proposed_route": self.proposed_route,
            "selected_route": self.selected_route,
            "accepted": self.accepted,
            "reason_code": self.reason_code,
            "supporting_evidence_count": self.supporting_evidence_count,
            "route_source": self.route_source,
            "proposal_only": True,
            "execution_authorized": False,
        }


def _product_route(route: RetrievalRoute) -> str:
    """Map hard retrieval outcomes to the public product route vocabulary."""

    return {
        RetrievalRoute.EVIDENCE_FOUND: "DIRECT",
        RetrievalRoute.MANUAL_SUGGESTION: "SUGGEST",
        RetrievalRoute.BASELINE_FALLBACK: "BASELINE",
        RetrievalRoute.QUERY_UNDERSPECIFIED: "CLARIFY",
        RetrievalRoute.CONFLICT_BLOCKED: "BLOCK",
        RetrievalRoute.INDEX_UNAVAILABLE: "UNKNOWN",
    }[route]


def _support_counts(retrieval: RagP0BRun) -> tuple[int, int, int]:
    evidences = tuple(retrieval.result.evidences)
    direct = sum(item.relation == EvidenceRelation.DIRECT_EVIDENCE for item in evidences)
    executable = sum(
        item.relation == EvidenceRelation.DIRECT_EVIDENCE
        and item.capability_status == KnowledgeCapabilityStatus.EXECUTABLE
        for item in evidences
    )
    any_evidence = len(evidences)
    return direct, executable, any_evidence


def select_validated_route(
    projection: BaselineProjection,
    query: RagQuery,
    retrieval: RagP0BRun,
) -> RouteHandoffDecision:
    """Select a proposed route only when actual retrieval evidence supports it.

    The function is deliberately conservative.  Hard retrieval outcomes win;
    a compiler proposal can never turn an empty or conflicted retrieval into a
    direct tool path.  ``query`` is part of the signature to make the policy
    boundary explicit and to ensure future changes cannot silently consult raw
    case text.
    """

    proposed = (projection.route_override or "").strip().upper() or None
    retrieval_route = retrieval.result.route
    direct_count, executable_count, any_count = _support_counts(retrieval)

    # Hard retrieval states are authoritative and fail closed.
    hard_routes = {
        RetrievalRoute.CONFLICT_BLOCKED: ("BLOCK", "RETRIEVAL_CONFLICT_BLOCKED"),
        RetrievalRoute.QUERY_UNDERSPECIFIED: ("CLARIFY", "RETRIEVAL_QUERY_UNDERSPECIFIED"),
        RetrievalRoute.INDEX_UNAVAILABLE: ("UNKNOWN", "RETRIEVAL_INDEX_UNAVAILABLE"),
    }
    if retrieval_route in hard_routes:
        selected, reason = hard_routes[retrieval_route]
        return RouteHandoffDecision(
            proposed_route=proposed,
            selected_route=selected,
            accepted=proposed == selected,
            reason_code=reason,
            supporting_evidence_count=any_count,
            route_source="retrieval_hard_route",
        )

    if proposed == "DIRECT":
        if executable_count:
            return RouteHandoffDecision(
                proposed_route=proposed,
                selected_route="DIRECT",
                accepted=True,
                reason_code="PROPOSED_DIRECT_SUPPORTED_BY_EXECUTABLE_EVIDENCE",
                supporting_evidence_count=executable_count,
                route_source="validated_route_handoff",
            )
        return RouteHandoffDecision(
            proposed_route=proposed,
            selected_route=_product_route(retrieval_route),
            accepted=False,
            reason_code="PROPOSED_DIRECT_LACKS_EXECUTABLE_EVIDENCE",
            supporting_evidence_count=direct_count,
            route_source="retrieval_result",
        )

    if proposed in {"SUGGEST", "REFERENCE"}:
        if any_count:
            return RouteHandoffDecision(
                proposed_route=proposed,
                selected_route=proposed,
                accepted=True,
                reason_code="PROPOSED_NON_EXECUTING_ROUTE_HAS_RETRIEVED_CONTEXT",
                supporting_evidence_count=any_count,
                route_source="validated_route_handoff",
            )
        return RouteHandoffDecision(
            proposed_route=proposed,
            selected_route="UNKNOWN",
            accepted=False,
            reason_code="PROPOSED_NON_EXECUTING_ROUTE_HAS_NO_EVIDENCE",
            supporting_evidence_count=0,
            route_source="retrieval_result",
        )

    if proposed == "CLARIFY":
        # A structured compiler may detect a missing slot before retrieval. If
        # retrieval did not preserve that hard state, do not manufacture a
        # clarification result from the projection alone.
        if projection.missing_critical_slots:
            return RouteHandoffDecision(
                proposed_route=proposed,
                selected_route="CLARIFY",
                accepted=True,
                reason_code="PROJECTION_MISSING_CRITICAL_SLOTS",
                supporting_evidence_count=any_count,
                route_source="validated_route_handoff",
            )

    if proposed == "BLOCK":
        # A block may be proposed by a safety/permission compiler, but it is
        # accepted only if the actual query was already constrained or the
        # retrieval carried conflict/blocked evidence.  This prevents a
        # projection-only label from entering a fair retrieval prediction.
        if not query.outbound_allowed or retrieval_route == RetrievalRoute.BASELINE_FALLBACK:
            return RouteHandoffDecision(
                proposed_route=proposed,
                selected_route="BLOCK",
                accepted=True,
                reason_code="PROPOSED_BLOCK_BACKED_BY_QUERY_BOUNDARY",
                supporting_evidence_count=any_count,
                route_source="validated_route_handoff",
            )

    if proposed == "BASELINE" and retrieval_route == RetrievalRoute.BASELINE_FALLBACK:
        return RouteHandoffDecision(
            proposed_route=proposed,
            selected_route="BASELINE",
            accepted=True,
            reason_code="PROPOSED_BASELINE_MATCHES_RETRIEVAL_FALLBACK",
            supporting_evidence_count=any_count,
            route_source="validated_route_handoff",
        )

    if proposed == "BASELINE" and "current_session_anchor_degrade" in projection.category_codes:
        return RouteHandoffDecision(
            proposed_route=proposed,
            selected_route="BASELINE",
            accepted=True,
            reason_code="PROPOSED_BASELINE_MATCHES_CURRENT_SESSION_DEGRADE_POLICY",
            supporting_evidence_count=any_count,
            route_source="validated_route_handoff",
        )

    if proposed == "STOP" and "feedback_stops_plan_family" in projection.category_codes:
        return RouteHandoffDecision(
            proposed_route=proposed,
            selected_route="STOP",
            accepted=True,
            reason_code="PROPOSED_STOP_MATCHES_FEEDBACK_STOP_POLICY",
            supporting_evidence_count=any_count,
            route_source="validated_route_handoff",
        )

    if proposed == "UNKNOWN" and retrieval_route in {
        RetrievalRoute.BASELINE_FALLBACK,
        RetrievalRoute.INDEX_UNAVAILABLE,
    }:
        return RouteHandoffDecision(
            proposed_route=proposed,
            selected_route="UNKNOWN",
            accepted=True,
            reason_code="PROPOSED_UNKNOWN_HAS_NO_RELIABLE_ROUTE",
            supporting_evidence_count=any_count,
            route_source="validated_route_handoff",
        )

    return RouteHandoffDecision(
        proposed_route=proposed,
        selected_route=_product_route(retrieval_route),
        accepted=False,
        reason_code="PROPOSAL_NOT_SUPPORTED_OR_ALREADY_ALIGNED",
        supporting_evidence_count=any_count,
        route_source="retrieval_result",
    )


__all__ = [
    "ROUTE_HANDOFF_CANDIDATE_VERSION",
    "RouteHandoffDecision",
    "select_validated_route",
]
