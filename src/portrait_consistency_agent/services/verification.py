"""Checkpoint 8C: explainable post-edit observation and strategy proposal.

The module deliberately keeps two responsibilities separate:

* ``observe_result_bytes`` runs the same local decoder/face geometry extractor
  on the returned image.  It produces structured facts without persisting
  pixels or raw face coordinates.
* ``verify_result`` compares those facts with the pre-edit gaps in ``EditPlan``
  and creates a ``VerificationResult``.  It never invents a score or lets an
  LLM change a measurement.  ``propose_verification_strategy`` is the bounded
  selector seam; this first implementation is a deterministic baseline.  A
  future Agent/RAG selector may propose a different item only inside the same
  allow-list and consent gate.

No external verification API is called here.  The V0 strategy policy enables
local geometry and a manual-review fallback; external/hybrid strategies remain
contract vocabulary for a later consented adapter.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field

from portrait_consistency_agent.core.contracts import (
    ComparisonTrend,
    EditPlan,
    FeatureComparison,
    FeedbackStatus,
    ManualReviewRequest,
    MeasurementStatus,
    NormalizedFeature,
    PhotoRole,
    ProviderRun,
    QualityFlag,
    ReferenceProfile,
    StopReason,
    UserFeedback,
    VerificationDecision,
    VerificationResult,
    VerificationStrategy,
    VerificationStrategyProposal,
)
from portrait_consistency_agent.core.policies import (
    VerificationPolicy,
    build_v0_safety_policy,
    build_v0_verification_policy,
)
from portrait_consistency_agent.core.rag_contracts import RagAdvisoryDecision
from portrait_consistency_agent.services.photo_quality import analyze_photo_bytes
from portrait_consistency_agent.services.reference_profile import extract_normalized_features
from portrait_consistency_agent.storage.local_store import LocalTraceStore

VERIFIER_VERSION = "verification-v0.1"
SELECTOR_VERSION = "verification-selector-v0.1"

FEATURE_CODE_BY_PRODUCT_FEATURE = {
    "face_lifting": "face_width_height_ratio",
    "eye_enlarging": "eye_area_mean_face_ratio",
    "whitening": "skin_tone",
    "smoothing": "skin_texture",
}


@dataclass(frozen=True)
class ResultObservation:
    """A safe in-memory projection of a provider result.

    ``image_bytes`` and raw face boxes never leave ``observe_result_bytes``.
    ``normalized_features`` are interpretable ratios/positions, not an
    identity embedding.
    """

    photo_id: str
    photo_sha256: str
    decode_ok: bool
    face_count: int
    normalized_features: tuple[NormalizedFeature, ...] = ()
    quality_flags: tuple[QualityFlag, ...] = ()
    reason_codes: tuple[str, ...] = ()
    metrics: dict[str, float] = field(default_factory=dict)
    analysis_version: str = "unknown"

    @property
    def comparable(self) -> bool:
        """Whether V0 can compare at least one single-face geometry safely."""

        return self.decode_ok and self.face_count == 1 and bool(self.normalized_features)

    def public_projection(self) -> dict[str, object]:
        """Return facts suitable for the UI and redacted Trace."""

        return {
            "photo_id": self.photo_id,
            "photo_sha256": self.photo_sha256,
            "decode_ok": self.decode_ok,
            "face_count": self.face_count,
            "measured_feature_codes": [
                feature.feature_code
                for feature in self.normalized_features
                if feature.status != MeasurementStatus.UNAVAILABLE
            ],
            "quality_flags": [flag.value for flag in self.quality_flags],
            "reason_codes": list(self.reason_codes),
            "metrics": {key: round(value, 4) for key, value in self.metrics.items()},
            "analysis_version": self.analysis_version,
            "raw_face_coordinates_saved": False,
        }


@dataclass(frozen=True)
class VerificationRunResult:
    """All outputs of one local verification call, including its Trace."""

    verification: VerificationResult
    observation: ResultObservation
    strategy_proposal: VerificationStrategyProposal
    user_message: str
    trace: tuple[dict[str, object], ...]


def observe_result_bytes(
    result_image_bytes: bytes,
    *,
    photo_id: str,
) -> ResultObservation:
    """Decode and measure a provider result in memory only.

    A valid image with no detectable face is still an available artifact, but
    it is not comparable and will route to re-upload/manual handling.  An
    empty or undecodable payload is marked unavailable so the caller cannot
    claim a successful verification.
    """

    observation = analyze_photo_bytes(
        result_image_bytes,
        photo_id=photo_id,
        photo_role=PhotoRole.RESULT,
    )
    decode_ok = (
        bool(result_image_bytes)
        and observation.width is not None
        and observation.height is not None
        and observation.image_format is not None
    )
    reasons = list(observation.reason_codes)
    if not decode_ok and "result_decode_failed" not in reasons:
        reasons.append("result_decode_failed")
    features: tuple[NormalizedFeature, ...] = ()
    if decode_ok and observation.face_count == 1:
        try:
            features = tuple(extract_normalized_features(observation))
        except ValueError:
            reasons.append("result_geometry_extraction_failed")
    return ResultObservation(
        photo_id=photo_id,
        photo_sha256=observation.photo_sha256,
        decode_ok=decode_ok,
        face_count=observation.face_count,
        normalized_features=features,
        quality_flags=observation.quality_flags,
        reason_codes=tuple(dict.fromkeys(reasons)),
        metrics=observation.metrics,
        analysis_version=observation.analysis_version,
    )


def propose_verification_strategy(
    observation: ResultObservation,
    *,
    policy: VerificationPolicy | None = None,
    available_strategies: Iterable[VerificationStrategy] | None = None,
    data_outbound_allowed: bool = False,
    knowledge_refs: Iterable[str] = (),
    proposal_id: str | None = None,
) -> VerificationStrategyProposal:
    """Propose one allowed verification route from structured evidence.

    The baseline prefers local geometry whenever it is comparable.  If that is
    impossible, it prefers an explicitly enabled external/hybrid route only
    when the caller has separately allowed image egress; otherwise it falls
    back to manual review.  This function is intentionally a *proposal*, not a
    tool call or a permission grant.
    """

    policy = policy or build_v0_verification_policy()
    available = list(available_strategies or policy.allowed_strategies)
    allowed = [item for item in policy.allowed_strategies if item in available]
    if not allowed:
        raise ValueError("no verification strategy is available under the current policy")

    if observation.comparable and VerificationStrategy.LOCAL_GEOMETRY in allowed:
        selected = VerificationStrategy.LOCAL_GEOMETRY
        reasons = ["result_decoded", "single_face", "local_geometry_measurable"]
    elif data_outbound_allowed and VerificationStrategy.HYBRID in allowed:
        selected = VerificationStrategy.HYBRID
        reasons = ["local_geometry_unavailable", "explicit_outbound_permission"]
    elif data_outbound_allowed and VerificationStrategy.EXTERNAL_SUBJECT_MATCH in allowed:
        selected = VerificationStrategy.EXTERNAL_SUBJECT_MATCH
        reasons = ["local_geometry_unavailable", "explicit_outbound_permission"]
    elif VerificationStrategy.MANUAL_VISUAL_REVIEW in allowed:
        selected = VerificationStrategy.MANUAL_VISUAL_REVIEW
        reasons = ["local_geometry_unavailable", "manual_review_fallback"]
    else:
        # This branch is only reachable with a custom allow-list that excludes
        # manual review.  Selecting local keeps the proposal schema valid; the
        # caller will still receive an unverifiable result and must not claim
        # success.
        selected = allowed[0]
        reasons = ["no_comparable_local_evidence", "only_strategy_available"]

    outbound = selected in {
        VerificationStrategy.EXTERNAL_SUBJECT_MATCH,
        VerificationStrategy.HYBRID,
    }
    return VerificationStrategyProposal(
        proposal_id=proposal_id or f"strategy_{uuid.uuid4().hex}",
        selected_strategy=selected,
        allowed_strategies=allowed,
        reason_codes=reasons,
        knowledge_refs=list(knowledge_refs),
        data_outbound=outbound,
        additional_consent_required=outbound,
        selector_mode="deterministic_baseline_v0",
        selector_version=SELECTOR_VERSION,
    )


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


def _trend(
    before_gap: float | None,
    after_gap: float | None,
    confidence: float,
    *,
    tolerance: float,
    minimum_confidence: float,
) -> ComparisonTrend:
    if before_gap is None or after_gap is None or confidence < minimum_confidence:
        return ComparisonTrend.UNVERIFIABLE
    change = before_gap - after_gap
    if abs(change) <= tolerance:
        return ComparisonTrend.NO_CHANGE
    return ComparisonTrend.IMPROVED if change > 0 else ComparisonTrend.WORSENED


def _overall_trend(
    comparisons: list[FeatureComparison],
    required_codes: set[str],
) -> ComparisonTrend:
    required = [item for item in comparisons if item.feature_code in required_codes]
    if not required:
        return ComparisonTrend.UNVERIFIABLE
    if any(item.trend == ComparisonTrend.WORSENED for item in required):
        return ComparisonTrend.WORSENED
    if any(item.trend == ComparisonTrend.UNVERIFIABLE for item in required):
        return ComparisonTrend.UNVERIFIABLE
    if any(item.trend == ComparisonTrend.IMPROVED for item in required):
        return ComparisonTrend.IMPROVED
    return ComparisonTrend.NO_CHANGE


def _user_message(
    *,
    strategy: VerificationStrategy,
    overall_trend: ComparisonTrend,
    decision: VerificationDecision,
    comparisons: list[FeatureComparison],
    reason_codes: list[str],
) -> str:
    labels = {
        ComparisonTrend.IMPROVED: "朝母版目标改善",
        ComparisonTrend.NO_CHANGE: "变化在当前测量误差范围内",
        ComparisonTrend.WORSENED: "至少一项已执行特征变得更偏离",
        ComparisonTrend.UNVERIFIABLE: "当前无法可靠判断",
    }
    measurable = sum(item.trend != ComparisonTrend.UNVERIFIABLE for item in comparisons)
    return (
        f"修后采用{strategy.value}复测，{measurable}项目标特征有可用证据；"
        f"结果{labels[overall_trend]}。下一步：{decision.value}。"
        f"原因码：{'、'.join(reason_codes)}。"
    )


def verify_result(
    *,
    profile: ReferenceProfile,
    plan: EditPlan,
    provider_run: ProviderRun,
    result_image_bytes: bytes,
    round_number: int | None = None,
    prior_no_improvement_streak: int = 0,
    previous_verification_id: str | None = None,
    previous_cumulative_improvement: bool | None = None,
    plan_family_id: str | None = None,
    last_known_good_artifact_ref: str | None = None,
    user_feedback: UserFeedback | None = None,
    rag_advice: RagAdvisoryDecision | None = None,
    policy: VerificationPolicy | None = None,
    safety_policy=None,
    store: LocalTraceStore | None = None,
    verification_id: str | None = None,
) -> VerificationRunResult:
    """Create one auditable result and route decision from actual output bytes.

    ``provider_run`` must be a successful factual receipt.  This prevents a
    failed or fabricated provider response from entering the verification
    ledger.  No call is made to Tencent in this function.
    """

    if provider_run.status.value != "succeeded":
        raise ValueError("only a successful ProviderRun can enter post-edit verification")
    if provider_run.plan_id != plan.plan_id or provider_run.plan_revision != plan.revision:
        raise ValueError("ProviderRun does not belong to the supplied plan revision")
    if provider_run.photo_id != plan.photo_id:
        raise ValueError("ProviderRun and EditPlan refer to different photos")

    policy = policy or build_v0_verification_policy()
    safety_policy = safety_policy or build_v0_safety_policy()
    current_round = round_number or plan.iteration
    if current_round < 1:
        raise ValueError("round_number must be positive")
    if current_round > safety_policy.max_provider_rounds:
        raise ValueError("round_number exceeds the safety policy")

    observation = observe_result_bytes(result_image_bytes, photo_id=plan.photo_id)
    proposal = propose_verification_strategy(
        observation,
        policy=policy,
        available_strategies=policy.allowed_strategies,
        knowledge_refs=(rag_advice.direct_evidence_refs if rag_advice is not None else ()),
    )
    trace: list[dict[str, object]] = [
        {
            "step": "observe_result",
            "photo_id": plan.photo_id,
            "result_sha256": observation.photo_sha256,
            "decode_ok": observation.decode_ok,
            "face_count": observation.face_count,
            "measured_feature_codes": [
                feature.feature_code for feature in observation.normalized_features
            ],
            "quality_flags": [flag.value for flag in observation.quality_flags],
            "analysis_version": observation.analysis_version,
        },
        {
            "step": "verification_strategy_select",
            "proposal_id": proposal.proposal_id,
            "selected_strategy": proposal.selected_strategy.value,
            "allowed_strategies": [item.value for item in proposal.allowed_strategies],
            "reason_codes": list(proposal.reason_codes),
            "data_outbound": proposal.data_outbound,
            "selector_mode": proposal.selector_mode,
            "selector_version": proposal.selector_version,
            "knowledge_refs": list(proposal.knowledge_refs),
        },
    ]
    if rag_advice is not None:
        trace.append(
            {
                "step": "rag_advisory_strategy_context",
                "advice_id": rag_advice.advice_id,
                "retrieval_route": rag_advice.retrieval_route.value,
                "advisory_route": rag_advice.advisory_route.value,
                "direct_evidence_refs": rag_advice.direct_evidence_refs,
                "reference_information_refs": rag_advice.reference_information_refs,
                "conflict_information_refs": rag_advice.conflict_information_refs,
                "execution_authorized_by_rag": False,
                "baseline_strategy_remains_policy_gated": True,
            }
        )

    reference_map = {item.feature_code: item for item in profile.normalized_features}
    after_map = {item.feature_code: item for item in observation.normalized_features}
    baseline_map = {item.feature_code: item for item in plan.baseline_feature_differences}
    required_codes = {
        FEATURE_CODE_BY_PRODUCT_FEATURE[change.feature.value]
        for change in plan.executable_changes
        if change.feature.value in FEATURE_CODE_BY_PRODUCT_FEATURE
    }
    all_codes = list(dict.fromkeys([*baseline_map, *required_codes]))
    comparisons: list[FeatureComparison] = []
    for code in all_codes:
        baseline = baseline_map.get(code)
        after_feature = after_map.get(code)
        after_gap = _gap(reference_map.get(code), after_feature)
        confidence = min(
            baseline.measurement_confidence if baseline is not None else 0.0,
            (
                after_feature.confidence
                if after_feature is not None and after_feature.confidence
                else 0.0
            ),
        )
        before_gap = baseline.normalized_gap if baseline is not None else None
        trend = _trend(
            before_gap,
            after_gap,
            confidence,
            tolerance=policy.measurement_tolerance,
            minimum_confidence=policy.minimum_measurement_confidence,
        )
        comparisons.append(
            FeatureComparison(
                feature_code=code,
                before_gap=before_gap,
                after_gap=after_gap,
                trend=trend,
                measurement_confidence=confidence,
            )
        )

    overall = _overall_trend(comparisons, required_codes)
    target_evidence_sufficient = bool(required_codes) and all(
        item.trend in {ComparisonTrend.IMPROVED, ComparisonTrend.NO_CHANGE}
        and item.after_gap is not None
        and item.after_gap <= policy.target_gap_tolerance
        for item in comparisons
        if item.feature_code in required_codes
    )
    if not observation.comparable:
        target_evidence_sufficient = False

    if overall == ComparisonTrend.IMPROVED:
        no_improvement_streak = 0
    else:
        no_improvement_streak = prior_no_improvement_streak + 1
    feedback = user_feedback or UserFeedback()
    reason_codes: list[str] = list(observation.reason_codes)
    decision: VerificationDecision
    stop_reason: StopReason | None
    manual_review: ManualReviewRequest | None = None
    # A follow-up may continue only when *every* completed family round has
    # moved in the correct direction. The first round has no predecessor, so
    # its cumulative status is simply its own observed trend.
    cumulative_improvement = overall == ComparisonTrend.IMPROVED and (
        previous_cumulative_improvement is not False
    )
    if feedback.status == FeedbackStatus.REJECTED:
        decision = VerificationDecision.STOP
        stop_reason = StopReason.USER_DISSATISFIED
        reason_codes.append("explicit_user_dissatisfaction")
    elif not observation.decode_ok:
        decision = VerificationDecision.RESHOOT
        stop_reason = StopReason.INPUT_NOT_COMPARABLE
        reason_codes.append("result_decode_failed")
    elif target_evidence_sufficient:
        decision = VerificationDecision.CLOSE
        stop_reason = StopReason.GOAL_MET
        reason_codes.append("all_executable_targets_within_gap_tolerance")
    elif overall == ComparisonTrend.WORSENED:
        if last_known_good_artifact_ref:
            decision = VerificationDecision.STOP
            stop_reason = StopReason.RESULT_WORSENED
            reason_codes.append("rollback_to_last_known_good_required")
        else:
            decision = VerificationDecision.MANUAL_REVIEW
            stop_reason = None
            manual_review = ManualReviewRequest(
                reason_codes=["worsened_result_missing_last_known_good_ref"],
            )
            reason_codes.append("rollback_evidence_missing_manual_review")
    elif overall == ComparisonTrend.UNVERIFIABLE:
        decision = VerificationDecision.RESHOOT
        stop_reason = StopReason.INPUT_NOT_COMPARABLE
        reason_codes.append("required_feature_not_reliably_measured")
    elif not cumulative_improvement:
        decision = VerificationDecision.STOP
        stop_reason = StopReason.NO_IMPROVEMENT
        reason_codes.append("cumulative_improvement_not_evidenced")
    elif current_round >= safety_policy.max_provider_rounds:
        decision = VerificationDecision.STOP
        stop_reason = StopReason.MAX_ROUNDS
        reason_codes.append("max_provider_rounds_reached")
    elif overall == ComparisonTrend.NO_CHANGE:
        decision = VerificationDecision.STOP
        stop_reason = StopReason.NO_IMPROVEMENT
        reason_codes.append("no_measurable_improvement")
    else:
        decision = VerificationDecision.REPLAN
        stop_reason = None
        reason_codes.append("measurable_improvement_but_target_not_reached")

    if observation.quality_flags:
        reason_codes.append("result_quality_flags_present")
    # V0 does not have a reliable automatic check for makeup/skin/background
    # preservation.  False here means "no measured violation", not "proved
    # unchanged"; the explicit flag is carried for user-facing honesty.
    reason_codes.append("preserved_attributes_not_automatically_verified")
    reason_codes = list(dict.fromkeys(reason_codes))[:16]

    artifact_ref = provider_run.result_artifact_ref or f"unavailable_{uuid.uuid4().hex}"
    result = VerificationResult(
        verification_id=verification_id or f"verification_{uuid.uuid4().hex}",
        session_id=plan.session_id,
        profile_id=plan.profile_id,
        profile_version=plan.profile_version,
        photo_id=plan.photo_id,
        plan_id=plan.plan_id,
        plan_revision=plan.revision,
        provider_run_id=provider_run.run_id,
        verification_strategy=proposal.selected_strategy,
        strategy_proposal_ref=proposal.proposal_id,
        strategy_reason_codes=list(proposal.reason_codes),
        knowledge_refs=list(proposal.knowledge_refs),
        data_outbound=proposal.data_outbound,
        additional_consent_required=proposal.additional_consent_required,
        verification_run_refs=[],
        verification_artifact_refs=[],
        plan_family_id=plan_family_id,
        previous_verification_id=previous_verification_id,
        cumulative_improvement=cumulative_improvement,
        target_evidence_sufficient=target_evidence_sufficient,
        preserved_attributes_verified=False,
        feature_comparisons=comparisons,
        overall_trend=overall,
        result_quality_flags=list(observation.quality_flags),
        prohibited_attribute_changed=False,
        result_artifact_available=observation.decode_ok,
        round_number=current_round,
        no_improvement_streak=no_improvement_streak,
        safety_policy=safety_policy,
        user_feedback=feedback,
        decision=decision,
        stop_reason=stop_reason,
        reason_codes=reason_codes,
        result_artifact_ref=artifact_ref,
        last_known_good_artifact_ref=last_known_good_artifact_ref,
        rollback_reason=(
            "修后趋势变差，保留上一张已知良好结果"
            if stop_reason == StopReason.RESULT_WORSENED
            else None
        ),
        manual_review=manual_review,
        verifier_version=VERIFIER_VERSION,
        extractor_version=observation.analysis_version,
        threshold_policy_version=policy.policy_version,
    )
    trace.extend(
        [
            {
                "step": "compare_features",
                "comparisons": [
                    {
                        "feature_code": item.feature_code,
                        "before_gap": item.before_gap,
                        "after_gap": item.after_gap,
                        "trend": item.trend.value,
                        "measurement_confidence": item.measurement_confidence,
                    }
                    for item in comparisons
                ],
                "measurement_tolerance": policy.measurement_tolerance,
                "target_gap_tolerance": policy.target_gap_tolerance,
            },
            {
                "step": "route",
                "overall_trend": overall.value,
                "target_evidence_sufficient": target_evidence_sufficient,
                "cumulative_improvement": cumulative_improvement,
                "round_number": current_round,
                "no_improvement_streak": no_improvement_streak,
                "decision": decision.value,
                "stop_reason": stop_reason.value if stop_reason else None,
                "reason_codes": reason_codes,
            },
            {
                "step": "persist_verification",
                "verification_id": result.verification_id,
                "provider_run_id": result.provider_run_id,
                "result_artifact_ref": result.result_artifact_ref,
                "result_bytes_persisted": False,
            },
        ]
    )
    if store is not None:
        store.save_verification_result(result)
        store.record_event(
            plan.session_id,
            "verification_trace",
            {"verification_id": result.verification_id, "trace": trace},
        )
    return VerificationRunResult(
        verification=result,
        observation=observation,
        strategy_proposal=proposal,
        user_message=_user_message(
            strategy=proposal.selected_strategy,
            overall_trend=overall,
            decision=decision,
            comparisons=comparisons,
            reason_codes=reason_codes,
        ),
        trace=tuple(trace),
    )
