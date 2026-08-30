"""Checkpoint 8C-2: bounded, evidence-led plan-family continuation.

The first plan is explicitly confirmed by the user.  A follow-up plan is not
a silent retry and not a copy of the first Tencent parameters: it is a new
immutable ``EditPlan`` for the *returned result image*.  It can exist only
when 8C found a measurable improvement but insufficient target evidence, and
it remains inside the original confirmation scope, time limit, feature list,
and maximum-round limit.

This module does not call Tencent.  The first plan in the family must already
have an explicit, bounded external-processing confirmation.  A child plan may
then be executed automatically inside that same scope after a deterministic
preflight (and the caller must write that trigger and evidence to Trace); a
new click is not required for every round.  If the scope, provider, purpose,
budget, consent or lineage changes, the caller must stop and obtain new
authorization instead of auto-executing.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from portrait_consistency_agent.core.contracts import (
    ComparisonTrend,
    EditableFeature,
    EditPlan,
    ExecutableChange,
    FeatureDifference,
    FeedbackEvidenceStrength,
    FeedbackLabelSource,
    FeedbackSignal,
    FeedbackStatus,
    IntentFrame,
    InteractionOutcome,
    InteractionStage,
    MeasurementStatus,
    NormalizedFeature,
    PlanStatus,
    ProductEvent,
    ProductEventType,
    ProviderRun,
    ProviderRunStatus,
    ReferenceProfile,
    TencentBeautifyParams,
    UserFeedback,
    VerificationDecision,
    VerificationResult,
)
from portrait_consistency_agent.core.policies import (
    FollowupMappingPolicy,
    build_v0_followup_mapping_policy,
)
from portrait_consistency_agent.services.verification import (
    FEATURE_CODE_BY_PRODUCT_FEATURE,
    ResultObservation,
    observe_result_bytes,
)
from portrait_consistency_agent.storage.local_store import LocalTraceStore

PLAN_FAMILY_PLANNER_VERSION = "plan-family-planner-v0.1"


@dataclass(frozen=True)
class FollowupPlanResult:
    """Read-only planning output for the next bounded result-changing round."""

    plan: EditPlan | None
    route: str
    reason_codes: tuple[str, ...]
    user_message: str
    observation: ResultObservation | None
    trace: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class FeedbackCaptureResult:
    """A redacted explicit feedback fact and its operational Trace."""

    feedback: UserFeedback
    trace: tuple[dict[str, object], ...]
    user_message: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _numeric_value(feature: NormalizedFeature | None) -> float | None:
    if feature is None or feature.status == MeasurementStatus.UNAVAILABLE:
        return None
    if isinstance(feature.value, bool) or not isinstance(feature.value, (int, float)):
        return None
    return float(feature.value)


def _gap(reference: NormalizedFeature | None, observed: NormalizedFeature | None) -> float | None:
    if reference is None or observed is None or reference.unit != observed.unit:
        return None
    reference_value = _numeric_value(reference)
    observed_value = _numeric_value(observed)
    if reference_value is None or observed_value is None:
        return None
    if reference.unit.value == "normalized_position":
        return abs(observed_value - reference_value)
    return abs(observed_value - reference_value) / max(abs(reference_value), 1e-6)


def _feature_difference(
    *,
    reference: NormalizedFeature | None,
    observed: NormalizedFeature | None,
    feature_code: str,
    editable: bool,
    reason_codes: list[str],
) -> FeatureDifference:
    confidence = min(
        reference.confidence if reference is not None and reference.confidence else 0.0,
        observed.confidence if observed is not None and observed.confidence else 0.0,
    )
    gap = _gap(reference, observed)
    return FeatureDifference(
        feature_code=feature_code,
        reference_value=_numeric_value(reference),
        observed_value=_numeric_value(observed),
        normalized_gap=gap,
        measurement_confidence=confidence,
        editable=editable and gap is not None,
        reason_codes=reason_codes
        if gap is not None
        else [*reason_codes, "feature_not_measurable_on_result"],
    )


def _feature_field(feature: EditableFeature) -> str:
    fields = {
        EditableFeature.FACE_LIFTING: "face_lifting",
        EditableFeature.EYE_ENLARGING: "eye_enlarging",
        EditableFeature.WHITENING: "whitening",
        EditableFeature.SMOOTHING: "smoothing",
    }
    return fields[feature]


def _params_for_changes(changes: list[ExecutableChange]) -> TencentBeautifyParams:
    values = {
        "face_lifting": 0,
        "eye_enlarging": 0,
        "whitening": 0,
        "smoothing": 0,
    }
    for change in changes:
        values[_feature_field(change.feature)] = change.proposed_absolute
    return TencentBeautifyParams(**values)


def _preflight_reasons(
    *,
    previous_plan: EditPlan,
    previous_provider_run: ProviderRun,
    previous_verification: VerificationResult,
    execution_intent: IntentFrame,
    profile: ReferenceProfile,
    result_image_bytes: bytes,
    now: datetime,
) -> list[str]:
    """Return every structural reason a plan family cannot continue."""

    reasons: list[str] = []
    scope = execution_intent.confirmation_scope
    result_hash = hashlib.sha256(result_image_bytes).hexdigest()
    if previous_provider_run.status != ProviderRunStatus.SUCCEEDED:
        reasons.append("previous_provider_run_not_succeeded")
    if previous_provider_run.plan_id != previous_plan.plan_id:
        reasons.append("previous_run_plan_mismatch")
    if previous_provider_run.plan_revision != previous_plan.revision:
        reasons.append("previous_run_plan_revision_mismatch")
    if previous_verification.provider_run_id != previous_provider_run.run_id:
        reasons.append("verification_provider_run_mismatch")
    if previous_verification.plan_id != previous_plan.plan_id:
        reasons.append("verification_plan_mismatch")
    if previous_verification.plan_revision != previous_plan.revision:
        reasons.append("verification_plan_revision_mismatch")
    if previous_verification.round_number != previous_plan.iteration:
        reasons.append("verification_round_plan_iteration_mismatch")
    if previous_verification.decision != VerificationDecision.REPLAN:
        reasons.append("verification_not_replan")
    if previous_verification.overall_trend != ComparisonTrend.IMPROVED:
        reasons.append("previous_round_not_improved")
    if not previous_verification.cumulative_improvement:
        reasons.append("cumulative_improvement_not_evidenced")
    if previous_verification.target_evidence_sufficient:
        reasons.append("target_evidence_already_sufficient")
    if previous_verification.result_quality_flags:
        reasons.append("result_quality_flags_block_followup")
    if previous_verification.user_feedback.status == FeedbackStatus.REJECTED:
        reasons.append("explicit_user_dissatisfaction")
    if not previous_verification.result_artifact_available:
        reasons.append("result_artifact_not_comparable")
    if previous_provider_run.result_artifact_sha256 != result_hash:
        reasons.append("result_bytes_do_not_match_previous_receipt")
    if not previous_provider_run.result_artifact_ref:
        reasons.append("previous_result_artifact_ref_missing")
    if previous_plan.session_id != execution_intent.session_id:
        reasons.append("plan_family_session_mismatch")
    if (
        previous_plan.profile_id != profile.profile_id
        or previous_plan.profile_version != profile.version
    ):
        reasons.append("profile_changed")
    if execution_intent.confirmation_ref != previous_plan.confirmation_ref:
        reasons.append("confirmation_ref_mismatch")
    if scope is None or execution_intent.confirmation_status.value != "confirmed":
        reasons.append("confirmation_not_confirmed")
    else:
        if now >= scope.expires_at:
            reasons.append("confirmation_expired")
        if previous_plan.photo_id not in scope.target_refs:
            reasons.append("confirmation_photo_out_of_scope")
        if previous_plan.iteration + 1 > scope.max_provider_rounds:
            reasons.append("confirmation_round_limit_exceeded")
    if previous_plan.expires_at is not None and now >= previous_plan.expires_at:
        reasons.append("confirmation_expired")
    if previous_plan.iteration + 1 > previous_plan.safety_policy.max_provider_rounds:
        reasons.append("safety_round_limit_exceeded")
    return list(dict.fromkeys(reasons))


def propose_followup_plan(
    *,
    previous_plan: EditPlan,
    previous_provider_run: ProviderRun,
    previous_verification: VerificationResult,
    execution_intent: IntentFrame,
    profile: ReferenceProfile,
    result_image_bytes: bytes,
    policy: FollowupMappingPolicy | None = None,
    store: LocalTraceStore | None = None,
    now: datetime | None = None,
    plan_id: str | None = None,
) -> FollowupPlanResult:
    """Build a new confirmed child plan only after a verified improvement.

    The returned plan reuses the original bounded confirmation reference.  It
    is valid only for the result image hash that 8C just verified; executor
    lineage checks make it impossible to substitute a different image.
    """

    now = now or _utc_now()
    policy = policy or build_v0_followup_mapping_policy()
    trace: list[dict[str, object]] = [
        {
            "step": "plan_family_preflight",
            "parent_plan_id": previous_plan.plan_id,
            "parent_provider_run_id": previous_provider_run.run_id,
            "previous_verification_id": previous_verification.verification_id,
            "next_iteration": previous_plan.iteration + 1,
            "policy_id": policy.policy_id,
            "policy_version": policy.policy_version,
        }
    ]
    reasons = _preflight_reasons(
        previous_plan=previous_plan,
        previous_provider_run=previous_provider_run,
        previous_verification=previous_verification,
        execution_intent=execution_intent,
        profile=profile,
        result_image_bytes=result_image_bytes,
        now=now,
    )
    if reasons:
        trace.append({"step": "plan_family_route", "route": "blocked", "reason_codes": reasons})
        return FollowupPlanResult(
            plan=None,
            route="blocked",
            reason_codes=tuple(reasons),
            user_message=(
                "本轮不会自动继续修图：现有证据或授权范围不满足下一轮条件。"
                f"原因：{'、'.join(reasons)}。"
            ),
            observation=None,
            trace=tuple(trace),
        )

    observation = observe_result_bytes(result_image_bytes, photo_id=previous_plan.photo_id)
    if not observation.comparable:
        reasons = [*observation.reason_codes, "result_not_comparable_for_followup"]
        trace.extend(
            [
                {
                    "step": "observe_result_for_followup",
                    "decode_ok": observation.decode_ok,
                    "face_count": observation.face_count,
                    "measured_feature_codes": [
                        feature.feature_code for feature in observation.normalized_features
                    ],
                },
                {"step": "plan_family_route", "route": "blocked", "reason_codes": reasons},
            ]
        )
        return FollowupPlanResult(
            plan=None,
            route="blocked",
            reason_codes=tuple(dict.fromkeys(reasons)),
            user_message="当前结果图无法可靠测量；系统不会盲目叠加下一轮参数。",
            observation=observation,
            trace=tuple(trace),
        )
    result_sha256 = hashlib.sha256(result_image_bytes).hexdigest()
    if observation.photo_sha256 != result_sha256:
        reasons = ["result_observation_hash_mismatch"]
        trace.extend(
            [
                {
                    "step": "observe_result_for_followup",
                    "observation_sha256": observation.photo_sha256,
                    "actual_result_sha256": result_sha256,
                },
                {"step": "plan_family_route", "route": "blocked", "reason_codes": reasons},
            ]
        )
        return FollowupPlanResult(
            plan=None,
            route="blocked",
            reason_codes=tuple(reasons),
            user_message="结果观察记录与当前结果图不一致；系统不会继续调用腾讯。",
            observation=observation,
            trace=tuple(trace),
        )

    comparison_by_code = {
        comparison.feature_code: comparison
        for comparison in previous_verification.feature_comparisons
    }
    reference_by_code = {feature.feature_code: feature for feature in profile.normalized_features}
    result_by_code = {feature.feature_code: feature for feature in observation.normalized_features}
    allowed = set(execution_intent.confirmation_scope.allowed_features)  # preflight checked scope
    changes: list[ExecutableChange] = []
    differences: list[FeatureDifference] = []
    skipped: list[str] = []
    for prior_change in previous_plan.executable_changes:
        code = FEATURE_CODE_BY_PRODUCT_FEATURE.get(prior_change.feature.value)
        comparison = comparison_by_code.get(code) if code else None
        result_feature = result_by_code.get(code) if code else None
        reference_feature = reference_by_code.get(code) if code else None
        if code:
            differences.append(
                _feature_difference(
                    reference=reference_feature,
                    observed=result_feature,
                    feature_code=code,
                    editable=(
                        comparison is not None
                        and comparison.trend == ComparisonTrend.IMPROVED
                        and prior_change.feature in allowed
                    ),
                    reason_codes=["derived_from_verified_result", "plan_family_round"],
                )
            )
        if (
            comparison is None
            or comparison.trend != ComparisonTrend.IMPROVED
            or comparison.after_gap is None
            or comparison.after_gap <= policy.target_gap_tolerance
            or prior_change.feature not in allowed
        ):
            skipped.append(prior_change.feature.value)
            continue
        increment = policy.increment_for_remaining_gap(comparison.after_gap)
        if increment <= 0:
            skipped.append(prior_change.feature.value)
            continue
        changes.append(
            ExecutableChange(
                feature=prior_change.feature,
                provider_parameter=prior_change.provider_parameter,
                user_delta=increment,
                # This is a fresh Tencent request on a fresh input image.  It
                # is intentionally not "previous provider strength + delta".
                current_absolute=0,
                proposed_absolute=increment,
                expected_direction=prior_change.expected_direction,
                rationale_codes=[
                    "previous_round_improved",
                    "remaining_verified_gap",
                    f"followup_mapping_{policy.policy_version}",
                ],
            )
        )
    if not changes:
        reasons = ["no_improving_executable_feature_remaining"]
        if skipped:
            reasons.append("features_not_eligible_for_incremental_followup")
        trace.extend(
            [
                {
                    "step": "derive_followup_parameters",
                    "eligible_feature_count": 0,
                    "skipped_features": skipped,
                },
                {"step": "plan_family_route", "route": "blocked", "reason_codes": reasons},
            ]
        )
        return FollowupPlanResult(
            plan=None,
            route="blocked",
            reason_codes=tuple(reasons),
            user_message="已验证改善不足以支持继续叠加可执行参数；系统停止自动重规划。",
            observation=observation,
            trace=tuple(trace),
        )

    child = EditPlan(
        plan_id=plan_id or f"plan_{uuid.uuid4().hex}",
        revision=1,
        parent_plan_id=previous_plan.plan_id,
        session_id=previous_plan.session_id,
        profile_id=previous_plan.profile_id,
        profile_version=previous_plan.profile_version,
        photo_id=previous_plan.photo_id,
        photo_sha256=result_sha256,
        intent_id=execution_intent.intent_id,
        quality_result_id=previous_plan.quality_result_id,
        iteration=previous_plan.iteration + 1,
        provider=previous_plan.provider,
        provider_api_version=previous_plan.provider_api_version,
        provider_card_id=previous_plan.provider_card_id,
        provider_card_version=previous_plan.provider_card_version,
        baseline_feature_differences=differences,
        executable_changes=changes,
        suggestion_only_changes=previous_plan.suggestion_only_changes,
        provider_absolute_params=_params_for_changes(changes),
        constraints_snapshot=previous_plan.constraints_snapshot,
        safety_policy=previous_plan.safety_policy,
        risk_notes=list(
            dict.fromkeys(
                [
                    *previous_plan.risk_notes,
                    "本轮输入为已复测的上一轮结果图，不是原始目标照",
                    "下一轮仅沿用已确认计划族的部位、时限与轮次上限",
                    "腾讯参数是本次新输入图上的单次强度，不与上一轮数值直接累加",
                ]
            )
        )[:16],
        requires_confirmation=True,
        confirmation_ref=previous_plan.confirmation_ref,
        confirmation_scope_hash=previous_plan.confirmation_scope_hash,
        status=PlanStatus.CONFIRMED,
        planner_version=PLAN_FAMILY_PLANNER_VERSION,
        mapping_policy_version=policy.policy_version,
        created_at=now,
        expires_at=previous_plan.expires_at,
    )
    trace.extend(
        [
            {
                "step": "observe_result_for_followup",
                **observation.public_projection(),
            },
            {
                "step": "derive_followup_parameters",
                "eligible_feature_count": len(changes),
                "skipped_features": skipped,
                "per_call_strengths": {
                    change.feature.value: change.proposed_absolute for change in changes
                },
                "parent_plan_id": previous_plan.plan_id,
                "input_result_sha256": result_sha256,
            },
            {
                "step": "persist_followup_plan",
                "plan_id": child.plan_id,
                "parent_plan_id": child.parent_plan_id,
                "iteration": child.iteration,
                "status": child.status.value,
                "reuses_confirmation": True,
                "execution_mode": "auto_bounded_followup",
                "user_round_confirmation_required": False,
                "inherited_confirmation_scope": True,
            },
        ]
    )
    if store is not None:
        store.save_edit_plan(child)
        store.record_event(
            child.session_id,
            "plan_family_followup_trace",
            {"plan_id": child.plan_id, "trace": trace},
        )
    return FollowupPlanResult(
        plan=child,
        route="followup_plan_ready",
        reason_codes=("verified_improvement_allows_bounded_followup",),
        user_message=(
            f"第 {child.iteration} 轮计划已生成：它只对上一轮已朝正确方向改善、"
            "但尚未达到当前目标证据线的部位做小步调整。系统会在首次同意的"
            "受限范围内自动执行；若自动前置检查不通过则停止，不会发送图片。"
        ),
        observation=observation,
        trace=tuple(trace),
    )


def capture_explicit_feedback(
    *,
    session_id: str,
    anonymous_user_id: str,
    verification: VerificationResult,
    signal: FeedbackSignal,
    comment_text: str | None = None,
    store: LocalTraceStore | None = None,
    now: datetime | None = None,
) -> FeedbackCaptureResult:
    """Record a user-visible like/dislike/comment without retaining raw text.

    A like/dislike is a strong satisfaction label.  A text comment is an
    explicit feedback event but stays ``unknown`` until a later IntentFrame
    clarifies whether it is praise, dissatisfaction, or a new request.
    """

    now = now or _utc_now()
    text_digest = hashlib.sha256((comment_text or "").strip().encode("utf-8")).hexdigest()
    if signal == FeedbackSignal.LIKE:
        feedback = UserFeedback(
            status=FeedbackStatus.ACCEPTED,
            label_source=FeedbackLabelSource.USER_EXPLICIT,
            explicit=True,
            signal=signal,
            evidence_strength=FeedbackEvidenceStrength.STRONG_FEEDBACK,
            reason_codes=["explicit_like"],
            recorded_at=now,
        )
        event_type = ProductEventType.FEEDBACK_LIKED
        outcome = InteractionOutcome.COMPLETED
        user_message = "已记录为明确满意反馈；系统不会再自动继续修图。"
    elif signal == FeedbackSignal.DISLIKE:
        feedback = UserFeedback(
            status=FeedbackStatus.REJECTED,
            label_source=FeedbackLabelSource.USER_EXPLICIT,
            explicit=True,
            signal=signal,
            evidence_strength=FeedbackEvidenceStrength.STRONG_FEEDBACK,
            reason_codes=["explicit_dislike"],
            recorded_at=now,
        )
        event_type = ProductEventType.FEEDBACK_DISLIKED
        outcome = InteractionOutcome.PATH_ABANDONED
        user_message = "已记录为明确不满意；计划族立即停止，等待你说明新的目标。"
    elif signal == FeedbackSignal.TEXT_COMMENT:
        feedback = UserFeedback(
            status=FeedbackStatus.UNKNOWN,
            label_source=FeedbackLabelSource.USER_EXPLICIT,
            explicit=True,
            signal=signal,
            evidence_strength=FeedbackEvidenceStrength.STRONG_FEEDBACK,
            reason_codes=["explicit_comment_requires_intent_clarification"],
            recorded_at=now,
        )
        event_type = ProductEventType.USER_COMMENTED
        outcome = InteractionOutcome.UNKNOWN
        user_message = "已记录你提交了文字反馈；系统不会把文字直接当作新的修图指令执行。"
    else:
        raise ValueError("8C-2 only accepts like, dislike, or text_comment feedback")

    trace = (
        {
            "step": "capture_explicit_feedback",
            "verification_id": verification.verification_id,
            "signal": signal.value,
            "feedback_status": feedback.status.value,
            "comment_present": bool((comment_text or "").strip()),
            "comment_sha256": text_digest if (comment_text or "").strip() else None,
            "raw_comment_persisted": False,
        },
    )
    if store is not None:
        store.record_product_event(
            ProductEvent(
                event_id=f"product_event_{uuid.uuid4().hex}",
                session_id=session_id,
                anonymous_user_id=anonymous_user_id,
                event_type=event_type,
                stage=InteractionStage.VERIFICATION,
                evidence_strength=feedback.evidence_strength,
                outcome=outcome,
                related_contract_ref=verification.verification_id,
                reason_codes=feedback.reason_codes,
                occurred_at=now,
            )
        )
        store.record_event(session_id, "verification_feedback_trace", {"trace": trace})
    return FeedbackCaptureResult(
        feedback=feedback,
        trace=trace,
        user_message=user_message,
    )
