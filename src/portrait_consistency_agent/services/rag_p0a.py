"""Governed SQLite/FTS retrieval for the RAG P0-A vertical slice.

P0-A deliberately retrieves only reviewed *tool knowledge*.  It does not read
photos or raw user messages, call an LLM, invoke a Tencent API, create an
``EditPlan``, or grant a tool permission.  Those remain separate future
integration steps after this slice has passed its retrieval and safety tests.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from portrait_consistency_agent.core.contracts import EditableFeature, PreserveAttribute
from portrait_consistency_agent.core.rag_contracts import (
    EvidenceRelation,
    KnowledgeCapabilityStatus,
    KnowledgeChunk,
    KnowledgeClaimType,
    KnowledgeEvidence,
    KnowledgeItem,
    KnowledgeLifecycleStatus,
    KnowledgeSourceType,
    RagQuery,
    RagRetrievalResult,
    RagStage,
    RetrievalRoute,
)
from portrait_consistency_agent.services.provider_cards import (
    load_tencent_beautify_card,
    load_tencent_compare_face_card,
    load_tencent_image_moderation_card,
)
from portrait_consistency_agent.storage.knowledge_store import LocalKnowledgeStore

P0A_RETRIEVAL_VERSION = "rag-p0a-sqlite-fts-v1"
P0A_FTS_LIMIT = 5
_READY_ADAPTER_STATUSES = frozenset({"implemented", "verified"})
_SAFE_FTS_TERM = re.compile(r"^[A-Za-z0-9_\-\u4e00-\u9fff]+$")
_KNOWLEDGE_INJECTION_MARKERS = (
    "ignore previous",
    "ignore all previous",
    "忽略权限",
    "泄露密钥",
    "调用未知 api",
    "调用未知api",
    "system prompt",
)

_FEATURE_TERMS: dict[EditableFeature, tuple[str, ...]] = {
    EditableFeature.FACE_LIFTING: ("face_lifting", "FaceLifting", "瘦脸"),
    EditableFeature.EYE_ENLARGING: ("eye_enlarging", "EyeEnlarging", "大眼"),
    EditableFeature.WHITENING: ("whitening", "Whitening", "美白"),
    EditableFeature.SMOOTHING: ("smoothing", "Smoothing", "磨皮"),
    EditableFeature.EYE_DISTANCE: ("eye_distance", "眼距"),
    EditableFeature.MOUTH_SHAPE: ("mouth_shape", "嘴型"),
    EditableFeature.LIPS_THICKNESS: ("lips_thickness", "唇厚"),
    EditableFeature.NOSE_WING: ("nose_wing", "鼻翼"),
    EditableFeature.SKIN_TONE: ("skin_tone", "肤色"),
    EditableFeature.MAKEUP: ("makeup", "妆面"),
}
_PRESERVE_TERMS: dict[PreserveAttribute, tuple[str, ...]] = {
    PreserveAttribute.SKIN_TONE: ("skin_tone", "Whitening", "美白"),
    PreserveAttribute.MAKEUP: ("makeup", "妆面"),
    PreserveAttribute.EXPRESSION: ("expression", "表情"),
    PreserveAttribute.BACKGROUND: ("background", "背景"),
    PreserveAttribute.HAIR: ("hair", "头发"),
    PreserveAttribute.BODY: ("body", "身体"),
}


@dataclass(frozen=True)
class SeedSummary:
    """Safe counters from seeding reviewed, repository-local Provider Cards."""

    items_seen: int
    items_written: int
    chunks_written: int
    knowledge_ids: tuple[str, ...]


@dataclass(frozen=True)
class RagP0ARun:
    """A retrieval result plus a redacted, replayable P0-A Trace."""

    result: RagRetrievalResult
    trace: tuple[dict[str, object], ...]
    metadata_candidate_count: int
    fts_candidate_count: int
    rejected_candidate_counts: dict[str, int]


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _reviewed_at(card: dict[str, object]) -> datetime:
    raw = str(card.get("reviewed_at", "2026-08-27"))
    return datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)


def _source_uris(card: dict[str, object]) -> list[str]:
    source = card.get("source")
    if not isinstance(source, dict):
        return []
    return sorted(str(value) for value in source.values() if isinstance(value, str))


def _item_from_card(
    card: dict[str, object],
    *,
    source_title: str,
    smoke_status: str,
) -> KnowledgeItem:
    effective_from = _reviewed_at(card)
    return KnowledgeItem(
        knowledge_id=str(card["card_id"]),
        source_type=KnowledgeSourceType.PROVIDER_CARD,
        source_title=source_title,
        source_uris=_source_uris(card),
        source_version=str(card["card_version"]),
        authority_level=5,
        effective_from=effective_from,
        review_due_at=effective_from + timedelta(days=14),
        lifecycle_status=KnowledgeLifecycleStatus.REVIEWED_ACTIVE,
        provider=str(card["provider"]),
        operation=str(card["operation"]),
        region="local_demo",
        adapter_status="implemented",
        smoke_status=smoke_status,
        privacy_class="tool_knowledge_no_user_media",
        cost_tier="unrated",
        content_sha256=_canonical_sha256(card),
        created_at=effective_from,
    )


def _chunk(
    *,
    chunk_id: str,
    item: KnowledgeItem,
    heading_path: list[str],
    claim_type: KnowledgeClaimType,
    capability_status: KnowledgeCapabilityStatus,
    content: str,
    keywords: list[str],
    feature_codes: list[EditableFeature],
    applicable_stages: list[RagStage],
    requires_adapter: bool = False,
    requires_outbound_image: bool = False,
) -> KnowledgeChunk:
    source_payload = {
        "chunk_id": chunk_id,
        "heading_path": heading_path,
        "claim_type": claim_type.value,
        "capability_status": capability_status.value,
        "content": content,
        "keywords": keywords,
        "feature_codes": [feature.value for feature in feature_codes],
        "applicable_stages": [stage.value for stage in applicable_stages],
        "requires_adapter": requires_adapter,
        "requires_outbound_image": requires_outbound_image,
    }
    return KnowledgeChunk(
        chunk_id=chunk_id,
        knowledge_id=item.knowledge_id,
        heading_path=heading_path,
        claim_type=claim_type,
        capability_status=capability_status,
        content=content,
        keywords=keywords,
        feature_codes=feature_codes,
        applicable_stages=applicable_stages,
        requires_adapter=requires_adapter,
        requires_outbound_image=requires_outbound_image,
        content_sha256=_canonical_sha256(source_payload),
        created_at=item.created_at,
    )


def build_reviewed_provider_knowledge() -> list[tuple[KnowledgeItem, list[KnowledgeChunk]]]:
    """Translate the three reviewed Provider Cards into atomic P0-A claims.

    This is a deterministic local transformation.  It is intentionally not a
    network crawler and never imports a user photo, API key, or Provider
    response body into the knowledge base.
    """

    beautify_card = load_tencent_beautify_card()
    compare_card = load_tencent_compare_face_card()
    moderation_card = load_tencent_image_moderation_card()

    beautify = _item_from_card(
        beautify_card,
        source_title="腾讯云 BeautifyPic 已审核能力卡",
        smoke_status="historical_receipt_required_for_execution",
    )
    beautify_chunks = [
        _chunk(
            chunk_id="beautify_face_lifting",
            item=beautify,
            heading_path=["BeautifyPic", "parameters", "FaceLifting"],
            claim_type=KnowledgeClaimType.PARAMETER,
            capability_status=KnowledgeCapabilityStatus.EXECUTABLE,
            content=(
                "BeautifyPic 的 FaceLifting 支持 0 到 100。当前产品必须显式传入该值；"
                "0 表示不瘦脸。它只能作为确定性 mapping_policy 的能力候选，不能由检索直接设值。"
            ),
            keywords=["BeautifyPic", "FaceLifting", "face_lifting", "瘦脸", "0", "100"],
            feature_codes=[EditableFeature.FACE_LIFTING],
            applicable_stages=[RagStage.PLAN_EDIT, RagStage.FAILURE_ROUTING],
            requires_adapter=True,
            requires_outbound_image=True,
        ),
        _chunk(
            chunk_id="beautify_eye_enlarging",
            item=beautify,
            heading_path=["BeautifyPic", "parameters", "EyeEnlarging"],
            claim_type=KnowledgeClaimType.PARAMETER,
            capability_status=KnowledgeCapabilityStatus.EXECUTABLE,
            content=(
                "BeautifyPic 的 EyeEnlarging 支持 0 到 100。当前产品必须显式传入该值；"
                "0 表示不做大眼。它只能作为确定性 mapping_policy 的能力候选，不能由检索直接设值。"
            ),
            keywords=["BeautifyPic", "EyeEnlarging", "eye_enlarging", "大眼", "0", "100"],
            feature_codes=[EditableFeature.EYE_ENLARGING],
            applicable_stages=[RagStage.PLAN_EDIT, RagStage.FAILURE_ROUTING],
            requires_adapter=True,
            requires_outbound_image=True,
        ),
        _chunk(
            chunk_id="beautify_whitening",
            item=beautify,
            heading_path=["BeautifyPic", "parameters", "Whitening"],
            claim_type=KnowledgeClaimType.PARAMETER,
            capability_status=KnowledgeCapabilityStatus.EXECUTABLE,
            content=(
                "BeautifyPic 的 Whitening 支持 0 到 100。它会改变肤色；"
                "只有用户明确允许肤色变化时才能成为执行候选，默认保持为 0。"
            ),
            keywords=["BeautifyPic", "Whitening", "whitening", "美白", "肤色", "0", "100"],
            feature_codes=[EditableFeature.WHITENING, EditableFeature.SKIN_TONE],
            applicable_stages=[RagStage.PLAN_EDIT, RagStage.FAILURE_ROUTING],
            requires_adapter=True,
            requires_outbound_image=True,
        ),
        _chunk(
            chunk_id="beautify_smoothing",
            item=beautify,
            heading_path=["BeautifyPic", "parameters", "Smoothing"],
            claim_type=KnowledgeClaimType.PARAMETER,
            capability_status=KnowledgeCapabilityStatus.EXECUTABLE,
            content=(
                "BeautifyPic 的 Smoothing 支持 0 到 100。它会改变皮肤纹理；"
                "只有用户明确允许肤质变化时才能成为执行候选，默认保持为 0。"
            ),
            keywords=["BeautifyPic", "Smoothing", "smoothing", "磨皮", "肤质", "0", "100"],
            feature_codes=[EditableFeature.SMOOTHING],
            applicable_stages=[RagStage.PLAN_EDIT, RagStage.FAILURE_ROUTING],
            requires_adapter=True,
            requires_outbound_image=True,
        ),
        _chunk(
            chunk_id="beautify_unsupported_facial_features",
            item=beautify,
            heading_path=["BeautifyPic", "limitations", "unsupported_features"],
            claim_type=KnowledgeClaimType.LIMITATION,
            capability_status=KnowledgeCapabilityStatus.UNSUPPORTED,
            content=(
                "当前已接入的 BeautifyPic 参数不包含眼距、嘴型、唇厚或鼻翼。"
                "这些需求只能输出手动建议或等待新的已审核工具，不能声称已经自动执行。"
            ),
            keywords=[
                "BeautifyPic",
                "eye_distance",
                "mouth_shape",
                "lips_thickness",
                "nose_wing",
                "眼距",
                "嘴型",
                "唇厚",
                "鼻翼",
            ],
            feature_codes=[
                EditableFeature.EYE_DISTANCE,
                EditableFeature.MOUTH_SHAPE,
                EditableFeature.LIPS_THICKNESS,
                EditableFeature.NOSE_WING,
            ],
            applicable_stages=[RagStage.PLAN_EDIT, RagStage.FAILURE_ROUTING],
        ),
        _chunk(
            chunk_id="beautify_multiface_restriction",
            item=beautify,
            heading_path=["BeautifyPic", "input", "multi_face"],
            claim_type=KnowledgeClaimType.INPUT_REQUIREMENT,
            capability_status=KnowledgeCapabilityStatus.SUGGESTION_ONLY,
            content=(
                "BeautifyPic 可能处理图片中最大的五张脸，但没有指定目标脸的选择器。"
                "当前运行规则要求多人图先裁剪或隔离目标单脸，不能直接声称只会修改用户选中的那张脸。"
            ),
            keywords=["BeautifyPic", "multi_face", "多人", "裁剪", "隔离", "target_face"],
            feature_codes=[],
            applicable_stages=[RagStage.QUALITY_GATE, RagStage.PLAN_EDIT, RagStage.FAILURE_ROUTING],
        ),
    ]

    compare = _item_from_card(
        compare_card,
        source_title="腾讯云 CompareFace 已审核能力卡",
        smoke_status="historical_receipt_required_for_execution",
    )
    compare_chunks = [
        _chunk(
            chunk_id="compare_face_subject_match",
            item=compare,
            heading_path=["CompareFace", "purpose", "current_session_subject_match"],
            claim_type=KnowledgeClaimType.CAPABILITY,
            capability_status=KnowledgeCapabilityStatus.EXECUTABLE,
            content=(
                "CompareFace 可在当前会话中比较两张图片并提供同一人物辅助证据。"
                "它比较各图最大的人脸，不能指定多人图中的目标脸。"
            ),
            keywords=["CompareFace", "same_person", "subject_match", "同一人物", "最大人脸"],
            feature_codes=[],
            applicable_stages=[RagStage.QUALITY_GATE, RagStage.VERIFICATION_STRATEGY],
            requires_adapter=True,
            requires_outbound_image=True,
        ),
        _chunk(
            chunk_id="compare_face_not_consistency_probability",
            item=compare,
            heading_path=["CompareFace", "limitations", "consistency_scope"],
            claim_type=KnowledgeClaimType.VERIFICATION_SCOPE,
            capability_status=KnowledgeCapabilityStatus.NOT_APPLICABLE,
            content=(
                "CompareFace 的原始 comparison score 不是校准概率，也不能证明五官已经与母版对齐。"
                "它只能补充同人证据，不能替代本地几何复测或人工视觉复核。"
            ),
            keywords=[
                "CompareFace",
                "raw_score",
                "consistency",
                "几何复测",
                "校准概率",
                "母版一致性",
            ],
            feature_codes=[],
            applicable_stages=[RagStage.QUALITY_GATE, RagStage.VERIFICATION_STRATEGY],
        ),
    ]

    moderation = _item_from_card(
        moderation_card,
        source_title="腾讯云 ImageModeration 已审核能力卡",
        smoke_status="one_authorized_pass_receipt",
    )
    moderation_chunks = [
        _chunk(
            chunk_id="image_moderation_safety_gate",
            item=moderation,
            heading_path=["ImageModeration", "purpose", "content_safety"],
            claim_type=KnowledgeClaimType.CAPABILITY,
            capability_status=KnowledgeCapabilityStatus.EXECUTABLE,
            content=(
                "ImageModeration 返回 Pass、Review 或 Block，用于图片内容安全门。"
                "当前产品将 Review 和 Block 保守路由为不可继续自动处理。"
            ),
            keywords=[
                "ImageModeration",
                "content_safety",
                "safety",
                "Pass",
                "Review",
                "Block",
                "内容安全",
            ],
            feature_codes=[],
            applicable_stages=[RagStage.QUALITY_GATE, RagStage.FAILURE_ROUTING],
            requires_adapter=True,
            requires_outbound_image=True,
        ),
        _chunk(
            chunk_id="image_moderation_not_quality_gate",
            item=moderation,
            heading_path=["ImageModeration", "limitations", "quality_and_subject"],
            claim_type=KnowledgeClaimType.VERIFICATION_SCOPE,
            capability_status=KnowledgeCapabilityStatus.NOT_APPLICABLE,
            content=(
                "ImageModeration 通过只说明当前审核结果允许继续内容安全路径。"
                "它不证明照片可编辑、同一人物、五官一致或修图已经达标。"
            ),
            keywords=[
                "ImageModeration",
                "quality",
                "subject_match",
                "editability",
                "照片质量",
                "同一人物",
            ],
            feature_codes=[],
            applicable_stages=[RagStage.QUALITY_GATE, RagStage.VERIFICATION_STRATEGY],
        ),
    ]
    return [
        (beautify, beautify_chunks),
        (compare, compare_chunks),
        (moderation, moderation_chunks),
    ]


def seed_reviewed_provider_knowledge(store: LocalKnowledgeStore) -> SeedSummary:
    """Seed/update only the local, human-reviewed Provider Card facts."""

    store.initialize()
    pairs = build_reviewed_provider_knowledge()
    items_written = 0
    chunks_written = 0
    for item, chunks in pairs:
        if store.replace_item(item, chunks):
            items_written += 1
            chunks_written += len(chunks)
    return SeedSummary(
        items_seen=len(pairs),
        items_written=items_written,
        chunks_written=chunks_written,
        knowledge_ids=tuple(item.knowledge_id for item, _ in pairs),
    )


def build_plan_edit_query(
    *,
    query_id: str,
    requested_features: Iterable[EditableFeature],
    allowed_features: Iterable[EditableFeature],
    preserve_constraints: Iterable[PreserveAttribute] = (),
    face_count: int | None = 1,
    outbound_allowed: bool = True,
    missing_critical_slots: Iterable[str] = (),
) -> RagQuery:
    """Build a structured P0-A planning query without a raw user utterance."""

    return RagQuery(
        query_id=query_id,
        stage=RagStage.PLAN_EDIT,
        requested_features=list(requested_features),
        allowed_features=list(allowed_features),
        preserve_constraints=list(preserve_constraints),
        provider_candidates=["tencent_cloud"],
        operation_candidates=["BeautifyPic"],
        face_count=face_count,
        outbound_allowed=outbound_allowed,
        adapter_required=True,
        missing_critical_slots=list(missing_critical_slots),
        intent_slots_present=["goal", "allowed_features", "preserve_attributes"],
    )


def _query_sha256(query: RagQuery) -> str:
    return _canonical_sha256(query.model_dump(mode="json"))


def _fts_terms(query: RagQuery) -> list[str]:
    terms: set[str] = set(query.operation_candidates)
    for feature in query.requested_features:
        terms.update(_FEATURE_TERMS[feature])
    for attribute in query.preserve_constraints:
        terms.update(_PRESERVE_TERMS[attribute])
    if query.face_count is not None and query.face_count > 1:
        terms.update({"multi_face", "多人", "裁剪", "隔离"})
    if query.subject_match_route is not None:
        terms.update({"CompareFace", "same_person", "subject_match"})
    if query.safety_route is not None:
        terms.update({"ImageModeration", "content_safety", "safety"})
    if query.stage == RagStage.VERIFICATION_STRATEGY:
        terms.update({"consistency", "几何复测", "verification"})
    return sorted(term for term in terms if _SAFE_FTS_TERM.fullmatch(term))


def _fts_expression(terms: Iterable[str]) -> str:
    safe_terms = [term for term in terms if _SAFE_FTS_TERM.fullmatch(term)]
    if not safe_terms:
        raise ValueError("RAG query has no safe FTS terms")
    return " OR ".join(f'"{term}"' for term in safe_terms)


def _is_injection_like(chunk: KnowledgeChunk) -> bool:
    normalized = f"{chunk.content} {' '.join(chunk.keywords)}".casefold()
    return any(marker in normalized for marker in _KNOWLEDGE_INJECTION_MARKERS)


def _is_direct_feature_match(query: RagQuery, chunk: KnowledgeChunk) -> bool:
    if query.requested_features:
        return bool(set(query.requested_features) & set(chunk.feature_codes))
    if query.face_count is not None and query.face_count > 1:
        return "multi_face" in chunk.keywords
    if query.subject_match_route is not None:
        return "CompareFace" in chunk.keywords
    if query.safety_route is not None:
        return "ImageModeration" in chunk.keywords
    if query.stage == RagStage.VERIFICATION_STRATEGY:
        return chunk.claim_type == KnowledgeClaimType.VERIFICATION_SCOPE
    return False


def _candidate_relation(query: RagQuery, chunk: KnowledgeChunk) -> EvidenceRelation:
    if _is_direct_feature_match(query, chunk):
        return EvidenceRelation.DIRECT_EVIDENCE
    return EvidenceRelation.REFERENCE_CONTEXT


def _eligibility_reason(
    query: RagQuery,
    item: KnowledgeItem,
    chunk: KnowledgeChunk,
    relation: EvidenceRelation,
) -> str | None:
    """Apply deterministic permissions/adapter metadata before evidence is adopted."""

    if _is_injection_like(chunk):
        return "knowledge_injection_blocked"
    if relation != EvidenceRelation.DIRECT_EVIDENCE:
        return None
    if chunk.requires_adapter and item.adapter_status not in _READY_ADAPTER_STATUSES:
        return "adapter_not_ready"
    if query.adapter_required and item.adapter_status not in _READY_ADAPTER_STATUSES:
        return "adapter_not_ready"
    if (
        chunk.requires_outbound_image
        and chunk.capability_status == KnowledgeCapabilityStatus.EXECUTABLE
        and not query.outbound_allowed
    ):
        return "outbound_not_allowed"
    requested_chunk_features = set(query.requested_features) & set(chunk.feature_codes)
    if (
        query.allowed_features
        and chunk.capability_status == KnowledgeCapabilityStatus.EXECUTABLE
        and requested_chunk_features
        and not requested_chunk_features.issubset(set(query.allowed_features))
    ):
        return "requested_feature_not_authorized"
    if (
        PreserveAttribute.SKIN_TONE in query.preserve_constraints
        and EditableFeature.WHITENING in chunk.feature_codes
    ):
        return "preserve_skin_tone"
    return None


def _user_summary(item: KnowledgeItem, chunk: KnowledgeChunk, relation: EvidenceRelation) -> str:
    feature_names = {
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
    features = "、".join(feature_names[feature] for feature in chunk.feature_codes)
    if chunk.capability_status == KnowledgeCapabilityStatus.UNSUPPORTED:
        return f"当前已审核工具暂不支持{features or '该需求'}自动执行；系统会降级为手动建议。"
    if chunk.capability_status == KnowledgeCapabilityStatus.SUGGESTION_ONLY:
        return "当前图片条件需要先裁剪/隔离或人工处理，不能直接承诺只改指定人脸。"
    if chunk.capability_status == KnowledgeCapabilityStatus.NOT_APPLICABLE:
        if item.operation == "CompareFace":
            return "CompareFace 只能补充同人证据，不能证明五官已经与母版对齐。"
        if item.operation == "ImageModeration":
            return "内容安全通过不代表照片可编辑、同人或已达到母版一致。"
        return "该资料只提供边界说明，不能单独支持自动执行。"
    if relation == EvidenceRelation.REFERENCE_CONTEXT:
        return f"{item.operation} 的这条资料提供背景限制，不能单独放行自动处理。"
    return f"已审核工具支持{features or item.operation}作为候选；仍须经过后续权限和参数规则。"


def _evidence(
    *,
    item: KnowledgeItem,
    chunk: KnowledgeChunk,
    rank: int,
    fts_score: float | None,
    relation: EvidenceRelation,
    adopted: bool,
    reason_codes: list[str],
) -> KnowledgeEvidence:
    return KnowledgeEvidence(
        knowledge_id=item.knowledge_id,
        chunk_id=chunk.chunk_id,
        source_title=item.source_title,
        source_version=item.source_version,
        lifecycle_status=item.lifecycle_status,
        relation=relation,
        claim_type=chunk.claim_type,
        capability_status=chunk.capability_status,
        feature_codes=chunk.feature_codes,
        rank=rank,
        fts_score=fts_score,
        adopted=adopted,
        reason_codes=reason_codes,
        user_summary=_user_summary(item, chunk, relation),
    )


class RagP0ARetriever:
    """Metadata-first, FTS-second retriever with explicit safe fallbacks."""

    def __init__(self, store: LocalKnowledgeStore) -> None:
        self.store = store

    def retrieve(self, query: RagQuery) -> RagP0ARun:
        """Run the bounded P0-A retrieval path and persist only safe audit facts."""

        started = time.perf_counter()
        query_sha256 = _query_sha256(query)
        trace: list[dict[str, object]] = [
            {
                "step": "query_contract",
                "query_id": query.query_id,
                "query_sha256": query_sha256,
                "stage": query.stage.value,
                "requested_features": [feature.value for feature in query.requested_features],
                "provider_candidates": query.provider_candidates,
                "operation_candidates": query.operation_candidates,
                "contains_raw_user_text": False,
                "contains_photo_or_face_vector": False,
            }
        ]
        rejected: dict[str, int] = {}

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
            self.store.record_query_run(query=query, result=result, trace=trace)
            return RagP0ARun(result, tuple(trace), 0, 0, rejected)

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
                self.store.record_query_run(query=query, result=result, trace=trace)
                return RagP0ARun(result, tuple(trace), 0, 0, rejected)

            metadata_candidates = self.store.active_metadata_candidates(query)
            lifecycle_counts = self.store.lifecycle_counts(query)
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
                self.store.record_query_run(query=query, result=result, trace=trace)
                return RagP0ARun(result, tuple(trace), 0, 0, rejected)

            terms = _fts_terms(query)
            expression = _fts_expression(terms)
            fts_candidates = self.store.fts_candidates(
                query,
                fts_expression=expression,
                limit=P0A_FTS_LIMIT,
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
                    "step": "index_failure",
                    "error_type": type(exc).__name__,
                    "external_calls": 0,
                }
            )
            self.store.record_query_run(query=query, result=result, trace=trace)
            return RagP0ARun(result, tuple(trace), 0, 0, rejected)

        trace.append(
            {
                "step": "fts_retrieval",
                "term_count": len(terms),
                "candidate_limit": P0A_FTS_LIMIT,
                "returned_candidate_count": len(fts_candidates),
                "index_version": self.store.INDEX_VERSION,
            }
        )
        if not fts_candidates:
            result = self._result(
                query=query,
                query_sha256=query_sha256,
                route=RetrievalRoute.BASELINE_FALLBACK,
                reason_codes=["RETRIEVER_MISS_SUSPECT"],
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
            self.store.record_query_run(query=query, result=result, trace=trace)
            return RagP0ARun(
                result,
                tuple(trace),
                len(metadata_candidates),
                0,
                rejected,
            )

        evidences: list[KnowledgeEvidence] = []
        adopted_direct_executable = False
        adopted_direct_nonexecutable = False
        for rank, (item, chunk, score) in enumerate(fts_candidates, start=1):
            relation = _candidate_relation(query, chunk)
            rejection = _eligibility_reason(query, item, chunk, relation)
            adopted = rejection is None and relation == EvidenceRelation.DIRECT_EVIDENCE
            if rejection is not None:
                rejected[rejection] = rejected.get(rejection, 0) + 1
            if adopted and chunk.capability_status == KnowledgeCapabilityStatus.EXECUTABLE:
                adopted_direct_executable = True
            if adopted and chunk.capability_status != KnowledgeCapabilityStatus.EXECUTABLE:
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
                    item=item,
                    chunk=chunk,
                    rank=rank,
                    fts_score=score,
                    relation=relation,
                    adopted=adopted,
                    reason_codes=reason_codes,
                )
            )

        if adopted_direct_executable:
            route = RetrievalRoute.EVIDENCE_FOUND
            reason_codes = ["ACTIVE_DIRECT_EXECUTABLE_EVIDENCE", "P0A_RETRIEVAL_ONLY"]
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
        self.store.record_query_run(query=query, result=result, trace=trace)
        return RagP0ARun(
            result=result,
            trace=tuple(trace),
            metadata_candidate_count=len(metadata_candidates),
            fts_candidate_count=len(fts_candidates),
            rejected_candidate_counts=rejected,
        )

    def _conflict_evidences(
        self,
        conflicts: dict[str, list[KnowledgeItem]],
    ) -> list[KnowledgeEvidence]:
        """Project conflicting sources without inventing an executable conclusion."""

        evidences: list[KnowledgeEvidence] = []
        rank = 1
        for group_id in sorted(conflicts):
            for item in sorted(conflicts[group_id], key=lambda candidate: candidate.knowledge_id):
                chunks = self.store.chunks_for_knowledge_ids([item.knowledge_id])
                # A conflict must be explainable from both (or all) competing
                # source facts.  Do not pick a convenient first chunk and hide
                # the rest; a bounded result still blocks execution.
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
            retrieval_version=P0A_RETRIEVAL_VERSION,
            index_version=self.store.INDEX_VERSION,
            latency_ms=max(0, round((time.perf_counter() - started) * 1000)),
        )
