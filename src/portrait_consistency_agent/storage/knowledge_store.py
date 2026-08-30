"""Local SQLite authority store for the governed RAG P0-A knowledge base.

The store is deliberately separate from user-operation storage.  It contains
only reviewed Provider/Policy knowledge and safe retrieval audit facts; it
never accepts photos, Base64 payloads, face vectors, user raw text, or secrets.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from portrait_consistency_agent.core.rag_contracts import (
    KnowledgeChunk,
    KnowledgeItem,
    KnowledgeLifecycleStatus,
    RagAdvisoryDecision,
    RagBadCaseRecord,
    RagQuery,
    RagRetrievalResult,
    RagStage,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LocalKnowledgeStore:
    """SQLite source-of-truth for P0-A items, chunks, FTS and query audits."""

    INDEX_VERSION = "sqlite-fts5-rag-p0a-v1"

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS knowledge_items (
                    knowledge_id TEXT PRIMARY KEY,
                    lifecycle_status TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    region TEXT NOT NULL,
                    source_version TEXT NOT NULL,
                    authority_level INTEGER NOT NULL,
                    effective_from TEXT NOT NULL,
                    expires_at TEXT,
                    review_due_at TEXT NOT NULL,
                    conflict_group_id TEXT,
                    item_payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    knowledge_id TEXT NOT NULL,
                    claim_type TEXT NOT NULL,
                    capability_status TEXT NOT NULL,
                    applicable_stages_json TEXT NOT NULL,
                    feature_codes_json TEXT NOT NULL,
                    heading_path_json TEXT NOT NULL,
                    keywords_json TEXT NOT NULL,
                    content TEXT NOT NULL,
                    chunk_payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(knowledge_id)
                );

                CREATE INDEX IF NOT EXISTS knowledge_items_active_filter
                ON knowledge_items(lifecycle_status, provider, operation, region, expires_at);

                CREATE INDEX IF NOT EXISTS knowledge_chunks_knowledge_id
                ON knowledge_chunks(knowledge_id);

                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunks_fts
                USING fts5(
                    chunk_id UNINDEXED,
                    content,
                    keywords,
                    heading_path,
                    tokenize = 'unicode61'
                );

                CREATE TABLE IF NOT EXISTS knowledge_ingestion_events (
                    event_id TEXT PRIMARY KEY,
                    knowledge_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS rag_query_runs (
                    query_id TEXT PRIMARY KEY,
                    query_sha256 TEXT NOT NULL,
                    route TEXT NOT NULL,
                    query_payload_json TEXT NOT NULL,
                    result_payload_json TEXT NOT NULL,
                    trace_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS rag_advisory_runs (
                    advice_id TEXT PRIMARY KEY,
                    query_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    advisory_route TEXT NOT NULL,
                    decision_payload_json TEXT NOT NULL,
                    trace_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS rag_bad_cases (
                    bad_case_id TEXT PRIMARY KEY,
                    query_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    diagnosis TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            self._ensure_knowledge_item_columns(connection)

    def replace_item(self, item: KnowledgeItem, chunks: Iterable[KnowledgeChunk]) -> bool:
        """Atomically replace one source version and its deterministic chunks."""

        chunk_list = list(chunks)
        if not chunk_list:
            raise ValueError("a KnowledgeItem must have at least one KnowledgeChunk")
        if any(chunk.knowledge_id != item.knowledge_id for chunk in chunk_list):
            raise ValueError("every chunk must belong to the supplied KnowledgeItem")
        if len({chunk.chunk_id for chunk in chunk_list}) != len(chunk_list):
            raise ValueError("chunk IDs must be unique within a KnowledgeItem")

        item_payload = item.model_dump(mode="json")
        expected_item_payload = json.dumps(item_payload, ensure_ascii=False, sort_keys=True)
        expected_chunk_payloads = {
            chunk.chunk_id: json.dumps(
                chunk.model_dump(mode="json"), ensure_ascii=False, sort_keys=True
            )
            for chunk in chunk_list
        }
        with self._connect() as connection:
            existing_item = connection.execute(
                "SELECT item_payload_json FROM knowledge_items WHERE knowledge_id = ?",
                (item.knowledge_id,),
            ).fetchone()
            existing_chunk_ids = connection.execute(
                "SELECT chunk_id FROM knowledge_chunks WHERE knowledge_id = ?",
                (item.knowledge_id,),
            ).fetchall()
            existing_chunks = connection.execute(
                "SELECT chunk_id, chunk_payload_json FROM knowledge_chunks WHERE knowledge_id = ?",
                (item.knowledge_id,),
            ).fetchall()
            if (
                existing_item is not None
                and existing_item["item_payload_json"] == expected_item_payload
                and {row["chunk_id"]: row["chunk_payload_json"] for row in existing_chunks}
                == expected_chunk_payloads
            ):
                return False
            for row in existing_chunk_ids:
                connection.execute(
                    "DELETE FROM knowledge_chunks_fts WHERE chunk_id = ?", (row["chunk_id"],)
                )
            connection.execute(
                "DELETE FROM knowledge_chunks WHERE knowledge_id = ?", (item.knowledge_id,)
            )
            connection.execute(
                """
                INSERT INTO knowledge_items (
                    knowledge_id, lifecycle_status, provider, operation, region,
                    source_version, authority_level, effective_from, expires_at, review_due_at,
                    conflict_group_id, item_payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(knowledge_id) DO UPDATE SET
                    lifecycle_status = excluded.lifecycle_status,
                    provider = excluded.provider,
                    operation = excluded.operation,
                    region = excluded.region,
                    source_version = excluded.source_version,
                    authority_level = excluded.authority_level,
                    effective_from = excluded.effective_from,
                    expires_at = excluded.expires_at,
                    review_due_at = excluded.review_due_at,
                    conflict_group_id = excluded.conflict_group_id,
                    item_payload_json = excluded.item_payload_json,
                    created_at = excluded.created_at
                """,
                (
                    item.knowledge_id,
                    item.lifecycle_status.value,
                    item.provider,
                    item.operation,
                    item.region,
                    item.source_version,
                    item.authority_level,
                    item.effective_from.isoformat(),
                    item.expires_at.isoformat() if item.expires_at is not None else None,
                    item.review_due_at.isoformat(),
                    item.conflict_group_id,
                    expected_item_payload,
                    item.created_at.isoformat(),
                ),
            )
            for chunk in chunk_list:
                payload = expected_chunk_payloads[chunk.chunk_id]
                connection.execute(
                    """
                    INSERT INTO knowledge_chunks (
                        chunk_id, knowledge_id, claim_type, capability_status,
                        applicable_stages_json, feature_codes_json, heading_path_json,
                        keywords_json, content, chunk_payload_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.chunk_id,
                        chunk.knowledge_id,
                        chunk.claim_type.value,
                        chunk.capability_status.value,
                        json.dumps([stage.value for stage in chunk.applicable_stages]),
                        json.dumps([feature.value for feature in chunk.feature_codes]),
                        json.dumps(chunk.heading_path, ensure_ascii=False),
                        json.dumps(chunk.keywords, ensure_ascii=False),
                        chunk.content,
                        payload,
                        chunk.created_at.isoformat(),
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO knowledge_chunks_fts (chunk_id, content, keywords, heading_path)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        chunk.chunk_id,
                        chunk.content,
                        " ".join(chunk.keywords),
                        " > ".join(chunk.heading_path),
                    ),
                )
            self._record_ingestion_event(
                connection,
                knowledge_id=item.knowledge_id,
                event_type="knowledge_item_replaced",
                payload={
                    "source_version": item.source_version,
                    "lifecycle_status": item.lifecycle_status.value,
                    "chunk_count": len(chunk_list),
                    "index_version": self.INDEX_VERSION,
                },
            )
        return True

    def active_metadata_candidates(
        self,
        query: RagQuery,
        *,
        now: datetime | None = None,
    ) -> list[tuple[KnowledgeItem, KnowledgeChunk]]:
        """Return current, metadata-eligible chunks before full-text ranking."""

        now = now or utc_now()
        clauses = [
            "i.lifecycle_status = ?",
            "i.effective_from <= ?",
            "(i.expires_at IS NULL OR i.expires_at > ?)",
        ]
        values: list[Any] = [
            KnowledgeLifecycleStatus.REVIEWED_ACTIVE.value,
            now.isoformat(),
            now.isoformat(),
        ]
        if query.provider_candidates:
            placeholders = ", ".join("?" for _ in query.provider_candidates)
            clauses.append(f"i.provider IN ({placeholders})")
            values.extend(query.provider_candidates)
        if query.operation_candidates:
            placeholders = ", ".join("?" for _ in query.operation_candidates)
            clauses.append(f"i.operation IN ({placeholders})")
            values.extend(query.operation_candidates)
        if query.region:
            clauses.append("i.region = ?")
            values.append(query.region)

        sql = f"""
            SELECT i.item_payload_json, c.chunk_payload_json
            FROM knowledge_chunks AS c
            JOIN knowledge_items AS i ON i.knowledge_id = c.knowledge_id
            WHERE {" AND ".join(clauses)}
            ORDER BY i.authority_level DESC, i.source_version DESC, c.chunk_id ASC
        """
        with self._connect() as connection:
            rows = connection.execute(sql, values).fetchall()
        return self._filter_stage(rows, query.stage)

    def active_index_documents(
        self,
        *,
        now: datetime | None = None,
    ) -> list[tuple[KnowledgeItem, KnowledgeChunk]]:
        """Return all current reviewed chunks for rebuilding a derived local vector index.

        This intentionally has no user query or user media input.  The caller
        must still re-apply query metadata filtering before dense retrieval;
        an index entry is never an execution authorization.
        """

        now = now or utc_now()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT i.item_payload_json, c.chunk_payload_json
                FROM knowledge_items AS i
                JOIN knowledge_chunks AS c ON c.knowledge_id = i.knowledge_id
                WHERE i.lifecycle_status = ?
                  AND i.effective_from <= ?
                  AND (i.expires_at IS NULL OR i.expires_at > ?)
                ORDER BY i.authority_level DESC, i.source_version DESC, c.chunk_id ASC
                """,
                (
                    KnowledgeLifecycleStatus.REVIEWED_ACTIVE.value,
                    now.isoformat(),
                    now.isoformat(),
                ),
            ).fetchall()
        return [
            (
                KnowledgeItem.model_validate(json.loads(row["item_payload_json"])),
                KnowledgeChunk.model_validate(json.loads(row["chunk_payload_json"])),
            )
            for row in rows
        ]

    def lifecycle_counts(
        self,
        query: RagQuery,
        *,
        now: datetime | None = None,
    ) -> dict[str, int]:
        """Count lifecycle outcomes before retrieval without exposing source text.

        This lets Trace distinguish ``NO_ACTIVE_KNOWLEDGE`` from the important
        case where a matching knowledge source was deliberately blocked because
        it expired, was withdrawn, or awaits conflict review.
        """

        now = now or utc_now()
        clauses = ["1 = 1"]
        values: list[Any] = []
        if query.provider_candidates:
            placeholders = ", ".join("?" for _ in query.provider_candidates)
            clauses.append(f"i.provider IN ({placeholders})")
            values.extend(query.provider_candidates)
        if query.operation_candidates:
            placeholders = ", ".join("?" for _ in query.operation_candidates)
            clauses.append(f"i.operation IN ({placeholders})")
            values.extend(query.operation_candidates)
        if query.region:
            clauses.append("i.region = ?")
            values.append(query.region)
        sql = f"""
            SELECT i.item_payload_json, c.chunk_payload_json
            FROM knowledge_items AS i
            JOIN knowledge_chunks AS c ON c.knowledge_id = i.knowledge_id
            WHERE {" AND ".join(clauses)}
        """
        with self._connect() as connection:
            rows = connection.execute(sql, values).fetchall()
        counts = {
            "active": 0,
            "expired_or_withdrawn": 0,
            "conflicted_pending_review": 0,
            "not_yet_effective": 0,
            "other_inactive": 0,
        }
        for row in rows:
            item = KnowledgeItem.model_validate(json.loads(row["item_payload_json"]))
            chunk = KnowledgeChunk.model_validate(json.loads(row["chunk_payload_json"]))
            if query.stage not in chunk.applicable_stages:
                continue
            if item.lifecycle_status == KnowledgeLifecycleStatus.CONFLICTED_PENDING_REVIEW:
                counts["conflicted_pending_review"] += 1
            elif item.lifecycle_status in {
                KnowledgeLifecycleStatus.EXPIRED,
                KnowledgeLifecycleStatus.WITHDRAWN,
                KnowledgeLifecycleStatus.SUPERSEDED,
            } or (item.expires_at is not None and item.expires_at <= now):
                counts["expired_or_withdrawn"] += 1
            elif item.effective_from > now:
                counts["not_yet_effective"] += 1
            elif item.lifecycle_status == KnowledgeLifecycleStatus.REVIEWED_ACTIVE:
                counts["active"] += 1
            else:
                counts["other_inactive"] += 1
        return counts

    def fts_candidates(
        self,
        query: RagQuery,
        *,
        fts_expression: str,
        limit: int,
        now: datetime | None = None,
    ) -> list[tuple[KnowledgeItem, KnowledgeChunk, float]]:
        """Search only metadata-eligible current chunks with SQLite FTS5."""

        if limit < 1:
            raise ValueError("FTS limit must be positive")
        now = now or utc_now()
        clauses = [
            "knowledge_chunks_fts MATCH ?",
            "i.lifecycle_status = ?",
            "i.effective_from <= ?",
            "(i.expires_at IS NULL OR i.expires_at > ?)",
        ]
        values: list[Any] = [
            fts_expression,
            KnowledgeLifecycleStatus.REVIEWED_ACTIVE.value,
            now.isoformat(),
            now.isoformat(),
        ]
        if query.provider_candidates:
            placeholders = ", ".join("?" for _ in query.provider_candidates)
            clauses.append(f"i.provider IN ({placeholders})")
            values.extend(query.provider_candidates)
        if query.operation_candidates:
            placeholders = ", ".join("?" for _ in query.operation_candidates)
            clauses.append(f"i.operation IN ({placeholders})")
            values.extend(query.operation_candidates)
        if query.region:
            clauses.append("i.region = ?")
            values.append(query.region)
        values.append(limit)
        sql = f"""
            SELECT i.item_payload_json, c.chunk_payload_json,
                   bm25(knowledge_chunks_fts) AS fts_score
            FROM knowledge_chunks_fts
            JOIN knowledge_chunks AS c ON c.chunk_id = knowledge_chunks_fts.chunk_id
            JOIN knowledge_items AS i ON i.knowledge_id = c.knowledge_id
            WHERE {" AND ".join(clauses)}
            ORDER BY fts_score ASC, i.authority_level DESC, c.chunk_id ASC
            LIMIT ?
        """
        with self._connect() as connection:
            rows = connection.execute(sql, values).fetchall()
        results: list[tuple[KnowledgeItem, KnowledgeChunk, float]] = []
        for row in rows:
            item = KnowledgeItem.model_validate(json.loads(row["item_payload_json"]))
            chunk = KnowledgeChunk.model_validate(json.loads(row["chunk_payload_json"]))
            if query.stage not in chunk.applicable_stages:
                continue
            results.append((item, chunk, float(row["fts_score"])))
        return results

    def active_conflict_groups(
        self,
        query: RagQuery,
        *,
        now: datetime | None = None,
    ) -> dict[str, list[KnowledgeItem]]:
        """Return relevant active/pending conflict groups for safe blocking.

        A hard fact that has already been marked ``conflicted_pending_review``
        must block a matching task rather than silently disappearing merely
        because it is no longer eligible for normal retrieval.
        """

        now = now or utc_now()
        clauses = [
            "i.lifecycle_status IN (?, ?)",
            "i.effective_from <= ?",
            "(i.expires_at IS NULL OR i.expires_at > ?)",
            "i.conflict_group_id IS NOT NULL",
        ]
        values: list[Any] = [
            KnowledgeLifecycleStatus.REVIEWED_ACTIVE.value,
            KnowledgeLifecycleStatus.CONFLICTED_PENDING_REVIEW.value,
            now.isoformat(),
            now.isoformat(),
        ]
        if query.provider_candidates:
            placeholders = ", ".join("?" for _ in query.provider_candidates)
            clauses.append(f"i.provider IN ({placeholders})")
            values.extend(query.provider_candidates)
        if query.operation_candidates:
            placeholders = ", ".join("?" for _ in query.operation_candidates)
            clauses.append(f"i.operation IN ({placeholders})")
            values.extend(query.operation_candidates)
        if query.region:
            clauses.append("i.region = ?")
            values.append(query.region)

        sql = f"""
            SELECT i.item_payload_json
            FROM knowledge_items AS i
            WHERE {" AND ".join(clauses)}
            ORDER BY i.authority_level DESC, i.source_version DESC, i.knowledge_id ASC
        """
        with self._connect() as connection:
            rows = connection.execute(sql, values).fetchall()

        grouped: dict[str, dict[str, KnowledgeItem]] = {}
        for row in rows:
            item = KnowledgeItem.model_validate(json.loads(row["item_payload_json"]))
            if item.conflict_group_id is None:
                continue
            grouped.setdefault(item.conflict_group_id, {})[item.knowledge_id] = item
        return {
            group_id: list(items.values()) for group_id, items in grouped.items() if len(items) >= 2
        }

    def record_query_run(
        self,
        *,
        query: RagQuery,
        result: RagRetrievalResult,
        trace: list[dict[str, object]],
    ) -> None:
        """Persist a structured, raw-text-free retrieval audit record."""

        if result.query_id != query.query_id:
            raise ValueError("query/result IDs must match")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO rag_query_runs (
                    query_id, query_sha256, route, query_payload_json,
                    result_payload_json, trace_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(query_id) DO UPDATE SET
                    query_sha256 = excluded.query_sha256,
                    route = excluded.route,
                    query_payload_json = excluded.query_payload_json,
                    result_payload_json = excluded.result_payload_json,
                    trace_json = excluded.trace_json,
                    created_at = excluded.created_at
                """,
                (
                    query.query_id,
                    result.query_sha256,
                    result.route.value,
                    json.dumps(query.model_dump(mode="json"), ensure_ascii=False, sort_keys=True),
                    json.dumps(result.model_dump(mode="json"), ensure_ascii=False, sort_keys=True),
                    json.dumps(trace, ensure_ascii=False, sort_keys=True),
                    utc_now().isoformat(),
                ),
            )

    def record_advisory_run(
        self,
        *,
        decision: RagAdvisoryDecision,
        trace: list[dict[str, object]],
    ) -> None:
        """Persist a redacted consumer decision without user media or raw text."""

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO rag_advisory_runs (
                    advice_id, query_id, stage, advisory_route,
                    decision_payload_json, trace_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(advice_id) DO UPDATE SET
                    query_id = excluded.query_id,
                    stage = excluded.stage,
                    advisory_route = excluded.advisory_route,
                    decision_payload_json = excluded.decision_payload_json,
                    trace_json = excluded.trace_json,
                    created_at = excluded.created_at
                """,
                (
                    decision.advice_id,
                    decision.query_id,
                    decision.stage.value,
                    decision.advisory_route.value,
                    json.dumps(
                        decision.model_dump(mode="json"), ensure_ascii=False, sort_keys=True
                    ),
                    json.dumps(trace, ensure_ascii=False, sort_keys=True),
                    utc_now().isoformat(),
                ),
            )

    def record_bad_case(self, record: RagBadCaseRecord) -> None:
        """Persist the safe reason a RAG-dependent path did not continue."""

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO rag_bad_cases (
                    bad_case_id, query_id, stage, diagnosis, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(bad_case_id) DO UPDATE SET
                    query_id = excluded.query_id,
                    stage = excluded.stage,
                    diagnosis = excluded.diagnosis,
                    payload_json = excluded.payload_json,
                    created_at = excluded.created_at
                """,
                (
                    record.bad_case_id,
                    record.query_id,
                    record.stage.value,
                    record.diagnosis.value,
                    json.dumps(record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True),
                    utc_now().isoformat(),
                ),
            )

    def chunks_for_knowledge_ids(
        self,
        knowledge_ids: Iterable[str],
    ) -> list[tuple[KnowledgeItem, KnowledgeChunk]]:
        """Return stored chunks for a bounded set of source IDs.

        Conflict traces need the real source/chunk references even though those
        pending items are intentionally excluded from normal active retrieval.
        """

        ids = list(knowledge_ids)
        if not ids:
            return []
        placeholders = ", ".join("?" for _ in ids)
        sql = f"""
            SELECT i.item_payload_json, c.chunk_payload_json
            FROM knowledge_items AS i
            JOIN knowledge_chunks AS c ON c.knowledge_id = i.knowledge_id
            WHERE i.knowledge_id IN ({placeholders})
            ORDER BY i.knowledge_id ASC, c.chunk_id ASC
        """
        with self._connect() as connection:
            rows = connection.execute(sql, ids).fetchall()
        return [
            (
                KnowledgeItem.model_validate(json.loads(row["item_payload_json"])),
                KnowledgeChunk.model_validate(json.loads(row["chunk_payload_json"])),
            )
            for row in rows
        ]

    def snapshot(self) -> dict[str, int]:
        """Return non-sensitive knowledge-base counters for the local demo page."""

        with self._connect() as connection:
            item_count = connection.execute(
                "SELECT COUNT(*) AS count FROM knowledge_items"
            ).fetchone()
            chunk_count = connection.execute(
                "SELECT COUNT(*) AS count FROM knowledge_chunks"
            ).fetchone()
            active_count = connection.execute(
                "SELECT COUNT(*) AS count FROM knowledge_items WHERE lifecycle_status = ?",
                (KnowledgeLifecycleStatus.REVIEWED_ACTIVE.value,),
            ).fetchone()
            query_count = connection.execute(
                "SELECT COUNT(*) AS count FROM rag_query_runs"
            ).fetchone()
            advisory_count = connection.execute(
                "SELECT COUNT(*) AS count FROM rag_advisory_runs"
            ).fetchone()
            bad_case_count = connection.execute(
                "SELECT COUNT(*) AS count FROM rag_bad_cases"
            ).fetchone()
        return {
            "knowledge_items": int(item_count["count"]),
            "knowledge_chunks": int(chunk_count["count"]),
            "active_items": int(active_count["count"]),
            "query_runs": int(query_count["count"]),
            "advisory_runs": int(advisory_count["count"]),
            "rag_bad_cases": int(bad_case_count["count"]),
        }

    def rag_dashboard_snapshot(self, *, now: datetime | None = None) -> dict[str, object]:
        """Aggregate safe RAG-governance facts for the local administrator UI.

        This deliberately works only from the RAG authority store.  It never
        returns source body text, a raw user sentence, photos, vectors, secrets
        or a provider request/response.  It is observability, not an automated
        evaluation report: Gold/holdout metrics are added only after their own
        reviewed evaluation checkpoint exists.
        """

        self.initialize()
        now = now or utc_now()
        with self._connect() as connection:
            lifecycle_rows = connection.execute(
                """
                SELECT lifecycle_status, COUNT(*) AS count
                FROM knowledge_items
                GROUP BY lifecycle_status
                ORDER BY lifecycle_status ASC
                """
            ).fetchall()
            review_rows = connection.execute(
                """
                SELECT review_due_at
                FROM knowledge_items
                WHERE lifecycle_status = ?
                """,
                (KnowledgeLifecycleStatus.REVIEWED_ACTIVE.value,),
            ).fetchall()
            route_rows = connection.execute(
                """
                SELECT route, COUNT(*) AS count
                FROM rag_query_runs
                GROUP BY route
                ORDER BY route ASC
                """
            ).fetchall()
            advisory_rows = connection.execute(
                """
                SELECT advisory_route, COUNT(*) AS count
                FROM rag_advisory_runs
                GROUP BY advisory_route
                ORDER BY advisory_route ASC
                """
            ).fetchall()
            bad_case_rows = connection.execute(
                """
                SELECT diagnosis, COUNT(*) AS count
                FROM rag_bad_cases
                GROUP BY diagnosis
                ORDER BY diagnosis ASC
                """
            ).fetchall()
            query_stage_rows = connection.execute(
                "SELECT query_payload_json FROM rag_query_runs"
            ).fetchall()
            advisory_stage_rows = connection.execute(
                "SELECT stage FROM rag_advisory_runs"
            ).fetchall()
            latest_query_row = connection.execute(
                "SELECT MAX(created_at) AS latest_at FROM rag_query_runs"
            ).fetchone()
            latest_advice_row = connection.execute(
                "SELECT MAX(created_at) AS latest_at FROM rag_advisory_runs"
            ).fetchone()

        query_stages: dict[str, int] = {}
        for row in query_stage_rows:
            payload = json.loads(row["query_payload_json"])
            stage = str(payload.get("stage", "unknown"))
            query_stages[stage] = query_stages.get(stage, 0) + 1
        advisory_stages: dict[str, int] = {}
        for row in advisory_stage_rows:
            stage = str(row["stage"])
            advisory_stages[stage] = advisory_stages.get(stage, 0) + 1

        review_due = [datetime.fromisoformat(str(row["review_due_at"])) for row in review_rows]
        due_within_14_days = sum(
            1 for due_at in review_due if now <= due_at <= now + timedelta(days=14)
        )
        overdue = sum(1 for due_at in review_due if due_at < now)
        snapshot: dict[str, object] = self.snapshot()
        snapshot.update(
            {
                "knowledge_lifecycle": {
                    str(row["lifecycle_status"]): int(row["count"]) for row in lifecycle_rows
                },
                "retrieval_routes": {str(row["route"]): int(row["count"]) for row in route_rows},
                "advisory_routes": {
                    str(row["advisory_route"]): int(row["count"]) for row in advisory_rows
                },
                "bad_case_diagnoses": {
                    str(row["diagnosis"]): int(row["count"]) for row in bad_case_rows
                },
                "query_stages": query_stages,
                "advisory_stages": advisory_stages,
                "review_due_within_14_days": due_within_14_days,
                "review_overdue": overdue,
                "latest_query_at": latest_query_row["latest_at"],
                "latest_advisory_at": latest_advice_row["latest_at"],
            }
        )
        return snapshot

    def knowledge_catalog(self, *, limit: int = 100) -> list[dict[str, object]]:
        """Return a source-level catalog without exposing the source body text."""

        if not 1 <= limit <= 500:
            raise ValueError("catalog limit must be between 1 and 500")
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT i.knowledge_id, i.lifecycle_status, i.provider, i.operation,
                       i.region, i.source_version, i.authority_level,
                       i.effective_from, i.review_due_at, i.expires_at,
                       COUNT(c.chunk_id) AS chunk_count
                FROM knowledge_items AS i
                LEFT JOIN knowledge_chunks AS c ON c.knowledge_id = i.knowledge_id
                GROUP BY i.knowledge_id
                ORDER BY i.authority_level DESC, i.provider ASC, i.operation ASC,
                         i.source_version DESC, i.knowledge_id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "knowledge_id": str(row["knowledge_id"]),
                "status": str(row["lifecycle_status"]),
                "provider": str(row["provider"]),
                "operation": str(row["operation"]),
                "region": str(row["region"]),
                "version": str(row["source_version"]),
                "authority_level": int(row["authority_level"]),
                "effective_from": str(row["effective_from"]),
                "review_due_at": str(row["review_due_at"]),
                "expires_at": row["expires_at"],
                "chunk_count": int(row["chunk_count"]),
            }
            for row in rows
        ]

    def recent_query_runs(self, *, limit: int = 20) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT query_id, query_sha256, route, result_payload_json, trace_json, created_at
                FROM rag_query_runs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "query_id": row["query_id"],
                "query_sha256": row["query_sha256"],
                "route": row["route"],
                "result": json.loads(row["result_payload_json"]),
                "trace": json.loads(row["trace_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def recent_advisory_runs(self, *, limit: int = 20) -> list[dict[str, object]]:
        """Return only safe RAG-consumer facts for an inspectable local UI."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT advice_id, query_id, stage, advisory_route,
                       decision_payload_json, trace_json, created_at
                FROM rag_advisory_runs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "advice_id": row["advice_id"],
                "query_id": row["query_id"],
                "stage": row["stage"],
                "advisory_route": row["advisory_route"],
                "decision": json.loads(row["decision_payload_json"]),
                "trace": json.loads(row["trace_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def recent_bad_cases(self, *, limit: int = 20) -> list[dict[str, object]]:
        """Return redacted retrieval failure records for bad-case triage."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT bad_case_id, query_id, stage, diagnosis, payload_json, created_at
                FROM rag_bad_cases
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "bad_case_id": row["bad_case_id"],
                "query_id": row["query_id"],
                "stage": row["stage"],
                "diagnosis": row["diagnosis"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    @staticmethod
    def _filter_stage(
        rows: Iterable[sqlite3.Row],
        stage: RagStage,
    ) -> list[tuple[KnowledgeItem, KnowledgeChunk]]:
        candidates: list[tuple[KnowledgeItem, KnowledgeChunk]] = []
        for row in rows:
            item = KnowledgeItem.model_validate(json.loads(row["item_payload_json"]))
            chunk = KnowledgeChunk.model_validate(json.loads(row["chunk_payload_json"]))
            if stage in chunk.applicable_stages:
                candidates.append((item, chunk))
        return candidates

    @staticmethod
    def _record_ingestion_event(
        connection: sqlite3.Connection,
        *,
        knowledge_id: str,
        event_type: str,
        payload: dict[str, object],
    ) -> None:
        event_id = f"knowledge_event_{knowledge_id}_{utc_now().timestamp():.6f}".replace(".", "_")
        connection.execute(
            """
            INSERT INTO knowledge_ingestion_events (
                event_id, knowledge_id, event_type, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                event_id,
                knowledge_id,
                event_type,
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                utc_now().isoformat(),
            ),
        )

    @staticmethod
    def _ensure_knowledge_item_columns(connection: sqlite3.Connection) -> None:
        """Apply the tiny additive migration needed by early local P0-A files."""

        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(knowledge_items)").fetchall()
        }
        if "authority_level" not in columns:
            connection.execute(
                "ALTER TABLE knowledge_items ADD COLUMN authority_level INTEGER NOT NULL DEFAULT 1"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
