"""Run the RAG advisory-only consumer smoke without reading any user media.

The script uses the same local-cache-only BGE adapters as the Streamlit page.
It prints only structured tool knowledge evidence, retrieval counts and
redacted routes.  It does not call an LLM, Tencent, or any other Provider.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from portrait_consistency_agent.core.contracts import EditableFeature
from portrait_consistency_agent.core.rag_contracts import (
    KnowledgeCapabilityStatus,
    KnowledgeChunk,
    KnowledgeClaimType,
    KnowledgeItem,
    KnowledgeLifecycleStatus,
    KnowledgeSourceType,
    RagQuery,
    RagStage,
)
from portrait_consistency_agent.core.settings import AppSettings
from portrait_consistency_agent.services.local_rag_models import (
    BgeEmbeddingBackend,
    BgeRerankerBackend,
)
from portrait_consistency_agent.services.rag_advisory import RagAdvisoryService
from portrait_consistency_agent.services.rag_p0a import (
    build_plan_edit_query,
    seed_reviewed_provider_knowledge,
)
from portrait_consistency_agent.services.rag_p0b import RagP0BHybridRetriever
from portrait_consistency_agent.storage.dense_index import LocalDenseIndex
from portrait_consistency_agent.storage.knowledge_store import LocalKnowledgeStore

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _conflict_pair(knowledge_id: str, version: str) -> tuple[KnowledgeItem, KnowledgeChunk]:
    now = datetime.now(timezone.utc)
    item = KnowledgeItem(
        knowledge_id=knowledge_id,
        source_type=KnowledgeSourceType.PROJECT_POLICY,
        source_title=f"Smoke conflict fixture {knowledge_id}",
        source_version=version,
        authority_level=5,
        effective_from=now - timedelta(days=1),
        review_due_at=now + timedelta(days=7),
        lifecycle_status=KnowledgeLifecycleStatus.REVIEWED_ACTIVE,
        provider="smoke_fixture_provider",
        operation="SmokeConflictOperation",
        region="local_demo",
        adapter_status="implemented",
        smoke_status="fixture_only",
        content_sha256=("a" if knowledge_id.endswith("a") else "b") * 64,
        conflict_group_id="smoke_conflict_group",
    )
    chunk = KnowledgeChunk(
        chunk_id=f"{knowledge_id}_chunk",
        knowledge_id=knowledge_id,
        heading_path=["smoke", "conflict"],
        claim_type=KnowledgeClaimType.CAPABILITY,
        capability_status=KnowledgeCapabilityStatus.EXECUTABLE,
        content="Controlled conflicting source for advisory-only routing smoke.",
        keywords=["SmokeConflictOperation", "conflict", knowledge_id],
        feature_codes=[EditableFeature.FACE_LIFTING],
        applicable_stages=[RagStage.PLAN_EDIT],
        content_sha256=("c" if knowledge_id.endswith("a") else "d") * 64,
    )
    return item, chunk


def _projection(run) -> dict[str, object]:
    decision = run.decision
    return {
        "advisory_route": decision.advisory_route.value,
        "retrieval_route": decision.retrieval_route.value,
        "direct_evidence_refs": decision.direct_evidence_refs,
        "reference_information_refs": decision.reference_information_refs,
        "conflict_information_refs": decision.conflict_information_refs,
        "execution_authorized": decision.execution_authorized,
        "existing_baseline_may_continue": decision.existing_baseline_may_continue,
        "bad_case": run.bad_case.diagnosis.value if run.bad_case is not None else None,
        "trace_last_step": run.trace[-1],
    }


def main() -> None:
    settings = AppSettings()
    with tempfile.TemporaryDirectory(prefix="portrait-rag-advisory-") as temporary:
        root = Path(temporary)
        store = LocalKnowledgeStore(root / "knowledge.sqlite3")
        store.initialize()
        seed_reviewed_provider_knowledge(store)
        service = RagAdvisoryService(
            store=store,
            retriever=RagP0BHybridRetriever(
                store=store,
                dense_index=LocalDenseIndex(root / "knowledge_vectors.sqlite3"),
                embedding_backend=BgeEmbeddingBackend(
                    model_id=settings.rag_embedding_model,
                    requested_revision=settings.rag_embedding_revision,
                    cache_path=PROJECT_ROOT / settings.rag_model_cache_path,
                    allow_model_download=False,
                ),
                reranker_backend=BgeRerankerBackend(
                    model_id=settings.rag_reranker_model,
                    requested_revision=settings.rag_reranker_revision,
                    cache_path=PROJECT_ROOT / settings.rag_model_cache_path,
                    allow_model_download=False,
                ),
            ),
        )
        g01 = service.advise(
            query=build_plan_edit_query(
                query_id="smoke_rag_g01",
                requested_features=[EditableFeature.FACE_LIFTING],
                allowed_features=[EditableFeature.FACE_LIFTING],
            ),
            existing_baseline_available=True,
            advice_id="smoke_advice_g01",
        )
        for knowledge_id, version in (
            ("smoke_conflict_a", "fixture_v1"),
            ("smoke_conflict_b", "fixture_v2"),
        ):
            item, chunk = _conflict_pair(knowledge_id, version)
            store.replace_item(item, [chunk])
        g09 = service.advise(
            query=RagQuery(
                query_id="smoke_rag_g09",
                stage=RagStage.PLAN_EDIT,
                requested_features=[EditableFeature.FACE_LIFTING],
                allowed_features=[EditableFeature.FACE_LIFTING],
                provider_candidates=["smoke_fixture_provider"],
                operation_candidates=["SmokeConflictOperation"],
                outbound_allowed=True,
                adapter_required=True,
            ),
            existing_baseline_available=True,
            advice_id="smoke_advice_g09",
        )
        miss = service.advise(
            query=RagQuery(
                query_id="smoke_rag_miss",
                stage=RagStage.PLAN_EDIT,
                requested_features=[EditableFeature.LIPS_THICKNESS],
                allowed_features=[EditableFeature.LIPS_THICKNESS],
                provider_candidates=["unknown_provider"],
                operation_candidates=["UnknownOperation"],
            ),
            existing_baseline_available=False,
            advice_id="smoke_advice_miss",
        )
        print(
            json.dumps(
                {
                    "smoke": "rag_advisory_v0.1",
                    "model_download_permitted": False,
                    "photo_or_raw_user_text_read": False,
                    "llm_called": False,
                    "provider_api_called": False,
                    "g01_direct_evidence": _projection(g01),
                    "g09_conflict": _projection(g09),
                    "retriever_miss": _projection(miss),
                    "knowledge_snapshot": store.snapshot(),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
