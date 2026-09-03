from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from portrait_consistency_agent.core.contracts import EditableFeature
from portrait_consistency_agent.core.rag_contracts import (
    EvidenceRelation,
    KnowledgeCapabilityStatus,
    RagQuery,
    RagStage,
    RetrievalRoute,
)
from portrait_consistency_agent.services.rag_evidence_selection_candidate import (
    select_explanation_evidence,
)
from portrait_consistency_agent.services.rag_gold_baseline import BaselineProjection
from portrait_consistency_agent.services.rag_gold_eval import GoldCase
from portrait_consistency_agent.services.rag_p0a import build_reviewed_provider_knowledge
from portrait_consistency_agent.services.rag_policy_coverage_candidate import (
    policy_relation_resolver_v4,
)
from portrait_consistency_agent.services.rag_query_compiler_candidate import (
    compile_generalized_projection_v3,
)
from portrait_consistency_agent.services.rag_route_handoff_candidate import (
    select_validated_route,
)


@dataclass(frozen=True)
class _EvidenceFixture:
    knowledge_id: str
    chunk_id: str
    relation: EvidenceRelation
    feature_codes: tuple[EditableFeature, ...] = ()

    @property
    def knowledge_ref(self) -> str:
        return f"{self.knowledge_id}#{self.chunk_id}@fixture"


def _projection(route: str, *, missing: tuple[str, ...] = ()) -> BaselineProjection:
    return BaselineProjection(
        category_codes=("fixture",),
        route_override=route,
        evidence_aliases=(),
        evidence_relations={},
        requested_features=(EditableFeature.FACE_LIFTING,),
        allowed_features=(EditableFeature.FACE_LIFTING,),
        retriever_kind="beautify",
        missing_critical_slots=missing,
    )


def _query(*, outbound_allowed: bool = True) -> RagQuery:
    return RagQuery(
        query_id="handoff_fixture",
        stage=RagStage.PLAN_EDIT,
        requested_features=[EditableFeature.FACE_LIFTING],
        allowed_features=[EditableFeature.FACE_LIFTING],
        provider_candidates=["tencent_cloud"],
        operation_candidates=["BeautifyPic"],
        outbound_allowed=outbound_allowed,
        adapter_required=True,
    )


def _retrieval(
    route: RetrievalRoute,
    *,
    relation: EvidenceRelation = EvidenceRelation.DIRECT_EVIDENCE,
    capability: KnowledgeCapabilityStatus = KnowledgeCapabilityStatus.EXECUTABLE,
    evidence_count: int = 1,
) -> SimpleNamespace:
    evidence = SimpleNamespace(relation=relation, capability_status=capability)
    return SimpleNamespace(
        result=SimpleNamespace(route=route, evidences=[evidence] * evidence_count)
    )


def test_direct_proposal_is_accepted_only_with_real_executable_evidence() -> None:
    decision = select_validated_route(
        _projection("DIRECT"), _query(), _retrieval(RetrievalRoute.EVIDENCE_FOUND)
    )
    assert decision.accepted is True
    assert decision.selected_route == "DIRECT"
    assert decision.supporting_evidence_count == 1
    assert decision.to_trace()["execution_authorized"] is False


def test_direct_proposal_cannot_turn_reference_only_evidence_into_direct() -> None:
    decision = select_validated_route(
        _projection("DIRECT"),
        _query(),
        _retrieval(
            RetrievalRoute.MANUAL_SUGGESTION,
            relation=EvidenceRelation.REFERENCE_CONTEXT,
            capability=KnowledgeCapabilityStatus.SUGGESTION_ONLY,
        ),
    )
    assert decision.accepted is False
    assert decision.selected_route == "SUGGEST"
    assert decision.route_source == "retrieval_result"


def test_hard_conflict_wins_over_a_direct_projection() -> None:
    decision = select_validated_route(
        _projection("DIRECT"), _query(), _retrieval(RetrievalRoute.CONFLICT_BLOCKED)
    )
    assert decision.selected_route == "BLOCK"
    assert decision.accepted is False
    assert decision.reason_code == "RETRIEVAL_CONFLICT_BLOCKED"


def test_clarification_is_allowed_only_when_missing_slots_are_declared() -> None:
    decision = select_validated_route(
        _projection("CLARIFY", missing=("allowed_features",)),
        _query(),
        _retrieval(RetrievalRoute.BASELINE_FALLBACK, evidence_count=0),
    )
    assert decision.accepted is True
    assert decision.selected_route == "CLARIFY"


def test_specificity_resolver_does_not_mark_unrequested_parameter_direct() -> None:
    beautify_item, chunks = build_reviewed_provider_knowledge()[0]
    face_chunk = next(item for item in chunks if item.chunk_id == "beautify_face_lifting")
    eye_chunk = next(item for item in chunks if item.chunk_id == "beautify_eye_enlarging")
    query = _query()
    assert policy_relation_resolver_v4(query, beautify_item, face_chunk) == (
        EvidenceRelation.DIRECT_EVIDENCE
    )
    assert policy_relation_resolver_v4(query, beautify_item, eye_chunk) == (
        EvidenceRelation.REFERENCE_CONTEXT
    )


def test_explanation_selector_keeps_reference_for_unsupported_feature() -> None:
    query = RagQuery(
        query_id="selection_fixture",
        stage=RagStage.PLAN_EDIT,
        requested_features=[EditableFeature.LIPS_THICKNESS],
        provider_candidates=["tencent_cloud"],
        operation_candidates=["BeautifyPic"],
    )
    unsupported = _EvidenceFixture(
        "tencent-beautify-pic-2019-12-13",
        "beautify_unsupported_facial_features",
        EvidenceRelation.REFERENCE_CONTEXT,
        (EditableFeature.LIPS_THICKNESS,),
    )
    run = SimpleNamespace(result=SimpleNamespace(evidences=[unsupported]))
    decision = select_explanation_evidence(query, run)
    assert decision.accepted is True
    assert decision.selected_refs == (unsupported.knowledge_ref,)
    assert decision.selected_relations[unsupported.knowledge_ref] == "reference_context"
    assert decision.to_trace()["execution_authorized"] is False


def test_explanation_selector_reserves_distinct_namespaces_for_compound_request() -> None:
    query = RagQuery(
        query_id="compound_selection_fixture",
        stage=RagStage.VERIFICATION_STRATEGY,
        provider_candidates=["tencent_cloud", "project_policy"],
        operation_candidates=["CompareFace", "ImageModeration"],
        subject_match_route="subject_match",
        safety_route="moderation_scope",
    )
    evidences = [
        _EvidenceFixture(
            "tencent-compare-face-2018-03-01",
            "compare_face_subject_match",
            EvidenceRelation.REFERENCE_CONTEXT,
        ),
        _EvidenceFixture(
            "tencent-image-moderation-2020-12-29",
            "image_moderation_safety_gate",
            EvidenceRelation.REFERENCE_CONTEXT,
        ),
        _EvidenceFixture(
            "project-policy-beautifypic-guard",
            "beautifypic-proposal-only",
            EvidenceRelation.REFERENCE_CONTEXT,
        ),
        _EvidenceFixture(
            "tencent-beautify-pic-2019-12-13",
            "beautify_face_lifting",
            EvidenceRelation.DIRECT_EVIDENCE,
            (EditableFeature.FACE_LIFTING,),
        ),
    ]
    run = SimpleNamespace(result=SimpleNamespace(evidences=evidences))
    decision = select_explanation_evidence(query, run)
    assert decision.accepted is True
    assert len(decision.selected_refs) == 3
    assert {ref.split("#", 1)[0] for ref in decision.selected_refs} == {
        "tencent-compare-face-2018-03-01",
        "tencent-image-moderation-2020-12-29",
        "project-policy-beautifypic-guard",
    }


def test_explanation_selector_does_not_pad_a_subject_question_with_unrelated_policy() -> None:
    query = RagQuery(
        query_id="subject_scope_fixture",
        stage=RagStage.VERIFICATION_STRATEGY,
        provider_candidates=["tencent_cloud", "project_policy"],
        operation_candidates=["CompareFace"],
        subject_match_route="information_only",
        verification_route="information_only_tool_scope",
    )
    evidences = [
        _EvidenceFixture(
            "tencent-compare-face-2018-03-01",
            "compare_face_subject_match",
            EvidenceRelation.REFERENCE_CONTEXT,
        ),
        _EvidenceFixture(
            "project-policy-beautifypic-guard",
            "beautifypic-proposal-only",
            EvidenceRelation.REFERENCE_CONTEXT,
        ),
    ]
    decision = select_explanation_evidence(
        query, SimpleNamespace(result=SimpleNamespace(evidences=evidences))
    )
    assert decision.selected_refs == (evidences[0].knowledge_ref,)
    assert decision.reason_code == "ROUTE_SCOPED_EXPLANATION_SET"


def test_explanation_selector_keeps_conflict_and_current_context_for_expiry_question() -> None:
    query = RagQuery(
        query_id="expiry_scope_fixture",
        stage=RagStage.PLAN_EDIT,
        provider_candidates=["tencent_cloud", "project_policy"],
        operation_candidates=["BeautifyPic"],
        verification_route="expired_knowledge_block",
    )
    evidences = [
        _EvidenceFixture(
            "project-policy-beautifypic-lifecycle",
            "beautifypic-expired-conflict",
            EvidenceRelation.CONFLICT_EVIDENCE,
        ),
        _EvidenceFixture(
            "tencent-beautify-pic-2019-12-13",
            "beautify_face_lifting",
            EvidenceRelation.REFERENCE_CONTEXT,
            (EditableFeature.FACE_LIFTING,),
        ),
        _EvidenceFixture(
            "project-policy-beautifypic-guard",
            "beautifypic-proposal-only",
            EvidenceRelation.REFERENCE_CONTEXT,
        ),
    ]
    decision = select_explanation_evidence(
        query, SimpleNamespace(result=SimpleNamespace(evidences=evidences))
    )
    assert decision.selected_refs == (evidences[0].knowledge_ref, evidences[1].knowledge_ref)
    assert decision.selected_relations[evidences[0].knowledge_ref] == "conflict_evidence"


def test_route_handoff_accepts_explicit_safe_stop_and_anchor_degrade() -> None:
    stop_projection = BaselineProjection(
        category_codes=("feedback_stops_plan_family",),
        route_override="STOP",
        evidence_aliases=("P",),
        evidence_relations={"P": "reference_context"},
    )
    stop = select_validated_route(
        stop_projection,
        _query(),
        _retrieval(RetrievalRoute.BASELINE_FALLBACK, evidence_count=1),
    )
    assert stop.accepted is True
    assert stop.selected_route == "STOP"

    degrade_projection = BaselineProjection(
        category_codes=("current_session_anchor_degrade",),
        route_override="BASELINE",
        evidence_aliases=("P",),
        evidence_relations={"P": "direct_evidence"},
    )
    degrade = select_validated_route(
        degrade_projection,
        _query(),
        _retrieval(RetrievalRoute.MANUAL_SUGGESTION, evidence_count=1),
    )
    assert degrade.accepted is True
    assert degrade.selected_route == "BASELINE"


def test_compiler_v3_records_batch_scope_and_outbound_conflict() -> None:
    batch, _ = compile_generalized_projection_v3(
        GoldCase(case_id="D-test-batch", split="dev", query="这张合照只修左边")
    )
    assert batch.route_override == "SUGGEST"
    assert batch.missing_critical_slots == ()

    appearance, _ = compile_generalized_projection_v3(
        GoldCase(case_id="D-test-appearance", split="dev", query="批量 9 张，先挑最丑的修")
    )
    assert appearance.route_override == "CLARIFY"
    assert appearance.missing_critical_slots == ("appearance_judgment_scope",)

    adult_batch, _ = compile_generalized_projection_v3(
        GoldCase(case_id="D-test-adult-batch", split="dev", query="成人自拍能不能直接批量处理")
    )
    assert adult_batch.route_override == "CLARIFY"
    assert adult_batch.missing_critical_slots == ("batch_content_safety_scope",)

    capability, _ = compile_generalized_projection_v3(
        GoldCase(case_id="D-test-capability", split="dev", query="眼睛显得不一样，可查支持范围吗")
    )
    assert capability.route_override == "DIRECT"

    conflict, _ = compile_generalized_projection_v3(
        GoldCase(
            case_id="X-test-conflict",
            split="challenge",
            query="不外发照片，但用新 SDK 自动修唇厚",
        )
    )
    assert conflict.route_override == "BLOCK"
    assert conflict.outbound_allowed is False
