"""Regression tests for the frozen RAG advisory-only integration boundary."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from portrait_consistency_agent.core.contracts import EditableFeature, PhotoRole
from portrait_consistency_agent.core.rag_contracts import (
    KnowledgeCapabilityStatus,
    KnowledgeChunk,
    KnowledgeClaimType,
    KnowledgeItem,
    KnowledgeLifecycleStatus,
    KnowledgeSourceType,
    RagAdvisoryRoute,
    RagBadCaseDiagnosis,
    RagQuery,
    RagStage,
)
from portrait_consistency_agent.services.edit_planner import diagnose_and_plan
from portrait_consistency_agent.services.local_rag_models import (
    DeterministicTokenEmbeddingBackend,
    TokenOverlapReranker,
)
from portrait_consistency_agent.services.rag_advisory import RagAdvisoryService
from portrait_consistency_agent.services.rag_p0a import (
    build_plan_edit_query,
    seed_reviewed_provider_knowledge,
)
from portrait_consistency_agent.services.rag_p0b import RagP0BHybridRetriever
from portrait_consistency_agent.storage.dense_index import LocalDenseIndex
from portrait_consistency_agent.storage.knowledge_store import LocalKnowledgeStore
from tests.test_edit_planner import make_intent, make_observation, make_profile, make_target_quality


def _store(tmp_path) -> LocalKnowledgeStore:
    store = LocalKnowledgeStore(tmp_path / "knowledge.sqlite3")
    store.initialize()
    return store


def _service(tmp_path, store: LocalKnowledgeStore) -> RagAdvisoryService:
    return RagAdvisoryService(
        store=store,
        retriever=RagP0BHybridRetriever(
            store=store,
            dense_index=LocalDenseIndex(tmp_path / "knowledge_vectors.sqlite3"),
            embedding_backend=DeterministicTokenEmbeddingBackend(),
            reranker_backend=TokenOverlapReranker(),
        ),
    )


def _conflicting_item(
    knowledge_id: str, source_version: str
) -> tuple[KnowledgeItem, KnowledgeChunk]:
    now = datetime.now(timezone.utc)
    item = KnowledgeItem(
        knowledge_id=knowledge_id,
        source_type=KnowledgeSourceType.PROJECT_POLICY,
        source_title=f"Conflicting fixture {knowledge_id}",
        source_version=source_version,
        authority_level=5,
        effective_from=now - timedelta(days=1),
        review_due_at=now + timedelta(days=7),
        lifecycle_status=KnowledgeLifecycleStatus.REVIEWED_ACTIVE,
        provider="fixture_provider",
        operation="FixtureOperation",
        region="local_demo",
        adapter_status="implemented",
        smoke_status="fixture_only",
        content_sha256=("a" if knowledge_id.endswith("a") else "b") * 64,
        conflict_group_id="fixture_conflict_group",
    )
    chunk = KnowledgeChunk(
        chunk_id=f"{knowledge_id}_chunk",
        knowledge_id=knowledge_id,
        heading_path=["fixture", "conflict"],
        claim_type=KnowledgeClaimType.CAPABILITY,
        capability_status=KnowledgeCapabilityStatus.EXECUTABLE,
        content=f"{knowledge_id} carries a deliberately conflicting capability assertion.",
        keywords=["FixtureOperation", "fixture", knowledge_id],
        feature_codes=[EditableFeature.FACE_LIFTING],
        applicable_stages=[RagStage.PLAN_EDIT],
        content_sha256=("c" if knowledge_id.endswith("a") else "d") * 64,
    )
    return item, chunk


def test_rag_g01_direct_evidence_can_inform_a_plan_but_never_authorize_execution(tmp_path) -> None:
    store = _store(tmp_path)
    seed_reviewed_provider_knowledge(store)
    run = _service(tmp_path, store).advise(
        query=build_plan_edit_query(
            query_id="rag_g01_face_lifting",
            requested_features=[EditableFeature.FACE_LIFTING],
            allowed_features=[EditableFeature.FACE_LIFTING],
        ),
        existing_baseline_available=True,
        advice_id="rag_advice_g01",
    )

    assert run.decision.advisory_route == RagAdvisoryRoute.ADVISORY_AVAILABLE
    assert run.decision.execution_authorized is False
    assert run.decision.direct_evidence_refs == [
        "tencent-beautify-pic-2019-12-13#beautify_face_lifting@reviewed_2026-08-27"
    ]
    assert run.decision.bad_case_ref is None
    assert store.snapshot()["advisory_runs"] == 1
    assert store.snapshot()["rag_bad_cases"] == 0
    assert run.trace[-1]["external_calls"] == 0

    target = make_observation("photo_target", role=PhotoRole.TARGET, face_width=540)
    plan_result = diagnose_and_plan(
        profile=make_profile(),
        target_observation=target,
        quality_result=make_target_quality(target),
        intent=make_intent(),
        rag_advice=run.decision,
        plan_id="plan_rag_g01",
    )
    assert plan_result.plan is not None
    assert plan_result.plan.knowledge_refs == run.decision.direct_evidence_refs
    assert plan_result.plan.requires_confirmation is True
    assert any(item["step"] == "rag_advisory_preflight" for item in plan_result.trace)


def test_rag_g09_conflict_returns_both_sources_and_blocks_all_execution_paths(tmp_path) -> None:
    store = _store(tmp_path)
    for knowledge_id, source_version in (
        ("conflict_a", "fixture_v1"),
        ("conflict_b", "fixture_v2"),
    ):
        item, chunk = _conflicting_item(knowledge_id, source_version)
        store.replace_item(item, [chunk])
    query = RagQuery(
        query_id="rag_g09_conflict",
        stage=RagStage.PLAN_EDIT,
        requested_features=[EditableFeature.FACE_LIFTING],
        allowed_features=[EditableFeature.FACE_LIFTING],
        provider_candidates=["fixture_provider"],
        operation_candidates=["FixtureOperation"],
        outbound_allowed=True,
        adapter_required=True,
    )

    run = _service(tmp_path, store).advise(
        query=query,
        existing_baseline_available=True,
        advice_id="rag_advice_g09",
    )

    assert run.decision.advisory_route == RagAdvisoryRoute.CONFLICT_BLOCKED
    assert run.decision.execution_authorized is False
    assert run.decision.existing_baseline_may_continue is False
    assert run.decision.non_execution_next_steps == [
        "manual_review",
        "manual_suggestion",
        "stop",
    ]
    assert set(run.decision.conflict_information_refs) == {
        "conflict_a#conflict_a_chunk@fixture_v1",
        "conflict_b#conflict_b_chunk@fixture_v2",
    }
    assert run.bad_case is not None
    assert run.bad_case.diagnosis == RagBadCaseDiagnosis.HARD_FACT_CONFLICT


def test_retriever_miss_stops_the_new_rag_branch_and_records_a_diagnosis(tmp_path) -> None:
    store = _store(tmp_path)
    seed_reviewed_provider_knowledge(store)
    query = RagQuery(
        query_id="rag_miss_unknown",
        stage=RagStage.PLAN_EDIT,
        requested_features=[EditableFeature.LIPS_THICKNESS],
        allowed_features=[EditableFeature.LIPS_THICKNESS],
        provider_candidates=["not_reviewed_provider"],
        operation_candidates=["UnknownOperation"],
    )

    run = _service(tmp_path, store).advise(
        query=query,
        existing_baseline_available=False,
        advice_id="rag_advice_miss_unknown",
    )

    assert run.decision.advisory_route == RagAdvisoryRoute.UNKNOWN_STOPPED
    assert run.decision.execution_authorized is False
    assert run.bad_case is not None
    assert run.bad_case.diagnosis == RagBadCaseDiagnosis.NO_ACTIVE_KNOWLEDGE
    assert store.recent_bad_cases(limit=1)[0]["diagnosis"] == "no_active_knowledge"


def test_retriever_miss_can_only_retain_an_independently_configured_baseline(tmp_path) -> None:
    store = _store(tmp_path)
    seed_reviewed_provider_knowledge(store)
    query = RagQuery(
        query_id="rag_miss_baseline",
        stage=RagStage.VERIFICATION_STRATEGY,
        provider_candidates=["not_reviewed_provider"],
        operation_candidates=["UnknownOperation"],
    )

    run = _service(tmp_path, store).advise(
        query=query,
        existing_baseline_available=True,
        advice_id="rag_advice_miss_baseline",
    )

    assert run.decision.advisory_route == RagAdvisoryRoute.BASELINE_DEGRADED
    assert run.decision.existing_baseline_may_continue is True
    assert run.decision.execution_authorized is False
    assert "use_existing_baseline" in run.decision.non_execution_next_steps
    assert run.bad_case is not None


def test_rag_governance_dashboard_snapshot_aggregates_only_safe_operational_facts(tmp_path) -> None:
    """The Dashboard must expose governance counts, never source body/user inputs."""

    store = _store(tmp_path)
    seed_reviewed_provider_knowledge(store)
    query = RagQuery(
        query_id="rag_dashboard_unknown",
        stage=RagStage.PLAN_EDIT,
        requested_features=[EditableFeature.LIPS_THICKNESS],
        allowed_features=[EditableFeature.LIPS_THICKNESS],
        provider_candidates=["not_reviewed_provider"],
        operation_candidates=["UnknownOperation"],
    )
    _service(tmp_path, store).advise(
        query=query,
        existing_baseline_available=False,
        advice_id="rag_dashboard_unknown_advice",
    )

    snapshot = store.rag_dashboard_snapshot()
    assert snapshot["knowledge_items"] == 3
    assert snapshot["knowledge_chunks"] == 10
    assert snapshot["query_runs"] == 1
    assert snapshot["advisory_runs"] == 1
    assert snapshot["rag_bad_cases"] == 1
    assert snapshot["retrieval_routes"] == {"baseline_fallback": 1}
    assert snapshot["advisory_routes"] == {"unknown_stopped": 1}
    assert snapshot["bad_case_diagnoses"] == {"no_active_knowledge": 1}
    assert snapshot["query_stages"] == {"plan_edit": 1}
    assert snapshot["advisory_stages"] == {"plan_edit": 1}

    catalog = store.knowledge_catalog()
    assert len(catalog) == 3
    assert set(catalog[0]) == {
        "knowledge_id",
        "status",
        "provider",
        "operation",
        "region",
        "version",
        "authority_level",
        "effective_from",
        "review_due_at",
        "expires_at",
        "chunk_count",
    }
    assert "content" not in str(catalog)
    assert "raw_text" not in str(snapshot)
