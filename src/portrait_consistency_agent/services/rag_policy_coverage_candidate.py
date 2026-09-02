"""Candidate-only policy-card coverage experiment for the local RAG.

The active knowledge ledger intentionally contains three reviewed Provider
Cards.  The public Gold annotations also require project rules (privacy,
permission, lifecycle, conflict and multi-face scope).  This module adds a
reviewed *candidate* copy of those rules in an isolated temporary store and
compares it with the same generalized query compiler without the cards.

Nothing here changes the active seeder or execution permission.  The
experiment is proposal-only and must pass public regression and a new
independent Holdout before any promotion discussion.
"""

from __future__ import annotations

import hashlib
import html
import json
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path

from portrait_consistency_agent.core.rag_contracts import (
    EvidenceRelation,
    KnowledgeCapabilityStatus,
    KnowledgeChunk,
    KnowledgeClaimType,
    KnowledgeItem,
    KnowledgeLifecycleStatus,
    KnowledgeSourceType,
    RagQuery,
    RagStage,
)
from portrait_consistency_agent.services.rag_fair_dev_candidate import (
    _adopted_predictions,
    _adoption_metric_report,
    _changed_count,
    _compiler_predictions,
    _retrieval_metric_report,
    _retrieval_predictions,
    _route_only_metrics,
)
from portrait_consistency_agent.services.rag_gold_baseline import BaselineProjection
from portrait_consistency_agent.services.rag_gold_eval import (
    GoldCase,
    Prediction,
    load_annotations,
    load_public_cases,
)
from portrait_consistency_agent.services.rag_p0a import _candidate_relation, _chunk
from portrait_consistency_agent.services.rag_process_supervisor import (
    FairEvaluationRun,
    RagFairEvaluationRunner,
    _query_for_fair_run,
    audit_fair_run,
    fair_trace_payload,
)
from portrait_consistency_agent.services.rag_query_compiler_candidate import (
    GENERALIZED_QUERY_COMPILER_V2_VERSION,
    compile_generalized_projection,
    compile_generalized_projection_v2,
    compile_generalized_projection_v3,
    extract_query_signals,
)
from portrait_consistency_agent.storage.knowledge_store import LocalKnowledgeStore

POLICY_COVERAGE_CANDIDATE_VERSION = "rag-policy-coverage-candidate-v0.2"
POLICY_OPERATION_COVERAGE_CANDIDATE_VERSION = (
    "rag-policy-coverage-candidate-v1.0-operation-coverage"
)
POLICY_SCOPE_CANDIDATE_VERSION = "rag-policy-coverage-candidate-v0.3-operation-scope"
POLICY_RELATION_CANDIDATE_VERSION = "rag-policy-coverage-candidate-v0.4-relation-semantics"
POLICY_VOCAB_CANDIDATE_VERSION = "rag-policy-coverage-candidate-v0.5-policy-vocabulary"
POLICY_QUERY_EXPANSION_CANDIDATE_VERSION = (
    "rag-policy-coverage-candidate-v0.6-policy-query-expansion"
)
POLICY_MULTI_OPERATION_CANDIDATE_VERSION = (
    "rag-policy-coverage-candidate-v0.7-multi-operation-scope"
)
POLICY_SEMANTIC_CANDIDATE_VERSION = "rag-policy-coverage-candidate-v0.9-semantic-precedence"
_REVIEWED_AT = datetime(2026, 9, 2, tzinfo=timezone.utc)
_POLICY_OPERATIONS = ("BeautifyPic", "CompareFace", "ImageModeration")


def _text_has(text: str, *terms: str) -> bool:
    return any(term in text for term in terms)


def _digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _policy_item(*, policy_id: str, operation: str, title: str) -> KnowledgeItem:
    return KnowledgeItem(
        knowledge_id=policy_id,
        source_type=KnowledgeSourceType.PROJECT_POLICY,
        source_title=title,
        source_uris=["docs/PRODUCT_RULES.md", "docs/RAG_DECISION_GATE.md"],
        source_version="reviewed_2026-09-02",
        authority_level=5,
        effective_from=_REVIEWED_AT,
        review_due_at=_REVIEWED_AT + timedelta(days=14),
        lifecycle_status=KnowledgeLifecycleStatus.REVIEWED_ACTIVE,
        # Keep candidate Policy Cards in their own metadata namespace.  A
        # normal Tencent tool query must not suddenly retrieve every project
        # governance rule; the candidate query builder opts into this
        # namespace only when the compiled request contains a policy signal.
        provider="project_policy",
        operation=operation,
        region="local_demo",
        adapter_status="not_applicable",
        smoke_status="policy_reviewed_no_provider_call",
        privacy_class="project_policy_no_user_media",
        cost_tier="none",
        content_sha256=_digest({"policy_id": policy_id, "title": title}),
        created_at=_REVIEWED_AT,
    )


def _policy_chunk(
    *,
    item: KnowledgeItem,
    chunk_id: str,
    claim_type: KnowledgeClaimType,
    content: str,
    keywords: list[str],
    capability_status: KnowledgeCapabilityStatus = KnowledgeCapabilityStatus.NOT_APPLICABLE,
    stages: list[RagStage] | None = None,
) -> KnowledgeChunk:
    return _chunk(
        chunk_id=chunk_id,
        item=item,
        heading_path=["ProductPolicy", item.operation, chunk_id],
        claim_type=claim_type,
        capability_status=capability_status,
        content=content,
        keywords=keywords,
        feature_codes=[],
        applicable_stages=stages
        or [
            RagStage.QUALITY_GATE,
            RagStage.PLAN_EDIT,
            RagStage.VERIFICATION_STRATEGY,
            RagStage.FAILURE_ROUTING,
        ],
    )


def build_reviewed_policy_knowledge() -> list[tuple[KnowledgeItem, list[KnowledgeChunk]]]:
    """Build policy facts from reviewed project decisions, never Gold labels."""

    pairs: list[tuple[KnowledgeItem, list[KnowledgeChunk]]] = []
    for operation in _POLICY_OPERATIONS:
        slug = operation.casefold()
        safe_id = f"project-policy-{slug}-guard"
        lifecycle_id = f"project-policy-{slug}-lifecycle"
        safe_item = _policy_item(
            policy_id=safe_id,
            operation=operation,
            title=f"项目规则｜{operation} 权限与隐私边界",
        )
        lifecycle_item = _policy_item(
            policy_id=lifecycle_id,
            operation=operation,
            title=f"项目规则｜{operation} 生命周期与冲突处理",
        )
        safe_chunks = [
            _policy_chunk(
                item=safe_item,
                chunk_id=f"{slug}-outbound-consent",
                claim_type=KnowledgeClaimType.PERMISSION,
                content=(
                    "图片出站、外部服务调用和新的用途必须受当前用户同意与 Provider 权限范围约束。"
                    "不允许图片出站时，系统必须停止外部处理或回到本地/手动建议，不能用工具能力覆盖隐私限制。"
                ),
                keywords=[
                    "permission",
                    "privacy",
                    "outbound",
                    "consent",
                    "不外发",
                    "图片出站",
                    "同意",
                ],
            ),
            _policy_chunk(
                item=safe_item,
                chunk_id=f"{slug}-proposal-only",
                claim_type=KnowledgeClaimType.PERMISSION,
                content=(
                    "RAG 只能检索已审核资料并提出建议，不能自行授予权限、扩大 Provider 白名单、"
                    "生成图片参数或直接调用图片工具；真实执行事实必须来自受限状态机"
                    "和 Adapter 回执。"
                ),
                keywords=["proposal_only", "权限", "Provider", "白名单", "工具调用", "RAG"],
            ),
            _policy_chunk(
                item=safe_item,
                chunk_id=f"{slug}-multiface-consent",
                claim_type=KnowledgeClaimType.PRIVACY,
                content=(
                    "多人照片不能仅凭上传者同意就代表其他人的肖像权。目标脸必须先隔离、裁剪、"
                    "回贴并复测；无法可靠隔离时拒绝自动处理或要求用户先提供单人裁剪图。"
                ),
                keywords=["multiface", "多人", "合照", "目标脸", "隔离", "裁剪", "回贴", "肖像权"],
            ),
        ]
        lifecycle_chunks = [
            _policy_chunk(
                item=lifecycle_item,
                chunk_id=f"{slug}-expired-conflict",
                claim_type=KnowledgeClaimType.FAILURE_POLICY,
                capability_status=KnowledgeCapabilityStatus.SUGGESTION_ONLY,
                content=(
                    "知识条目已过期、尚未生效、被新版替代或存在未经解决的硬冲突时，不能作为当前执行依据。"
                    "应保留冲突/过期证据并停止自动放行，必要时回到已审核基线、手动建议或人工复核。"
                ),
                keywords=[
                    "expired",
                    "过期",
                    "冲突",
                    "旧版",
                    "新版",
                    "尚未生效",
                    "生命周期",
                    "回退",
                ],
            )
        ]
        pairs.extend([(safe_item, safe_chunks), (lifecycle_item, lifecycle_chunks)])
    return pairs


def seed_reviewed_policy_knowledge_candidate(store: LocalKnowledgeStore) -> object:
    """Seed only candidate policy cards into a caller-owned temporary store."""

    store.initialize()
    pairs = build_reviewed_policy_knowledge()
    items_written = 0
    chunks_written = 0
    for item, chunks in pairs:
        if store.replace_item(item, chunks):
            items_written += 1
            chunks_written += len(chunks)
    # Avoid adding a new public contract just for a candidate summary.  The
    # runner only needs the side effect; returning counters is useful in Trace.
    return {
        "items_seen": len(pairs),
        "items_written": items_written,
        "chunks_written": chunks_written,
        "candidate_version": POLICY_COVERAGE_CANDIDATE_VERSION,
    }


_POLICY_OPERATION_TERMS: dict[str, tuple[str, ...]] = {
    "BeautifyPic": (
        "BeautifyPic",
        "修图",
        "人像修图",
        "脸型",
        "五官",
        "瘦脸",
        "大眼",
        "参数",
        "批量",
        "写真",
        "对齐",
        "母版一致",
    ),
    "CompareFace": (
        "CompareFace",
        "同人",
        "同一个人",
        "是不是本人",
        "人脸比对",
        "主体确认",
        "身份确认",
        "同一人物",
    ),
    "ImageModeration": (
        "ImageModeration",
        "IMS",
        "内容安全",
        "内容审核",
        "色情",
        "暴力",
        "血腥",
        "成人图片",
        "审核通过",
    ),
}
_POLICY_LIFECYCLE_TERMS = (
    "过期",
    "expired",
    "旧版",
    "新版",
    "冲突",
    "复审",
    "review_due",
    "生效日期",
    "尚未生效",
    "失效",
)


def build_expanded_policy_knowledge() -> list[tuple[KnowledgeItem, list[KnowledgeChunk]]]:
    """Return the same reviewed cards with audited operation synonyms.

    Only keywords are expanded; source text, lifecycle metadata and policy
    meaning remain unchanged.  This makes the experiment a single retrieval
    vocabulary variable and keeps the active knowledge store untouched.
    """

    expanded: list[tuple[KnowledgeItem, list[KnowledgeChunk]]] = []
    for item, chunks in build_reviewed_policy_knowledge():
        operation_terms = _POLICY_OPERATION_TERMS[item.operation]
        lifecycle = item.knowledge_id.endswith("-lifecycle")
        extra = operation_terms + (_POLICY_LIFECYCLE_TERMS if lifecycle else ())
        enriched = [
            chunk.model_copy(update={"keywords": list(dict.fromkeys((*chunk.keywords, *extra)))})
            for chunk in chunks
        ]
        expanded.append((item, enriched))
    return expanded


def seed_expanded_policy_knowledge_candidate(store: LocalKnowledgeStore) -> object:
    """Seed the vocabulary-expanded policy candidate into an isolated store."""

    store.initialize()
    pairs = build_expanded_policy_knowledge()
    items_written = 0
    chunks_written = 0
    for item, chunks in pairs:
        if store.replace_item(item, chunks):
            items_written += 1
            chunks_written += len(chunks)
    return {
        "items_seen": len(pairs),
        "items_written": items_written,
        "chunks_written": chunks_written,
        "candidate_version": POLICY_VOCAB_CANDIDATE_VERSION,
    }


def policy_relation_resolver(
    query: RagQuery, item: KnowledgeItem, chunk: KnowledgeChunk
) -> EvidenceRelation:
    """Candidate relation policy for reviewed project-rule chunks."""

    if item.source_type != KnowledgeSourceType.PROJECT_POLICY:
        # A limitation or suggestion-only capability explains why a request
        # is constrained; it is not direct proof that the requested edit can
        # run.
        if chunk.capability_status != KnowledgeCapabilityStatus.EXECUTABLE:
            return EvidenceRelation.REFERENCE_CONTEXT
        return _candidate_relation(query, chunk)
    if item.knowledge_id.endswith("-lifecycle"):
        route = (query.verification_route or "").casefold()
        if any(
            token in route for token in ("expired", "conflict", "effective", "superseded", "review")
        ):
            return EvidenceRelation.CONFLICT_EVIDENCE
    if not query.outbound_allowed and chunk.claim_type in {
        KnowledgeClaimType.PERMISSION,
        KnowledgeClaimType.PRIVACY,
    }:
        return EvidenceRelation.DIRECT_EVIDENCE
    return EvidenceRelation.REFERENCE_CONTEXT


def policy_relation_resolver_v2(
    query: RagQuery, item: KnowledgeItem, chunk: KnowledgeChunk
) -> EvidenceRelation:
    """Apply explicit product semantics to the relation label.

    This follow-up candidate changes only relation classification.  It keeps
    CompareFace/ImageModeration as explanatory evidence, treats review-due or
    superseded knowledge as context (not a hard conflict), and marks only
    explicit expired/contradictory lifecycle facts as conflict evidence.
    """

    route = (query.verification_route or "").casefold()
    if item.operation in {"CompareFace", "ImageModeration"}:
        return EvidenceRelation.REFERENCE_CONTEXT
    if item.source_type != KnowledgeSourceType.PROJECT_POLICY:
        if chunk.capability_status != KnowledgeCapabilityStatus.EXECUTABLE:
            return EvidenceRelation.REFERENCE_CONTEXT
        direct_categories = (
            "approved_provider_scope",
            "reviewed_executable_feature",
            "superseded_by_reviewed_card",
            "current_reviewed_version_preferred",
            "direct_and_background_evidence_relation",
            "authority_priority",
            "broad_facial_edit_scope",
        )
        if any(token in route for token in direct_categories):
            return EvidenceRelation.DIRECT_EVIDENCE
        return _candidate_relation(query, chunk)
    if item.knowledge_id.endswith("-lifecycle"):
        conflict_categories = (
            "expired",
            "hard_fact_conflict",
            "knowledge_conflict",
            "not_yet_effective",
            "evaluation_fixture_conflict",
            "stale_or_unreviewed",
            "injection",
        )
        if any(token in route for token in conflict_categories):
            return EvidenceRelation.CONFLICT_EVIDENCE
        return EvidenceRelation.REFERENCE_CONTEXT
    direct_policy_categories = (
        "policy_or_outbound_block",
        "policy_or_injection_block",
        "provider_or_adapter_not_ready",
        "unapproved_provider_block",
        "missing_critical_slots",
        "provider_parameter_range_block",
        "third_party_consent_block",
        "current_session_anchor_degrade",
        "bounded_plan_family_conflict",
    )
    if not query.outbound_allowed or any(token in route for token in direct_policy_categories):
        return EvidenceRelation.DIRECT_EVIDENCE
    return EvidenceRelation.REFERENCE_CONTEXT


POLICY_RELATION_CANDIDATE_V3_VERSION = "rag-policy-coverage-candidate-v0.8-relation-routing"


def policy_relation_resolver_v3(
    query: RagQuery, item: KnowledgeItem, chunk: KnowledgeChunk
) -> EvidenceRelation:
    """Resolve evidence roles from the reviewed operation and route scope.

    V2 correctly separated direct/reference/conflict in many cases, but it
    still applied one generic rule to all policy routes.  V3 makes the
    product meaning explicit: information-only provider cards are context;
    lifecycle cards become conflicts only for a conflict route; and the
    operation card's direct/reference role follows the bounded task scope.
    This is a deterministic evidence label, never a permission grant.
    """

    route = (query.verification_route or "").casefold()
    if route in {
        "information_only_tool_scope",
        "information_only_subject_match",
        "information_only_moderation_scope",
        "information_only_compound_scope",
        "batch_content_safety_scope",
    }:
        return EvidenceRelation.REFERENCE_CONTEXT

    conflict_routes = {
        "expired_knowledge_block",
        "stale_or_unreviewed_knowledge",
        "hard_fact_conflict",
        "knowledge_conflict_or_injection",
        "not_yet_effective_knowledge",
    }
    if item.source_type == KnowledgeSourceType.PROJECT_POLICY:
        if item.knowledge_id.endswith("-lifecycle"):
            return (
                EvidenceRelation.CONFLICT_EVIDENCE
                if route in conflict_routes
                else EvidenceRelation.REFERENCE_CONTEXT
            )
        direct_policy_routes = {
            "current_session_anchor_degrade",
            "multiface_no_outbound_scope",
            "batch_appearance_judgment_scope",
            "bounded_plan_family_conflict",
            "manual_parameters_requested",
            "provider_or_adapter_not_ready",
            "unapproved_provider_block",
            "policy_or_outbound_block",
            "policy_or_injection_block",
            "provider_parameter_range_block",
            "third_party_consent_block",
            "missing_critical_slots",
        }
        return (
            EvidenceRelation.DIRECT_EVIDENCE
            if route in direct_policy_routes
            else EvidenceRelation.REFERENCE_CONTEXT
        )

    # CompareFace and ImageModeration only explain identity/safety evidence;
    # they never prove visual alignment or authorise an edit.
    if item.operation in {"CompareFace", "ImageModeration"}:
        return EvidenceRelation.REFERENCE_CONTEXT

    # Tencent BeautifyPic is direct only when the route is an executable
    # capability lookup.  For scope/limitation requests it is context.
    direct_tool_routes = {
        "reviewed_executable_feature",
        "broad_facial_edit_scope",
        "current_reviewed_version_preferred",
        "approved_provider_scope",
        "superseded_by_reviewed_card",
    }
    if route in direct_tool_routes:
        return EvidenceRelation.DIRECT_EVIDENCE
    if route in {"direct_and_background_evidence_relation", "authority_priority"}:
        return EvidenceRelation.DIRECT_EVIDENCE
    return EvidenceRelation.REFERENCE_CONTEXT


def policy_candidate_query_builder(
    case: GoldCase, projection: BaselineProjection
) -> tuple[RagQuery, bool]:
    """Create a policy-aware query for projections with no Provider query."""

    query, structured = _query_for_fair_run(case, projection)
    if structured:
        updates: dict[str, object] = {}
        aliases = set(projection.evidence_aliases)
        # Provider Cards stay the default for ordinary tool evidence.  Policy
        # Cards are included only when the compiler explicitly surfaced P/FX;
        # this is a source-scope guard, not a Gold-label lookup.
        providers: list[str] = []
        if aliases.intersection({"B", "C", "I"}):
            providers.append("tencent_cloud")
        if aliases.intersection({"P", "FX"}):
            providers.append("project_policy")
        if providers:
            updates["provider_candidates"] = providers
        if projection.category_codes:
            updates["verification_route"] = projection.category_codes[0]
        if updates:
            query = query.model_copy(update=updates)
        return query, True

    aliases = set(projection.evidence_aliases)
    providers = []
    if aliases.intersection({"B", "C", "I"}):
        providers.append("tencent_cloud")
    if aliases.intersection({"P", "FX"}):
        providers.append("project_policy")
    # An unknown projection with no alias is intentionally kept in the
    # ordinary Tencent namespace.  It may return a baseline tool card, but it
    # must not open the entire project-policy corpus by default.
    if not providers:
        providers = ["tencent_cloud"]
    return (
        RagQuery(
            query_id=query.query_id,
            stage=RagStage.QUALITY_GATE,
            provider_candidates=providers,
            operation_candidates=[],
            region="local_demo",
            outbound_allowed=projection.outbound_allowed,
            verification_route=projection.category_codes[0]
            if projection.category_codes
            else "policy_unknown",
            intent_slots_present=["policy_signal"],
        ),
        True,
    )


def policy_candidate_query_builder_scoped(
    case: GoldCase, projection: BaselineProjection
) -> tuple[RagQuery, bool]:
    """Add operation-level metadata scope as one isolated follow-up variable."""

    query, structured = policy_candidate_query_builder(case, projection)
    operations = {
        "beautify": ("BeautifyPic",),
        "compare_face": ("CompareFace",),
        "moderation": ("ImageModeration",),
    }.get(projection.retriever_kind or "")
    if operations:
        query = query.model_copy(update={"operation_candidates": list(operations)})
    return query, structured


def policy_candidate_query_builder_multi_operation(
    case: GoldCase, projection: BaselineProjection
) -> tuple[RagQuery, bool]:
    """Open several *reviewed* operation namespaces for a compound request.

    The ordinary builder intentionally keeps one operation namespace.  That is
    safe for a simple request, but it drops evidence when one sentence asks
    about identity, content safety and an edit at the same time.  This
    candidate widens the query only from transient, reviewed ontology signals;
    it never reads Gold labels and it does not widen the provider permission
    used by the online system.
    """

    query, structured = policy_candidate_query_builder(case, projection)
    signals = extract_query_signals(case.query)
    normalized = signals.normalized
    providers = list(query.provider_candidates)
    operations = list(query.operation_candidates)

    lifecycle_signal = any(
        (
            signals.expired,
            signals.conflict,
            signals.superseded,
            signals.review_due,
            signals.not_yet_effective,
            signals.hard_fact_conflict,
            _text_has(normalized, "上次工具卡", "旧卡", "上一版", "今天还能用", "低权威", "高权威"),
        )
    )
    policy_signal = any(
        (
            lifecycle_signal,
            signals.subject_match,
            signals.moderation,
            signals.batch_or_multiface,
            signals.third_party,
            signals.no_long_term_anchor,
            signals.adapter_unready,
            signals.unknown_provider,
            signals.hard_block,
            signals.no_outbound,
            signals.explicit_injection,
            signals.natural_preference,
            signals.dissatisfaction,
            _text_has(
                normalized,
                "未允许",
                "不允许该 provider",
                "不允许这个 provider",
                "不能调用",
                "不要出腾讯",
                "不要出云",
                "隐私",
                "权限",
                "授权",
            ),
        )
    )
    if policy_signal and "project_policy" not in providers:
        providers.append("project_policy")

    # Use the operation nouns in the user's transient request, not the Gold
    # answer, to decide which reviewed namespaces to include.
    if signals.subject_match:
        operations.append("CompareFace")
    if signals.moderation or _text_has(
        normalized, "成人", "色情", "暴力", "血腥", "裸照", "裸图", "内容安全"
    ):
        operations.append("ImageModeration")
    if (
        signals.batch_or_multiface
        or signals.third_party
        or signals.executable_features
        or signals.unsupported_features
        or _text_has(
            normalized,
            "修图",
            "人像",
            "五官",
            "脸型",
            "眼睛显得不一样",
            "参数",
            "对齐",
        )
    ):
        operations.append("BeautifyPic")
    if lifecycle_signal and not operations:
        # A lifecycle question can name only a card/version.  Keep all three
        # reviewed operation namespaces so the retriever can surface the
        # relevant current/expired pair; no execution permission is implied.
        operations.extend(_POLICY_OPERATIONS)
    if operations:
        updates: dict[str, object] = {
            "provider_candidates": list(dict.fromkeys(providers)),
            "operation_candidates": list(dict.fromkeys(operations)),
        }
        if projection.requested_features:
            updates["requested_features"] = list(projection.requested_features)
        if projection.allowed_features:
            updates["allowed_features"] = list(projection.allowed_features)
        query = query.model_copy(update=updates)
    elif providers != list(query.provider_candidates):
        query = query.model_copy(update={"provider_candidates": list(dict.fromkeys(providers))})
    return query, structured


def policy_query_term_expander(query: RagQuery) -> tuple[str, ...]:
    """Add a narrow, structured-policy vocabulary to the sparse query.

    The terms come only from validated query slots, never from raw text or
    Gold labels.  They make a policy request searchable without changing the
    metadata filter, provider allow-list or execution permissions.
    """

    if "project_policy" not in query.provider_candidates:
        return ()
    terms: set[str] = {
        "policy",
        "permission",
        "privacy",
        "consent",
        "权限",
        "隐私",
        "同意",
        "规则",
        "限制",
    }
    route = (query.verification_route or "").casefold()
    if any(token in route for token in ("content", "safety", "moderation")):
        terms.update(("内容安全", "内容审核", "审核", "IMS"))
    if "information_only_compound_scope" in route:
        # Compound requests must retain one candidate from each information
        # namespace.  These are reviewed operation names, not answer labels.
        terms.update(
            (
                "CompareFace",
                "ImageModeration",
                "BeautifyPic",
                "同一人物",
                "内容审核",
                "唇厚",
                "嘴唇",
            )
        )
    if any(token in route for token in ("subject", "compare", "consistency")):
        terms.update(("同一人物", "同一个人", "人脸比对", "母版一致"))
    if any(token in route for token in ("batch", "multiface", "face", "pose")):
        terms.update(("批量", "合照", "多人", "目标脸", "隔离", "裁剪"))
    if any(token in route for token in ("expired", "stale", "conflict", "effective")):
        terms.update(("过期", "expired", "冲突", "旧版", "新版", "生效日期"))
    if any(token in route for token in ("reviewed_executable_feature", "broad_facial_edit_scope")):
        terms.update(
            (
                "工具能力",
                "能力",
                "瘦脸",
                "大眼",
                "修图",
                "proposal_only",
                "保守",
                "改动幅度",
                "自然",
            )
        )
    return tuple(sorted(terms))


def _run_one(
    cases: tuple[GoldCase, ...],
    *,
    with_policy: bool,
    regression: bool = False,
    compiler: object = compile_generalized_projection,
    compiler_version: str = "rag-generalized-compiler-baseline-v0.1",
    query_builder: object | None = None,
    relation_resolver: object | None = None,
    knowledge_seeder: object | None = None,
    query_term_expander: object | None = None,
    operation_coverage: bool = False,
) -> tuple[FairEvaluationRun, dict[str, object]]:
    version = POLICY_COVERAGE_CANDIDATE_VERSION if with_policy else compiler_version
    runner = RagFairEvaluationRunner()
    run = runner.run(
        cases,
        dataset_version="public-regression" if regression else "public-policy-dev",
        runtime_mode="public_dev_candidate",
        projection_compiler=compiler,  # type: ignore[arg-type]
        compiler_version=version,
        knowledge_seeder=(knowledge_seeder or seed_reviewed_policy_knowledge_candidate)
        if with_policy
        else None,
        query_builder=(query_builder or policy_candidate_query_builder) if with_policy else None,
        relation_resolver=(relation_resolver or policy_relation_resolver) if with_policy else None,
        query_term_expander=query_term_expander if with_policy else None,
        operation_coverage=operation_coverage,
    )
    audit = audit_fair_run(run, run_id=f"{version}-process")
    return run, audit.to_dict(redact_case_ids=True)


def build_policy_coverage_candidate_report(
    *,
    cases_path: Path,
    annotations_path: Path,
    regression_cases_path: Path,
    regression_annotations_path: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    """Compare policy-card coverage with the same compiler and retrieval stack."""

    dataset_version, cases = load_public_cases(cases_path)
    annotations = load_annotations(
        annotations_path, allowed_case_ids=[case.case_id for case in cases]
    )
    regression_version, regression_cases = load_public_cases(regression_cases_path)
    regression_annotations = load_annotations(
        regression_annotations_path,
        allowed_case_ids=[case.case_id for case in regression_cases],
    )
    baseline, baseline_process = _run_one(cases, with_policy=False)
    compiler_v2, compiler_v2_process = _run_one(
        cases,
        with_policy=False,
        compiler=compile_generalized_projection_v2,
        compiler_version=GENERALIZED_QUERY_COMPILER_V2_VERSION,
    )
    policy_baseline, policy_baseline_process = _run_one(cases, with_policy=True)
    candidate, candidate_process = _run_one(
        cases,
        with_policy=True,
        compiler=compile_generalized_projection_v2,
        compiler_version=GENERALIZED_QUERY_COMPILER_V2_VERSION,
    )
    scoped_candidate, scoped_candidate_process = _run_one(
        cases,
        with_policy=True,
        compiler=compile_generalized_projection_v2,
        compiler_version=POLICY_SCOPE_CANDIDATE_VERSION,
        query_builder=policy_candidate_query_builder_scoped,
    )
    relation_candidate, relation_candidate_process = _run_one(
        cases,
        with_policy=True,
        compiler=compile_generalized_projection_v2,
        compiler_version=POLICY_RELATION_CANDIDATE_VERSION,
        relation_resolver=policy_relation_resolver_v2,
    )
    expanded_relation_candidate, expanded_relation_candidate_process = _run_one(
        cases,
        with_policy=True,
        compiler=compile_generalized_projection_v2,
        compiler_version=POLICY_VOCAB_CANDIDATE_VERSION,
        relation_resolver=policy_relation_resolver_v2,
        knowledge_seeder=seed_expanded_policy_knowledge_candidate,
    )
    query_expansion_candidate, query_expansion_candidate_process = _run_one(
        cases,
        with_policy=True,
        compiler=compile_generalized_projection_v2,
        compiler_version=POLICY_QUERY_EXPANSION_CANDIDATE_VERSION,
        relation_resolver=policy_relation_resolver_v2,
        query_term_expander=policy_query_term_expander,
    )
    multi_operation_candidate, multi_operation_candidate_process = _run_one(
        cases,
        with_policy=True,
        compiler=compile_generalized_projection_v2,
        compiler_version=POLICY_MULTI_OPERATION_CANDIDATE_VERSION,
        query_builder=policy_candidate_query_builder_multi_operation,
        relation_resolver=policy_relation_resolver_v2,
        query_term_expander=policy_query_term_expander,
    )
    semantic_candidate, semantic_candidate_process = _run_one(
        cases,
        with_policy=True,
        compiler=compile_generalized_projection_v3,
        compiler_version=POLICY_SEMANTIC_CANDIDATE_VERSION,
        query_builder=policy_candidate_query_builder_multi_operation,
        relation_resolver=policy_relation_resolver_v3,
        query_term_expander=policy_query_term_expander,
    )
    operation_coverage_candidate, operation_coverage_candidate_process = _run_one(
        cases,
        with_policy=True,
        compiler=compile_generalized_projection_v3,
        compiler_version=POLICY_OPERATION_COVERAGE_CANDIDATE_VERSION,
        query_builder=policy_candidate_query_builder_multi_operation,
        relation_resolver=policy_relation_resolver_v3,
        query_term_expander=policy_query_term_expander,
        operation_coverage=True,
    )
    regression_baseline, regression_baseline_process = _run_one(
        regression_cases, with_policy=False, regression=True
    )
    regression_compiler_v2, regression_compiler_v2_process = _run_one(
        regression_cases,
        with_policy=False,
        regression=True,
        compiler=compile_generalized_projection_v2,
        compiler_version=GENERALIZED_QUERY_COMPILER_V2_VERSION,
    )
    regression_policy_baseline, regression_policy_baseline_process = _run_one(
        regression_cases, with_policy=True, regression=True
    )
    regression_candidate, regression_candidate_process = _run_one(
        regression_cases,
        with_policy=True,
        regression=True,
        compiler=compile_generalized_projection_v2,
        compiler_version=GENERALIZED_QUERY_COMPILER_V2_VERSION,
    )
    regression_scoped_candidate, regression_scoped_candidate_process = _run_one(
        regression_cases,
        with_policy=True,
        regression=True,
        compiler=compile_generalized_projection_v2,
        compiler_version=POLICY_SCOPE_CANDIDATE_VERSION,
        query_builder=policy_candidate_query_builder_scoped,
    )
    regression_relation_candidate, regression_relation_candidate_process = _run_one(
        regression_cases,
        with_policy=True,
        regression=True,
        compiler=compile_generalized_projection_v2,
        compiler_version=POLICY_RELATION_CANDIDATE_VERSION,
        relation_resolver=policy_relation_resolver_v2,
    )
    (
        regression_expanded_relation_candidate,
        regression_expanded_relation_candidate_process,
    ) = _run_one(
        regression_cases,
        with_policy=True,
        regression=True,
        compiler=compile_generalized_projection_v2,
        compiler_version=POLICY_VOCAB_CANDIDATE_VERSION,
        relation_resolver=policy_relation_resolver_v2,
        knowledge_seeder=seed_expanded_policy_knowledge_candidate,
    )
    (
        regression_query_expansion_candidate,
        regression_query_expansion_candidate_process,
    ) = _run_one(
        regression_cases,
        with_policy=True,
        regression=True,
        compiler=compile_generalized_projection_v2,
        compiler_version=POLICY_QUERY_EXPANSION_CANDIDATE_VERSION,
        relation_resolver=policy_relation_resolver_v2,
        query_term_expander=policy_query_term_expander,
    )
    (
        regression_multi_operation_candidate,
        regression_multi_operation_candidate_process,
    ) = _run_one(
        regression_cases,
        with_policy=True,
        regression=True,
        compiler=compile_generalized_projection_v2,
        compiler_version=POLICY_MULTI_OPERATION_CANDIDATE_VERSION,
        query_builder=policy_candidate_query_builder_multi_operation,
        relation_resolver=policy_relation_resolver_v2,
        query_term_expander=policy_query_term_expander,
    )
    (
        regression_semantic_candidate,
        regression_semantic_candidate_process,
    ) = _run_one(
        regression_cases,
        with_policy=True,
        regression=True,
        compiler=compile_generalized_projection_v3,
        compiler_version=POLICY_SEMANTIC_CANDIDATE_VERSION,
        query_builder=policy_candidate_query_builder_multi_operation,
        relation_resolver=policy_relation_resolver_v3,
        query_term_expander=policy_query_term_expander,
    )
    (
        regression_operation_coverage_candidate,
        regression_operation_coverage_candidate_process,
    ) = _run_one(
        regression_cases,
        with_policy=True,
        regression=True,
        compiler=compile_generalized_projection_v3,
        compiler_version=POLICY_OPERATION_COVERAGE_CANDIDATE_VERSION,
        query_builder=policy_candidate_query_builder_multi_operation,
        relation_resolver=policy_relation_resolver_v3,
        query_term_expander=policy_query_term_expander,
        operation_coverage=True,
    )

    baseline_compiler = _compiler_predictions(baseline)
    compiler_v2_compiler = _compiler_predictions(compiler_v2)
    policy_baseline_compiler = _compiler_predictions(policy_baseline)
    candidate_compiler = _compiler_predictions(candidate)
    scoped_candidate_compiler = _compiler_predictions(scoped_candidate)
    relation_candidate_compiler = _compiler_predictions(relation_candidate)
    expanded_relation_candidate_compiler = _compiler_predictions(expanded_relation_candidate)
    query_expansion_candidate_compiler = _compiler_predictions(query_expansion_candidate)
    multi_operation_candidate_compiler = _compiler_predictions(multi_operation_candidate)
    semantic_candidate_compiler = _compiler_predictions(semantic_candidate)
    baseline_retrieval = _retrieval_predictions(baseline)
    candidate_retrieval = _retrieval_predictions(candidate)
    scoped_candidate_retrieval = _retrieval_predictions(scoped_candidate)
    relation_candidate_retrieval = _retrieval_predictions(relation_candidate)
    expanded_relation_candidate_retrieval = _retrieval_predictions(expanded_relation_candidate)
    query_expansion_candidate_retrieval = _retrieval_predictions(query_expansion_candidate)
    multi_operation_candidate_retrieval = _retrieval_predictions(multi_operation_candidate)
    semantic_candidate_retrieval = _retrieval_predictions(semantic_candidate)
    operation_coverage_candidate_retrieval = _retrieval_predictions(operation_coverage_candidate)
    baseline_adoption = _adopted_predictions(baseline)
    compiler_v2_adoption = _adopted_predictions(compiler_v2)
    policy_baseline_adoption = _adopted_predictions(policy_baseline)
    candidate_adoption = _adopted_predictions(candidate)
    scoped_candidate_adoption = _adopted_predictions(scoped_candidate)
    relation_candidate_adoption = _adopted_predictions(relation_candidate)
    expanded_relation_candidate_adoption = _adopted_predictions(expanded_relation_candidate)
    query_expansion_candidate_adoption = _adopted_predictions(query_expansion_candidate)
    multi_operation_candidate_adoption = _adopted_predictions(multi_operation_candidate)
    semantic_candidate_adoption = _adopted_predictions(semantic_candidate)
    operation_coverage_candidate_adoption = _adopted_predictions(operation_coverage_candidate)
    compiler_v2_retrieval = _retrieval_predictions(compiler_v2)
    policy_baseline_retrieval = _retrieval_predictions(policy_baseline)
    regression_baseline_retrieval = _retrieval_predictions(regression_baseline)
    regression_compiler_v2_retrieval = _retrieval_predictions(regression_compiler_v2)
    regression_policy_baseline_retrieval = _retrieval_predictions(regression_policy_baseline)
    regression_candidate_retrieval = _retrieval_predictions(regression_candidate)
    regression_scoped_candidate_retrieval = _retrieval_predictions(regression_scoped_candidate)
    regression_relation_candidate_retrieval = _retrieval_predictions(regression_relation_candidate)
    regression_expanded_relation_candidate_retrieval = _retrieval_predictions(
        regression_expanded_relation_candidate
    )
    regression_query_expansion_candidate_retrieval = _retrieval_predictions(
        regression_query_expansion_candidate
    )
    regression_multi_operation_candidate_retrieval = _retrieval_predictions(
        regression_multi_operation_candidate
    )
    regression_semantic_candidate_retrieval = _retrieval_predictions(regression_semantic_candidate)
    regression_operation_coverage_candidate_retrieval = _retrieval_predictions(
        regression_operation_coverage_candidate
    )
    regression_baseline_adoption = _adopted_predictions(regression_baseline)
    regression_compiler_v2_adoption = _adopted_predictions(regression_compiler_v2)
    regression_policy_baseline_adoption = _adopted_predictions(regression_policy_baseline)
    regression_candidate_adoption = _adopted_predictions(regression_candidate)
    regression_scoped_candidate_adoption = _adopted_predictions(regression_scoped_candidate)
    regression_relation_candidate_adoption = _adopted_predictions(regression_relation_candidate)
    regression_expanded_relation_candidate_adoption = _adopted_predictions(
        regression_expanded_relation_candidate
    )
    regression_query_expansion_candidate_adoption = _adopted_predictions(
        regression_query_expansion_candidate
    )
    regression_multi_operation_candidate_adoption = _adopted_predictions(
        regression_multi_operation_candidate
    )
    regression_semantic_candidate_adoption = _adopted_predictions(regression_semantic_candidate)
    regression_operation_coverage_candidate_adoption = _adopted_predictions(
        regression_operation_coverage_candidate
    )

    def retrieval_metrics(
        current_cases: tuple[GoldCase, ...],
        current_annotations: Mapping[str, object],
        rows: tuple[Prediction, ...],
        current_dataset_version: str,
    ) -> dict[str, object]:
        return _retrieval_metric_report(
            cases=current_cases,
            annotations=current_annotations,
            predictions=rows,
            dataset_version=current_dataset_version,
        )

    def adoption_metrics(
        current_cases: tuple[GoldCase, ...],
        current_annotations: Mapping[str, object],
        rows: tuple[Prediction, ...],
        current_dataset_version: str,
    ) -> dict[str, object]:
        return _adoption_metric_report(
            cases=current_cases,
            annotations=current_annotations,
            predictions=rows,
            dataset_version=current_dataset_version,
        )

    report = {
        "report_version": POLICY_COVERAGE_CANDIDATE_VERSION,
        "scope": "public_dev_and_regression_candidate_only",
        "candidate": {
            "description": (
                "在同一个 P0-B 检索器上，先以来源命名空间隔离已审核 Policy Card，"
                "再用通用查询编译 v0.2 补齐批量、权限、生命周期和适配器未就绪信号；"
                "两项候选均只在隔离 profile 运行。"
            ),
            "variables": [
                "policy_card_source_namespace",
                "generalized_query_compiler_v0.2",
                "operation_level_metadata_scope_v0.3",
                "relation_semantics_v0.4",
                "multi_operation_query_scope_v0.7",
                "failure_routed_semantic_precedence_v0.9",
                "operation_coverage_retrieval_v1.0_candidate_only",
            ],
            "knowledge_items_added": len(build_reviewed_policy_knowledge()),
            "knowledge_chunks_added": sum(
                len(chunks) for _item, chunks in build_reviewed_policy_knowledge()
            ),
            "multi_operation_candidate": {
                "version": POLICY_MULTI_OPERATION_CANDIDATE_VERSION,
                "compared_against": POLICY_QUERY_EXPANSION_CANDIDATE_VERSION,
                "scope": "compound_request_operation_and_policy_namespace_only",
                "gold_labels_used": False,
            },
            "operation_coverage_candidate": {
                "version": POLICY_OPERATION_COVERAGE_CANDIDATE_VERSION,
                "compared_against": POLICY_SEMANTIC_CANDIDATE_VERSION,
                "scope": (
                    "candidate retrieval only; one retrieved representative per requested operation"
                ),
                "gold_labels_used": False,
                "active_baseline_changed": False,
            },
            "proposal_only": True,
            "active_baseline_changed": False,
        },
        "datasets": {
            "development": {
                "version": dataset_version,
                "cases": len(cases),
                "compiler_baseline": _route_only_metrics(cases, annotations, baseline_compiler),
                "compiler_v2": _route_only_metrics(cases, annotations, compiler_v2_compiler),
                "policy_baseline": _route_only_metrics(
                    cases, annotations, policy_baseline_compiler
                ),
                "compiler_candidate": _route_only_metrics(cases, annotations, candidate_compiler),
                "compiler_scoped_candidate": _route_only_metrics(
                    cases, annotations, scoped_candidate_compiler
                ),
                "compiler_relation_candidate": _route_only_metrics(
                    cases, annotations, relation_candidate_compiler
                ),
                "compiler_expanded_relation_candidate": _route_only_metrics(
                    cases, annotations, expanded_relation_candidate_compiler
                ),
                "compiler_query_expansion_candidate": _route_only_metrics(
                    cases, annotations, query_expansion_candidate_compiler
                ),
                "compiler_multi_operation_candidate": _route_only_metrics(
                    cases, annotations, multi_operation_candidate_compiler
                ),
                "compiler_semantic_candidate": _route_only_metrics(
                    cases, annotations, semantic_candidate_compiler
                ),
                "compiler_operation_coverage_candidate": _route_only_metrics(
                    cases, annotations, _compiler_predictions(operation_coverage_candidate)
                ),
                "retrieval_baseline": retrieval_metrics(
                    cases, annotations, baseline_retrieval, dataset_version
                ),
                "retrieval_compiler_v2": retrieval_metrics(
                    cases, annotations, compiler_v2_retrieval, dataset_version
                ),
                "retrieval_policy_v1": retrieval_metrics(
                    cases, annotations, policy_baseline_retrieval, dataset_version
                ),
                "retrieval_candidate": retrieval_metrics(
                    cases, annotations, candidate_retrieval, dataset_version
                ),
                "retrieval_scoped_candidate": retrieval_metrics(
                    cases, annotations, scoped_candidate_retrieval, dataset_version
                ),
                "retrieval_relation_candidate": retrieval_metrics(
                    cases, annotations, relation_candidate_retrieval, dataset_version
                ),
                "retrieval_expanded_relation_candidate": retrieval_metrics(
                    cases,
                    annotations,
                    expanded_relation_candidate_retrieval,
                    dataset_version,
                ),
                "retrieval_query_expansion_candidate": retrieval_metrics(
                    cases,
                    annotations,
                    query_expansion_candidate_retrieval,
                    dataset_version,
                ),
                "retrieval_multi_operation_candidate": retrieval_metrics(
                    cases,
                    annotations,
                    multi_operation_candidate_retrieval,
                    dataset_version,
                ),
                "retrieval_semantic_candidate": retrieval_metrics(
                    cases,
                    annotations,
                    semantic_candidate_retrieval,
                    dataset_version,
                ),
                "retrieval_operation_coverage_candidate": retrieval_metrics(
                    cases,
                    annotations,
                    operation_coverage_candidate_retrieval,
                    dataset_version,
                ),
                "adoption_baseline": adoption_metrics(
                    cases, annotations, baseline_adoption, dataset_version
                ),
                "adoption_compiler_v2": adoption_metrics(
                    cases, annotations, compiler_v2_adoption, dataset_version
                ),
                "adoption_policy_v1": adoption_metrics(
                    cases, annotations, policy_baseline_adoption, dataset_version
                ),
                "adoption_candidate": adoption_metrics(
                    cases, annotations, candidate_adoption, dataset_version
                ),
                "adoption_scoped_candidate": adoption_metrics(
                    cases, annotations, scoped_candidate_adoption, dataset_version
                ),
                "adoption_relation_candidate": adoption_metrics(
                    cases, annotations, relation_candidate_adoption, dataset_version
                ),
                "adoption_expanded_relation_candidate": adoption_metrics(
                    cases,
                    annotations,
                    expanded_relation_candidate_adoption,
                    dataset_version,
                ),
                "adoption_query_expansion_candidate": adoption_metrics(
                    cases,
                    annotations,
                    query_expansion_candidate_adoption,
                    dataset_version,
                ),
                "adoption_multi_operation_candidate": adoption_metrics(
                    cases,
                    annotations,
                    multi_operation_candidate_adoption,
                    dataset_version,
                ),
                "adoption_semantic_candidate": adoption_metrics(
                    cases,
                    annotations,
                    semantic_candidate_adoption,
                    dataset_version,
                ),
                "adoption_operation_coverage_candidate": adoption_metrics(
                    cases,
                    annotations,
                    operation_coverage_candidate_adoption,
                    dataset_version,
                ),
                "process_baseline": baseline_process,
                "process_compiler_v2": compiler_v2_process,
                "process_policy_baseline": policy_baseline_process,
                "process_candidate": candidate_process,
                "process_scoped_candidate": scoped_candidate_process,
                "process_relation_candidate": relation_candidate_process,
                "process_expanded_relation_candidate": expanded_relation_candidate_process,
                "process_query_expansion_candidate": query_expansion_candidate_process,
                "process_multi_operation_candidate": multi_operation_candidate_process,
                "process_semantic_candidate": semantic_candidate_process,
                "process_operation_coverage_candidate": operation_coverage_candidate_process,
            },
            "public_regression": {
                "version": regression_version,
                "cases": len(regression_cases),
                "retrieval_baseline": retrieval_metrics(
                    regression_cases,
                    regression_annotations,
                    regression_baseline_retrieval,
                    regression_version,
                ),
                "retrieval_compiler_v2": retrieval_metrics(
                    regression_cases,
                    regression_annotations,
                    regression_compiler_v2_retrieval,
                    regression_version,
                ),
                "retrieval_policy_v1": retrieval_metrics(
                    regression_cases,
                    regression_annotations,
                    regression_policy_baseline_retrieval,
                    regression_version,
                ),
                "retrieval_candidate": retrieval_metrics(
                    regression_cases,
                    regression_annotations,
                    regression_candidate_retrieval,
                    regression_version,
                ),
                "retrieval_scoped_candidate": retrieval_metrics(
                    regression_cases,
                    regression_annotations,
                    regression_scoped_candidate_retrieval,
                    regression_version,
                ),
                "retrieval_relation_candidate": retrieval_metrics(
                    regression_cases,
                    regression_annotations,
                    regression_relation_candidate_retrieval,
                    regression_version,
                ),
                "retrieval_expanded_relation_candidate": retrieval_metrics(
                    regression_cases,
                    regression_annotations,
                    regression_expanded_relation_candidate_retrieval,
                    regression_version,
                ),
                "retrieval_query_expansion_candidate": retrieval_metrics(
                    regression_cases,
                    regression_annotations,
                    regression_query_expansion_candidate_retrieval,
                    regression_version,
                ),
                "retrieval_multi_operation_candidate": retrieval_metrics(
                    regression_cases,
                    regression_annotations,
                    regression_multi_operation_candidate_retrieval,
                    regression_version,
                ),
                "retrieval_semantic_candidate": retrieval_metrics(
                    regression_cases,
                    regression_annotations,
                    regression_semantic_candidate_retrieval,
                    regression_version,
                ),
                "retrieval_operation_coverage_candidate": retrieval_metrics(
                    regression_cases,
                    regression_annotations,
                    regression_operation_coverage_candidate_retrieval,
                    regression_version,
                ),
                "adoption_baseline": adoption_metrics(
                    regression_cases,
                    regression_annotations,
                    regression_baseline_adoption,
                    regression_version,
                ),
                "adoption_compiler_v2": adoption_metrics(
                    regression_cases,
                    regression_annotations,
                    regression_compiler_v2_adoption,
                    regression_version,
                ),
                "adoption_policy_v1": adoption_metrics(
                    regression_cases,
                    regression_annotations,
                    regression_policy_baseline_adoption,
                    regression_version,
                ),
                "adoption_candidate": adoption_metrics(
                    regression_cases,
                    regression_annotations,
                    regression_candidate_adoption,
                    regression_version,
                ),
                "adoption_scoped_candidate": adoption_metrics(
                    regression_cases,
                    regression_annotations,
                    regression_scoped_candidate_adoption,
                    regression_version,
                ),
                "adoption_relation_candidate": adoption_metrics(
                    regression_cases,
                    regression_annotations,
                    regression_relation_candidate_adoption,
                    regression_version,
                ),
                "adoption_expanded_relation_candidate": adoption_metrics(
                    regression_cases,
                    regression_annotations,
                    regression_expanded_relation_candidate_adoption,
                    regression_version,
                ),
                "adoption_query_expansion_candidate": adoption_metrics(
                    regression_cases,
                    regression_annotations,
                    regression_query_expansion_candidate_adoption,
                    regression_version,
                ),
                "adoption_multi_operation_candidate": adoption_metrics(
                    regression_cases,
                    regression_annotations,
                    regression_multi_operation_candidate_adoption,
                    regression_version,
                ),
                "adoption_semantic_candidate": adoption_metrics(
                    regression_cases,
                    regression_annotations,
                    regression_semantic_candidate_adoption,
                    regression_version,
                ),
                "adoption_operation_coverage_candidate": adoption_metrics(
                    regression_cases,
                    regression_annotations,
                    regression_operation_coverage_candidate_adoption,
                    regression_version,
                ),
                "process_baseline": regression_baseline_process,
                "process_compiler_v2": regression_compiler_v2_process,
                "process_policy_baseline": regression_policy_baseline_process,
                "process_candidate": regression_candidate_process,
                "process_scoped_candidate": regression_scoped_candidate_process,
                "process_relation_candidate": regression_relation_candidate_process,
                "process_expanded_relation_candidate": (
                    regression_expanded_relation_candidate_process
                ),
                "process_query_expansion_candidate": (regression_query_expansion_candidate_process),
                "process_multi_operation_candidate": regression_multi_operation_candidate_process,
                "process_semantic_candidate": regression_semantic_candidate_process,
                "process_operation_coverage_candidate": (
                    regression_operation_coverage_candidate_process
                ),
            },
        },
        "changed_prediction_count": _changed_count(baseline_retrieval, candidate_retrieval),
        "scoped_candidate_changed_prediction_count": _changed_count(
            candidate_retrieval, scoped_candidate_retrieval
        ),
        "relation_candidate_changed_prediction_count": _changed_count(
            candidate_retrieval, relation_candidate_retrieval
        ),
        "expanded_relation_candidate_changed_prediction_count": _changed_count(
            relation_candidate_retrieval, expanded_relation_candidate_retrieval
        ),
        "query_expansion_candidate_changed_prediction_count": _changed_count(
            relation_candidate_retrieval, query_expansion_candidate_retrieval
        ),
        "multi_operation_candidate_changed_prediction_count": _changed_count(
            query_expansion_candidate_retrieval, multi_operation_candidate_retrieval
        ),
        "semantic_candidate_changed_prediction_count": _changed_count(
            multi_operation_candidate_retrieval, semantic_candidate_retrieval
        ),
        "operation_coverage_candidate_changed_prediction_count": _changed_count(
            semantic_candidate_retrieval, operation_coverage_candidate_retrieval
        ),
        "compiler_v2_changed_prediction_count": _changed_count(
            baseline_retrieval, compiler_v2_retrieval
        ),
        "policy_v1_changed_prediction_count": _changed_count(
            baseline_retrieval, policy_baseline_retrieval
        ),
        "regression_changed_prediction_count": _changed_count(
            regression_baseline_retrieval, regression_candidate_retrieval
        ),
        "regression_scoped_candidate_changed_prediction_count": _changed_count(
            regression_candidate_retrieval, regression_scoped_candidate_retrieval
        ),
        "regression_relation_candidate_changed_prediction_count": _changed_count(
            regression_candidate_retrieval, regression_relation_candidate_retrieval
        ),
        "regression_expanded_relation_candidate_changed_prediction_count": _changed_count(
            regression_relation_candidate_retrieval,
            regression_expanded_relation_candidate_retrieval,
        ),
        "regression_query_expansion_candidate_changed_prediction_count": _changed_count(
            regression_relation_candidate_retrieval,
            regression_query_expansion_candidate_retrieval,
        ),
        "regression_multi_operation_candidate_changed_prediction_count": _changed_count(
            regression_query_expansion_candidate_retrieval,
            regression_multi_operation_candidate_retrieval,
        ),
        "regression_semantic_candidate_changed_prediction_count": _changed_count(
            regression_multi_operation_candidate_retrieval,
            regression_semantic_candidate_retrieval,
        ),
        "regression_operation_coverage_candidate_changed_prediction_count": _changed_count(
            regression_semantic_candidate_retrieval,
            regression_operation_coverage_candidate_retrieval,
        ),
        "regression_compiler_v2_changed_prediction_count": _changed_count(
            regression_baseline_retrieval, regression_compiler_v2_retrieval
        ),
        "regression_policy_v1_changed_prediction_count": _changed_count(
            regression_baseline_retrieval, regression_policy_baseline_retrieval
        ),
        "policy": {
            "network_called": False,
            "llm_called": False,
            "provider_api_called": False,
            "hidden_answer_key_read": False,
            "prediction_source": "actual_retrieved_evidence_only",
            "promotion_decision": "not_promoted_proposal_only",
            "multi_operation_candidate_promotion": "not_promoted_pending_independent_holdout",
            "semantic_candidate_promotion": "not_promoted_pending_independent_holdout",
            "operation_coverage_candidate_promotion": ("not_promoted_pending_independent_holdout"),
        },
        "interpretation": (
            "该实验通过多条轨道拆分来源隔离、编译改进和操作级过滤的贡献，并使用相同的排序器和评测口径。"
            "开发集或公开回归的提升不能替代独立 Holdout；安全/过程门失败、任何回归退化，"
            "或答案泄露都必须拒绝 promotion。V5 仍需在候选稳定后用全新未重叠 Holdout 验收。"
        ),
        "next_step": "review_operation_coverage_deltas_then_create_v5_owner_review_draft",
    }
    traces = {
        "report_version": POLICY_COVERAGE_CANDIDATE_VERSION,
        "baseline": fair_trace_payload(baseline),
        "compiler_v2": fair_trace_payload(compiler_v2),
        "policy_baseline": fair_trace_payload(policy_baseline),
        "candidate": fair_trace_payload(candidate),
        "scoped_candidate": fair_trace_payload(scoped_candidate),
        "relation_candidate": fair_trace_payload(relation_candidate),
        "expanded_relation_candidate": fair_trace_payload(expanded_relation_candidate),
        "query_expansion_candidate": fair_trace_payload(query_expansion_candidate),
        "multi_operation_candidate": fair_trace_payload(multi_operation_candidate),
        "semantic_candidate": fair_trace_payload(semantic_candidate),
        "operation_coverage_candidate": fair_trace_payload(operation_coverage_candidate),
        "regression_baseline": fair_trace_payload(regression_baseline),
        "regression_compiler_v2": fair_trace_payload(regression_compiler_v2),
        "regression_policy_baseline": fair_trace_payload(regression_policy_baseline),
        "regression_candidate": fair_trace_payload(regression_candidate),
        "regression_scoped_candidate": fair_trace_payload(regression_scoped_candidate),
        "regression_relation_candidate": fair_trace_payload(regression_relation_candidate),
        "regression_expanded_relation_candidate": fair_trace_payload(
            regression_expanded_relation_candidate
        ),
        "regression_query_expansion_candidate": fair_trace_payload(
            regression_query_expansion_candidate
        ),
        "regression_multi_operation_candidate": fair_trace_payload(
            regression_multi_operation_candidate
        ),
        "regression_semantic_candidate": fair_trace_payload(regression_semantic_candidate),
        "regression_operation_coverage_candidate": fair_trace_payload(
            regression_operation_coverage_candidate
        ),
    }
    return report, traces


def render_policy_coverage_candidate_html(report: Mapping[str, object]) -> str:
    datasets = report.get("datasets", {})
    datasets = datasets if isinstance(datasets, Mapping) else {}
    rows: list[str] = []
    for name, data in datasets.items():
        if not isinstance(data, Mapping):
            continue
        for track in (
            "retrieval_baseline",
            "retrieval_compiler_v2",
            "retrieval_policy_v1",
            "retrieval_candidate",
            "retrieval_scoped_candidate",
            "retrieval_relation_candidate",
            "retrieval_expanded_relation_candidate",
            "retrieval_query_expansion_candidate",
            "retrieval_multi_operation_candidate",
            "retrieval_semantic_candidate",
            "retrieval_operation_coverage_candidate",
            "adoption_candidate",
            "adoption_scoped_candidate",
            "adoption_relation_candidate",
            "adoption_expanded_relation_candidate",
            "adoption_query_expansion_candidate",
            "adoption_multi_operation_candidate",
            "adoption_semantic_candidate",
            "adoption_operation_coverage_candidate",
        ):
            metrics = data.get(track, {})
            metrics = metrics if isinstance(metrics, Mapping) else {}
            rows.append(
                "<tr><th>"
                + html.escape(f"{name}/{track}")
                + "</th>"
                + "".join(
                    f"<td>{html.escape(str(metrics.get(key, '—')))}</td>"
                    for key in ("cases", "evidence_relation_accuracy", "recall_at_5", "mrr")
                )
                + "</tr>"
            )
    style = (
        "body{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;"
        "max-width:1100px;margin:30px auto;padding:0 22px;background:#f7f8fb;"
        "color:#18212b;line-height:1.55}table{width:100%;border-collapse:collapse;"
        "background:#fff}th,td{border:1px solid #dce3ec;padding:9px;text-align:left}"
        "th{background:#eef2f6}.note{padding:14px 16px;background:#fff7df;"
        "border-left:4px solid #c88900;margin:14px 0}"
    )
    return (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<title>RAG Policy Card Coverage Candidate</title>"
        f"<style>{style}</style></head><body><h1>RAG｜Policy Card 覆盖候选</h1>"
        "<div class='note'>只增加隔离临时知识卡，不修改 active baseline；指标来自真实检索结果。"
        "本页不包含 Holdout 答案，也不代表 RAG 已产品化。</div>"
        "<table><thead><tr><th>数据/轨道</th><th>题数</th><th>证据关系</th>"
        "<th>Recall@5</th><th>MRR</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table><p>开发集改变检索 Prediction：<strong>"
        + html.escape(str(report.get("changed_prediction_count", "—")))
        + "</strong>；公开回归改变：<strong>"
        + html.escape(str(report.get("regression_changed_prediction_count", "—")))
        + "</strong>；操作级过滤新增改变：<strong>"
        + html.escape(str(report.get("scoped_candidate_changed_prediction_count", "—")))
        + "</strong>。</p></body></html>"
    )


def write_policy_coverage_candidate_report(
    report: Mapping[str, object],
    traces: Mapping[str, object],
    *,
    json_path: Path,
    html_path: Path,
    trace_path: Path,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html_path.write_text(render_policy_coverage_candidate_html(report), encoding="utf-8")
    trace_path.write_text(json.dumps(traces, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


__all__ = [
    "POLICY_COVERAGE_CANDIDATE_VERSION",
    "POLICY_SCOPE_CANDIDATE_VERSION",
    "POLICY_RELATION_CANDIDATE_VERSION",
    "POLICY_VOCAB_CANDIDATE_VERSION",
    "POLICY_QUERY_EXPANSION_CANDIDATE_VERSION",
    "POLICY_MULTI_OPERATION_CANDIDATE_VERSION",
    "POLICY_SEMANTIC_CANDIDATE_VERSION",
    "POLICY_OPERATION_COVERAGE_CANDIDATE_VERSION",
    "POLICY_RELATION_CANDIDATE_V3_VERSION",
    "build_reviewed_policy_knowledge",
    "build_expanded_policy_knowledge",
    "build_policy_coverage_candidate_report",
    "policy_candidate_query_builder",
    "policy_candidate_query_builder_scoped",
    "policy_candidate_query_builder_multi_operation",
    "policy_query_term_expander",
    "policy_relation_resolver",
    "policy_relation_resolver_v2",
    "policy_relation_resolver_v3",
    "render_policy_coverage_candidate_html",
    "seed_reviewed_policy_knowledge_candidate",
    "seed_expanded_policy_knowledge_candidate",
    "write_policy_coverage_candidate_report",
]
