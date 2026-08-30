"""Local hybrid RAG P0-B: metadata -> FTS + dense -> RRF -> rerank -> evidence.

P0-B deliberately improves retrieval *ranking*, not tool autonomy.  It only
uses canonical text assembled from a validated ``RagQuery`` and reviewed tool
knowledge.  It still delegates all capability/permission/expiry/conflict rules
to the same deterministic P0-A policy functions, and it never reads a photo,
raw user message, face vector, secret, or Provider receipt.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass

from portrait_consistency_agent.core.contracts import EditableFeature, PreserveAttribute
from portrait_consistency_agent.core.rag_contracts import (
    EvidenceRelation,
    KnowledgeChunk,
    KnowledgeEvidence,
    KnowledgeItem,
    KnowledgeLifecycleStatus,
    RagQuery,
    RagRetrievalResult,
    RetrievalRoute,
)
from portrait_consistency_agent.services.local_rag_models import (
    EmbeddingBackend,
    LocalModelUnavailable,
    RerankerBackend,
)
from portrait_consistency_agent.services.rag_p0a import (
    _candidate_relation,
    _eligibility_reason,
    _evidence,
    _fts_expression,
    _fts_terms,
    _query_sha256,
)
from portrait_consistency_agent.storage.dense_index import (
    DenseIndexDocument,
    LocalDenseIndex,
)
from portrait_consistency_agent.storage.knowledge_store import LocalKnowledgeStore

P0B_RETRIEVAL_VERSION = "rag-p0b-hybrid-local-v1"
P0B_SPARSE_LIMIT = 8
P0B_DENSE_LIMIT = 8
P0B_RRF_OUTPUT_LIMIT = 10
P0B_RERANK_LIMIT = 10
P0B_EVIDENCE_LIMIT = 3
P0B_RRF_CONSTANT = 60

_FEATURE_LABELS: dict[EditableFeature, str] = {
    EditableFeature.FACE_LIFTING: "瘦脸",
    EditableFeature.EYE_ENLARGING: "大眼",
    EditableFeature.WHITENING: "美白",
    EditableFeature.SMOOTHING: "磨皮",
    EditableFeature.EYE_DISTANCE: "眼距",
    EditableFeature.MOUTH_SHAPE: "嘴型",
    EditableFeature.LIPS_THICKNESS: "唇厚",
    EditableFeature.NOSE_WING: "鼻翼",
    EditableFeature.SKIN_TONE: "肤色",
    EditableFeature.MAKEUP: "妆面",
}
_PRESERVE_LABELS: dict[PreserveAttribute, str] = {
    PreserveAttribute.SKIN_TONE: "保持肤色",
    PreserveAttribute.MAKEUP: "保持妆面",
    PreserveAttribute.EXPRESSION: "保持表情",
    PreserveAttribute.BACKGROUND: "保持背景",
    PreserveAttribute.HAIR: "保持头发",
    PreserveAttribute.BODY: "保持身体",
}


@dataclass(frozen=True)
class RagP0BRun:
    """Result and safe execution trace for one P0-B hybrid retrieval run."""

    result: RagRetrievalResult
    trace: tuple[dict[str, object], ...]
    metadata_candidate_count: int
    sparse_candidate_count: int
    dense_candidate_count: int
    fused_candidate_count: int
    rejected_candidate_counts: dict[str, int]
    dense_mode: str
    reranker_mode: str


@dataclass(frozen=True)
class _Candidate:
    item: KnowledgeItem
    chunk: KnowledgeChunk
    sparse_rank: int | None = None
    sparse_score: float | None = None
    dense_rank: int | None = None
    dense_score: float | None = None
    rrf_score: float = 0.0
    rerank_score: float | None = None


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_dense_query_text(query: RagQuery) -> str:
    """Create local-model input exclusively from validated non-sensitive slots."""

    requested = [f"{item.value} {_FEATURE_LABELS[item]}" for item in query.requested_features]
    allowed = [f"{item.value} {_FEATURE_LABELS[item]}" for item in query.allowed_features]
    preserved = [f"{item.value} {_PRESERVE_LABELS[item]}" for item in query.preserve_constraints]
    parts = [
        f"task_stage {query.stage.value}",
        f"provider {' '.join(query.provider_candidates) or 'unspecified'}",
        f"operation {' '.join(query.operation_candidates) or 'unspecified'}",
        f"requested {' '.join(requested) or 'none'}",
        f"allowed {' '.join(allowed) or 'none'}",
        f"preserve {' '.join(preserved) or 'none'}",
        f"face_count {query.face_count if query.face_count is not None else 'unknown'}",
        f"subject_route {query.subject_match_route or 'none'}",
        f"safety_route {query.safety_route or 'none'}",
        f"verification_route {query.verification_route or 'none'}",
    ]
    return "\n".join(parts)


def _dense_document_text(item: KnowledgeItem, chunk: KnowledgeChunk) -> str:
    """Build a local embedding document from reviewed knowledge only."""

    return "\n".join(
        [
            f"provider {item.provider}",
            f"operation {item.operation}",
            f"source_version {item.source_version}",
            f"claim_type {chunk.claim_type.value}",
            f"capability_status {chunk.capability_status.value}",
            f"heading {' > '.join(chunk.heading_path)}",
            f"keywords {' '.join(chunk.keywords)}",
            str(chunk.content),
        ]
    )


def _dense_documents(store: LocalKnowledgeStore) -> list[DenseIndexDocument]:
    documents: list[DenseIndexDocument] = []
    for item, chunk in store.active_index_documents():
        text = _dense_document_text(item, chunk)
        documents.append(
            DenseIndexDocument(
                chunk_id=chunk.chunk_id,
                knowledge_id=item.knowledge_id,
                document_sha256=_canonical_sha256(
                    {
                        "knowledge_id": item.knowledge_id,
                        "source_version": item.source_version,
                        "chunk_sha256": chunk.content_sha256,
                        "text": text,
                    }
                ),
                text=text,
            )
        )
    return documents


def _rrf_rank(candidates: dict[str, _Candidate]) -> list[_Candidate]:
    fused: list[_Candidate] = []
    for candidate in candidates.values():
        score = 0.0
        if candidate.sparse_rank is not None:
            score += 1.0 / (P0B_RRF_CONSTANT + candidate.sparse_rank)
        if candidate.dense_rank is not None:
            score += 1.0 / (P0B_RRF_CONSTANT + candidate.dense_rank)
        fused.append(
            _Candidate(
                item=candidate.item,
                chunk=candidate.chunk,
                sparse_rank=candidate.sparse_rank,
                sparse_score=candidate.sparse_score,
                dense_rank=candidate.dense_rank,
                dense_score=candidate.dense_score,
                rrf_score=score,
            )
        )
    return sorted(
        fused,
        key=lambda candidate: (-candidate.rrf_score, candidate.chunk.chunk_id),
    )[:P0B_RRF_OUTPUT_LIMIT]


class RagP0BHybridRetriever:
    """Hybrid local retriever whose final adoption policy remains deterministic."""

    def __init__(
        self,
        *,
        store: LocalKnowledgeStore,
        dense_index: LocalDenseIndex,
        embedding_backend: EmbeddingBackend,
        reranker_backend: RerankerBackend,
    ) -> None:
        self.store = store
        self.dense_index = dense_index
        self.embedding_backend = embedding_backend
        self.reranker_backend = reranker_backend

    def retrieve(self, query: RagQuery) -> RagP0BRun:
        """Run P0-B with sparse-only degradation when local weights are unavailable."""

        started = time.perf_counter()
        query_sha256 = _query_sha256(query)
        dense_query = build_dense_query_text(query)
        trace: list[dict[str, object]] = [
            {
                "step": "query_contract",
                "query_id": query.query_id,
                "query_sha256": query_sha256,
                "semantic_query_sha256": _canonical_sha256(dense_query),
                "stage": query.stage.value,
                "requested_features": [feature.value for feature in query.requested_features],
                "provider_candidates": query.provider_candidates,
                "operation_candidates": query.operation_candidates,
                "contains_raw_user_text": False,
                "contains_photo_or_face_vector": False,
            }
        ]
        rejected: dict[str, int] = {}
        counts = {"metadata": 0, "sparse": 0, "dense": 0, "fused": 0}
        dense_mode = "not_started"
        reranker_mode = "not_started"

        if query.missing_critical_slots:
            result = self._result(
                query=query,
                query_sha256=query_sha256,
                route=RetrievalRoute.QUERY_UNDERSPECIFIED,
                reason_codes=["MISSING_CRITICAL_SLOTS"],
                evidences=[],
                started=started,
            )
            trace.append(
                {
                    "step": "route",
                    "route": result.route.value,
                    "reason_codes": result.reason_codes,
                    "missing_critical_slot_count": len(query.missing_critical_slots),
                    "external_calls": 0,
                }
            )
            return self._finish(query, result, trace, counts, rejected, dense_mode, reranker_mode)

        try:
            conflicts = self.store.active_conflict_groups(query)
            if conflicts:
                evidences = self._conflict_evidences(conflicts)
                result = self._result(
                    query=query,
                    query_sha256=query_sha256,
                    route=RetrievalRoute.CONFLICT_BLOCKED,
                    reason_codes=["HARD_FACT_CONFLICT"],
                    evidences=evidences,
                    started=started,
                )
                trace.extend(
                    [
                        {
                            "step": "conflict_check",
                            "conflict_group_count": len(conflicts),
                            "conflict_groups": sorted(conflicts),
                            "external_calls": 0,
                        },
                        {
                            "step": "route",
                            "route": result.route.value,
                            "reason_codes": result.reason_codes,
                            "external_calls": 0,
                        },
                    ]
                )
                return self._finish(
                    query, result, trace, counts, rejected, dense_mode, reranker_mode
                )

            metadata_candidates = self.store.active_metadata_candidates(query)
            lifecycle_counts = self.store.lifecycle_counts(query)
            counts["metadata"] = len(metadata_candidates)
            trace.append(
                {
                    "step": "metadata_filter",
                    "eligible_active_chunk_count": len(metadata_candidates),
                    "lifecycle_filter": KnowledgeLifecycleStatus.REVIEWED_ACTIVE.value,
                    "region": query.region,
                    "lifecycle_counts": lifecycle_counts,
                }
            )
            if not metadata_candidates:
                reason_codes = ["NO_ACTIVE_KNOWLEDGE"]
                if lifecycle_counts["expired_or_withdrawn"]:
                    reason_codes.append("EXPIRED_KNOWLEDGE_BLOCKED")
                result = self._result(
                    query=query,
                    query_sha256=query_sha256,
                    route=RetrievalRoute.BASELINE_FALLBACK,
                    reason_codes=reason_codes,
                    evidences=[],
                    started=started,
                )
                trace.append(
                    {
                        "step": "route",
                        "route": result.route.value,
                        "reason_codes": result.reason_codes,
                        "external_calls": 0,
                    }
                )
                return self._finish(
                    query, result, trace, counts, rejected, dense_mode, reranker_mode
                )

            terms = _fts_terms(query)
            sparse_candidates = []
            if terms:
                sparse_candidates = self.store.fts_candidates(
                    query,
                    fts_expression=_fts_expression(terms),
                    limit=P0B_SPARSE_LIMIT,
                )
            counts["sparse"] = len(sparse_candidates)
            trace.append(
                {
                    "step": "sparse_retrieval",
                    "term_count": len(terms),
                    "candidate_limit": P0B_SPARSE_LIMIT,
                    "returned_candidate_count": len(sparse_candidates),
                    "index_version": self.store.INDEX_VERSION,
                }
            )
        except (sqlite3.Error, ValueError) as exc:
            result = self._result(
                query=query,
                query_sha256=query_sha256,
                route=RetrievalRoute.INDEX_UNAVAILABLE,
                reason_codes=["INDEX_UNAVAILABLE"],
                evidences=[],
                started=started,
            )
            trace.append(
                {
                    "step": "sparse_index_failure",
                    "error_type": type(exc).__name__,
                    "external_calls": 0,
                }
            )
            return self._finish(query, result, trace, counts, rejected, dense_mode, reranker_mode)

        candidate_by_chunk = {
            chunk.chunk_id: _Candidate(
                item=item,
                chunk=chunk,
                sparse_rank=rank,
                sparse_score=score,
            )
            for rank, (item, chunk, score) in enumerate(sparse_candidates, start=1)
        }
        metadata_by_chunk = {chunk.chunk_id: (item, chunk) for item, chunk in metadata_candidates}
        try:
            summary = self.dense_index.build_or_update(
                backend=self.embedding_backend,
                documents=_dense_documents(self.store),
            )
            dense_hits = self.dense_index.search(
                backend=self.embedding_backend,
                query_text=dense_query,
                allowed_chunk_ids=sorted(metadata_by_chunk),
                limit=P0B_DENSE_LIMIT,
            )
            dense_mode = "local_bge_dense"
            counts["dense"] = len(dense_hits)
            trace.extend(
                [
                    {
                        "step": "dense_index_build",
                        "backend": self.embedding_backend.backend_name,
                        "model_id": summary.model_id,
                        "requested_revision": summary.requested_revision,
                        "actual_revision": summary.actual_revision,
                        "dimension": summary.dimension,
                        "indexed_count": summary.indexed_count,
                        "reused_count": summary.reused_count,
                        "index_version": summary.index_version,
                        "contains_user_data": False,
                    },
                    {
                        "step": "dense_retrieval",
                        "candidate_limit": P0B_DENSE_LIMIT,
                        "returned_candidate_count": len(dense_hits),
                        "model_id": self.embedding_backend.model_id,
                        "actual_revision": self.embedding_backend.actual_revision,
                    },
                ]
            )
            for hit in dense_hits:
                item, chunk = metadata_by_chunk[hit.chunk_id]
                prior = candidate_by_chunk.get(hit.chunk_id)
                candidate_by_chunk[hit.chunk_id] = _Candidate(
                    item=item,
                    chunk=chunk,
                    sparse_rank=prior.sparse_rank if prior else None,
                    sparse_score=prior.sparse_score if prior else None,
                    dense_rank=hit.rank,
                    dense_score=hit.score,
                )
        except (LocalModelUnavailable, sqlite3.Error, ValueError) as exc:
            dense_mode = "sparse_fallback_local_model_unavailable"
            trace.append(
                {
                    "step": "dense_unavailable",
                    "error_type": type(exc).__name__,
                    "reason_code": "LOCAL_DENSE_UNAVAILABLE",
                    "fallback": "sparse_only",
                    "external_calls": 0,
                }
            )

        fused = _rrf_rank(candidate_by_chunk)
        counts["fused"] = len(fused)
        trace.append(
            {
                "step": "rrf_fusion",
                "rrf_constant": P0B_RRF_CONSTANT,
                "output_limit": P0B_RRF_OUTPUT_LIMIT,
                "sparse_candidate_count": len(sparse_candidates),
                "dense_candidate_count": counts["dense"],
                "fused_candidate_count": len(fused),
                "candidate_rank_records": [
                    {
                        "knowledge_ref": self._knowledge_ref(candidate),
                        "sparse_rank": candidate.sparse_rank,
                        "dense_rank": candidate.dense_rank,
                        "rrf_rank": rank,
                    }
                    for rank, candidate in enumerate(fused, start=1)
                ],
            }
        )
        if not fused:
            result = self._result(
                query=query,
                query_sha256=query_sha256,
                route=RetrievalRoute.BASELINE_FALLBACK,
                reason_codes=["RETRIEVER_MISS_SUSPECT", "NO_TOOL_CALL"],
                evidences=[],
                started=started,
            )
            trace.append(
                {
                    "step": "route",
                    "route": result.route.value,
                    "reason_codes": result.reason_codes,
                    "external_calls": 0,
                }
            )
            return self._finish(query, result, trace, counts, rejected, dense_mode, reranker_mode)

        reranked = fused[:P0B_RERANK_LIMIT]
        try:
            scores = self.reranker_backend.score(
                dense_query,
                [_dense_document_text(candidate.item, candidate.chunk) for candidate in reranked],
            )
            reranked = [
                _Candidate(
                    item=candidate.item,
                    chunk=candidate.chunk,
                    sparse_rank=candidate.sparse_rank,
                    sparse_score=candidate.sparse_score,
                    dense_rank=candidate.dense_rank,
                    dense_score=candidate.dense_score,
                    rrf_score=candidate.rrf_score,
                    rerank_score=float(score),
                )
                for candidate, score in zip(reranked, scores, strict=True)
            ]
            reranked.sort(
                key=lambda candidate: (
                    -(
                        candidate.rerank_score
                        if candidate.rerank_score is not None
                        else float("-inf")
                    ),
                    -candidate.rrf_score,
                    candidate.chunk.chunk_id,
                )
            )
            reranker_mode = "local_bge_cross_encoder"
            trace.append(
                {
                    "step": "local_rerank",
                    "backend": self.reranker_backend.backend_name,
                    "model_id": self.reranker_backend.model_id,
                    "requested_revision": self.reranker_backend.requested_revision,
                    "actual_revision": self.reranker_backend.actual_revision,
                    "candidate_count": len(reranked),
                    "output_limit": P0B_RERANK_LIMIT,
                    "score_not_an_execution_threshold": True,
                    "candidate_rank_records": [
                        {"knowledge_ref": self._knowledge_ref(candidate), "rerank_rank": rank}
                        for rank, candidate in enumerate(reranked, start=1)
                    ],
                }
            )
        except (LocalModelUnavailable, ValueError) as exc:
            reranker_mode = "rrf_fallback_local_reranker_unavailable"
            trace.append(
                {
                    "step": "reranker_unavailable",
                    "error_type": type(exc).__name__,
                    "reason_code": "LOCAL_RERANKER_UNAVAILABLE",
                    "fallback": "rrf_order",
                    "external_calls": 0,
                }
            )

        evidences: list[KnowledgeEvidence] = []
        adopted_direct_executable = False
        adopted_direct_nonexecutable = False
        for rank, candidate in enumerate(reranked, start=1):
            relation = _candidate_relation(query, candidate.chunk)
            rejection = _eligibility_reason(query, candidate.item, candidate.chunk, relation)
            adopted = rejection is None and relation == EvidenceRelation.DIRECT_EVIDENCE
            if rejection is not None:
                rejected[rejection] = rejected.get(rejection, 0) + 1
            if adopted and candidate.chunk.capability_status.value == "executable":
                adopted_direct_executable = True
            if adopted and candidate.chunk.capability_status.value != "executable":
                adopted_direct_nonexecutable = True
            reason_codes = [
                "ACTIVE_REVIEWED",
                "DIRECT_FEATURE_MATCH"
                if relation == EvidenceRelation.DIRECT_EVIDENCE
                else "REFERENCE_CONTEXT_ONLY",
            ]
            if rejection is not None:
                reason_codes.append(rejection.upper())
            evidences.append(
                _evidence(
                    item=candidate.item,
                    chunk=candidate.chunk,
                    rank=rank,
                    fts_score=candidate.sparse_score,
                    relation=relation,
                    adopted=adopted,
                    reason_codes=reason_codes,
                )
            )

        adopted_evidences = [item for item in evidences if item.adopted]
        if len(adopted_evidences) > P0B_EVIDENCE_LIMIT:
            allowed_refs = {item.knowledge_ref for item in adopted_evidences[:P0B_EVIDENCE_LIMIT]}
            evidences = [
                item.model_copy(update={"adopted": item.knowledge_ref in allowed_refs})
                for item in evidences
            ]

        if adopted_direct_executable:
            route = RetrievalRoute.EVIDENCE_FOUND
            reason_codes = ["ACTIVE_DIRECT_EXECUTABLE_EVIDENCE", "P0B_HYBRID_RETRIEVAL_ONLY"]
        elif adopted_direct_nonexecutable:
            route = RetrievalRoute.MANUAL_SUGGESTION
            reason_codes = ["DIRECT_LIMITATION_OR_UNSUPPORTED", "NO_TOOL_CALL"]
        elif rejected.get("knowledge_injection_blocked", 0):
            route = RetrievalRoute.BASELINE_FALLBACK
            reason_codes = ["KNOWLEDGE_INJECTION_BLOCKED", "NO_TOOL_CALL"]
        else:
            route = RetrievalRoute.BASELINE_FALLBACK
            reason_codes = ["NO_ADOPTABLE_DIRECT_EVIDENCE", "NO_TOOL_CALL"]

        result = self._result(
            query=query,
            query_sha256=query_sha256,
            route=route,
            reason_codes=reason_codes,
            evidences=evidences,
            started=started,
        )
        trace.extend(
            [
                {
                    "step": "evidence_classification",
                    "direct_evidence_count": sum(
                        item.relation == EvidenceRelation.DIRECT_EVIDENCE for item in evidences
                    ),
                    "adopted_count": sum(item.adopted for item in evidences),
                    "rejected_candidate_counts": rejected,
                    "evidence_limit": P0B_EVIDENCE_LIMIT,
                },
                {
                    "step": "route",
                    "route": result.route.value,
                    "reason_codes": result.reason_codes,
                    "external_calls": 0,
                    "edit_plan_written": False,
                    "provider_run_written": False,
                },
            ]
        )
        return self._finish(query, result, trace, counts, rejected, dense_mode, reranker_mode)

    def _finish(
        self,
        query: RagQuery,
        result: RagRetrievalResult,
        trace: list[dict[str, object]],
        counts: dict[str, int],
        rejected: dict[str, int],
        dense_mode: str,
        reranker_mode: str,
    ) -> RagP0BRun:
        self.store.record_query_run(query=query, result=result, trace=trace)
        return RagP0BRun(
            result=result,
            trace=tuple(trace),
            metadata_candidate_count=counts["metadata"],
            sparse_candidate_count=counts["sparse"],
            dense_candidate_count=counts["dense"],
            fused_candidate_count=counts["fused"],
            rejected_candidate_counts=rejected,
            dense_mode=dense_mode,
            reranker_mode=reranker_mode,
        )

    def _conflict_evidences(
        self, conflicts: dict[str, list[KnowledgeItem]]
    ) -> list[KnowledgeEvidence]:
        evidences: list[KnowledgeEvidence] = []
        rank = 1
        for group_id in sorted(conflicts):
            for item in sorted(conflicts[group_id], key=lambda value: value.knowledge_id):
                chunks = self.store.chunks_for_knowledge_ids([item.knowledge_id])
                # The consumer must see every bounded competing source fact,
                # not a single representative selected by the retriever.
                for _stored_item, chunk in chunks:
                    if rank > 10:
                        return evidences
                    evidences.append(
                        _evidence(
                            item=item,
                            chunk=chunk,
                            rank=rank,
                            fts_score=None,
                            relation=EvidenceRelation.CONFLICT_EVIDENCE,
                            adopted=False,
                            reason_codes=["HARD_FACT_CONFLICT", f"GROUP_{group_id.upper()}"],
                        )
                    )
                    rank += 1
        return evidences

    def _result(
        self,
        *,
        query: RagQuery,
        query_sha256: str,
        route: RetrievalRoute,
        reason_codes: list[str],
        evidences: list[KnowledgeEvidence],
        started: float,
    ) -> RagRetrievalResult:
        return RagRetrievalResult(
            query_id=query.query_id,
            query_sha256=query_sha256,
            route=route,
            reason_codes=reason_codes,
            evidences=evidences,
            retrieval_version=P0B_RETRIEVAL_VERSION,
            index_version=f"{self.store.INDEX_VERSION}+{self.dense_index.INDEX_VERSION}",
            latency_ms=max(0, round((time.perf_counter() - started) * 1000)),
        )

    @staticmethod
    def _knowledge_ref(candidate: _Candidate) -> str:
        return (
            f"{candidate.item.knowledge_id}#{candidate.chunk.chunk_id}@"
            f"{candidate.item.source_version}"
        )
