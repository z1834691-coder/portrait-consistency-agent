"""Local, non-authoritative dense vector index for RAG P0-B.

SQLite remains the authority for reviewed knowledge.  This file stores only
derived normalized vectors and document hashes, so it can be rebuilt from the
authority store whenever a model or reviewed source changes.  It never stores
user media, raw user text, face vectors, secrets, or tool receipts.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from portrait_consistency_agent.services.local_rag_models import EmbeddingBackend


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class DenseIndexDocument:
    chunk_id: str
    knowledge_id: str
    document_sha256: str
    text: str


@dataclass(frozen=True)
class DenseIndexBuildSummary:
    index_key: str
    model_id: str
    requested_revision: str
    actual_revision: str
    dimension: int
    indexed_count: int
    reused_count: int
    removed_count: int
    index_version: str


@dataclass(frozen=True)
class DenseSearchHit:
    chunk_id: str
    score: float
    rank: int


class LocalDenseIndex:
    """SQLite persistence plus NumPy cosine search for a small local P0-B corpus."""

    INDEX_VERSION = "local-dense-cosine-v1"

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS dense_index_manifest (
                    index_key TEXT PRIMARY KEY,
                    model_id TEXT NOT NULL,
                    requested_revision TEXT NOT NULL,
                    actual_revision TEXT NOT NULL,
                    dimension INTEGER NOT NULL,
                    document_count INTEGER NOT NULL,
                    manifest_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS dense_index_vectors (
                    index_key TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    knowledge_id TEXT NOT NULL,
                    document_sha256 TEXT NOT NULL,
                    dimension INTEGER NOT NULL,
                    vector_blob BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (index_key, chunk_id)
                );

                CREATE INDEX IF NOT EXISTS dense_index_vectors_lookup
                ON dense_index_vectors(index_key, chunk_id);
                """
            )

    def build_or_update(
        self,
        *,
        backend: EmbeddingBackend,
        documents: Iterable[DenseIndexDocument],
    ) -> DenseIndexBuildSummary:
        """Build only changed vectors; source text remains in the authority store."""

        self.initialize()
        current = {document.chunk_id: document for document in documents}
        if not current:
            raise ValueError("dense index requires at least one reviewed knowledge document")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT chunk_id, document_sha256, dimension
                FROM dense_index_vectors
                WHERE index_key = ?
                """,
                (backend.index_key,),
            ).fetchall()
        existing = {str(row["chunk_id"]): row for row in rows}
        changed = [
            document
            for chunk_id, document in sorted(current.items())
            if chunk_id not in existing
            or str(existing[chunk_id]["document_sha256"]) != document.document_sha256
        ]
        removed = sorted(set(existing) - set(current))
        vectors = (
            backend.encode([document.text for document in changed]) if changed else np.empty((0, 0))
        )
        if changed and (vectors.ndim != 2 or vectors.shape[0] != len(changed)):
            raise ValueError("embedding backend returned an invalid matrix")
        dimension = int(vectors.shape[1]) if changed else int(rows[0]["dimension"])
        if dimension < 1:
            raise ValueError("dense embedding dimension must be positive")

        with self._connect() as connection:
            if removed:
                placeholders = ", ".join("?" for _ in removed)
                connection.execute(
                    "DELETE FROM dense_index_vectors "
                    f"WHERE index_key = ? AND chunk_id IN ({placeholders})",
                    [backend.index_key, *removed],
                )
            for document, vector in zip(changed, vectors, strict=True):
                normalized = self._normalized_vector(vector, dimension)
                connection.execute(
                    """
                    INSERT INTO dense_index_vectors (
                        index_key, chunk_id, knowledge_id, document_sha256,
                        dimension, vector_blob, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(index_key, chunk_id) DO UPDATE SET
                        knowledge_id = excluded.knowledge_id,
                        document_sha256 = excluded.document_sha256,
                        dimension = excluded.dimension,
                        vector_blob = excluded.vector_blob,
                        created_at = excluded.created_at
                    """,
                    (
                        backend.index_key,
                        document.chunk_id,
                        document.knowledge_id,
                        document.document_sha256,
                        dimension,
                        sqlite3.Binary(normalized.tobytes()),
                        utc_now().isoformat(),
                    ),
                )
            manifest = {
                "index_version": self.INDEX_VERSION,
                "model_id": backend.model_id,
                "requested_revision": backend.requested_revision,
                "actual_revision": backend.actual_revision,
                "dimension": dimension,
                "document_count": len(current),
            }
            connection.execute(
                """
                INSERT INTO dense_index_manifest (
                    index_key, model_id, requested_revision, actual_revision,
                    dimension, document_count, manifest_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(index_key) DO UPDATE SET
                    model_id = excluded.model_id,
                    requested_revision = excluded.requested_revision,
                    actual_revision = excluded.actual_revision,
                    dimension = excluded.dimension,
                    document_count = excluded.document_count,
                    manifest_json = excluded.manifest_json,
                    created_at = excluded.created_at
                """,
                (
                    backend.index_key,
                    backend.model_id,
                    backend.requested_revision,
                    backend.actual_revision,
                    dimension,
                    len(current),
                    json.dumps(manifest, ensure_ascii=False, sort_keys=True),
                    utc_now().isoformat(),
                ),
            )
        return DenseIndexBuildSummary(
            index_key=backend.index_key,
            model_id=backend.model_id,
            requested_revision=backend.requested_revision,
            actual_revision=backend.actual_revision,
            dimension=dimension,
            indexed_count=len(changed),
            reused_count=len(current) - len(changed),
            removed_count=len(removed),
            index_version=self.INDEX_VERSION,
        )

    def search(
        self,
        *,
        backend: EmbeddingBackend,
        query_text: str,
        allowed_chunk_ids: Sequence[str],
        limit: int,
    ) -> list[DenseSearchHit]:
        """Cosine-search only metadata-approved source chunks, never the whole disk."""

        if limit < 1:
            raise ValueError("dense limit must be positive")
        if not allowed_chunk_ids:
            return []
        query_vector = backend.encode([query_text])
        if query_vector.shape[0] != 1:
            raise ValueError("embedding backend returned an invalid query vector")
        placeholders = ", ".join("?" for _ in allowed_chunk_ids)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT chunk_id, dimension, vector_blob
                FROM dense_index_vectors
                WHERE index_key = ? AND chunk_id IN ({placeholders})
                """,
                [backend.index_key, *allowed_chunk_ids],
            ).fetchall()
        if not rows:
            return []
        dimension = int(rows[0]["dimension"])
        query = self._normalized_vector(query_vector[0], dimension)
        scored: list[tuple[str, float]] = []
        for row in rows:
            if int(row["dimension"]) != dimension:
                raise ValueError("dense index dimension mismatch")
            vector = np.frombuffer(row["vector_blob"], dtype=np.float32).copy()
            vector = self._normalized_vector(vector, dimension)
            scored.append((str(row["chunk_id"]), float(np.dot(query, vector))))
        ordered = sorted(scored, key=lambda value: (-value[1], value[0]))[:limit]
        return [
            DenseSearchHit(chunk_id=chunk_id, score=score, rank=rank)
            for rank, (chunk_id, score) in enumerate(ordered, 1)
        ]

    def snapshot(self) -> dict[str, int]:
        self.initialize()
        with self._connect() as connection:
            manifest_count = connection.execute(
                "SELECT COUNT(*) AS count FROM dense_index_manifest"
            ).fetchone()
            vector_count = connection.execute(
                "SELECT COUNT(*) AS count FROM dense_index_vectors"
            ).fetchone()
        return {
            "dense_index_manifests": int(manifest_count["count"]),
            "dense_vectors": int(vector_count["count"]),
        }

    def manifest_snapshot(self) -> list[dict[str, object]]:
        """Return safe manifest/vector counts for lifecycle consistency audits."""

        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT m.index_key, m.model_id, m.requested_revision, m.actual_revision,
                       m.dimension, m.document_count, m.created_at,
                       (SELECT COUNT(*) FROM dense_index_vectors AS v
                        WHERE v.index_key = m.index_key) AS indexed_vector_count
                FROM dense_index_manifest AS m
                ORDER BY m.created_at DESC, m.index_key ASC
                """
            ).fetchall()
        return [
            {
                "index_key": str(row["index_key"]),
                "model_id": str(row["model_id"]),
                "requested_revision": str(row["requested_revision"]),
                "actual_revision": str(row["actual_revision"]),
                "dimension": int(row["dimension"]),
                "document_count": int(row["document_count"]),
                "indexed_vector_count": int(row["indexed_vector_count"]),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _normalized_vector(value: np.ndarray, dimension: int) -> np.ndarray:
        vector = np.asarray(value, dtype=np.float32).reshape(-1)
        if len(vector) != dimension or not np.isfinite(vector).all():
            raise ValueError("dense vector is invalid")
        norm = float(np.linalg.norm(vector))
        if norm == 0:
            raise ValueError("dense vector must not be all zero")
        return (vector / norm).astype(np.float32, copy=False)
