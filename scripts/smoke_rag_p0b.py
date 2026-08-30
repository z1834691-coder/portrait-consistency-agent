#!/usr/bin/env python3
"""Run the P0-B local hybrid RAG path against reviewed tool knowledge only.

The default is deliberately local-cache-only.  ``--allow-model-download`` is a
one-time, explicit provisioning action for the BGE weights; it does not send
photos, raw user utterances, face vectors, secrets, or any Tencent/LLM request.
Both modes use a temporary SQLite knowledge/vector index and print a redacted,
replayable retrieval Trace.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from portrait_consistency_agent.core.contracts import EditableFeature
from portrait_consistency_agent.core.settings import AppSettings
from portrait_consistency_agent.services.local_rag_models import (
    BgeEmbeddingBackend,
    BgeRerankerBackend,
)
from portrait_consistency_agent.services.rag_p0a import (
    build_plan_edit_query,
    seed_reviewed_provider_knowledge,
)
from portrait_consistency_agent.services.rag_p0b import RagP0BHybridRetriever
from portrait_consistency_agent.storage.dense_index import LocalDenseIndex
from portrait_consistency_agent.storage.knowledge_store import LocalKnowledgeStore


def _arguments() -> argparse.Namespace:
    settings = AppSettings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-model-download",
        action="store_true",
        help="Explicitly allow downloading public BGE model files into the ignored local cache.",
    )
    parser.add_argument(
        "--model-cache",
        type=Path,
        default=settings.rag_model_cache_path,
        help="Ignored local cache location for BGE model files.",
    )
    return parser.parse_args()


def _case(retriever: RagP0BHybridRetriever, *, name: str, query) -> dict[str, object]:
    run = retriever.retrieve(query)
    return {
        "case": name,
        "route": run.result.route.value,
        "reason_codes": run.result.reason_codes,
        "retrieval_latency_ms": run.result.latency_ms,
        "knowledge_refs": run.result.knowledge_refs,
        "user_evidence_cards": run.result.user_evidence_cards(),
        "metadata_candidate_count": run.metadata_candidate_count,
        "sparse_candidate_count": run.sparse_candidate_count,
        "dense_candidate_count": run.dense_candidate_count,
        "fused_candidate_count": run.fused_candidate_count,
        "dense_mode": run.dense_mode,
        "reranker_mode": run.reranker_mode,
        "rejected_candidate_counts": run.rejected_candidate_counts,
        "trace": list(run.trace),
    }


def main() -> None:
    args = _arguments()
    settings = AppSettings()
    embedding = BgeEmbeddingBackend(
        model_id=settings.rag_embedding_model,
        requested_revision=settings.rag_embedding_revision,
        cache_path=args.model_cache,
        allow_model_download=args.allow_model_download,
    )
    reranker = BgeRerankerBackend(
        model_id=settings.rag_reranker_model,
        requested_revision=settings.rag_reranker_revision,
        cache_path=args.model_cache,
        allow_model_download=args.allow_model_download,
    )
    with TemporaryDirectory(prefix="portrait_rag_p0b_") as directory:
        root = Path(directory)
        store = LocalKnowledgeStore(root / "knowledge.sqlite3")
        seed = seed_reviewed_provider_knowledge(store)
        retriever = RagP0BHybridRetriever(
            store=store,
            dense_index=LocalDenseIndex(root / "knowledge_vectors.sqlite3"),
            embedding_backend=embedding,
            reranker_backend=reranker,
        )
        cases = [
            _case(
                retriever,
                name="active_face_lifting",
                query=build_plan_edit_query(
                    query_id="smoke_rag_p0b_face_lifting",
                    requested_features=[EditableFeature.FACE_LIFTING],
                    allowed_features=[EditableFeature.FACE_LIFTING],
                ),
            ),
            _case(
                retriever,
                name="unsupported_lips_thickness",
                query=build_plan_edit_query(
                    query_id="smoke_rag_p0b_lips_thickness",
                    requested_features=[EditableFeature.LIPS_THICKNESS],
                    allowed_features=[EditableFeature.LIPS_THICKNESS],
                ),
            ),
            _case(
                retriever,
                name="outbound_not_allowed",
                query=build_plan_edit_query(
                    query_id="smoke_rag_p0b_outbound_denied",
                    requested_features=[EditableFeature.FACE_LIFTING],
                    allowed_features=[EditableFeature.FACE_LIFTING],
                    outbound_allowed=False,
                ),
            ),
            _case(
                retriever,
                name="missing_critical_slot",
                query=build_plan_edit_query(
                    query_id="smoke_rag_p0b_missing_slot",
                    requested_features=[EditableFeature.EYE_ENLARGING],
                    allowed_features=[],
                    missing_critical_slots=["allowed_features"],
                ),
            ),
        ]
        output = {
            "smoke_type": "local_hybrid_rag_p0b",
            "model_download_permitted": args.allow_model_download,
            "model_download_may_use_network": args.allow_model_download,
            "tool_or_provider_network_called": False,
            "photo_or_raw_user_text_read": False,
            "llm_called": False,
            "provider_api_called": False,
            "model_cache": str(args.model_cache),
            "models": {
                "embedding": {
                    "model_id": embedding.model_id,
                    "requested_revision": embedding.requested_revision,
                    "actual_revision": embedding.actual_revision,
                },
                "reranker": {
                    "model_id": reranker.model_id,
                    "requested_revision": reranker.requested_revision,
                    "actual_revision": reranker.actual_revision,
                },
            },
            "seed": {
                "items_seen": seed.items_seen,
                "items_written": seed.items_written,
                "chunks_written": seed.chunks_written,
                "knowledge_ids": list(seed.knowledge_ids),
            },
            "cases": cases,
            "snapshot": store.snapshot(),
        }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
