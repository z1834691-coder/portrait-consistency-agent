"""Run the non-mutating RAG knowledge lifecycle audit."""

from __future__ import annotations

import argparse
from pathlib import Path

from portrait_consistency_agent.core.settings import AppSettings
from portrait_consistency_agent.services.rag_lifecycle import (
    audit_rag_lifecycle,
    write_lifecycle_audit_report,
)
from portrait_consistency_agent.services.rag_p0a import seed_reviewed_provider_knowledge
from portrait_consistency_agent.storage.dense_index import LocalDenseIndex
from portrait_consistency_agent.storage.knowledge_store import LocalKnowledgeStore

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--vectors", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "reports/rag_lifecycle_audit.json",
    )
    parser.add_argument(
        "--html",
        type=Path,
        default=PROJECT_ROOT / "reports/rag_lifecycle_audit.html",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Generate an artifact without recording the audit in the local ledger.",
    )
    args = parser.parse_args()

    settings = AppSettings()
    database = args.database or PROJECT_ROOT / settings.knowledge_database_path
    vectors = args.vectors or PROJECT_ROOT / settings.rag_vector_database_path
    store = LocalKnowledgeStore(database)
    seed = seed_reviewed_provider_knowledge(store)
    run = audit_rag_lifecycle(
        store,
        dense_index=LocalDenseIndex(vectors),
        persist=not args.no_persist,
    )
    write_lifecycle_audit_report(run, json_path=args.output, html_path=args.html)
    print(
        {
            "status": "complete",
            "audit_id": run.audit.audit_id,
            "knowledge_items": run.audit.knowledge_item_count,
            "active_items": run.audit.active_item_count,
            "active_chunks": run.audit.active_chunk_count,
            "issue_counts": run.audit.issue_counts,
            "index_status": run.audit.index.status.value,
            "seed_items_written": seed.items_written,
            "persisted": not args.no_persist,
            "output": str(args.output),
            "html": str(args.html),
        }
    )


if __name__ == "__main__":
    main()
