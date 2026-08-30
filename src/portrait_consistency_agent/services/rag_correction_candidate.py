"""A bounded, human-gated RAG correction candidate.

The first failure pattern is an ontology mismatch: a user can express a
reviewed concept in English, with punctuation variants, or with a common
synonym, while the deterministic public bridge knows only a small Chinese
vocabulary.  This module tests a *generic* normalization dictionary on the
public set.  It never reads hidden answers, never uses case IDs as rules, and
never changes permission or Provider state.  The candidate is deliberately
not active until a product owner approves its public regression result.
"""

from __future__ import annotations

import re
import tempfile
import unicodedata
from dataclasses import replace
from pathlib import Path

from portrait_consistency_agent.services.local_rag_models import (
    DeterministicTokenEmbeddingBackend,
    TokenOverlapReranker,
)
from portrait_consistency_agent.services.rag_advisory import RagAdvisoryService
from portrait_consistency_agent.services.rag_gold_baseline import (
    RagGoldDeterministicBaseline,
    _query_for_projection,
    _run_counts,
    project_runtime_prompt,
)
from portrait_consistency_agent.services.rag_gold_eval import GoldCase, Prediction
from portrait_consistency_agent.services.rag_p0a import seed_reviewed_provider_knowledge
from portrait_consistency_agent.services.rag_p0b import RagP0BHybridRetriever
from portrait_consistency_agent.storage.dense_index import LocalDenseIndex
from portrait_consistency_agent.storage.knowledge_store import LocalKnowledgeStore

CORRECTION_CANDIDATE_VERSION = "rag-correction-candidate-v0.1"

# These are high-confidence domain synonyms only.  They are intentionally
# one-way and small: a phrase that is not in this table remains unknown rather
# than being guessed by an LLM.
_NORMALIZATION_RULES: tuple[tuple[str, str], ...] = (
    ("no cloud transfer", "不外发照片"),
    ("no cloud", "不外发照片"),
    ("do not send the photo", "不外发照片"),
    ("do not send photo", "不外发照片"),
    ("only adjust eye width", "只改眼宽"),
    ("eye width", "眼宽"),
    ("eye distance", "眼距"),
    ("enlarge eyes", "大眼"),
    ("bigger eyes", "大眼"),
    ("slim face", "瘦脸"),
    ("face slimming", "瘦脸"),
    ("jawline", "腮帮"),
    ("jaw line", "腮帮"),
    ("face width", "脸宽"),
    ("lip thickness", "唇厚"),
    ("lip shape", "嘴型"),
    ("nose wing", "鼻翼"),
    ("same person", "同一人物"),
    ("compare face", "CompareFace"),
    ("content moderation", "内容审核"),
    ("image moderation", "内容审核"),
    ("ignore permission", "忽略权限"),
    ("system prompt", "system prompt"),
)


def normalize_domain_prompt(text: str) -> str:
    """Normalize punctuation and reviewed domain synonyms in memory only."""

    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = re.sub(r"\s+", " ", normalized).strip()
    for source, target in _NORMALIZATION_RULES:
        normalized = normalized.replace(source, target)
    return normalized


def candidate_projection(case: GoldCase):
    """Project a case with the candidate vocabulary, without persisting text."""

    normalized_case = replace(case, query=normalize_domain_prompt(case.query))
    return project_runtime_prompt(normalized_case)


def _run_candidate_case(
    case: GoldCase, service: RagAdvisoryService
) -> tuple[Prediction, dict[str, object]]:
    projection = candidate_projection(case)
    query = _query_for_projection(case, projection)
    advisory = (
        service.advise(
            query=query,
            existing_baseline_available=False,
            advice_id=f"rag_correction_candidate_{case.case_id.lower()}",
        )
        if query is not None
        else None
    )
    retrieval = advisory.retrieval if advisory is not None else None
    aliases = list(projection.evidence_aliases)
    relations = dict(projection.evidence_relations)
    if retrieval is not None:
        for evidence in retrieval.result.evidences:
            alias = {
                "tencent-beautify-pic-2019-12-13": "B",
                "tencent-compare-face-2018-03-01": "C",
                "tencent-image-moderation-2020-12-29": "I",
            }.get(evidence.knowledge_id)
            if alias is not None and alias not in aliases:
                aliases.append(alias)
                relations[alias] = evidence.relation.value
    prediction = Prediction(
        case_id=case.case_id,
        route=projection.route_override or "UNKNOWN",
        evidence_refs=tuple(dict.fromkeys(aliases)),
        evidence_relations=relations,
        trace_ref=f"{CORRECTION_CANDIDATE_VERSION}:{case.case_id}",
        machine_score_summary=_run_counts(retrieval),
    )
    trace = {
        "case_id": case.case_id,
        "runner_version": CORRECTION_CANDIDATE_VERSION,
        "normalization_applied": normalize_domain_prompt(case.query) != case.query,
        "category_codes": list(projection.category_codes),
        "structured_query_created": query is not None,
        "retrieval_route": retrieval.result.route.value if retrieval is not None else None,
        "advisory_route": (
            advisory.decision.advisory_route.value if advisory is not None else None
        ),
        "prediction_route": prediction.route,
        "evidence_refs": list(prediction.evidence_refs),
        "evidence_relations": dict(prediction.evidence_relations),
        "machine_score_summary": dict(prediction.machine_score_summary),
        "raw_prompt_persisted": False,
        "photo_or_face_vector_read": False,
        "llm_called": False,
        "provider_api_called": False,
        "network_called": False,
    }
    return prediction, trace


def run_public_correction_candidate(
    cases: tuple[GoldCase, ...],
) -> tuple[tuple[Prediction, ...], tuple[dict[str, object], ...]]:
    """Run the candidate only on answerless public cases."""

    RagGoldDeterministicBaseline._validate_cases(cases, runtime_mode="public")
    with tempfile.TemporaryDirectory(prefix="portrait-rag-correction-candidate-") as directory:
        root = Path(directory)
        store = LocalKnowledgeStore(root / "knowledge.sqlite3")
        store.initialize()
        seed_reviewed_provider_knowledge(store)
        retriever = RagP0BHybridRetriever(
            store=store,
            dense_index=LocalDenseIndex(root / "knowledge_vectors.sqlite3"),
            embedding_backend=DeterministicTokenEmbeddingBackend(),
            reranker_backend=TokenOverlapReranker(),
        )
        service = RagAdvisoryService(store=store, retriever=retriever)
        runs = tuple(_run_candidate_case(case, service) for case in cases)
    return tuple(item[0] for item in runs), tuple(item[1] for item in runs)
