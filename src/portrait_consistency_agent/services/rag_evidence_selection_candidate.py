"""Proposal-only evidence selection for user-facing RAG explanations.

P0-B marks only direct evidence as ``adopted`` because that flag is used by
the execution gate.  That is correct for permission, but too narrow for an
explanation: an unsupported feature, a subject-match limitation, or a policy
boundary may be a reference that the user still needs to see.  This candidate
selects a small, query-scoped explanation set from the already retrieved
ranked list.  It cannot create evidence, grant execution, or read Gold data.
"""

from __future__ import annotations

from dataclasses import dataclass

from portrait_consistency_agent.core.rag_contracts import (
    EvidenceRelation,
    KnowledgeEvidence,
    RagQuery,
)
from portrait_consistency_agent.services.rag_p0b import RagP0BRun

# v0.1 reserved one item per namespace and then filled the remaining slots in
# retrieval order.  That was safe for execution, but it made an explanation
# page cite unrelated policy cards (for example, a CompareFace question also
# received a generic BeautifyPic policy).  v0.2 makes the scope depend on the
# validated route/operation slots.  The scope is still only an explanation
# proposal and never changes the execution gate.
EVIDENCE_SELECTION_CANDIDATE_VERSION = "rag-evidence-selection-candidate-v0.2-route-scoped"
EVIDENCE_SELECTION_LIMIT = 3


@dataclass(frozen=True)
class EvidenceSelectionDecision:
    """Traceable explanation evidence; this is not an execution decision."""

    selected_refs: tuple[str, ...]
    selected_relations: dict[str, str]
    accepted: bool
    reason_code: str
    candidate_count: int
    direct_count: int
    reference_count: int
    conflict_count: int

    def to_trace(self) -> dict[str, object]:
        return {
            "version": EVIDENCE_SELECTION_CANDIDATE_VERSION,
            "selected_refs": list(self.selected_refs),
            "selected_relations": dict(self.selected_relations),
            "accepted": self.accepted,
            "reason_code": self.reason_code,
            "candidate_count": self.candidate_count,
            "direct_count": self.direct_count,
            "reference_count": self.reference_count,
            "conflict_count": self.conflict_count,
            "selection_scope": "explanation_only",
            "proposal_only": True,
            "execution_authorized": False,
        }


def _namespace(evidence: KnowledgeEvidence) -> str | None:
    knowledge_id = evidence.knowledge_id
    if knowledge_id.startswith("project-policy-"):
        return "FX" if knowledge_id.endswith("-lifecycle") else "P"
    if knowledge_id.startswith("tencent-beautify-pic-"):
        return "B"
    if knowledge_id.startswith("tencent-compare-face-"):
        return "C"
    if knowledge_id.startswith("tencent-image-moderation-"):
        return "I"
    return None


def _requested_namespace(query: RagQuery, namespace: str) -> bool:
    operations = set(query.operation_candidates)
    if namespace == "B":
        return bool(
            query.requested_features
            or "BeautifyPic" in operations
            or query.stage.value == "plan_edit"
        )
    if namespace == "C":
        return bool(query.subject_match_route or "CompareFace" in operations)
    if namespace == "I":
        return bool(query.safety_route or "ImageModeration" in operations)
    if namespace in {"P", "FX"}:
        return "project_policy" in query.provider_candidates
    return False


def _feature_match(query: RagQuery, evidence: KnowledgeEvidence) -> bool:
    if not query.requested_features:
        return False
    return bool(set(query.requested_features).intersection(evidence.feature_codes))


def _is_preferred_for_namespace(
    query: RagQuery, evidence: KnowledgeEvidence, namespace: str
) -> bool:
    if _namespace(evidence) != namespace:
        return False
    if namespace == "B" and query.requested_features:
        # Keep a requested feature first.  Unsupported feature chunks carry
        # those same feature codes and therefore remain useful references.
        return _feature_match(query, evidence)
    if namespace == "FX":
        return evidence.relation == EvidenceRelation.CONFLICT_EVIDENCE
    if namespace == "P":
        return evidence.relation in {
            EvidenceRelation.DIRECT_EVIDENCE,
            EvidenceRelation.REFERENCE_CONTEXT,
        }
    return True


def _route_scope(query: RagQuery) -> tuple[str, ...] | None:
    """Return the evidence namespaces relevant to this validated route.

    This is an ontology-level policy, not a Gold lookup.  A known route should
    not be padded with every namespace that happened to score in retrieval.
    ``None`` means that no reviewed route semantics are available and the
    conservative ranked fallback may be used.
    """

    route = (query.verification_route or "").casefold()
    if not route:
        return None
    if "information_only_compound" in route:
        base = ["I", "C", "B"]
        if "policy_context" in query.intent_slots_present:
            base.append("P")
        return tuple(base)
    if "batch_content_safety" in route:
        return ("I", "P")
    if "batch_appearance" in route:
        return ("P", "B")
    if "batch_or_multiface" in route:
        # If the target scope is still missing, the tool limitation and the
        # governing policy are both useful.  If scope is already supplied,
        # keep the explanation focused on the consent/policy card.  An
        # explicit face-isolation instruction is itself a meaningful tool
        # scope, so retain both the limitation and the policy explanation.
        if (
            query.missing_critical_slots
            or "missing_scope" in query.intent_slots_present
            or "face_isolation" in query.intent_slots_present
        ):
            return ("B", "P")
        return ("P",)
    if any(token in route for token in ("third_party_consent", "unapproved_provider")):
        return ("P",)
    if any(
        token in route for token in ("policy_or_", "current_session_anchor", "missing_critical")
    ):
        return ("P",)
    if "provider_or_adapter_not_ready" in route:
        return ("B", "P")
    if "provider_parameter_range" in route:
        return ("B", "P")
    if "multiface_no_outbound" in route or "pose_limits" in route:
        return ("B", "P")
    if "manual_parameters" in route:
        return ("B", "P")
    if "unsupported_facial" in route:
        return ("B",)
    if "feedback_" in route or "policy_lifecycle_information" in route:
        return ("P",)
    if "index_unavailable" in route or "uncalibrated" in route:
        return ("P",)
    if "knowledge_review_due" in route:
        return ("FX",)
    if "bounded_plan_family" in route:
        return ("B", "P")
    if "authority_priority" in route or "direct_and_background" in route:
        return ("B", "FX")
    if "superseded" in route or "expired_knowledge" in route:
        return ("FX", "B")
    if any(
        token in route
        for token in ("stale_", "not_yet_effective", "hard_fact_conflict", "knowledge_conflict")
    ):
        return ("FX",)
    if "information_only" in route:
        operations = set(query.operation_candidates)
        ordered: list[str] = []
        if "ImageModeration" in operations:
            ordered.append("I")
        if "CompareFace" in operations:
            ordered.append("C")
        if "BeautifyPic" in operations:
            ordered.append("B")
        if "policy_context" in query.intent_slots_present:
            ordered.append("P")
        return tuple(ordered) or None
    if "reviewed_executable_feature" in route or "broad_facial_edit" in route:
        if "broad_facial_edit" in route:
            return ("B", "P")
        if (
            len(query.requested_features) > 1
            or query.preserve_constraints
            or "policy_context" in query.intent_slots_present
        ):
            return ("B", "P")
        return ("B",)
    if "approved_provider_scope" in route or "current_reviewed_version" in route:
        return ("B", "FX") if "current_reviewed_version" in route else ("B", "P")
    return None


def _candidates_for_namespace(
    query: RagQuery,
    evidences: tuple[KnowledgeEvidence, ...],
    namespace: str,
) -> list[KnowledgeEvidence]:
    """Rank candidates within one allowed namespace without inventing facts."""

    candidates = [item for item in evidences if _namespace(item) == namespace]
    if namespace == "FX":
        candidates.sort(key=lambda item: item.relation != EvidenceRelation.CONFLICT_EVIDENCE)
    elif namespace == "B" and query.requested_features:
        # A requested feature card is more useful than an unrelated parameter
        # card.  Keep stable retrieval order as the tie-breaker.
        candidates.sort(
            key=lambda item: (
                not _feature_match(query, item),
                item.relation != EvidenceRelation.DIRECT_EVIDENCE,
            )
        )
    elif namespace == "P":
        candidates.sort(
            key=lambda item: (
                item.relation != EvidenceRelation.DIRECT_EVIDENCE,
                item.relation == EvidenceRelation.CONFLICT_EVIDENCE,
            )
        )
    return candidates


def select_explanation_evidence(
    query: RagQuery,
    retrieval: RagP0BRun,
) -> EvidenceSelectionDecision:
    """Select up to three retrieved facts for explanation, never for execution.

    The selector first reserves one best fact for each structured namespace
    requested by the query.  It then fills remaining slots with the original
    retrieval order.  Direct evidence is not required: a reference or a
    conflict is useful when the user asks why a route is limited or blocked.
    """

    evidences = tuple(retrieval.result.evidences)
    requested_namespaces = _route_scope(query)
    if requested_namespaces is None:
        requested_namespaces = tuple(
            namespace
            for namespace in ("B", "C", "I", "FX", "P")
            if _requested_namespace(query, namespace)
        )
    selected: list[KnowledgeEvidence] = []
    selected_ids: set[str] = set()

    def add(item: KnowledgeEvidence) -> None:
        if len(selected) >= EVIDENCE_SELECTION_LIMIT:
            return
        if item.knowledge_ref in selected_ids:
            return
        selected.append(item)
        selected_ids.add(item.knowledge_ref)

    for namespace in requested_namespaces:
        candidates = _candidates_for_namespace(query, evidences, namespace)
        preferred = next(
            (item for item in candidates if _is_preferred_for_namespace(query, item, namespace)),
            candidates[0] if candidates else None,
        )
        if preferred is not None:
            add(preferred)

    # A known scope is a hard explanation boundary.  Only an unknown route may
    # use the ranked fallback, and even then it remains capped at three items.
    if _route_scope(query) is None:
        for item in evidences:
            if len(selected) >= EVIDENCE_SELECTION_LIMIT:
                break
            if _namespace(item) in requested_namespaces:
                add(item)

    selected_refs = tuple(item.knowledge_ref for item in selected)
    selected_relations = {item.knowledge_ref: item.relation.value for item in selected}
    direct_count = sum(item.relation == EvidenceRelation.DIRECT_EVIDENCE for item in evidences)
    reference_count = sum(item.relation == EvidenceRelation.REFERENCE_CONTEXT for item in evidences)
    conflict_count = sum(item.relation == EvidenceRelation.CONFLICT_EVIDENCE for item in evidences)
    if not selected:
        reason = "NO_RETRIEVED_EXPLANATION_EVIDENCE"
    elif _route_scope(query) is not None:
        reason = "ROUTE_SCOPED_EXPLANATION_SET"
    elif requested_namespaces:
        reason = "NAMESPACE_SCOPED_EXPLANATION_SET"
    else:
        reason = "RANKED_RETRIEVAL_EXPLANATION_SET"
    return EvidenceSelectionDecision(
        selected_refs=selected_refs,
        selected_relations=selected_relations,
        accepted=bool(selected),
        reason_code=reason,
        candidate_count=len(evidences),
        direct_count=direct_count,
        reference_count=reference_count,
        conflict_count=conflict_count,
    )


__all__ = [
    "EVIDENCE_SELECTION_CANDIDATE_VERSION",
    "EVIDENCE_SELECTION_LIMIT",
    "EvidenceSelectionDecision",
    "select_explanation_evidence",
]
