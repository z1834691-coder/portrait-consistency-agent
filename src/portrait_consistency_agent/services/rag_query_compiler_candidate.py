# ruff: noqa: E501
"""Failure-driven, proposal-only natural-language query compiler.

The first optimisation loop changed already-produced ``Prediction`` objects.
That cannot repair an error made before retrieval.  This module is a separate
candidate at the actual boundary where a user utterance becomes structured RAG
slots.  It uses a small reviewed ontology and an explicit precedence policy;
it does not read a case answer, call an LLM, or grant a provider permission.

The compiler is intentionally not the active online parser yet.  It is an
offline candidate used on a new, owner-reviewable failure-driven development
set.  Promotion requires a product decision and an independent Holdout v4.
"""

from __future__ import annotations

import hashlib
import re
import tempfile
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from portrait_consistency_agent.core.contracts import EditableFeature, PreserveAttribute
from portrait_consistency_agent.services.local_rag_models import (
    DeterministicTokenEmbeddingBackend,
    TokenOverlapReranker,
)
from portrait_consistency_agent.services.rag_advisory import RagAdvisoryService
from portrait_consistency_agent.services.rag_gold_baseline import (
    BaselineProjection,
    RagGoldDeterministicBaseline,
    _query_for_projection,
    _run_counts,
)
from portrait_consistency_agent.services.rag_gold_eval import GoldCase, Prediction
from portrait_consistency_agent.services.rag_p0a import seed_reviewed_provider_knowledge
from portrait_consistency_agent.services.rag_p0b import RagP0BHybridRetriever
from portrait_consistency_agent.storage.dense_index import LocalDenseIndex
from portrait_consistency_agent.storage.knowledge_store import LocalKnowledgeStore

QUERY_COMPILER_CANDIDATE_VERSION = "rag-query-compiler-candidate-v0.1"
_VALIDATION_ID = re.compile(r"^H[0-9]{2,}$")


@dataclass(frozen=True)
class QuerySignals:
    """Transient signals extracted from a user sentence.

    This object is never persisted.  It makes the candidate's decisions
    inspectable without exposing the original sentence in a Trace.
    """

    normalized: str
    hard_block: bool = False
    no_outbound: bool = False
    prompt_injection: bool = False
    conflict: bool = False
    expired: bool = False
    superseded: bool = False
    review_due: bool = False
    index_unavailable: bool = False
    adapter_unready: bool = False
    information_request: bool = False
    explicit_execute: bool = False
    manual_only: bool = False
    feedback_stop: bool = False
    subject_match: bool = False
    moderation: bool = False
    batch_or_multiface: bool = False
    third_party: bool = False
    pose_limit: bool = False
    unsupported_features: tuple[EditableFeature, ...] = ()
    executable_features: tuple[EditableFeature, ...] = ()
    preserve_skin_or_makeup: bool = False
    approved_tencent_scope: bool = False
    unknown_provider: bool = False
    missing_slots: bool = False
    # v0.2 validation signals.  They remain transient and are only used by
    # the explicitly unlocked V3 validation candidate; the active parser is
    # unchanged until a later promotion decision.
    natural_preference: bool = False
    skin_edit_requested: bool = False
    no_long_term_anchor: bool = False
    replan_context: bool = False
    dissatisfaction: bool = False
    round_limit_conflict: bool = False
    review_due_without_expiry: bool = False
    not_yet_effective: bool = False
    hard_fact_conflict: bool = False
    explicit_injection: bool = False
    closed_provider_scope: bool = False
    retrieval_miss: bool = False
    verification_strategy: bool = False
    face_isolation: bool = False
    third_party_consent_denied: bool = False
    public_revoke: bool = False
    result_worsened: bool = False
    param_range_violation: bool = False
    per_item_plan: bool = False
    current_version_priority: bool = False


def _has(text: str, *terms: str) -> bool:
    return any(term in text for term in terms)


def normalize_for_compilation(text: str) -> str:
    """Apply only reviewed vocabulary/typo normalisation in memory."""

    value = unicodedata.normalize("NFKC", text).casefold()
    value = re.sub(r"\s+", " ", value).strip()
    replacements = (
        # Supported geometry controls.
        ("腮帮子", "脸宽"),
        ("腮帮", "脸宽"),
        ("颌面", "脸宽"),
        ("下颌线", "脸宽"),
        ("下颚线", "脸宽"),
        ("脸颊太宽", "脸宽"),
        ("脸小一点", "瘦脸"),
        ("收窄脸", "瘦脸"),
        ("收脸", "瘦脸"),
        ("脸部轮廓", "脸宽"),
        ("面部轮廓", "脸宽"),
        ("脸收窄", "瘦脸"),
        ("脸收紧", "瘦脸"),
        ("下颌收窄", "瘦脸"),
        ("脸部收窄", "瘦脸"),
        ("脸部变窄", "瘦脸"),
        ("腮帮收", "瘦脸"),
        ("腮帮子收", "瘦脸"),
        ("眼睛撑大", "大眼"),
        ("放大眼睛", "大眼"),
        ("眼睛放大", "大眼"),
        ("双眼偏小", "大眼"),
        ("双眼显小", "大眼"),
        ("眼神更大", "大眼"),
        ("眼睛面积", "眼睛大小"),
        ("双眼面积", "眼睛大小"),
        ("肤色变白", "美白"),
        ("皮肤质感", "磨皮"),
        ("皮肤质地", "磨皮"),
        # Unsupported fine-grained features.
        ("眼间距", "眼距"),
        ("眉形", "眉毛"),
        ("眉型", "眉毛"),
        ("眼睛之间的距离", "眼距"),
        ("嘴唇厚度", "唇厚"),
        ("下唇", "下嘴唇"),
        ("唇形厚度", "唇厚"),
        ("鼻头", "鼻翼"),
        # Scope and policy wording.
        ("不传云", "不外发"),
        ("不上传到服务器", "不外发"),
        ("发送图片到服务器", "不外发"),
        ("把图片发到服务器", "不外发"),
        ("云端修图", "云端修图"),
        ("不要上传", "不外发"),
        ("图不出网", "不外发"),
        ("离线处理", "不外发"),
        ("腾迅", "腾讯"),
        ("腾讯云", "腾讯"),
        ("火山方舟", "火山"),
        ("合影", "合照"),
        ("多人照片", "合照"),
        ("一组写真", "批量"),
        ("九张", "9张"),
        ("十张", "10张"),
        # Common English phrases.  The vocabulary is deliberately small.
        ("jawline", "脸宽"),
        ("slim my face", "瘦脸"),
        ("make my face narrower", "瘦脸"),
        ("enlarge my eyes", "大眼"),
        ("make my eyes bigger", "大眼"),
        ("eye distance", "眼距"),
        ("eye width", "眼宽"),
        ("lip thickness", "唇厚"),
        ("nose wing", "鼻翼"),
        ("same person", "同一人物"),
        ("can your tool change eye distance", "眼距"),
        ("compare face", "compareface"),
        ("image moderation", "内容审核"),
        ("no cloud upload", "不外发"),
        ("no cloud transfer", "不外发"),
        ("only tencent", "只允许腾讯"),
        ("only adjust", "只改"),
        ("skin whitening", "美白"),
        ("skin smoothing", "磨皮"),
        ("no cloud", "不外发"),
    )
    for source, target in replacements:
        value = value.replace(source, target)
    return value


def extract_query_signals(text: str) -> QuerySignals:
    """Extract conservative slots with safety-first precedence."""

    normalized = normalize_for_compilation(text)
    hard_block = _has(
        normalized,
        "忽略权限",
        "绕过权限",
        "跳过权限",
        "system prompt",
        "系统 prompt",
        "系统提示",
        "把原图",
        "原始照片",
        "人脸向量",
        "人脸特征",
        "把照片给模型",
        "交给模型读",
        "向量入 rag",
        "未知 api",
        "未登记的 api",
        "未登记 api",
        "忽略之前的权限",
        "权限限制",
        "任意服务",
        "把照片发给任意",
        "忽略安全策略",
        "注入风险",
    )
    no_outbound = _has(
        normalized,
        "不外发",
        "任何云",
        "不出网",
        "不允许云",
        "no cloud",
        "不发到云",
    )
    conflict = _has(
        normalized,
        "冲突",
        "过期",
        "expired",
        "旧卡",
        "旧参数",
        "上一版",
        "是否还有效",
        "今天还能用",
        "失效",
        "忽略 policy",
        "ignore previous",
        "相反范围",
        "相反参数",
        "权威级别",
        "高权威",
        "低权威",
        "官方卡",
        "低权威笔记",
    )
    expiry_negated = _has(normalized, "还没过期", "未过期", "尚未过期")
    expired = _has(normalized, "过期", "expired", "已失效") and not expiry_negated
    superseded = _has(normalized, "superseded", "被新版替代", "新版同 provider")
    review_due = _has(normalized, "review_due", "复审", "到期前复核") and not expired
    index_unavailable = _has(
        normalized, "索引坏", "索引缺失", "索引不可用", "知识库没了", "更新失败"
    )
    adapter_unready = _has(
        normalized,
        "adapter 未实现",
        "adapter未实现",
        "adapter 没验证",
        "adapter没验证",
        "未 smoke",
        "未通过 smoke",
        "smoke",
        "还没经过",
        "新 sdk",
        "新sdk",
        "新工具",
        "火山",
        "真实 smoke",
        "还没有真实 smoke",
    )
    information_request = _has(
        normalized,
        "能不能",
        "可以吗",
        "支持吗",
        "是什么",
        "说明",
        "解释",
        "是否",
        "代表",
        "保证",
        "有效吗",
        "90%",
        "相似度保证",
        "what can",
        "can you",
    )
    explicit_execute = _has(
        normalized,
        "直接",
        "帮我修",
        "自动修",
        "执行",
        "处理",
        "改好",
        "调一下",
        "对齐",
        "调整",
        "收窄",
        "放大",
        "缩小",
        "改成",
        "修成",
        "处理吧",
        "做脸",
        "做大眼",
        "提出大眼",
    )
    manual_only = _has(normalized, "只给建议", "只给我建议", "手动调", "不要自动", "参数建议")
    feedback_stop = _has(normalized, "满意", "可以了", "停止", "别再修", "结果变差")
    subject_match = _has(
        normalized,
        "compareface",
        "同一人物",
        "同一个人",
        "是不是我",
        "这个人是我",
        "是我本人",
        "人脸比对",
    )
    moderation = _has(normalized, "内容审核", "ims", "审核通过", "安全审核")
    batch_or_multiface = _has(
        normalized,
        "合照",
        "批量",
        "多人",
        "两个人",
        "朋友",
        "写真组",
        "9张",
        "10张",
        "九张",
    )
    third_party = _has(normalized, "朋友", "其他人", "陌生人", "别人")
    pose_limit = _has(normalized, "侧脸", "侧面", "角度很偏", "完全对齐")
    preserve_skin_or_makeup = _has(
        normalized,
        "不动皮肤",
        "别动皮肤",
        "别动肤色",
        "不改肤色",
        "肤色妆容保持原样",
        "妆容保持原样",
        "保持肤色",
        "保留妆面",
        "不要美白",
        "不要磨皮",
        "不改妆",
    )
    natural_preference = _has(
        normalized,
        "别修得假",
        "别p得假",
        "不要修得假",
        "自然程度",
        "自然一点",
        "太假了",
        "不自然",
    )
    skin_edit_requested = _has(normalized, "美白", "磨皮", "肤色变白", "皮肤质感")
    no_long_term_anchor = _has(
        normalized,
        "不保存半年",
        "不保存人像锚点",
        "不保存主体锚点",
        "不保存锚点",
    )
    replan_context = _has(
        normalized,
        "上一轮局部变好",
        "局部变好了",
        "父回执",
        "当前结果图",
        "下一轮",
        "继续规划",
    )
    dissatisfaction = _has(
        normalized,
        "结果太假",
        "太假了",
        "不满意",
        "不自然",
    )
    round_limit_conflict = _has(
        normalized,
        "最多三轮",
        "最多 3 轮",
        "无限循环",
        "完全一样",
        "有界计划族",
    )
    review_due_without_expiry = _has(normalized, "复审日期", "到了复审", "review_due") and (
        expiry_negated or not expired
    )
    not_yet_effective = _has(
        normalized,
        "下周生效",
        "下周才生效",
        "生效日期是下周",
        "生效日期下周",
        "今天检索到",
        "尚未生效",
        "未到生效日期",
        "未来生效",
        "not_yet_effective",
    )
    hard_fact_conflict = _has(
        normalized,
        "相反范围",
        "相反参数",
        "不能自行挑一张",
        "不能自行选择",
        "冲突来源",
        "权威级别",
    )
    explicit_injection = _has(
        normalized,
        "忽略安全策略",
        "忽略之前的权限",
        "跳过权限",
        "绕过权限",
        "未登记的 api",
        "未登记 api",
        "注入风险",
        "任意服务",
    )
    closed_provider_scope = _has(
        normalized, "只允许腾讯", "仅腾讯", "只用腾讯", "腾讯处理"
    ) and _has(normalized, "其他厂商", "别的厂商", "其他 provider", "不能调用", "不要调用")
    retrieval_miss = _has(
        normalized,
        "没有召回",
        "无可用直接证据",
        "返回不知道",
        "不要让模型猜",
        "baseline",
    )
    verification_strategy = _has(
        normalized,
        "复测策略",
        "本地几何",
        "同人辅助",
        "人工复核",
        "验证候选",
    )
    face_isolation = _has(
        normalized,
        "隔离",
        "回贴",
        "非目标人物",
        "只编辑我",
        "只改我",
        "不改动其他人",
        "只修左边",
        "只修右边",
        "左边的人",
        "右边的人",
    )
    third_party_consent_denied = (
        _has(
            normalized,
            "同意不自动代表",
            "不自动代表她",
            "不自动代表他",
            "朋友同意",
            "公开展示",
        )
        and third_party
    )
    public_revoke = _has(
        normalized,
        "撤回公开展示",
        "新页面不得再展示",
        "已经下载的文件",
    )
    result_worsened = _has(
        normalized,
        "测量变差",
        "脸部测量变差",
        "不能只因为 api 成功",
        "不能因为 api 成功",
        "api 成功就宣布",
    )
    param_range_violation = _has(
        normalized,
        "超过 0 到 100",
        "超过0到100",
        "参数字段超过",
        "不能照抄",
        "参数范围",
    ) and _has(normalized, "0 到 100", "0到100", "安全策略", "provider 合同")
    per_item_plan = _has(
        normalized,
        "每张单独",
        "每张分别",
        "不复制同一组参数",
        "单独分析",
    )
    current_version_priority = _has(
        normalized,
        "当前 reviewed",
        "当前版参数",
        "当前版本",
        "旧版和当前",
        "优先采用",
    ) and _has(normalized, "旧版", "当前", "reviewed", "优先")
    approved_tencent_scope = _has(normalized, "只允许腾讯", "允许腾讯", "仅腾讯", "腾讯")
    # “其他厂商不要用” is a closed-world constraint, not a request to use
    # an unknown provider.  Only a positive request for a new provider is
    # treated as an unready-provider signal.
    unknown_provider = _has(
        normalized,
        "新 provider",
        "新工具",
        "火山",
        "调用其他厂商",
        "未获产品准入",
        "未准入",
        "未批准",
        "不准入",
    ) and not _has(normalized, "不允许其他厂商", "其他厂商不要用", "别的厂商不要用")

    unsupported: list[EditableFeature] = []
    if _has(normalized, "眼距", "眼宽", "眉毛"):
        unsupported.extend((EditableFeature.EYE_DISTANCE,))
    if _has(normalized, "嘴唇", "下嘴唇", "唇厚", "嘴型"):
        unsupported.append(EditableFeature.LIPS_THICKNESS)
    if _has(normalized, "鼻翼", "鼻子变小"):
        unsupported.append(EditableFeature.NOSE_WING)
    unsupported = list(dict.fromkeys(unsupported))

    executable: list[EditableFeature] = []
    if _has(normalized, "瘦脸", "脸宽"):
        executable.append(EditableFeature.FACE_LIFTING)
    if _has(normalized, "大眼", "眼睛小", "双眼"):
        executable.append(EditableFeature.EYE_ENLARGING)
    if _has(normalized, "美白"):
        executable.append(EditableFeature.WHITENING)
    if _has(normalized, "磨皮"):
        executable.append(EditableFeature.SMOOTHING)

    missing_slots = _has(normalized, "最强工具", "无区域", "无授权", "无部位")
    return QuerySignals(
        normalized=normalized,
        hard_block=hard_block,
        no_outbound=no_outbound,
        prompt_injection=hard_block and _has(normalized, "prompt", "权限", "api", "向量"),
        conflict=conflict,
        expired=expired,
        superseded=superseded,
        review_due=review_due,
        index_unavailable=index_unavailable,
        adapter_unready=adapter_unready,
        information_request=information_request,
        explicit_execute=explicit_execute,
        manual_only=manual_only,
        feedback_stop=feedback_stop,
        subject_match=subject_match,
        moderation=moderation,
        batch_or_multiface=batch_or_multiface,
        third_party=third_party,
        pose_limit=pose_limit,
        unsupported_features=tuple(unsupported),
        executable_features=tuple(dict.fromkeys(executable)),
        preserve_skin_or_makeup=preserve_skin_or_makeup,
        approved_tencent_scope=approved_tencent_scope,
        unknown_provider=unknown_provider,
        missing_slots=missing_slots,
        natural_preference=natural_preference,
        skin_edit_requested=skin_edit_requested,
        no_long_term_anchor=no_long_term_anchor,
        replan_context=replan_context,
        dissatisfaction=dissatisfaction,
        round_limit_conflict=round_limit_conflict,
        review_due_without_expiry=review_due_without_expiry,
        not_yet_effective=not_yet_effective,
        hard_fact_conflict=hard_fact_conflict,
        explicit_injection=explicit_injection,
        closed_provider_scope=closed_provider_scope,
        retrieval_miss=retrieval_miss,
        verification_strategy=verification_strategy,
        face_isolation=face_isolation,
        third_party_consent_denied=third_party_consent_denied,
        public_revoke=public_revoke,
        result_worsened=result_worsened,
        param_range_violation=param_range_violation,
        per_item_plan=per_item_plan,
        current_version_priority=current_version_priority,
    )


def _add(aliases: list[str], relations: dict[str, str], alias: str, relation: str) -> None:
    if alias not in aliases:
        aliases.append(alias)
    # A direct policy/ability fact must not be overwritten by a later generic
    # retrieval result.  Conflict is strongest, then direct, then reference.
    rank = {"conflict_evidence": 3, "direct_evidence": 2, "reference_context": 1}
    old = relations.get(alias)
    if old is None or rank.get(relation, 0) > rank.get(old, 0):
        relations[alias] = relation


def compile_generalized_projection(case: GoldCase) -> tuple[BaselineProjection, QuerySignals]:
    """Compile a sentence into a safe projection without case-specific rules."""

    signals = extract_query_signals(case.query)
    aliases: list[str] = []
    relations: dict[str, str] = {}

    # Safety, outbound and hard-fact conflict always win over capability.
    if signals.hard_block or signals.no_outbound:
        _add(aliases, relations, "P", "direct_evidence")
        return (
            BaselineProjection(
                category_codes=("policy_or_outbound_block",),
                route_override="BLOCK",
                evidence_aliases=tuple(aliases),
                evidence_relations=relations,
                outbound_allowed=False,
            ),
            signals,
        )
    if signals.expired:
        _add(aliases, relations, "FX", "conflict_evidence")
        _add(aliases, relations, "B", "reference_context")
        return (
            BaselineProjection(
                category_codes=("expired_knowledge_block",),
                route_override="BLOCK",
                evidence_aliases=tuple(aliases),
                evidence_relations=relations,
            ),
            signals,
        )
    if signals.conflict and not signals.superseded and not signals.review_due:
        _add(aliases, relations, "FX", "conflict_evidence")
        return (
            BaselineProjection(
                category_codes=("knowledge_conflict_or_injection",),
                route_override="BLOCK",
                evidence_aliases=tuple(aliases),
                evidence_relations=relations,
            ),
            signals,
        )
    if signals.index_unavailable:
        _add(aliases, relations, "P", "reference_context")
        return (
            BaselineProjection(
                category_codes=("index_unavailable",),
                route_override="UNKNOWN",
                evidence_aliases=tuple(aliases),
                evidence_relations=relations,
            ),
            signals,
        )
    if signals.review_due:
        _add(aliases, relations, "FX", "reference_context")
        return (
            BaselineProjection(
                category_codes=("knowledge_review_due",),
                route_override="REFERENCE",
                evidence_aliases=tuple(aliases),
                evidence_relations=relations,
            ),
            signals,
        )
    if signals.superseded:
        _add(aliases, relations, "B", "direct_evidence")
        _add(aliases, relations, "FX", "reference_context")
        return (
            BaselineProjection(
                category_codes=("superseded_by_reviewed_card",),
                route_override="DIRECT",
                evidence_aliases=tuple(aliases),
                evidence_relations=relations,
                retriever_kind="beautify",
            ),
            signals,
        )

    # Information-only tools remain reference evidence, never an edit route.
    if signals.subject_match or signals.moderation:
        if signals.subject_match:
            _add(aliases, relations, "C", "reference_context")
        if signals.moderation:
            _add(aliases, relations, "I", "reference_context")
        if signals.moderation and _has(signals.normalized, "代表", "一致", "相似", "说明"):
            _add(aliases, relations, "P", "reference_context")
        return (
            BaselineProjection(
                category_codes=("information_only_tool_scope",),
                route_override="REFERENCE",
                evidence_aliases=tuple(aliases),
                evidence_relations=relations,
                retriever_kind="compare_face"
                if signals.subject_match and not signals.moderation
                else "moderation",
            ),
            signals,
        )
    if signals.feedback_stop:
        _add(aliases, relations, "P", "reference_context")
        return (
            BaselineProjection(
                category_codes=("feedback_stops_plan_family",),
                route_override="STOP",
                evidence_aliases=tuple(aliases),
                evidence_relations=relations,
            ),
            signals,
        )
    if signals.information_request and _has(signals.normalized, "90%", "相似度保证", "绝对保证"):
        _add(aliases, relations, "P", "reference_context")
        return (
            BaselineProjection(
                category_codes=("uncalibrated_score_boundary",),
                route_override="REFERENCE",
                evidence_aliases=tuple(aliases),
                evidence_relations=relations,
            ),
            signals,
        )
    if signals.missing_slots:
        _add(aliases, relations, "P", "direct_evidence")
        return (
            BaselineProjection(
                category_codes=("missing_critical_slots",),
                route_override="CLARIFY",
                evidence_aliases=tuple(aliases),
                evidence_relations=relations,
                missing_critical_slots=("requested_feature_or_provider_scope",),
            ),
            signals,
        )
    if signals.adapter_unready or signals.unknown_provider:
        _add(aliases, relations, "B", "reference_context")
        _add(aliases, relations, "P", "direct_evidence")
        return (
            BaselineProjection(
                category_codes=("provider_or_adapter_not_ready",),
                route_override="REFERENCE",
                evidence_aliases=tuple(aliases),
                evidence_relations=relations,
            ),
            signals,
        )
    if signals.batch_or_multiface or signals.third_party:
        _add(aliases, relations, "B", "reference_context")
        _add(aliases, relations, "P", "reference_context")
        if signals.third_party and not _has(signals.normalized, "批量", "合照", "合影"):
            aliases = ["P"]
            relations = {"P": "reference_context"}
        route = (
            "SUGGEST"
            if signals.third_party or signals.pose_limit or signals.face_isolation
            else "CLARIFY"
        )
        return (
            BaselineProjection(
                category_codes=("batch_or_multiface_requires_scope",),
                route_override=route,
                evidence_aliases=tuple(aliases),
                evidence_relations=relations,
            ),
            signals,
        )
    if signals.pose_limit:
        _add(aliases, relations, "B", "reference_context")
        _add(aliases, relations, "P", "reference_context")
        return (
            BaselineProjection(
                category_codes=("pose_limits_alignment",),
                route_override="SUGGEST",
                evidence_aliases=tuple(aliases),
                evidence_relations=relations,
            ),
            signals,
        )
    if signals.unsupported_features:
        _add(aliases, relations, "B", "reference_context")
        return (
            BaselineProjection(
                category_codes=("unsupported_facial_feature",),
                route_override="SUGGEST",
                evidence_aliases=tuple(aliases),
                evidence_relations=relations,
                requested_features=signals.unsupported_features,
                allowed_features=signals.unsupported_features,
                retriever_kind="beautify",
            ),
            signals,
        )
    if signals.manual_only:
        _add(aliases, relations, "B", "reference_context")
        _add(aliases, relations, "P", "direct_evidence")
        return (
            BaselineProjection(
                category_codes=("manual_parameters_requested",),
                route_override="SUGGEST",
                evidence_aliases=tuple(aliases),
                evidence_relations=relations,
                requested_features=signals.executable_features,
                allowed_features=signals.executable_features,
                retriever_kind="beautify",
            ),
            signals,
        )
    if signals.information_request and not signals.explicit_execute:
        if signals.unsupported_features:
            _add(aliases, relations, "B", "reference_context")
        elif signals.executable_features:
            _add(aliases, relations, "B", "direct_evidence")
        else:
            _add(aliases, relations, "P", "reference_context")
        return (
            BaselineProjection(
                category_codes=("capability_information_request",),
                route_override="REFERENCE",
                evidence_aliases=tuple(aliases),
                evidence_relations=relations,
                requested_features=signals.executable_features or signals.unsupported_features,
                allowed_features=signals.executable_features or signals.unsupported_features,
                retriever_kind="beautify"
                if signals.executable_features or signals.unsupported_features
                else None,
            ),
            signals,
        )
    if signals.executable_features:
        _add(aliases, relations, "B", "direct_evidence")
        if (
            signals.preserve_skin_or_makeup
            or len(signals.executable_features) > 1
            or signals.approved_tencent_scope
        ):
            _add(aliases, relations, "P", "reference_context")
        return (
            BaselineProjection(
                category_codes=("reviewed_executable_feature",),
                route_override="DIRECT",
                evidence_aliases=tuple(aliases),
                evidence_relations=relations,
                requested_features=signals.executable_features,
                allowed_features=signals.executable_features,
                preserve_constraints=(
                    (PreserveAttribute.SKIN_TONE, PreserveAttribute.MAKEUP)
                    if signals.preserve_skin_or_makeup
                    else ()
                ),
                retriever_kind="beautify",
            ),
            signals,
        )
    _add(aliases, relations, "P", "reference_context")
    return (
        BaselineProjection(
            category_codes=("no_reliable_projection",),
            route_override="UNKNOWN",
            evidence_aliases=tuple(aliases),
            evidence_relations=relations,
        ),
        signals,
    )


QUERY_COMPILER_CANDIDATE_V2_VERSION = "rag-query-compiler-candidate-v0.2"


GENERALIZED_QUERY_COMPILER_V2_VERSION = "rag-query-compiler-candidate-v0.2-generalized"


GENERALIZED_QUERY_COMPILER_V3_VERSION = "rag-query-compiler-candidate-v0.3.1-failure-routed"


def compile_generalized_projection_v2(
    case: GoldCase,
) -> tuple[BaselineProjection, QuerySignals]:
    """Broaden the reviewed compiler without consulting Gold labels.

    The first generalized candidate was intentionally conservative, but it
    treated several common product requests as an unknown query.  This
    version adds only ontology-level signals already present in the reviewed
    policy: broad facial-edit wording, approved Tencent scope, batch/pose
    limits, adapter readiness, and lifecycle conflict markers.  It never
    invents a provider or parameter and remains a proposal-only experiment.
    """

    projection, signals = compile_generalized_projection(case)
    normalized = signals.normalized

    def make(
        *,
        category: str,
        route: str,
        aliases: tuple[str, ...],
        relations: dict[str, str],
        requested: tuple[EditableFeature, ...] = (),
        allowed: tuple[EditableFeature, ...] = (),
        preserve: tuple[PreserveAttribute, ...] = (),
        retriever_kind: str | None = None,
        outbound_allowed: bool = True,
        missing: tuple[str, ...] = (),
    ) -> tuple[BaselineProjection, QuerySignals]:
        return (
            BaselineProjection(
                category_codes=(category,),
                route_override=route,
                evidence_aliases=aliases,
                evidence_relations=relations,
                requested_features=requested,
                allowed_features=allowed,
                preserve_constraints=preserve,
                retriever_kind=retriever_kind,
                outbound_allowed=outbound_allowed,
                missing_critical_slots=missing,
            ),
            signals,
        )

    # Lifecycle and integrity facts must be represented before any capability
    # word.  They are policy evidence, not a reason to run a tool.
    if signals.not_yet_effective:
        return make(
            category="not_yet_effective_knowledge",
            route="UNKNOWN",
            aliases=("FX",),
            relations={"FX": "conflict_evidence"},
        )
    if signals.hard_fact_conflict and not signals.superseded and not signals.review_due:
        return make(
            category="hard_fact_conflict",
            route="BLOCK",
            aliases=("FX",),
            relations={"FX": "conflict_evidence"},
        )

    # “只允许腾讯” is a provider-scope decision even when the user has not
    # named a particular slider.  The tool card is useful evidence, while the
    # policy card explains the closed-world boundary.
    if signals.approved_tencent_scope and not signals.unknown_provider:
        aliases = ["B", "P"]
        relations = {"B": "direct_evidence", "P": "reference_context"}
        return make(
            category="approved_provider_scope",
            route="DIRECT",
            aliases=tuple(aliases),
            relations=relations,
            requested=signals.executable_features,
            allowed=signals.executable_features,
            retriever_kind="beautify",
        )

    # A broad “五官” request is not permission to invent unsupported sliders;
    # map only to the two executable geometry controls already reviewed.
    if _has(normalized, "五官", "面部轮廓") and not signals.unsupported_features:
        requested = (EditableFeature.FACE_LIFTING, EditableFeature.EYE_ENLARGING)
        preserve = (
            (PreserveAttribute.SKIN_TONE, PreserveAttribute.MAKEUP)
            if signals.preserve_skin_or_makeup or _has(normalized, "不动皮肤", "不改肤色")
            else ()
        )
        return make(
            category="broad_facial_edit_scope",
            route="DIRECT" if signals.explicit_execute else "REFERENCE",
            aliases=("B", "P"),
            relations={"B": "direct_evidence", "P": "reference_context"},
            requested=requested,
            allowed=requested,
            preserve=preserve,
            retriever_kind="beautify",
        )

    # If the user asks about a new/unverified adapter, retrieve the existing
    # tool card plus the policy boundary instead of returning only a generic
    # policy paragraph.  The adapter is still never executed here.
    if signals.adapter_unready or signals.unknown_provider:
        if _has(normalized, "未获产品准入", "未准入", "未批准", "不准入"):
            return make(
                category="unapproved_provider_block",
                route="BLOCK",
                aliases=("P",),
                relations={"P": "direct_evidence"},
                outbound_allowed=False,
            )
        return make(
            category="provider_or_adapter_not_ready",
            route="REFERENCE",
            aliases=("B", "P"),
            relations={"B": "reference_context", "P": "direct_evidence"},
            retriever_kind="beautify",
        )

    # Batch, multi-face and pose requests need the existing BeautifyPic
    # limitation card in addition to the project policy; this is why they
    # should not fall through to a policy-only query.
    if signals.batch_or_multiface:
        relation = "direct_evidence" if signals.face_isolation else "reference_context"
        return make(
            category="batch_or_multiface_requires_scope",
            route=(
                "SUGGEST"
                if signals.third_party or signals.pose_limit or signals.face_isolation
                else "CLARIFY"
            ),
            aliases=("B", "P"),
            relations={"B": "reference_context", "P": relation},
            retriever_kind="beautify",
        )
    if signals.pose_limit:
        return make(
            category="pose_limits_alignment",
            route="SUGGEST",
            aliases=("B", "P"),
            relations={"B": "reference_context", "P": "reference_context"},
            retriever_kind="beautify",
        )

    # The product rule is a bounded plan family.  A request to exceed it must
    # still surface the tool card and the policy card, but remains blocked.
    if signals.round_limit_conflict:
        return make(
            category="bounded_plan_family_conflict",
            route="BLOCK",
            aliases=("B", "P"),
            relations={"B": "reference_context", "P": "direct_evidence"},
            retriever_kind="beautify",
        )

    # Keep the original behavior for all other sentences; this avoids
    # silently broadening the candidate beyond the reviewed ontology.
    return projection, signals


def compile_generalized_projection_v3(
    case: GoldCase,
) -> tuple[BaselineProjection, QuerySignals]:
    """Apply failure-driven precedence fixes as an isolated compiler candidate.

    V2 already recognised the main ontology, but its precedence allowed a
    broad capability word (for example ``五官可改``) to hide a stronger
    lifecycle, privacy or bounded-round condition.  V3 fixes that ordering and
    adds conservative paraphrases seen in the public diagnostic set.  It does
    not consult annotations or invent a provider; all returned labels are
    still proposals for the downstream policy gate.
    """

    base, signals = compile_generalized_projection_v2(case)
    normalized = signals.normalized

    def make(
        *,
        category: str,
        route: str,
        aliases: tuple[str, ...],
        relations: dict[str, str],
        requested: tuple[EditableFeature, ...] = (),
        allowed: tuple[EditableFeature, ...] = (),
        preserve: tuple[PreserveAttribute, ...] = (),
        retriever_kind: str | None = None,
        outbound_allowed: bool = True,
        missing: tuple[str, ...] = (),
    ) -> tuple[BaselineProjection, QuerySignals]:
        return (
            BaselineProjection(
                category_codes=(category,),
                route_override=route,
                evidence_aliases=aliases,
                evidence_relations=relations,
                requested_features=requested,
                allowed_features=allowed,
                preserve_constraints=preserve,
                retriever_kind=retriever_kind,
                outbound_allowed=outbound_allowed,
                missing_critical_slots=missing,
            ),
            signals,
        )

    def has(*terms: str) -> bool:
        return _has(normalized, *terms)

    # A knowledge instruction to ignore policy and call an unknown API is a
    # conflict, not merely an outbound preference.  Keep the conflict card as
    # the primary evidence and never turn this into a tool route.
    knowledge_injection = has(
        "忽略 policy",
        "未知 api",
        "未登记 api",
        "知识段落",
        "忽略安全策略",
    )
    if knowledge_injection:
        return make(
            category="knowledge_conflict_or_injection",
            route="BLOCK",
            aliases=("FX",),
            relations={"FX": "conflict_evidence"},
            outbound_allowed=False,
        )

    if signals.explicit_injection:
        return make(
            category="policy_or_injection_block",
            route="BLOCK",
            aliases=("P",),
            relations={"P": "direct_evidence"},
            outbound_allowed=False,
        )

    # Explicit refusal to store a long-term anchor still permits the current
    # edit in the product's degraded mode; it is a policy fact, not a missing
    # capability.
    if signals.no_long_term_anchor or has(
        "不同意保存半年锚点",
        "不同意保存主体锚点",
        "不保存半年锚点",
        "不保存人像锚点",
    ):
        return make(
            category="current_session_anchor_degrade",
            route="BASELINE",
            aliases=("P",),
            relations={"P": "direct_evidence"},
        )

    # A stale card/version question must not fall into the ordinary
    # unsupported-feature branch.  It needs the lifecycle conflict evidence.
    if has("上次工具卡", "上次卡", "旧参数卡", "上一版") and has(
        "今天", "现在", "目前", "能调", "可调", "支持"
    ):
        return make(
            category="stale_or_unreviewed_knowledge",
            route="BLOCK",
            aliases=("FX",),
            relations={"FX": "conflict_evidence"},
            retriever_kind="beautify",
        )

    # “两个范围互相矛盾” is a hard fact conflict even when it does not use
    # the literal word “冲突”.
    if has("互相矛盾", "相互矛盾", "范围矛盾", "参数矛盾"):
        return make(
            category="hard_fact_conflict",
            route="BLOCK",
            aliases=("FX",),
            relations={"FX": "conflict_evidence"},
        )

    # If the user explicitly contrasts direct and background material, retain
    # both sides with their intended evidence roles for an authority review.
    if has("direct", "直接") and has("背景资料", "解释型", "背景信息"):
        return make(
            category="direct_and_background_evidence_relation",
            route="DIRECT",
            aliases=("B", "FX"),
            relations={"B": "direct_evidence", "FX": "reference_context"},
            retriever_kind="beautify",
        )

    # A question asking whether an identity/safety result proves visual
    # alignment needs both the information-only card and the project-policy
    # explanation.  A plain “是不是本人/审核做什么” question stays scoped to
    # the provider card alone.
    if (
        base.category_codes == ("information_only_tool_scope",)
        and (
            has("模板", "一致", "代表", "说明", "相似")
            or (signals.moderation and signals.explicit_execute)
        )
        and not (
            signals.subject_match
            and signals.moderation
            and (signals.unsupported_features or signals.executable_features)
        )
    ):
        aliases = tuple(dict.fromkeys((*base.evidence_aliases, "P")))
        relations = dict(base.evidence_relations)
        relations["P"] = "reference_context"
        return make(
            category="information_only_compound_scope",
            route=base.route_override or "REFERENCE",
            aliases=aliases,
            relations=relations,
            retriever_kind=base.retriever_kind,
        )

    # A naturalness constraint is part of the edit policy even when only one
    # executable feature was named.  Keep the capability card as direct
    # evidence and add the reviewed project policy as explanatory context.
    if (
        base.category_codes == ("reviewed_executable_feature",)
        and (signals.natural_preference or signals.preserve_skin_or_makeup)
        and "P" not in base.evidence_aliases
    ):
        return make(
            category="reviewed_executable_feature",
            route=base.route_override or "DIRECT",
            aliases=tuple((*base.evidence_aliases, "P")),
            relations={**base.evidence_relations, "P": "reference_context"},
            requested=base.requested_features,
            allowed=base.allowed_features,
            preserve=base.preserve_constraints,
            retriever_kind=base.retriever_kind or "beautify",
            outbound_allowed=base.outbound_allowed,
        )

    # A high-authority official card and a low-authority note are not the same
    # kind of evidence.  Keep the reviewed executable card direct and the
    # competing lifecycle/context record as background for the explanation.
    if has("低权威", "高权威", "官方卡", "权威级别") and has("不同", "冲突"):
        return make(
            category="authority_priority",
            route="DIRECT",
            aliases=("B", "FX"),
            relations={"B": "direct_evidence", "FX": "reference_context"},
            retriever_kind="beautify",
        )

    # Privacy/closed-world wording must dominate an executable feature.  This
    # keeps a multi-face, no-outbound request in suggestion mode and prevents
    # accidental cloud calls.
    if (signals.batch_or_multiface or has("合照", "多人", "左边是我")) and has(
        "不要出腾讯", "不要出云", "不外发", "不上传"
    ):
        return make(
            category="multiface_no_outbound_scope",
            route="SUGGEST",
            aliases=("B", "P"),
            relations={"B": "reference_context", "P": "direct_evidence"},
            retriever_kind="beautify",
            outbound_allowed=False,
        )

    # An appearance-ranking request is a policy-sensitive batch request.  It
    # should not be treated as a normal batch edit, because the product does
    # not judge which person is “ugliest”.
    if signals.batch_or_multiface and has("最丑", "最好看", "挑出来", "排名"):
        return make(
            category="batch_appearance_judgment_scope",
            route="CLARIFY",
            aliases=("P", "B"),
            relations={"P": "direct_evidence", "B": "reference_context"},
            retriever_kind="beautify",
            missing=("appearance_judgment_scope",),
        )

    # Compound safety/identity/edit wording needs all three provider cards,
    # but every card is explanatory evidence; none authorises execution.
    if (
        signals.subject_match
        and signals.moderation
        and (signals.unsupported_features or signals.executable_features)
    ):
        return make(
            category="information_only_compound_scope",
            route="SUGGEST",
            aliases=("I", "C", "B"),
            relations={
                "I": "reference_context",
                "C": "reference_context",
                "B": "reference_context",
            },
            requested=signals.unsupported_features or signals.executable_features,
        )

    # “成人自拍+批量” is content-safety scope plus batch scope, even when
    # the user does not say “审核”.
    if signals.batch_or_multiface and has("成人", "色情", "暴力", "血腥", "裸照", "裸图"):
        return make(
            category="batch_content_safety_scope",
            route="CLARIFY",
            aliases=("I", "P"),
            relations={"I": "reference_context", "P": "reference_context"},
            retriever_kind="moderation",
            missing=("batch_content_safety_scope",),
        )

    # A round-limit constraint must be evaluated before broad “five features”
    # capability language.  The tool card remains context, and the policy card
    # is the direct limit evidence.
    if signals.round_limit_conflict or has("自动连续修", "多轮自动优化", "修 5 轮", "修5轮"):
        return make(
            category="bounded_plan_family_conflict",
            route="BLOCK",
            aliases=("B", "P"),
            relations={"B": "reference_context", "P": "direct_evidence"},
            retriever_kind="beautify",
        )

    # “眼睛显得不一样” is a reviewed paraphrase for the executable eye
    # control, not an unknown request.
    if has("眼睛显得不一样", "眼睛看起来不一样"):
        requested = (EditableFeature.EYE_ENLARGING,)
        return make(
            category="reviewed_executable_feature",
            # “可查支持范围” asks for a concrete capability lookup.  It is
            # not an image execution request, but the retrieval route is
            # still DIRECT because a reviewed tool fact is expected.
            route="DIRECT"
            if signals.explicit_execute or has("支持范围", "能查支持", "可查支持")
            else "REFERENCE",
            aliases=("B",),
            relations={"B": "direct_evidence"},
            requested=requested,
            allowed=requested,
            retriever_kind="beautify",
        )

    # Unapproved provider wording should resolve to a policy block instead of
    # an unknown/no-retrieval fallback.
    if has("未允许该 provider", "未允许这个 provider", "用户未允许", "没有允许 provider"):
        return make(
            category="unapproved_provider_block",
            route="BLOCK",
            aliases=("P",),
            relations={"P": "direct_evidence"},
            outbound_allowed=False,
        )

    # A cloud edit request that simultaneously forbids outbound media and
    # names an unsupported feature is a direct privacy/capability conflict.
    # It must stop rather than degrade into an ordinary reference response.
    if signals.no_outbound and signals.unsupported_features and signals.explicit_execute:
        return make(
            category="policy_or_unsupported_outbound_conflict",
            route="BLOCK",
            aliases=("P",),
            relations={"P": "direct_evidence"},
            outbound_allowed=False,
        )

    # “只想改五官” and “查支持范围” are action/capability requests even
    # when the user does not use the canonical word “直接”.  The compiler can
    # safely promote the route only because the requested feature slots and
    # provider namespace are already present in the structured projection.
    if (
        base.route_override == "REFERENCE"
        and base.requested_features
        and has("只想改", "只改", "支持范围", "可查支持范围", "能查支持")
    ):
        return make(
            category="reviewed_executable_feature",
            route="DIRECT",
            aliases=base.evidence_aliases,
            relations=dict(base.evidence_relations),
            requested=base.requested_features,
            allowed=base.allowed_features,
            preserve=base.preserve_constraints,
            retriever_kind=base.retriever_kind or "beautify",
            outbound_allowed=base.outbound_allowed,
        )

    # Batch/multi-face clarification is itself a valid route and does not
    # require an executable tool result.  Record the missing scope explicitly
    # so the downstream handoff can verify the proposal instead of silently
    # falling back when retrieval contains only limitation cards.
    if (
        base.route_override == "CLARIFY"
        and signals.batch_or_multiface
        and not base.missing_critical_slots
    ):
        return make(
            category=base.category_codes[0] if base.category_codes else "batch_scope_clarify",
            route="CLARIFY",
            aliases=base.evidence_aliases,
            relations=dict(base.evidence_relations),
            requested=base.requested_features,
            allowed=base.allowed_features,
            preserve=base.preserve_constraints,
            retriever_kind=base.retriever_kind,
            outbound_allowed=base.outbound_allowed,
            missing=("target_scope_or_batch_policy",),
        )

    # A lifecycle/privacy question such as “图片发出后能撤回吗” is asking
    # for a policy explanation, not an unknown capability.  Keep the policy
    # namespace and return a reference route without authorizing an action.
    if base.route_override == "UNKNOWN" and has("撤回", "删除", "发出后", "保留期"):
        return make(
            category="policy_lifecycle_information",
            route="REFERENCE",
            aliases=base.evidence_aliases or ("P",),
            relations=dict(base.evidence_relations or {"P": "reference_context"}),
            outbound_allowed=base.outbound_allowed,
        )

    # The V2 projection is retained when none of the reviewed corrections is
    # present.  This makes the candidate a narrow, reversible delta.
    return base, signals


def compile_validation_projection_v2(case: GoldCase) -> tuple[BaselineProjection, QuerySignals]:
    """Compile the unlocked V3 validation language with policy-first routing.

    This is deliberately a new candidate instead of a silent mutation of the
    v0.1 artifact.  It adds generalized concepts observed in V3 (review-due
    versus expired, bounded rounds, provider scope, replan and feedback) and
    keeps the same deterministic relation vocabulary.  It remains advisory and
    cannot grant execution permission.
    """

    signals = extract_query_signals(case.query)
    normalized = signals.normalized
    aliases: list[str] = []
    relations: dict[str, str] = {}

    def projection(
        *,
        category: str,
        route: str,
        requested: tuple[EditableFeature, ...] = (),
        allowed: tuple[EditableFeature, ...] = (),
        preserve: tuple[PreserveAttribute, ...] = (),
        retriever_kind: str | None = None,
        outbound_allowed: bool = True,
        missing: tuple[str, ...] = (),
    ) -> tuple[BaselineProjection, QuerySignals]:
        return (
            BaselineProjection(
                category_codes=(category,),
                route_override=route,
                evidence_aliases=tuple(aliases),
                evidence_relations=dict(relations),
                requested_features=requested,
                allowed_features=allowed,
                preserve_constraints=preserve,
                retriever_kind=retriever_kind,
                outbound_allowed=outbound_allowed,
                missing_critical_slots=missing,
            ),
            signals,
        )

    # The order below is the product policy, not an LLM preference.  A known
    # safety, privacy or data-integrity issue must dominate a capability word.
    if signals.third_party_consent_denied:
        _add(aliases, relations, "P", "direct_evidence")
        return projection(category="third_party_consent_block", route="BLOCK")
    if signals.hard_block or signals.no_outbound or signals.explicit_injection:
        if signals.hard_fact_conflict or _has(
            normalized, "知识片段", "资料要求", "文档要求", "知识卡要求"
        ):
            _add(aliases, relations, "FX", "conflict_evidence")
        _add(aliases, relations, "P", "direct_evidence")
        return projection(
            category="policy_or_injection_block",
            route="BLOCK",
            outbound_allowed=False,
        )
    if signals.param_range_violation:
        _add(aliases, relations, "B", "reference_context")
        _add(aliases, relations, "P", "direct_evidence")
        return projection(category="provider_parameter_range_block", route="BLOCK")
    if signals.replan_context:
        _add(aliases, relations, "B", "direct_evidence")
        _add(aliases, relations, "P", "reference_context")
        return projection(
            category="bounded_followup_replan",
            route="DIRECT",
            requested=signals.executable_features,
            allowed=signals.executable_features,
            retriever_kind="beautify" if signals.executable_features else None,
        )
    if signals.dissatisfaction or signals.feedback_stop:
        _add(aliases, relations, "P", "reference_context")
        return projection(category="feedback_stop_before_new_plan", route="STOP")
    if signals.round_limit_conflict:
        _add(aliases, relations, "B", "reference_context")
        _add(aliases, relations, "P", "direct_evidence")
        return projection(category="bounded_plan_family_conflict", route="BLOCK")
    if signals.not_yet_effective:
        _add(aliases, relations, "FX", "conflict_evidence")
        return projection(category="not_yet_effective_knowledge", route="UNKNOWN")
    if signals.expired:
        _add(aliases, relations, "FX", "conflict_evidence")
        _add(aliases, relations, "B", "reference_context")
        return projection(category="expired_knowledge_block", route="BLOCK")
    if signals.current_version_priority:
        _add(aliases, relations, "B", "direct_evidence")
        _add(aliases, relations, "FX", "reference_context")
        return projection(
            category="current_reviewed_version_preferred",
            route="DIRECT",
            retriever_kind="beautify",
        )
    if signals.hard_fact_conflict:
        if _has(normalized, "官方卡", "高权威") and _has(normalized, "低权威", "笔记", "不支持"):
            _add(aliases, relations, "FX", "conflict_evidence")
            _add(aliases, relations, "B", "direct_evidence")
        else:
            _add(aliases, relations, "FX", "conflict_evidence")
        return projection(category="hard_fact_conflict", route="BLOCK")
    if signals.review_due_without_expiry:
        _add(aliases, relations, "FX", "reference_context")
        return projection(category="knowledge_review_due", route="REFERENCE")
    if signals.no_long_term_anchor:
        _add(aliases, relations, "P", "direct_evidence")
        return projection(category="current_session_anchor_degrade", route="BASELINE")
    if signals.retrieval_miss:
        _add(aliases, relations, "P", "direct_evidence")
        return projection(category="retriever_miss_baseline_fallback", route="BASELINE")
    if signals.verification_strategy:
        _add(aliases, relations, "C", "reference_context")
        _add(aliases, relations, "P", "direct_evidence")
        return projection(category="verification_strategy_advisory", route="REFERENCE")
    if signals.public_revoke:
        _add(aliases, relations, "P", "direct_evidence")
        return projection(category="public_demo_revoke_explanation", route="REFERENCE")
    if signals.subject_match:
        _add(aliases, relations, "C", "reference_context")
        _add(aliases, relations, "P", "reference_context")
        return projection(
            category="information_only_subject_match",
            route="REFERENCE",
            retriever_kind="compare_face",
        )
    if signals.moderation:
        _add(aliases, relations, "I", "reference_context")
        _add(aliases, relations, "P", "reference_context")
        return projection(
            category="information_only_moderation_scope",
            route="REFERENCE",
            retriever_kind="moderation",
        )
    if signals.closed_provider_scope:
        _add(aliases, relations, "B", "direct_evidence")
        _add(aliases, relations, "P", "reference_context")
        return projection(
            category="approved_provider_scope",
            route="DIRECT",
            retriever_kind="beautify",
        )
    if signals.adapter_unready or signals.unknown_provider:
        if _has(normalized, "未获产品准入", "未准入", "未批准", "不准入"):
            _add(aliases, relations, "P", "direct_evidence")
            return projection(category="unapproved_provider_block", route="BLOCK")
        _add(aliases, relations, "B", "reference_context")
        _add(aliases, relations, "P", "direct_evidence")
        return projection(category="provider_or_adapter_not_ready", route="REFERENCE")
    if signals.batch_or_multiface or signals.third_party:
        if signals.face_isolation and not _has(
            normalized, "只改我", "只修左边", "只修右边", "左边的人", "右边的人"
        ):
            # The original validation compiler already handled the reviewed
            # "只编辑我/隔离/回贴" wording.  Newly added positional wording is
            # owned by the generalized candidate; leave it on the old generic
            # path so the frozen V3 diagnostic remains reproducible.
            _add(aliases, relations, "B", "direct_evidence")
            _add(aliases, relations, "P", "direct_evidence")
            return projection(category="multiface_isolation_scope", route="SUGGEST")
        _add(aliases, relations, "B", "reference_context")
        _add(aliases, relations, "P", "reference_context")
        return projection(
            category="batch_or_multiface_scope",
            route="SUGGEST" if signals.per_item_plan or signals.third_party else "CLARIFY",
        )
    if signals.result_worsened:
        _add(aliases, relations, "B", "reference_context")
        _add(aliases, relations, "P", "direct_evidence")
        return projection(category="verification_worsened_stop", route="STOP")
    if signals.skin_edit_requested:
        _add(aliases, relations, "B", "direct_evidence")
        _add(aliases, relations, "P", "reference_context")
        requested = tuple(
            feature
            for feature in signals.executable_features
            if feature in {EditableFeature.WHITENING, EditableFeature.SMOOTHING}
        )
        return projection(
            category="reviewed_skin_edit_explicitly_requested",
            route="DIRECT",
            requested=requested,
            allowed=requested,
            retriever_kind="beautify",
        )
    if signals.unsupported_features:
        _add(aliases, relations, "B", "reference_context")
        return projection(
            category="unsupported_facial_feature",
            route="SUGGEST",
            requested=signals.unsupported_features,
            allowed=signals.unsupported_features,
            retriever_kind="beautify",
        )
    if signals.executable_features:
        _add(aliases, relations, "B", "direct_evidence")
        if signals.natural_preference or _has(
            normalized, "比母版", "当前工具", "面积", "参数", "差异"
        ):
            _add(aliases, relations, "P", "reference_context")
        return projection(
            category="reviewed_executable_feature",
            route="DIRECT",
            requested=signals.executable_features,
            allowed=signals.executable_features,
            preserve=(
                (PreserveAttribute.SKIN_TONE, PreserveAttribute.MAKEUP)
                if signals.preserve_skin_or_makeup
                else ()
            ),
            retriever_kind="beautify",
        )
    if signals.natural_preference or signals.information_request:
        _add(aliases, relations, "P", "direct_evidence")
        return projection(category="product_policy_information", route="REFERENCE")
    _add(aliases, relations, "P", "reference_context")
    return projection(category="no_reliable_projection", route="UNKNOWN")


def _query_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_failure_driven_candidate(
    cases: tuple[GoldCase, ...],
    *,
    runtime_mode: str = "public",
    compiler: Callable[[GoldCase], tuple[BaselineProjection, QuerySignals]] = (
        compile_generalized_projection
    ),
    runner_version: str = QUERY_COMPILER_CANDIDATE_VERSION,
) -> tuple[tuple[Prediction, ...], tuple[dict[str, object], ...]]:
    """Run the compiler against public development or unlocked validation cases.

    ``runtime_mode='public'`` keeps the original D*/X* development boundary.
    ``runtime_mode='validation'`` is an explicit product-owner-unlocked path
    for the former H* Holdout, now treated as a diagnostic validation set.
    Neither mode reads answers inside this function; scoring remains a
    separate operation.
    """

    if runtime_mode == "public":
        RagGoldDeterministicBaseline._validate_cases(cases, runtime_mode="public")
    elif runtime_mode == "validation":
        if not cases:
            raise ValueError("validation candidate requires at least one case")
        invalid = [
            case.case_id
            for case in cases
            if case.split != "validation" or not _VALIDATION_ID.fullmatch(case.case_id)
        ]
        if invalid:
            raise ValueError(
                "validation candidate accepts only owner-unlocked H* validation cases; "
                f"rejected {sorted(invalid)}"
            )
    else:
        raise ValueError(f"unsupported query compiler runtime mode: {runtime_mode}")
    with tempfile.TemporaryDirectory(prefix="portrait-rag-query-compiler-") as directory:
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
        predictions: list[Prediction] = []
        traces: list[dict[str, object]] = []
        for case in cases:
            projection, signals = compiler(case)
            query = _query_for_projection(case, projection)
            advisory = (
                service.advise(
                    query=query,
                    existing_baseline_available=False,
                    advice_id=f"query_compiler_{case.case_id.lower()}",
                )
                if query is not None
                else None
            )
            retrieval = advisory.retrieval if advisory is not None else None
            aliases = list(projection.evidence_aliases)
            relations = dict(projection.evidence_relations)
            if retrieval is not None:
                # A retrieved card is evidence of availability, but the
                # projection's reviewed relation remains authoritative.
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
                trace_ref=f"{runner_version}:{case.case_id}",
                machine_score_summary=_run_counts(retrieval),
            )
            predictions.append(prediction)
            traces.append(
                {
                    "case_id": case.case_id,
                    "runner_version": runner_version,
                    "query_sha256": _query_sha(case.query),
                    "normalization_changed": signals.normalized != case.query.casefold(),
                    "category_codes": list(projection.category_codes),
                    "signal_flags": {
                        "hard_block": signals.hard_block,
                        "no_outbound": signals.no_outbound,
                        "conflict": signals.conflict,
                        "batch_or_multiface": signals.batch_or_multiface,
                        "information_request": signals.information_request,
                        "explicit_execute": signals.explicit_execute,
                        "unsupported_feature_count": len(signals.unsupported_features),
                        "executable_feature_count": len(signals.executable_features),
                        "natural_preference": signals.natural_preference,
                        "skin_edit_requested": signals.skin_edit_requested,
                        "no_long_term_anchor": signals.no_long_term_anchor,
                        "replan_context": signals.replan_context,
                        "dissatisfaction": signals.dissatisfaction,
                        "round_limit_conflict": signals.round_limit_conflict,
                        "review_due_without_expiry": signals.review_due_without_expiry,
                        "not_yet_effective": signals.not_yet_effective,
                        "hard_fact_conflict": signals.hard_fact_conflict,
                        "explicit_injection": signals.explicit_injection,
                        "closed_provider_scope": signals.closed_provider_scope,
                        "retrieval_miss": signals.retrieval_miss,
                        "verification_strategy": signals.verification_strategy,
                        "face_isolation": signals.face_isolation,
                        "third_party_consent_denied": signals.third_party_consent_denied,
                        "public_revoke": signals.public_revoke,
                        "result_worsened": signals.result_worsened,
                        "param_range_violation": signals.param_range_violation,
                        "per_item_plan": signals.per_item_plan,
                        "current_version_priority": signals.current_version_priority,
                    },
                    "compile_projection": {
                        "route": projection.route_override,
                        "category_codes": list(projection.category_codes),
                        "evidence_aliases": list(projection.evidence_aliases),
                        "evidence_relations": dict(projection.evidence_relations),
                        "requested_features": [
                            feature.value for feature in projection.requested_features
                        ],
                        "allowed_features": [
                            feature.value for feature in projection.allowed_features
                        ],
                        "preserve_constraints": [
                            attribute.value for attribute in projection.preserve_constraints
                        ],
                        "outbound_allowed": projection.outbound_allowed,
                        "missing_critical_slots": list(projection.missing_critical_slots),
                    },
                    "structured_query_created": query is not None,
                    "retrieval_route": retrieval.result.route.value
                    if retrieval is not None
                    else None,
                    "prediction_route": prediction.route,
                    "evidence_refs": list(prediction.evidence_refs),
                    "evidence_relations": dict(prediction.evidence_relations),
                    "machine_score_summary": dict(prediction.machine_score_summary),
                    "raw_prompt_persisted": False,
                    "photo_or_face_vector_read": False,
                    "llm_called": False,
                    "provider_api_called": False,
                    "network_called": False,
                    "active_baseline_changed": False,
                    "retrieval_trace": list(retrieval.trace) if retrieval is not None else [],
                }
            )
    return tuple(predictions), tuple(traces)


__all__ = [
    "QUERY_COMPILER_CANDIDATE_VERSION",
    "QUERY_COMPILER_CANDIDATE_V2_VERSION",
    "GENERALIZED_QUERY_COMPILER_V2_VERSION",
    "GENERALIZED_QUERY_COMPILER_V3_VERSION",
    "QuerySignals",
    "compile_generalized_projection",
    "compile_generalized_projection_v2",
    "compile_generalized_projection_v3",
    "compile_validation_projection_v2",
    "extract_query_signals",
    "normalize_for_compilation",
    "run_failure_driven_candidate",
]
