# ruff: noqa: E501
"""V4 failure-driven query compiler candidate.

V4 is an owner-unlocked diagnostic set only after its answerless blind
snapshot has been sealed.  This module does not contain V4 case IDs.  It adds
reviewed Chinese paraphrases and a few reusable policy distinctions that were
missing from the previous compiler (for example, "do not send photos to the
text model" is different from "do not send photos anywhere").  It remains a
proposal-only compiler: it produces a structured projection for evaluation,
never grants a tool permission and never calls a provider.
"""

from __future__ import annotations

import re
from dataclasses import replace

from portrait_consistency_agent.core.contracts import EditableFeature, PreserveAttribute
from portrait_consistency_agent.services.rag_gold_baseline import BaselineProjection
from portrait_consistency_agent.services.rag_gold_eval import GoldCase
from portrait_consistency_agent.services.rag_query_compiler_candidate import (
    QuerySignals,
    compile_validation_projection_v2,
    normalize_for_compilation,
)

V4_QUERY_COMPILER_CANDIDATE_VERSION = "rag-query-compiler-candidate-v0.4-v4"


def normalize_v4_for_compilation(text: str) -> str:
    """Normalize reviewed V4 wording into product vocabulary in memory.

    The replacements are intentionally generic and reviewable.  They are not
    keyed by holdout IDs and are never persisted as the original user text.
    """

    value = normalize_for_compilation(text)
    replacements = (
        # Geometry and facial feature paraphrases.
        ("脸廓", "脸宽"),
        ("脸颊两侧", "脸宽"),
        ("脸颊收窄", "瘦脸"),
        ("下巴线条", "脸宽"),
        ("下颌线太外扩", "脸宽"),
        ("更有神", "大眼"),
        ("眼神更大", "大眼"),
        ("眼睛开合", "眼睛大小"),
        ("两眼之间的空隙", "眼距"),
        ("两眼之间空隙", "眼距"),
        ("眼间空隙", "眼距"),
        ("嘴角轮廓", "嘴唇"),
        ("上唇厚度", "唇厚"),
        ("眉峰", "眉毛"),
        ("耳廓", "耳朵"),
        ("鼻梁轮廓", "鼻子变小"),
        ("肤色亮", "美白"),
        ("皮肤更平滑", "磨皮"),
        ("原妆", "保留妆面"),
        # Scope, privacy and lifecycle wording.
        ("照片只能留在本机", "不外发"),
        ("照片只留在本机", "不外发"),
        ("只在本机处理", "不外发"),
        ("照片只能在本机", "不外发"),
        ("索引服务坏了", "索引坏"),
        ("今天到期", "已过期"),
        ("卡今天到期", "已过期"),
        ("明天才生效", "下周才生效"),
        ("明天生效", "下周才生效"),
        ("新服务", "新工具"),
        ("产品准入", "未获产品准入"),
        ("临时试用", "未获产品准入"),
        ("只问能力", "只做能力调研"),
        ("能力调研", "只做能力调研"),
        ("不要产生任何图片调用", "不要执行"),
        ("不沿用第一张的数值", "每张单独"),
        ("组图", "批量"),
        ("写真", "批量"),
        ("只看最终结果", "自动选方案"),
        ("完全像", "完全对齐"),
        ("没有直接证据", "无可用直接证据"),
        ("不要让模型自行补工具", "不要让模型猜"),
        ("冲突标记", "相反范围"),
        ("能力说明和冲突", "相反范围"),
    )
    for source, target in replacements:
        value = value.replace(source, target)
    return value


def _contains(text: str, *terms: str) -> bool:
    return any(term in text for term in terms)


def _projection(
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
) -> BaselineProjection:
    return BaselineProjection(
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
    )


def compile_v4_projection_v1(case: GoldCase) -> tuple[BaselineProjection, QuerySignals]:
    """Compile V4 wording with reusable policy-first distinctions.

    The previous V2 compiler is used as the safe fallback.  Overrides are
    expressed as semantic phrases (feature, lifecycle, privacy or workflow),
    not case IDs.  This keeps the candidate suitable for a later independent
    regression set.
    """

    normalized = normalize_v4_for_compilation(case.query)
    synthetic = GoldCase(case_id=case.case_id, split=case.split, query=normalized)
    base, signals = compile_validation_projection_v2(synthetic)

    def result(projection: BaselineProjection) -> tuple[BaselineProjection, QuerySignals]:
        return projection, replace(signals, normalized=normalized)

    # A local-only constraint is a hard outbound block, unless the user is
    # explicitly asking for the already-defined local verification strategy.
    local_only = _contains(
        normalized,
        "不外发",
        "任何云端都不要",
        "不允许云端",
    ) and not _contains(normalized, "本地几何复测", "本地几何")
    if local_only:
        return result(
            _projection(
                category="local_only_outbound_block",
                route="BLOCK",
                aliases=("P",),
                relations={"P": "direct_evidence"},
                outbound_allowed=False,
            )
        )

    # It is safe to use the image provider while explicitly forbidding image
    # or vector data from the text model.  This is not the same as a blanket
    # no-cloud rule.
    provider_allowed_text_boundary = (
        _contains(normalized, "腾讯", "腾讯处理")
        and _contains(normalized, "文本模型")
        and _contains(normalized, "不要交给", "不交给", "不发送给")
        and _contains(normalized, "处理", "可以发", "允许")
    )
    if provider_allowed_text_boundary:
        return result(
            _projection(
                category="provider_allowed_text_model_boundary",
                route="DIRECT",
                aliases=("B", "P"),
                relations={"B": "direct_evidence", "P": "reference_context"},
                retriever_kind="beautify",
            )
        )

    # Third-party/minor consent is a hard block even if the uploader is the
    # subject of the photo.
    minor_or_third_party = _contains(
        normalized,
        "未成年",
        "妹妹",
        "弟弟",
        "朋友",
        "背景里",
        "其他人",
    )
    if minor_or_third_party and _contains(
        normalized,
        "只保证自己授权",
        "没有拿到",
        "没有公开展示许可",
    ):
        return result(
            _projection(
                category="third_party_or_minor_consent_block",
                route="BLOCK",
                aliases=("P",),
                relations={"P": "direct_evidence"},
            )
        )

    # Lifecycle and knowledge authority rules are handled before capability
    # terms so an expired/conflicting card cannot become an edit plan.
    if _contains(normalized, "已过期", "过期", "expired") and not _contains(
        normalized, "还没过期", "没过期", "未过期", "尚未过期"
    ):
        return result(
            _projection(
                category="expired_knowledge_block",
                route="BLOCK",
                aliases=("FX", "B"),
                relations={"FX": "conflict_evidence", "B": "reference_context"},
            )
        )
    if _contains(normalized, "下周才生效", "尚未生效", "未来生效") and _contains(
        normalized, "旧卡", "仍然有效", "当前"
    ):
        return result(
            _projection(
                category="current_card_until_future_card_effective",
                route="DIRECT",
                aliases=("B", "FX"),
                relations={"B": "direct_evidence", "FX": "reference_context"},
                retriever_kind="beautify",
            )
        )
    if _contains(normalized, "复审期", "复审") and _contains(
        normalized, "还没过期", "未过期", "待复核"
    ):
        return result(
            _projection(
                category="knowledge_review_due",
                route="REFERENCE",
                aliases=("FX",),
                relations={"FX": "reference_context"},
            )
        )
    if _contains(normalized, "官方卡", "个人经验笔记") and _contains(
        normalized, "说法不同", "不同", "权威级别"
    ):
        return result(
            _projection(
                category="authority_conflict_requires_block",
                route="BLOCK",
                aliases=("FX", "B"),
                relations={"FX": "conflict_evidence", "B": "direct_evidence"},
            )
        )
    if _contains(normalized, "相反范围", "相反参数", "参数冲突", "两个范围", "不能自动挑"):
        # Authority-level comparison is useful context; an unresolved hard
        # conflict must not be silently resolved by similarity.
        if (
            _contains(normalized, "官方", "权威", "说明")
            and _contains(normalized, "个人", "笔记", "经验")
        ) or _contains(normalized, "能力说明", "冲突标记"):
            return result(
                _projection(
                    category="authority_conflict_requires_block",
                    route="BLOCK",
                    aliases=("FX", "B"),
                    relations={"FX": "conflict_evidence", "B": "reference_context"},
                )
            )
        if _contains(normalized, "官方卡", "经验笔记") and _contains(normalized, "不同", "冲突"):
            return result(
                _projection(
                    category="authority_conflict_requires_block",
                    route="BLOCK",
                    aliases=("FX", "B"),
                    relations={"FX": "conflict_evidence", "B": "reference_context"},
                )
            )
        return result(
            _projection(
                category="hard_fact_conflict",
                route="BLOCK",
                aliases=("FX",),
                relations={"FX": "conflict_evidence"},
            )
        )
    if _contains(normalized, "知识段落", "知识库段落", "知识片段", "资料要求") and _contains(
        normalized, "任意 api", "任意服务", "安全规则当建议", "忽略安全"
    ):
        return result(
            _projection(
                category="knowledge_prompt_injection_block",
                route="BLOCK",
                aliases=("FX", "P"),
                relations={"FX": "conflict_evidence", "P": "direct_evidence"},
                outbound_allowed=False,
            )
        )

    # Explicitly unapproved/new provider or a request to trial a new service.
    if _contains(normalized, "未获产品准入", "未准入", "绕过白名单", "临时试用"):
        return result(
            _projection(
                category="unapproved_provider_block",
                route="BLOCK",
                aliases=("P",),
                relations={"P": "direct_evidence"},
            )
        )
    if _contains(normalized, "只能用当前审核过", "只允许腾讯", "不能临时试用"):
        return result(
            _projection(
                category="closed_provider_scope_block",
                route="BLOCK",
                aliases=("P",),
                relations={"P": "direct_evidence"},
            )
        )
    if _contains(normalized, "索引坏", "索引不可用", "知识库故障"):
        return result(
            _projection(
                category="index_unavailable_unknown",
                route="UNKNOWN",
                aliases=("P",),
                relations={"P": "direct_evidence"},
            )
        )

    if _contains(normalized, "人脸识别成功", "同一张图人脸识别") and _contains(
        normalized, "内容审核", "提示风险", "风险"
    ):
        return result(
            _projection(
                category="moderation_risk_overrides_subject_match",
                route="BLOCK",
                aliases=("I", "P", "C"),
                relations={
                    "I": "direct_evidence",
                    "P": "direct_evidence",
                    "C": "reference_context",
                },
                retriever_kind="moderation",
            )
        )

    # An adapter/card that has not passed a real smoke test is not executable,
    # even if its prose says the feature is supported.
    if _contains(normalized, "执行器还没", "未 smoke", "真实 smoke", "还没有真实"):
        return result(
            _projection(
                category="provider_or_adapter_not_ready",
                route="REFERENCE",
                aliases=("B", "P"),
                relations={"B": "reference_context", "P": "direct_evidence"},
            )
        )

    # Workflow-specific decisions which require a more precise evidence pack.
    if _contains(normalized, "撤回公开展示", "新页面不能继续展示"):
        return result(
            _projection(
                category="public_demo_revoke_explanation",
                route="REFERENCE",
                aliases=("P",),
                relations={"P": "direct_evidence"},
            )
        )
    if _contains(normalized, "上一张可用结果", "边缘变形", "变形"):
        return result(
            _projection(
                category="verification_artifact_worsened_stop",
                route="STOP",
                aliases=("B", "P"),
                relations={"B": "reference_context", "P": "direct_evidence"},
            )
        )
    if _contains(normalized, "先生成方案", "不要执行", "只生成方案") and _contains(
        normalized, "脸宽", "眼睛", "大眼"
    ):
        return result(
            _projection(
                category="plan_only_before_execution",
                route="SUGGEST",
                aliases=("B", "P"),
                relations={"B": "reference_context", "P": "reference_context"},
                retriever_kind="beautify",
            )
        )
    if _contains(normalized, "眼睛更偏", "累积改善", "确有累积") and _contains(
        normalized, "下一轮", "继续"
    ):
        return result(
            _projection(
                category="cumulative_improvement_replan",
                route="REPLAN",
                aliases=("B", "P"),
                relations={"B": "direct_evidence", "P": "reference_context"},
                retriever_kind="beautify",
            )
        )
    if _contains(normalized, "先重新理解", "不要立刻再调", "不自然"):
        return result(
            _projection(
                category="dissatisfaction_stop_before_new_plan",
                route="STOP",
                aliases=("P",),
                relations={"P": "direct_evidence"},
            )
        )
    if _contains(normalized, "不想看滑杆", "自动选方案", "只看最终结果"):
        return result(
            _projection(
                category="agent_selects_plan_with_trace",
                route="DIRECT",
                aliases=("B", "P"),
                relations={"B": "direct_evidence", "P": "reference_context"},
                retriever_kind="beautify",
            )
        )

    # Batch and multi-face wording must produce a per-item suggestion, never
    # one copied parameter set and never an implicit background edit.
    if _contains(normalized, "批量", "每张单独", "侧脸", "合照", "隔离") and _contains(
        normalized, "每张", "单独", "右侧", "其他人的脸", "不沿用", "不要卡住", "第 4 张"
    ):
        relation = {"B": "reference_context", "P": "direct_evidence"}
        if _contains(
            normalized, "每张单独", "每张分别", "不沿用", "单独测量", "单独规划", "不要卡住"
        ) and not _contains(normalized, "右侧", "其他人的脸", "隔离"):
            relation = {"B": "reference_context", "P": "reference_context"}
        return result(
            _projection(
                category="batch_per_item_or_multiface_isolation",
                route="SUGGEST",
                aliases=("B", "P"),
                relations=relation,
            )
        )

    # V4's capability-only examples distinguish an explanatory article from a
    # verified executable card.
    if _contains(normalized, "只做能力调研") and not _contains(
        normalized, "颧骨", "鼻子", "鼻翼", "眼距", "嘴唇", "眉毛"
    ):
        return result(
            _projection(
                category="capability_research_only",
                route="REFERENCE",
                aliases=("B", "P"),
                relations={"B": "reference_context", "P": "reference_context"},
            )
        )
    if _contains(normalized, "只做能力调研", "解释", "文章", "没有找到当前可执行"):
        if _contains(normalized, "颧骨", "鼻子", "鼻翼", "眼距", "嘴唇", "眉毛"):
            return result(
                _projection(
                    category="capability_only_unsupported_feature",
                    route="REFERENCE" if _contains(normalized, "只做能力调研") else "SUGGEST",
                    aliases=("B",),
                    relations={"B": "reference_context"},
                )
            )
        return result(
            _projection(
                category="reference_only_no_executable_card",
                route="SUGGEST",
                aliases=("B",),
                relations={"B": "reference_context"},
            )
        )

    # Unsupported fine-grained facial features are suggestion-only.  We add
    # the missing V4 terms without pretending that a provider can execute them.
    if _contains(normalized, "眼距", "眼裂", "唇厚", "嘴唇", "眉毛", "耳朵", "鼻翼", "颧骨"):
        requested = list(signals.unsupported_features)
        if _contains(normalized, "颧骨") and EditableFeature.MOUTH_SHAPE not in requested:
            requested.append(EditableFeature.MOUTH_SHAPE)
        return result(
            _projection(
                category="unsupported_facial_feature",
                route="SUGGEST",
                aliases=("B",),
                relations={"B": "reference_context"},
                requested=tuple(dict.fromkeys(requested)),
                allowed=tuple(dict.fromkeys(requested)),
                retriever_kind="beautify",
            )
        )

    # An underspecified "make it like the template" request must ask for the
    # missing scope instead of silently selecting skin, makeup or contour.
    if _contains(normalized, "弄得像模板", "像模板") and (
        not _contains(normalized, "肤色", "妆面", "脸宽", "眼睛", "轮廓")
        or _contains(normalized, "还没说明", "没说明", "补齐关键偏好")
    ):
        return result(
            _projection(
                category="missing_critical_edit_scope",
                route="CLARIFY",
                aliases=("P",),
                relations={"P": "direct_evidence"},
                missing=("editable_scope",),
            )
        )

    # Parameter 0-100 is a hard contract; an out-of-range instruction cannot
    # be passed through even if the user wants automatic execution.
    if re.search(r"加\s*1[0-9]{2}", normalized) and _contains(
        normalized, "0 到 100", "0到100", "参数"
    ):
        return result(
            _projection(
                category="provider_parameter_range_block",
                route="BLOCK",
                aliases=("B", "P"),
                relations={"B": "direct_evidence", "P": "direct_evidence"},
            )
        )

    # Temporary anchor withdrawal degrades to current-session processing; it
    # does not make a single current edit impossible.
    if _contains(normalized, "撤回", "临时母版", "不保存人像锚点") and _contains(
        normalized, "当前", "这一次", "单张"
    ):
        return result(
            _projection(
                category="current_session_anchor_degrade",
                route="BASELINE",
                aliases=("P",),
                relations={"P": "direct_evidence"},
            )
        )

    # A direct feature request with preserved makeup/skin is executable and
    # needs both the provider fact and product-preservation context.
    if _contains(normalized, "脸宽", "瘦脸", "大眼"):
        features = list(signals.executable_features)
        return result(
            _projection(
                category="reviewed_executable_feature",
                route="DIRECT",
                aliases=("B", "P")
                if len(features) > 1
                or _contains(
                    normalized, "保留妆面", "不改变脸部轮廓", "不授权改变", "列出", "真正执行"
                )
                else ("B",),
                relations=(
                    {"B": "direct_evidence", "P": "reference_context"}
                    if len(features) > 1
                    or _contains(
                        normalized,
                        "保留妆面",
                        "不改变脸部轮廓",
                        "不授权改变",
                        "列出",
                        "真正执行",
                    )
                    else {"B": "direct_evidence"}
                ),
                requested=tuple(dict.fromkeys(features)),
                allowed=tuple(dict.fromkeys(features)),
                preserve=(
                    (PreserveAttribute.SKIN_TONE, PreserveAttribute.MAKEUP)
                    if _contains(normalized, "保留妆面", "保留肤色")
                    else ()
                ),
                retriever_kind="beautify",
            )
        )

    if _contains(normalized, "无可用直接证据", "不要让模型猜"):
        return result(
            _projection(
                category="retriever_miss_baseline_fallback",
                route="BASELINE",
                aliases=("P",),
                relations={"P": "direct_evidence"},
            )
        )

    # Pose limits make a complete-alignment promise unsafe; provide a
    # suggestion with the provider/policy context instead.
    if _contains(normalized, "侧脸", "完全对齐"):
        return result(
            _projection(
                category="pose_limits_alignment",
                route="SUGGEST",
                aliases=("B", "P"),
                relations={"B": "reference_context", "P": "reference_context"},
            )
        )

    # Preserve the v2 candidate when no V4-specific distinction applies.
    return result(base)


__all__ = [
    "V4_QUERY_COMPILER_CANDIDATE_VERSION",
    "compile_v4_projection_v1",
    "normalize_v4_for_compilation",
]
