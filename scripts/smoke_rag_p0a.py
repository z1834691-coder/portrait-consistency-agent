#!/usr/bin/env python3
"""Run the real local RAG P0-A retrieval path without any network call.

It imports the repository's reviewed Provider Cards into a temporary SQLite
knowledge database, runs structured (not raw user text) queries, and prints
the exact safe Trace/retrieval outcome.  It never reads a photo, a .env file,
or calls an LLM/Tencent API.
"""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from portrait_consistency_agent.core.contracts import EditableFeature
from portrait_consistency_agent.services.rag_p0a import (
    RagP0ARetriever,
    build_plan_edit_query,
    seed_reviewed_provider_knowledge,
)
from portrait_consistency_agent.storage.knowledge_store import LocalKnowledgeStore


def _run_case(retriever: RagP0ARetriever, *, name: str, query) -> dict[str, object]:
    run = retriever.retrieve(query)
    return {
        "case": name,
        "route": run.result.route.value,
        "reason_codes": run.result.reason_codes,
        "knowledge_refs": run.result.knowledge_refs,
        "user_evidence_cards": run.result.user_evidence_cards(),
        "metadata_candidate_count": run.metadata_candidate_count,
        "fts_candidate_count": run.fts_candidate_count,
        "rejected_candidate_counts": run.rejected_candidate_counts,
        "trace": list(run.trace),
    }


def main() -> None:
    with TemporaryDirectory(prefix="portrait_rag_p0a_") as directory:
        store = LocalKnowledgeStore(Path(directory) / "knowledge.sqlite3")
        seed = seed_reviewed_provider_knowledge(store)
        retriever = RagP0ARetriever(store)
        cases = [
            _run_case(
                retriever,
                name="active_face_lifting",
                query=build_plan_edit_query(
                    query_id="smoke_rag_face_lifting",
                    requested_features=[EditableFeature.FACE_LIFTING],
                    allowed_features=[EditableFeature.FACE_LIFTING],
                ),
            ),
            _run_case(
                retriever,
                name="unsupported_lips_thickness",
                query=build_plan_edit_query(
                    query_id="smoke_rag_lips_thickness",
                    requested_features=[EditableFeature.LIPS_THICKNESS],
                    allowed_features=[EditableFeature.LIPS_THICKNESS],
                ),
            ),
            _run_case(
                retriever,
                name="outbound_not_allowed",
                query=build_plan_edit_query(
                    query_id="smoke_rag_outbound_denied",
                    requested_features=[EditableFeature.FACE_LIFTING],
                    allowed_features=[EditableFeature.FACE_LIFTING],
                    outbound_allowed=False,
                ),
            ),
            _run_case(
                retriever,
                name="missing_critical_slot",
                query=build_plan_edit_query(
                    query_id="smoke_rag_missing_slot",
                    requested_features=[EditableFeature.EYE_ENLARGING],
                    allowed_features=[],
                    missing_critical_slots=["allowed_features"],
                ),
            ),
        ]
        output = {
            "smoke_type": "real_local_sqlite_fts_p0a",
            "network_called": False,
            "photo_or_raw_user_text_read": False,
            "llm_called": False,
            "provider_api_called": False,
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
