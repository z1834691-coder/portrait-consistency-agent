"""Explainable geometry diagnosis and pre-edit plan generation.

Checkpoint 8A deliberately stops before any image-editing API call.  It joins
the already completed local quality/safety/subject gates with a locked
``ReferenceProfile`` and a textual ``IntentFrame``.  Numeric differences and
Tencent strengths are calculated by this deterministic module, not guessed by
an LLM.  The returned ``EditPlan`` is immutable, ``proposed`` and always needs
bounded user confirmation before a later executor can call Tencent.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from portrait_consistency_agent.core.contracts import (
    AdjustmentMode,
    ChangeDirection,
    ContentSafetyStatus,
    EditableFeature,
    EditPlan,
    ExecutableChange,
    FeatureDifference,
    IntentAction,
    IntentFrame,
    MeasurementStatus,
    MeasurementUnit,
    NormalizedFeature,
    PhotoQualityResult,
    PlanConstraintsSnapshot,
    PlanStatus,
    PreserveAttribute,
    QualityRoute,
    ReferenceProfile,
    SafetyPolicySnapshot,
    SubjectMatchStatus,
    SuggestionOnlyChange,
    TencentBeautifyParams,
)
from portrait_consistency_agent.core.policies import build_v0_safety_policy
from portrait_consistency_agent.core.rag_contracts import RagAdvisoryDecision, RagAdvisoryRoute
from portrait_consistency_agent.services.photo_quality import PhotoObservation
from portrait_consistency_agent.services.provider_cards import load_tencent_beautify_card
from portrait_consistency_agent.storage.local_store import LocalTraceStore

PLANNER_VERSION = "geometry-edit-planner-v0.1"
MAPPING_POLICY_ID = "mapping_policy_v0.1"
MAPPING_POLICY_VERSION = "2026-08-28"


@dataclass(frozen=True)
class EditMappingPolicy:
    """Versioned product mapping from measured gap to provider strength.

    These are configurable product choices, not a calibrated probability model.
    A later benchmark can replace this policy without changing the contracts.
    """

    policy_id: str = MAPPING_POLICY_ID
    policy_version: str = MAPPING_POLICY_VERSION
    within_tolerance: float = 0.04
    max_auto_gap: float = 0.12
    strength_floor: int = 4
    max_strength_by_mode: dict[AdjustmentMode, int] = field(
        default_factory=lambda: {
            AdjustmentMode.PRESERVE_ORIGINAL: 8,
            AdjustmentMode.BALANCED: 15,
            AdjustmentMode.CONSISTENCY_FIRST: 22,
        }
    )
    minimum_measurement_confidence: float = 0.80

    def __post_init__(self) -> None:
        if not 0 < self.within_tolerance < self.max_auto_gap:
            raise ValueError("mapping tolerances must be ordered and positive")
        if not 0 <= self.strength_floor <= 100:
            raise ValueError("strength_floor must stay within Tencent's 0..100 range")
        if not 0 < self.minimum_measurement_confidence <= 1:
            raise ValueError("minimum_measurement_confidence must be in (0, 1]")
        if any(not 0 <= value <= 100 for value in self.max_strength_by_mode.values()):
            raise ValueError("mode strength caps must stay within Tencent's 0..100 range")

    def strength_for_gap(self, gap: float, mode: AdjustmentMode) -> int:
        """Map a usable gap to a small, visible provider strength."""

        cap = self.max_strength_by_mode[mode]
        if gap <= self.within_tolerance:
            return 0
        if gap >= self.max_auto_gap:
            return cap
        progress = (gap - self.within_tolerance) / (self.max_auto_gap - self.within_tolerance)
        value = self.strength_floor + progress * (cap - self.strength_floor)
        return max(self.strength_floor, min(cap, round(value)))


@dataclass(frozen=True)
class PlanDraftResult:
    """User-facing and trace-facing result of one read-only planning run."""

    plan: EditPlan | None
    feature_differences: tuple[FeatureDifference, ...]
    route: str
    reason_codes: tuple[str, ...]
    user_message: str
    trace: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class _MappingRule:
    feature_code: str
    product_feature: EditableFeature
    provider_parameter: str
    # ``target_above`` is the direction in which the provider strength should
    # increase.  FaceLifting reduces a wider face ratio; EyeEnlarging increases
    # a smaller eye-area ratio.
    target_above: ChangeDirection
    display_name: str
    unit: MeasurementUnit


MAPPING_RULES: tuple[_MappingRule, ...] = (
    _MappingRule(
        feature_code="face_width_height_ratio",
        product_feature=EditableFeature.FACE_LIFTING,
        provider_parameter="FaceLifting",
        target_above=ChangeDirection.INCREASE,
        display_name="脸部宽高比例",
        unit=MeasurementUnit.NORMALIZED_RATIO,
    ),
    _MappingRule(
        feature_code="eye_area_mean_face_ratio",
        product_feature=EditableFeature.EYE_ENLARGING,
        provider_parameter="EyeEnlarging",
        target_above=ChangeDirection.DECREASE,
        display_name="眼睛面积占脸部比例",
        unit=MeasurementUnit.NORMALIZED_RATIO,
    ),
)


def _numeric_value(feature: NormalizedFeature | None) -> float | None:
    if feature is None or feature.status == MeasurementStatus.UNAVAILABLE:
        return None
    if isinstance(feature.value, bool) or not isinstance(feature.value, (int, float)):
        return None
    return float(feature.value)


def _feature_map(features: list[NormalizedFeature]) -> dict[str, NormalizedFeature]:
    return {feature.feature_code: feature for feature in features}


def _gap(reference: NormalizedFeature, observed: NormalizedFeature) -> float | None:
    ref_value = _numeric_value(reference)
    observed_value = _numeric_value(observed)
    if ref_value is None or observed_value is None:
        return None
    if reference.unit == MeasurementUnit.NORMALIZED_POSITION:
        return abs(observed_value - ref_value)
    return abs(observed_value - ref_value) / max(abs(ref_value), 1e-6)


def _confidence(reference: NormalizedFeature, observed: NormalizedFeature) -> float:
    return min(reference.confidence or 0.0, observed.confidence or 0.0)


def _preflight_reasons(
    *,
    profile: ReferenceProfile,
    target_observation: PhotoObservation,
    quality_result: PhotoQualityResult,
    intent: IntentFrame,
    subject_match_uncertain_acknowledged: bool,
) -> list[str]:
    reasons: list[str] = []
    if quality_result.photo_id != target_observation.photo_id:
        reasons.append("quality_photo_mismatch")
    if quality_result.photo_sha256 != target_observation.photo_sha256:
        reasons.append("quality_hash_mismatch")
    if quality_result.content_safety_status != ContentSafetyStatus.PASSED:
        reasons.append("content_safety_not_passed")
    if quality_result.subject_match_status == SubjectMatchStatus.NO_MATCH:
        reasons.append("subject_match_not_confirmed")
    elif (
        quality_result.subject_match_status == SubjectMatchStatus.UNCERTAIN
        and not subject_match_uncertain_acknowledged
    ):
        reasons.append("subject_match_confirmation_required")
    quality_route_allowed = quality_result.route in {
        QualityRoute.CONTINUE,
        QualityRoute.WARN_CONTINUE,
    }
    uncertain_route_acknowledged = (
        quality_result.subject_match_status == SubjectMatchStatus.UNCERTAIN
        and subject_match_uncertain_acknowledged
        and quality_result.route == QualityRoute.SUBJECT_CONFIRMATION_REQUIRED
    )
    if not quality_route_allowed and not uncertain_route_acknowledged:
        reasons.append("quality_route_not_continuable")
    if quality_result.face_count != 1 or target_observation.face_count != 1:
        reasons.append("single_face_required_for_v0_plan")
    if profile.profile_id == "":
        reasons.append("profile_missing")
    if intent.missing_slots:
        reasons.append("intent_missing_slots")
    return reasons


def _feature_difference(
    reference: NormalizedFeature | None,
    observed: NormalizedFeature | None,
    *,
    feature_code: str,
    editable: bool,
    reason_codes: list[str],
) -> FeatureDifference:
    if reference is None or observed is None:
        return FeatureDifference(
            feature_code=feature_code,
            measurement_confidence=0.0,
            editable=False,
            reason_codes=[*reason_codes, "feature_not_measurable"],
        )
    confidence = _confidence(reference, observed)
    value_gap = _gap(reference, observed)
    if value_gap is None:
        return FeatureDifference(
            feature_code=feature_code,
            measurement_confidence=confidence,
            editable=False,
            reason_codes=[*reason_codes, "feature_not_measurable"],
        )
    return FeatureDifference(
        feature_code=feature_code,
        reference_value=_numeric_value(reference),
        observed_value=_numeric_value(observed),
        normalized_gap=value_gap,
        measurement_confidence=confidence,
        editable=editable,
        reason_codes=reason_codes,
    )


def _suggestion(
    feature: EditableFeature,
    instruction: str,
    *reason_codes: str,
    user_delta: int | None = None,
) -> SuggestionOnlyChange:
    return SuggestionOnlyChange(
        feature=feature,
        user_delta=user_delta,
        instruction=instruction,
        reason_codes=list(reason_codes) or ["suggestion_only"],
    )


def _provider_parameters(
    *,
    face_lifting: int = 0,
    eye_enlarging: int = 0,
) -> TencentBeautifyParams:
    # Whitening and smoothing stay explicit zero in every V0 plan.  This keeps
    # the existing product decision that skin tone/texture is user-controlled.
    return TencentBeautifyParams(
        face_lifting=face_lifting,
        eye_enlarging=eye_enlarging,
        whitening=0,
        smoothing=0,
    )


def _plan_message(
    *,
    executable_changes: list[ExecutableChange],
    suggestions: list[SuggestionOnlyChange],
    differences: list[FeatureDifference],
    blocked_reason: str | None = None,
) -> str:
    reason_labels = {
        "subject_match_confirmation_required": "同人比对处于不确定区间，需要确认这是本人且有权编辑",
        "subject_match_not_confirmed": "同人比对未通过，需要检查照片或重新上传",
        "quality_route_not_continuable": "照片质量或当前可编辑性不允许继续",
        "content_safety_not_passed": "内容安全检查未通过",
        "single_face_required_for_v0_plan": "当前版本只处理单人脸照片",
    }
    measured = [item for item in differences if item.normalized_gap is not None]
    measured_text = (
        f"已完成 {len(measured)} 项局部几何测量；这些百分比是照片几何差异，不是相似度概率。"
        if measured
        else "当前没有可可靠展示的局部几何测量。"
    )
    actions = "、".join(
        f"{change.provider_parameter} +{change.user_delta}" for change in executable_changes
    )
    if actions:
        action_text = f"可生成待确认方案：{actions}。"
    else:
        action_text = "当前没有可自动执行的参数。"
    suggestion_text = (
        " " + "；".join(item.instruction for item in suggestions) if suggestions else ""
    )
    reason_text = ""
    if blocked_reason:
        labels = [reason_labels.get(code, code) for code in blocked_reason.split("、")]
        reason_text = f" 原因：{'；'.join(dict.fromkeys(labels))}。"
    return measured_text + " " + action_text + suggestion_text + reason_text


def diagnose_and_plan(
    *,
    profile: ReferenceProfile,
    target_observation: PhotoObservation,
    quality_result: PhotoQualityResult,
    intent: IntentFrame,
    mapping_policy: EditMappingPolicy | None = None,
    safety_policy: SafetyPolicySnapshot | None = None,
    rag_advice: RagAdvisoryDecision | None = None,
    subject_match_uncertain_acknowledged: bool = False,
    store: LocalTraceStore | None = None,
    plan_id: str | None = None,
) -> PlanDraftResult:
    """Create a read-only, explainable plan for one target photo.

    No image bytes are accepted and no network call is made.  A hard preflight
    failure returns ``plan=None``.  Otherwise a proposed ``EditPlan`` is
    created—even when no executable change is needed—so the diagnosis remains
    auditable in the local ledger.
    """

    mapping_policy = mapping_policy or EditMappingPolicy()
    safety_policy = safety_policy or build_v0_safety_policy()
    trace: list[dict[str, object]] = [
        {
            "step": "preflight",
            "profile_id": profile.profile_id,
            "profile_version": profile.version,
            "photo_id": target_observation.photo_id,
            "quality_route": quality_result.route.value,
            "content_safety": quality_result.content_safety_status.value,
            "subject_match": quality_result.subject_match_status.value,
            "subject_match_uncertain_acknowledged": subject_match_uncertain_acknowledged,
        }
    ]

    preflight = _preflight_reasons(
        profile=profile,
        target_observation=target_observation,
        quality_result=quality_result,
        intent=intent,
        subject_match_uncertain_acknowledged=subject_match_uncertain_acknowledged,
    )
    if rag_advice is not None:
        trace.append(
            {
                "step": "rag_advisory_preflight",
                "advice_id": rag_advice.advice_id,
                "retrieval_route": rag_advice.retrieval_route.value,
                "advisory_route": rag_advice.advisory_route.value,
                "direct_evidence_refs": rag_advice.direct_evidence_refs,
                "reference_information_refs": rag_advice.reference_information_refs,
                "conflict_information_refs": rag_advice.conflict_information_refs,
                "execution_authorized_by_rag": False,
                "existing_baseline_may_continue": rag_advice.existing_baseline_may_continue,
            }
        )
        if rag_advice.advisory_route in {
            RagAdvisoryRoute.CONFLICT_BLOCKED,
            RagAdvisoryRoute.UNKNOWN_STOPPED,
            RagAdvisoryRoute.MANUAL_SUGGESTION_ONLY,
        }:
            preflight.append(f"rag_{rag_advice.advisory_route.value}")
    if preflight:
        message = _plan_message(
            executable_changes=[],
            suggestions=[],
            differences=[],
            blocked_reason="、".join(preflight),
        )
        trace.append({"step": "route", "route": "blocked", "reason_codes": preflight})
        result = PlanDraftResult(
            plan=None,
            feature_differences=(),
            route="blocked",
            reason_codes=tuple(preflight),
            user_message=message,
            trace=tuple(trace),
        )
        if store is not None:
            store.record_event(
                quality_result.session_id,
                "edit_plan_diagnosis_blocked",
                {"photo_id": target_observation.photo_id, "reason_codes": preflight},
            )
        return result

    reference_features = _feature_map(profile.normalized_features)
    target_features = _feature_map(
        # Keep the same extraction implementation as Profile v0, while never
        # persisting the target image or its raw coordinates.
        _target_features(target_observation)
    )
    differences: list[FeatureDifference] = []
    executable: list[ExecutableChange] = []
    suggestions: list[SuggestionOnlyChange] = []
    params = {"face_lifting": 0, "eye_enlarging": 0}
    allowed = list(intent.allowed_features or profile.allowed_features)
    blocked = list(dict.fromkeys([*profile.blocked_features, *intent.blocked_features]))
    if set(allowed) & set(blocked):
        blocked = [feature for feature in blocked if feature not in set(allowed)]
    mode = intent.adjustment_mode or profile.adjustment_mode
    can_generate_executable_plan = intent.action in {
        IntentAction.PROVIDE_PLAN,
        IntentAction.EXECUTE,
    }

    mapped_codes = {rule.feature_code for rule in MAPPING_RULES}
    for rule in MAPPING_RULES:
        reference = reference_features.get(rule.feature_code)
        observed = target_features.get(rule.feature_code)
        diff = _feature_difference(
            reference,
            observed,
            feature_code=rule.feature_code,
            editable=reference is not None and observed is not None,
            reason_codes=["mapped_feature"],
        )
        differences.append(diff)
        ref_value = _numeric_value(reference)
        observed_value = _numeric_value(observed)
        confidence = diff.measurement_confidence
        if ref_value is None or observed_value is None:
            suggestions.append(
                _suggestion(
                    rule.product_feature,
                    f"{rule.display_name}暂时无法可靠测量，建议重拍正脸或手动调整。",
                    "feature_not_measurable",
                )
            )
            continue
        gap = diff.normalized_gap or 0.0
        if gap <= mapping_policy.within_tolerance:
            differences[-1] = diff.model_copy(
                update={
                    "reason_codes": [
                        "mapped_feature",
                        "feature_within_tolerance",
                    ]
                }
            )
            continue
        if confidence < mapping_policy.minimum_measurement_confidence:
            differences[-1] = diff.model_copy(
                update={
                    "editable": False,
                    "reason_codes": [
                        "mapped_feature",
                        "measurement_confidence_below_planning_minimum",
                    ],
                }
            )
            suggestions.append(
                _suggestion(
                    rule.product_feature,
                    f"{rule.display_name}的测量可靠性不足，暂不自动调整；可重拍更清晰的正脸。",
                    "measurement_confidence_below_planning_minimum",
                )
            )
            continue
        target_direction = (
            ChangeDirection.INCREASE
            if observed_value > ref_value
            else ChangeDirection.DECREASE
            if observed_value < ref_value
            else ChangeDirection.PRESERVE
        )
        if target_direction != rule.target_above:
            differences[-1] = diff.model_copy(
                update={
                    "editable": False,
                    "reason_codes": [
                        "mapped_feature",
                        "provider_cannot_move_toward_reference",
                    ],
                }
            )
            suggestions.append(
                _suggestion(
                    rule.product_feature,
                    f"{rule.display_name}的偏差方向不是当前工具能可靠反向调整的方向，建议暂不自动执行。",
                    "provider_cannot_move_toward_reference",
                )
            )
            continue
        if rule.product_feature in blocked:
            differences[-1] = diff.model_copy(
                update={
                    "editable": False,
                    "reason_codes": [
                        "mapped_feature",
                        "feature_blocked_by_user",
                    ],
                }
            )
            suggestions.append(
                _suggestion(
                    rule.product_feature,
                    f"你已禁止调整{rule.display_name}，因此只保留诊断，不执行参数。",
                    "feature_blocked_by_user",
                )
            )
            continue
        if rule.product_feature not in allowed:
            differences[-1] = diff.model_copy(
                update={
                    "editable": False,
                    "reason_codes": [
                        "mapped_feature",
                        "feature_not_allowed_by_intent",
                    ],
                }
            )
            suggestions.append(
                _suggestion(
                    rule.product_feature,
                    f"本轮没有授权调整{rule.display_name}，如需处理请在下一轮明确允许。",
                    "feature_not_allowed_by_intent",
                )
            )
            continue
        if not can_generate_executable_plan:
            differences[-1] = diff.model_copy(
                update={
                    "editable": False,
                    "reason_codes": ["mapped_feature", "diagnosis_only_intent"],
                }
            )
            continue
        strength = mapping_policy.strength_for_gap(gap, mode)
        if strength <= 0:
            continue
        field_name = (
            "face_lifting"
            if rule.product_feature == EditableFeature.FACE_LIFTING
            else "eye_enlarging"
        )
        params[field_name] = strength
        executable.append(
            ExecutableChange(
                feature=rule.product_feature,
                provider_parameter=rule.provider_parameter,
                user_delta=strength,
                current_absolute=0,
                proposed_absolute=strength,
                expected_direction=ChangeDirection.INCREASE,
                rationale_codes=[
                    "measured_geometry_gap",
                    f"gap_{round(gap * 100, 1)}_percent",
                    f"mapping_policy_{mapping_policy.policy_version}",
                ],
            )
        )
        differences[-1] = diff.model_copy(
            update={
                "reason_codes": [
                    "mapped_feature",
                    "plan_generated",
                ]
            }
        )

    # Supporting geometry remains visible for diagnosis but cannot silently
    # become a provider parameter (framing is not face shape, and eye distance
    # is not eye size).
    for code, reference in reference_features.items():
        if code in mapped_codes or code not in target_features:
            continue
        observed = target_features.get(code)
        differences.append(
            _feature_difference(
                reference,
                observed,
                feature_code=code,
                editable=False,
                reason_codes=["diagnostic_only", "no_current_provider_mapping"],
            )
        )

    if quality_result.route == QualityRoute.WARN_CONTINUE:
        suggestions.append(
            _suggestion(
                EditableFeature.FACE_LIFTING,
                "这张照片存在质量警告，执行前请再次确认可能存在偏差。",
                "quality_warning",
            )
        )
    if (
        quality_result.subject_match_status == SubjectMatchStatus.UNCERTAIN
        and subject_match_uncertain_acknowledged
    ):
        suggestions.append(
            _suggestion(
                EditableFeature.FACE_LIFTING,
                "同人比对处于不确定区间；你已确认这是本人且有权编辑，系统会继续，但结果可能存在偏差。",
                "subject_match_uncertain_acknowledged",
            )
        )

    card = load_tencent_beautify_card()
    plan = EditPlan(
        plan_id=plan_id or f"plan_{uuid.uuid4().hex}",
        revision=1,
        session_id=quality_result.session_id,
        profile_id=profile.profile_id,
        profile_version=profile.version,
        photo_id=target_observation.photo_id,
        photo_sha256=target_observation.photo_sha256,
        intent_id=intent.intent_id,
        quality_result_id=quality_result.quality_result_id,
        iteration=1,
        provider="tencent_beautify_pic",
        provider_api_version=str(card["api_version"]),
        provider_card_id=str(card["card_id"]),
        provider_card_version=str(card["card_version"]),
        knowledge_refs=(rag_advice.direct_evidence_refs if rag_advice is not None else []),
        baseline_feature_differences=differences,
        executable_changes=executable,
        suggestion_only_changes=suggestions,
        provider_absolute_params=_provider_parameters(**params),
        constraints_snapshot=PlanConstraintsSnapshot(
            allowed_features=allowed,
            blocked_features=blocked,
            preserve_attributes=list(
                dict.fromkeys(
                    [
                        *profile.preserve_attributes,
                        *intent.preserve_attributes,
                        PreserveAttribute.SKIN_TONE,
                        PreserveAttribute.MAKEUP,
                    ]
                )
            ),
            adjustment_mode=mode,
        ),
        safety_policy=safety_policy,
        risk_notes=[
            "几何差异来自当前照片测量，未校准为概率",
            "本计划只在用户确认后允许外部编辑",
            *(
                ["同人比对处于不确定区间，已记录用户本人/编辑权确认；不把它升级为 match 事实"]
                if subject_match_uncertain_acknowledged
                else []
            ),
            *(["RAG 仅提供已审核工具证据，未提供执行授权"] if rag_advice is not None else []),
        ],
        requires_confirmation=True,
        status=PlanStatus.PROPOSED,
        planner_version=PLANNER_VERSION,
        mapping_policy_version=mapping_policy.policy_version,
    )
    route = "plan_ready" if executable else "diagnosis_only"
    reason_codes = ["plan_generated" if executable else "no_executable_change"]
    trace.extend(
        [
            {
                "step": "measure",
                "feature_codes": [item.feature_code for item in differences],
                "measurement_count": len(
                    [item for item in differences if item.normalized_gap is not None]
                ),
            },
            {
                "step": "map",
                "mapping_policy_id": mapping_policy.policy_id,
                "mapping_policy_version": mapping_policy.policy_version,
                "adjustment_mode": mode.value,
                "executable_changes": [
                    {
                        "feature": change.feature.value,
                        "provider_parameter": change.provider_parameter,
                        "user_delta": change.user_delta,
                        "proposed_absolute": change.proposed_absolute,
                    }
                    for change in executable
                ],
                "suggestion_only_count": len(suggestions),
            },
            {
                "step": "persist_plan",
                "plan_id": plan.plan_id,
                "status": plan.status.value,
                "requires_confirmation": plan.requires_confirmation,
            },
        ]
    )
    result = PlanDraftResult(
        plan=plan,
        feature_differences=tuple(differences),
        route=route,
        reason_codes=tuple(reason_codes),
        user_message=_plan_message(
            executable_changes=executable,
            suggestions=suggestions,
            differences=differences,
        ),
        trace=tuple(trace),
    )
    if store is not None:
        store.save_edit_plan(plan)
        store.record_event(
            quality_result.session_id,
            "edit_plan_trace",
            {"plan_id": plan.plan_id, "route": route, "trace": trace},
        )
    return result


def _target_features(observation: PhotoObservation) -> list[NormalizedFeature]:
    """Reuse Profile v0's extractor while keeping target data in memory only."""

    from portrait_consistency_agent.services.reference_profile import extract_normalized_features

    return extract_normalized_features(observation)
