from __future__ import annotations

from datetime import datetime, timedelta, timezone

from portrait_consistency_agent.core.contracts import EditableFeature
from portrait_consistency_agent.core.rag_contracts import (
    KnowledgeCapabilityStatus,
    KnowledgeChunk,
    KnowledgeClaimType,
    KnowledgeItem,
    KnowledgeLifecycleStatus,
    KnowledgeSourceType,
    RagIndexStatus,
    RagLifecycleAction,
    RagLifecycleIssueCode,
    RagStage,
)
from portrait_consistency_agent.services.local_rag_models import (
    DeterministicTokenEmbeddingBackend,
    TokenOverlapReranker,
)
from portrait_consistency_agent.services.rag_lifecycle import (
    audit_rag_lifecycle,
    render_lifecycle_audit_html,
)
from portrait_consistency_agent.services.rag_p0a import (
    build_plan_edit_query,
    seed_reviewed_provider_knowledge,
)
from portrait_consistency_agent.services.rag_p0b import RagP0BHybridRetriever
from portrait_consistency_agent.storage.dense_index import LocalDenseIndex
from portrait_consistency_agent.storage.knowledge_store import LocalKnowledgeStore

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def _store(tmp_path) -> LocalKnowledgeStore:
    store = LocalKnowledgeStore(tmp_path / "knowledge.sqlite3")
    store.initialize()
    return store


def _item(
    knowledge_id: str,
    *,
    status: KnowledgeLifecycleStatus,
    effective_from: datetime,
    review_due_at: datetime,
    expires_at: datetime | None = None,
    source_uris: list[str] | None = None,
    conflict_group_id: str | None = None,
) -> tuple[KnowledgeItem, KnowledgeChunk]:
    item = KnowledgeItem(
        knowledge_id=knowledge_id,
        source_type=KnowledgeSourceType.PROJECT_POLICY,
        source_title=f"Lifecycle fixture {knowledge_id}",
        source_uris=source_uris or [],
        source_version="fixture-v1",
        authority_level=5,
        effective_from=effective_from,
        review_due_at=review_due_at,
        expires_at=expires_at,
        lifecycle_status=status,
        provider="fixture_provider",
        operation="FixtureOperation",
        region="local_demo",
        adapter_status="implemented",
        smoke_status="fixture_only",
        content_sha256=("a" * 64),
        conflict_group_id=conflict_group_id,
        created_at=effective_from,
    )
    chunk = KnowledgeChunk(
        chunk_id=f"{knowledge_id}_chunk",
        knowledge_id=knowledge_id,
        heading_path=["fixture", "lifecycle"],
        claim_type=KnowledgeClaimType.LIMITATION,
        capability_status=KnowledgeCapabilityStatus.SUGGESTION_ONLY,
        content=f"private fixture body for {knowledge_id}",
        keywords=["FixtureOperation", "lifecycle"],
        feature_codes=[EditableFeature.FACE_LIFTING],
        applicable_stages=[RagStage.PLAN_EDIT],
        content_sha256=("b" * 64),
        created_at=effective_from,
    )
    return item, chunk


def test_current_reviewed_knowledge_audit_is_clean_and_persisted(tmp_path) -> None:
    store = _store(tmp_path)
    seed_reviewed_provider_knowledge(store)

    run = audit_rag_lifecycle(
        store,
        dense_index=LocalDenseIndex(tmp_path / "knowledge_vectors.sqlite3"),
        now=NOW,
        audit_id="lifecycle_clean",
    )

    assert run.audit.knowledge_item_count == 3
    assert run.audit.active_item_count == 3
    assert run.audit.active_chunk_count == 10
    assert run.audit.issue_counts == {}
    assert all(
        item.recommended_action == RagLifecycleAction.KEEP_ACTIVE for item in run.audit.item_audits
    )
    assert run.audit.index.status == RagIndexStatus.NOT_BUILT
    assert store.recent_lifecycle_audits(limit=1)[0]["audit_id"] == "lifecycle_clean"
    persisted = str(store.recent_lifecycle_audits(limit=1)[0])
    assert "private fixture body" not in persisted


def test_lifecycle_audit_classifies_expired_candidate_conflict_and_future_items(tmp_path) -> None:
    store = _store(tmp_path)
    fixtures = [
        _item(
            "expired_item",
            status=KnowledgeLifecycleStatus.REVIEWED_ACTIVE,
            effective_from=NOW - timedelta(days=10),
            review_due_at=NOW - timedelta(days=2),
            expires_at=NOW - timedelta(minutes=1),
            source_uris=["https://example.test/expired"],
        ),
        _item(
            "candidate_item",
            status=KnowledgeLifecycleStatus.CANDIDATE,
            effective_from=NOW - timedelta(days=1),
            review_due_at=NOW + timedelta(days=2),
        ),
        _item(
            "conflict_item",
            status=KnowledgeLifecycleStatus.CONFLICTED_PENDING_REVIEW,
            effective_from=NOW - timedelta(days=1),
            review_due_at=NOW + timedelta(days=2),
            source_uris=["https://example.test/conflict"],
            conflict_group_id="fixture_conflict",
        ),
        _item(
            "future_item",
            status=KnowledgeLifecycleStatus.REVIEWED_ACTIVE,
            effective_from=NOW + timedelta(days=1),
            review_due_at=NOW + timedelta(days=2),
            source_uris=["https://example.test/future"],
        ),
    ]
    for item, chunk in fixtures:
        store.replace_item(item, [chunk])

    run = audit_rag_lifecycle(store, now=NOW, audit_id="lifecycle_findings")
    by_id = {item.knowledge_id: item for item in run.audit.item_audits}
    assert by_id["expired_item"].recommended_action == RagLifecycleAction.BLOCKED_FROM_RETRIEVAL
    assert RagLifecycleIssueCode.EXPIRED in by_id["expired_item"].issue_codes
    assert by_id["candidate_item"].recommended_action == RagLifecycleAction.HOLD_NOT_YET_EFFECTIVE
    assert RagLifecycleIssueCode.CANDIDATE_NOT_PUBLISHED in by_id["candidate_item"].issue_codes
    assert RagLifecycleIssueCode.MISSING_SOURCE_URI in by_id["candidate_item"].issue_codes
    assert by_id["conflict_item"].recommended_action == RagLifecycleAction.BLOCKED_FROM_RETRIEVAL
    assert RagLifecycleIssueCode.CONFLICT_PENDING_REVIEW in by_id["conflict_item"].issue_codes
    assert by_id["future_item"].recommended_action == RagLifecycleAction.HOLD_NOT_YET_EFFECTIVE
    assert RagLifecycleIssueCode.NOT_YET_EFFECTIVE in by_id["future_item"].issue_codes
    assert run.trace[1]["knowledge_status_mutated"] is False
    assert run.trace[-1]["external_calls"] == 0


def test_dense_index_audit_is_in_sync_after_p0b_build(tmp_path) -> None:
    store = _store(tmp_path)
    seed_reviewed_provider_knowledge(store)
    dense_index = LocalDenseIndex(tmp_path / "knowledge_vectors.sqlite3")
    RagP0BHybridRetriever(
        store=store,
        dense_index=dense_index,
        embedding_backend=DeterministicTokenEmbeddingBackend(),
        reranker_backend=TokenOverlapReranker(),
    ).retrieve(
        build_plan_edit_query(
            query_id="lifecycle_index_build",
            requested_features=[EditableFeature.FACE_LIFTING],
            allowed_features=[EditableFeature.FACE_LIFTING],
        )
    )

    run = audit_rag_lifecycle(store, dense_index=dense_index, now=NOW, audit_id="lifecycle_index")
    assert run.audit.index.status == RagIndexStatus.IN_SYNC
    assert run.audit.index.active_chunk_count == 10
    assert run.audit.index.manifest_document_count == 10
    assert run.audit.index.indexed_vector_count == 10


def test_lifecycle_report_is_visual_and_does_not_include_source_body(tmp_path) -> None:
    store = _store(tmp_path)
    item, chunk = _item(
        "report_fixture",
        status=KnowledgeLifecycleStatus.REVIEWED_ACTIVE,
        effective_from=NOW - timedelta(days=1),
        review_due_at=NOW + timedelta(days=1),
        source_uris=["https://example.test/report"],
    )
    store.replace_item(item, [chunk])
    run = audit_rag_lifecycle(store, now=NOW, persist=False, audit_id="lifecycle_html")

    html = render_lifecycle_audit_html(run)
    assert "RAG 知识生命周期审计" in html
    assert "report_fixture" in html
    assert chunk.content not in html
    assert "auto_status_change_allowed" in html
