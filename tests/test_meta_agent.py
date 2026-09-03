from __future__ import annotations

from datetime import datetime, timezone

import pytest

from portrait_consistency_agent.core.contracts import EditableFeature, PhotoRole
from portrait_consistency_agent.core.rag_contracts import (
    RagAdvisoryDecision,
    RagAdvisoryRoute,
    RagStage,
    RetrievalRoute,
)
from portrait_consistency_agent.services.edit_planner import diagnose_and_plan
from portrait_consistency_agent.services.meta_agent import (
    MetaAgentRoute,
    MetaAgentStage,
    MetaAgentToolSelector,
)
from portrait_consistency_agent.services.tool_registry import ToolRegistry
from tests.test_edit_planner import (
    make_intent,
    make_observation,
    make_profile,
    make_target_quality,
)


def test_registry_exposes_reviewed_baseline_and_web_candidate() -> None:
    selector = MetaAgentToolSelector()

    tools = {tool.tool_id: tool for tool in selector.registry.tools}

    assert tools["tencent_beautify_pic"].review_status == "verified"
    assert tools["tencent_beautify_pic"].execution_allowed is True
    assert tools["tencent_effect_web"].review_status == "candidate"
    assert tools["tencent_effect_web"].execution_allowed is False
    assert set(tools["tencent_effect_web"].available_features) >= {
        "face_lifting",
        "eye_enlarging",
    }


def test_explicit_web_route_is_proposal_only_with_baseline_fallback() -> None:
    selector = MetaAgentToolSelector()

    proposal = selector.propose(
        stage=MetaAgentStage.PLAN_EDIT,
        requested_features=[EditableFeature.FACE_LIFTING, EditableFeature.EYE_ENLARGING],
        preferred_tool_id="tencent_effect_web",
        proposal_id="tool_proposal_web_001",
    )

    assert proposal.route == MetaAgentRoute.CANDIDATE_PROPOSAL_ONLY
    assert proposal.selected_tool_id == "tencent_effect_web"
    assert proposal.selected_operation == "WebARImage"
    assert proposal.fallback_tool_id == "tencent_beautify_pic"
    assert proposal.execution_authorized is False
    assert "candidate_not_admitted" in proposal.reason_codes
    assert proposal.trace[-1]["provider_run_created"] is False
    assert all(
        "image" not in str(item).lower() or "bytes_read" in str(item) for item in proposal.trace
    )


def test_verified_web_route_is_scoped_and_still_non_authorising() -> None:
    registry = ToolRegistry.default()
    web = registry.get("tencent_effect_web")
    assert web is not None
    verified_web = web.model_copy(
        update={
            "review_status": "verified",
            "promotion_scope": "private_demo_beta",
            "execution_allowed": True,
            "reason_codes": ("verified_private_demo_scope",),
        }
    )
    selector = MetaAgentToolSelector(
        ToolRegistry(
            tools=tuple(
                verified_web if item.tool_id == "tencent_effect_web" else item
                for item in registry.tools
            )
        )
    )
    proposal = selector.propose(
        stage=MetaAgentStage.PLAN_EDIT,
        requested_features=[EditableFeature.FACE_LIFTING],
        preferred_tool_id="tencent_effect_web",
        proposal_id="tool_proposal_verified_web_001",
    )

    assert proposal.route == MetaAgentRoute.VERIFIED_TOOL_SELECTED
    assert proposal.selected_tool_id == "tencent_effect_web"
    assert proposal.execution_authorized is False
    assert "verified_private_demo_scope" in proposal.reason_codes
    assert proposal.trace[-1]["provider_run_created"] is False


def test_web_proposal_binds_to_web_edit_plan_without_authorizing_execution() -> None:
    proposal = MetaAgentToolSelector().propose(
        stage=MetaAgentStage.PLAN_EDIT,
        requested_features=[EditableFeature.FACE_LIFTING, EditableFeature.EYE_ENLARGING],
        preferred_tool_id="tencent_effect_web",
        proposal_id="tool_proposal_web_plan_binding_001",
    )
    assert proposal.selected_tool_id == "tencent_effect_web"
    assert proposal.execution_authorized is False

    profile = make_profile()
    target = make_observation(
        "photo_target",
        PhotoRole.TARGET,
        face_width=540,
        eye_boxes=((0.28, 0.36, 0.11, 0.07), (0.60, 0.37, 0.11, 0.07)),
    )
    planned = diagnose_and_plan(
        profile=profile,
        target_observation=target,
        quality_result=make_target_quality(target),
        intent=make_intent(),
        provider_id=proposal.selected_tool_id,
        plan_id="plan_web_proposal_binding_001",
    )

    assert planned.plan is not None
    assert planned.plan.provider == proposal.selected_tool_id
    assert planned.plan.provider_card_id == proposal.selected_card_id
    assert "candidate" in " ".join(planned.plan.risk_notes)


def test_default_route_selects_reviewed_baseline_without_network() -> None:
    selector = MetaAgentToolSelector()

    proposal = selector.propose(
        stage="execute",
        requested_features=["face_lifting"],
        proposal_id="tool_proposal_baseline_001",
    )

    assert proposal.route == MetaAgentRoute.BASELINE_SELECTED
    assert proposal.selected_tool_id == "tencent_beautify_pic"
    assert proposal.execution_authorized is False
    assert proposal.trace[-1]["external_call_made"] is False


def test_unknown_feature_is_manual_suggestion_and_never_provider_run() -> None:
    proposal = MetaAgentToolSelector().propose(
        stage=MetaAgentStage.PLAN_EDIT,
        requested_features=["lips_thickness"],
        proposal_id="tool_proposal_unknown_001",
    )

    assert proposal.route == MetaAgentRoute.MANUAL_SUGGESTION
    assert proposal.selected_tool_id is None
    assert proposal.execution_authorized is False
    assert "requested_capability_not_registered" in proposal.reason_codes
    assert proposal.trace[-1]["provider_run_created"] is False


def test_rag_conflict_stops_without_baseline_or_candidate_authorisation() -> None:
    advice = RagAdvisoryDecision(
        advice_id="rag_advice_conflict_001",
        query_id="rag_query_conflict_001",
        stage=RagStage.PLAN_EDIT,
        retrieval_route=RetrievalRoute.CONFLICT_BLOCKED,
        advisory_route=RagAdvisoryRoute.CONFLICT_BLOCKED,
        conflict_information_refs=["knowledge_conflict#chunk_01@v1"],
        proposal_allowed=False,
        existing_baseline_may_continue=False,
        execution_authorized=False,
        non_execution_next_steps=["manual_review", "stop"],
        reason_codes=["hard_fact_conflict"],
        created_at=datetime.now(timezone.utc),
    )

    proposal = MetaAgentToolSelector().propose(
        stage=MetaAgentStage.PLAN_EDIT,
        requested_features=["face_lifting"],
        preferred_tool_id="tencent_effect_web",
        rag_advice=advice,
        proposal_id="tool_proposal_conflict_001",
    )

    assert proposal.route == MetaAgentRoute.BLOCKED
    assert proposal.selected_tool_id is None
    assert proposal.execution_authorized is False
    assert "rag_advisory_blocked" in proposal.reason_codes
    assert proposal.evidence_refs == ["knowledge_conflict#chunk_01@v1"]
    assert proposal.trace[-1]["external_call_made"] is False


def test_invalid_stage_or_empty_feature_fails_closed() -> None:
    selector = MetaAgentToolSelector()
    with pytest.raises(ValueError, match="requested feature names"):
        selector.propose(stage="plan_edit", requested_features=[""])
    with pytest.raises(ValueError):
        selector.propose(stage="not_a_stage", requested_features=["face_lifting"])
