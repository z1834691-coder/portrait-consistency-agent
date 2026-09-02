from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from portrait_consistency_agent.core.contracts import (
    AdjustmentMode,
    AnchorStatus,
    ArtifactLifecycle,
    BatchFailurePolicy,
    ChangeDirection,
    ComparisonTrend,
    ConfirmationScope,
    ConfirmationStatus,
    ContentSafetyEvidence,
    ContentSafetyStatus,
    EditableFeature,
    EditPlan,
    ErrorCategory,
    ErrorPhase,
    ExecutableChange,
    FeatureComparison,
    FeedbackEvidenceStrength,
    FeedbackLabelSource,
    FeedbackSignal,
    FeedbackStatus,
    IntentAction,
    IntentFrame,
    IntentGoal,
    IsolationStatus,
    ManualReviewRequest,
    MeasurementStatus,
    MeasurementUnit,
    NormalizedFeature,
    OutputPreference,
    ParserMode,
    PhotoQualityResult,
    PhotoRole,
    PlanConstraintsSnapshot,
    PlanStatus,
    ProfileStatus,
    ProviderErrorDetail,
    ProviderRun,
    ProviderRunStatus,
    QualityFlag,
    QualityRoute,
    ReferenceProfile,
    ReferenceSource,
    Route,
    StopReason,
    SubjectAnchorMetadata,
    SubjectMatchEvidence,
    SubjectMatchStatus,
    SuggestionOnlyChange,
    TargetScope,
    TencentBeautifyParams,
    TencentEffectWebParams,
    UserFeedback,
    VerificationDecision,
    VerificationResult,
)
from portrait_consistency_agent.core.policies import (
    build_v0_data_retention_policy,
    build_v0_quality_routing_policy,
    build_v0_safety_policy,
)

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
SHA = "a" * 64
OTHER_SHA = "b" * 64


def make_subject_match_evidence(**overrides: object) -> SubjectMatchEvidence:
    values: dict[str, object] = {
        "provider": "fixture_subject_adapter",
        "operation": "compare_subject",
        "model_version": "subject-fixture-v1",
        "threshold_policy_version": "subject-threshold-v0",
        "receipt_ref": "subject_receipt_001",
        "raw_score": 92.0,
        "raw_score_min": 0.0,
        "raw_score_max": 100.0,
        "calibrated": True,
        "evaluated_at": NOW,
    }
    values.update(overrides)
    return SubjectMatchEvidence(**values)


def make_profile(**overrides: object) -> ReferenceProfile:
    values: dict[str, object] = {
        "profile_id": "profile_001",
        "user_id": "user_001",
        "version": 1,
        "status": ProfileStatus.ACTIVE,
        "feature_snapshot_ref": "snapshot_001",
        "normalized_features": [
            NormalizedFeature(
                feature_code="face_width_height_ratio",
                value=0.72,
                unit=MeasurementUnit.NORMALIZED_RATIO,
                status=MeasurementStatus.MEASURED,
                confidence=0.93,
            )
        ],
        "reference_quality_result_id": "quality_reference_001",
        "allowed_features": [EditableFeature.FACE_LIFTING, EditableFeature.EYE_ENLARGING],
        "blocked_features": [EditableFeature.MAKEUP],
        "adjustment_mode": AdjustmentMode.BALANCED,
        "subject_anchor": SubjectAnchorMetadata(
            anchor_ref="anchor_001",
            consent_record_ref="consent_001",
            status=AnchorStatus.ACTIVE,
            created_at=NOW,
            expires_at=NOW + timedelta(days=183),
            retention_policy=build_v0_data_retention_policy(),
            access_policy_version="restricted-v1",
        ),
        "profile_schema_version": "profile-v0.3",
        "extractor_version": "extractor-v0",
        "canonicalization_version": "canonical-v0",
        "consent_policy_version": "consent-v0",
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return ReferenceProfile(**values)


def make_quality(**overrides: object) -> PhotoQualityResult:
    values: dict[str, object] = {
        "quality_result_id": "quality_001",
        "session_id": "session_001",
        "photo_id": "photo_001",
        "photo_sha256": SHA,
        "photo_role": PhotoRole.TARGET,
        "face_count": 1,
        "isolation_status": IsolationStatus.NOT_REQUIRED,
        "subject_match_status": SubjectMatchStatus.MATCH,
        "subject_match_confidence": 0.92,
        "subject_match_evidence": make_subject_match_evidence(),
        "quality_confidence": 0.90,
        "editability_confidence": 0.85,
        "content_safety_status": ContentSafetyStatus.PASSED,
        "content_safety_evidence": ContentSafetyEvidence(
            provider="fixture_safety_adapter",
            operation="classify_image_safety",
            provider_version="fixture-v1",
            policy_version="safety-content-v0",
            receipt_ref="safety_receipt_001",
            evaluated_at=NOW,
        ),
        "route": QualityRoute.CONTINUE,
        "routing_policy": build_v0_quality_routing_policy(),
        "analysis_version": "quality-v0",
        "provider_card_id": "tencent-beautify-pic-2019-12-13",
        "provider_card_version": "reviewed_2026-08-27",
        "created_at": NOW,
    }
    values.update(overrides)
    return PhotoQualityResult(**values)


def make_confirmation_scope(**overrides: object) -> ConfirmationScope:
    values: dict[str, object] = {
        "scope_id": "scope_001",
        "target_refs": ["photo_001"],
        "allowed_features": [EditableFeature.FACE_LIFTING, EditableFeature.EYE_ENLARGING],
        "max_provider_rounds": 3,
        "safety_policy_id": "safety_v0",
        "created_at": NOW,
        "expires_at": NOW + timedelta(hours=1),
    }
    values.update(overrides)
    return ConfirmationScope(**values)


def make_plan(**overrides: object) -> EditPlan:
    values: dict[str, object] = {
        "plan_id": "plan_001",
        "revision": 1,
        "session_id": "session_001",
        "profile_id": "profile_001",
        "profile_version": 1,
        "photo_id": "photo_001",
        "photo_sha256": SHA,
        "intent_id": "intent_001",
        "quality_result_id": "quality_001",
        "iteration": 1,
        "provider_api_version": "2019-12-13",
        "provider_card_id": "tencent-beautify-pic-2019-12-13",
        "provider_card_version": "reviewed_2026-08-27",
        "executable_changes": [
            ExecutableChange(
                feature=EditableFeature.FACE_LIFTING,
                provider_parameter="FaceLifting",
                user_delta=8,
                current_absolute=0,
                proposed_absolute=8,
                expected_direction=ChangeDirection.INCREASE,
                rationale_codes=["face_width_gap"],
            )
        ],
        "suggestion_only_changes": [
            SuggestionOnlyChange(
                feature=EditableFeature.LIPS_THICKNESS,
                user_delta=4,
                instruction="在支持唇厚的工具中手动小幅调整",
                reason_codes=["provider_unsupported"],
            )
        ],
        "provider_absolute_params": TencentBeautifyParams(face_lifting=8),
        "constraints_snapshot": PlanConstraintsSnapshot(
            allowed_features=[EditableFeature.FACE_LIFTING, EditableFeature.EYE_ENLARGING],
            blocked_features=[EditableFeature.MAKEUP],
            adjustment_mode=AdjustmentMode.BALANCED,
        ),
        "safety_policy": build_v0_safety_policy(),
        "status": PlanStatus.PROPOSED,
        "planner_version": "planner-v0",
        "mapping_policy_version": "mapping-v0",
        "created_at": NOW,
    }
    values.update(overrides)
    return EditPlan(**values)


def make_provider_run(**overrides: object) -> ProviderRun:
    values: dict[str, object] = {
        "run_id": "run_001",
        "trace_id": "trace_001",
        "plan_id": "plan_001",
        "plan_revision": 1,
        "session_id": "session_001",
        "photo_id": "photo_001",
        "attempt_number": 1,
        "provider_api_version": "2019-12-13",
        "region": "ap-guangzhou",
        "endpoint": "fmu.tencentcloudapi.com",
        "provider_card_id": "tencent-beautify-pic-2019-12-13",
        "provider_card_version": "reviewed_2026-08-27",
        "idempotency_key": "idem_001",
        "request_hash": SHA,
        "request_params": TencentBeautifyParams(face_lifting=8),
        "input_artifact_ref": "input_artifact_001",
        "input_artifact_sha256": SHA,
        "confirmation_ref": "confirm_001",
        "confirmation_scope_hash": OTHER_SHA,
        "consent_policy_version": "consent-v0",
        "status": ProviderRunStatus.SUCCEEDED,
        "provider_request_id": "request-001",
        "result_artifact_ref": "session_memory_result_001",
        "result_artifact_sha256": OTHER_SHA,
        "artifact_lifecycle": ArtifactLifecycle(expires_at=NOW + timedelta(minutes=10)),
        "started_at": NOW,
        "completed_at": NOW + timedelta(milliseconds=420),
        "network_latency_ms": 420,
        "total_latency_ms": 420,
    }
    values.update(overrides)
    return ProviderRun(**values)


def make_verification(**overrides: object) -> VerificationResult:
    values: dict[str, object] = {
        "verification_id": "verify_001",
        "session_id": "session_001",
        "profile_id": "profile_001",
        "profile_version": 1,
        "photo_id": "photo_001",
        "plan_id": "plan_001",
        "plan_revision": 1,
        "provider_run_id": "run_001",
        "feature_comparisons": [
            FeatureComparison(
                feature_code="face_width_height_ratio",
                before_gap=0.12,
                after_gap=0.08,
                trend=ComparisonTrend.IMPROVED,
                measurement_confidence=0.91,
            )
        ],
        "overall_trend": ComparisonTrend.IMPROVED,
        "result_artifact_available": True,
        "round_number": 1,
        "no_improvement_streak": 0,
        "safety_policy": build_v0_safety_policy(),
        "decision": VerificationDecision.REPLAN,
        "result_artifact_ref": "session_memory_result_001",
        "last_known_good_artifact_ref": "session_memory_result_001",
        "verifier_version": "verify-v0",
        "extractor_version": "extractor-v0",
        "threshold_policy_version": "threshold-v0",
        "created_at": NOW,
    }
    values.update(overrides)
    return VerificationResult(**values)


def test_reference_profile_is_structured_and_contains_no_raw_photo_field() -> None:
    payload = make_profile().model_dump(mode="json")

    assert payload["normalized_features"][0]["feature_code"] == "face_width_height_ratio"
    assert "raw_image" not in payload
    assert "feature_vector" not in payload
    assert "skin_tone" not in {item["feature_code"] for item in payload["normalized_features"]}


def test_geometry_only_profile_cannot_keep_active_subject_anchor() -> None:
    with pytest.raises(ValidationError, match="geometry-only"):
        make_profile(status=ProfileStatus.GEOMETRY_ONLY)


def test_geometry_only_profile_cannot_keep_anchor_pending_deletion() -> None:
    pending_anchor = SubjectAnchorMetadata(
        anchor_ref="anchor_001",
        consent_record_ref="consent_001",
        status=AnchorStatus.DELETE_PENDING,
        created_at=NOW,
        expires_at=NOW + timedelta(days=183),
        retention_policy=build_v0_data_retention_policy(),
        access_policy_version="restricted-v1",
        deletion_requested_at=NOW + timedelta(days=1),
        access_revoked_at=NOW + timedelta(days=1),
        primary_delete_due_at=NOW + timedelta(days=2),
        backup_delete_due_at=NOW + timedelta(days=9),
    )

    with pytest.raises(ValidationError, match="geometry-only"):
        make_profile(status=ProfileStatus.GEOMETRY_ONLY, subject_anchor=pending_anchor)


def test_quality_and_editability_use_most_restrictive_configured_route() -> None:
    result = make_quality(
        quality_confidence=0.90,
        editability_confidence=0.70,
        route=QualityRoute.WARN_CONTINUE,
        reason_codes=["editability_medium"],
    )

    assert result.route == QualityRoute.WARN_CONTINUE


def test_subject_match_is_routed_independently_from_quality() -> None:
    result = make_quality(
        subject_match_status=SubjectMatchStatus.UNCERTAIN,
        subject_match_confidence=0.62,
        subject_match_evidence=make_subject_match_evidence(raw_score=62.0),
        route=QualityRoute.SUBJECT_CONFIRMATION_REQUIRED,
        reason_codes=["subject_uncertain"],
    )

    assert result.quality_confidence == 0.90
    assert result.route == QualityRoute.SUBJECT_CONFIRMATION_REQUIRED


def test_uncalibrated_subject_score_cannot_masquerade_as_confidence() -> None:
    evidence = make_subject_match_evidence(calibrated=False)
    provisional = make_quality(
        subject_match_status=SubjectMatchStatus.UNCERTAIN,
        subject_match_confidence=None,
        subject_match_evidence=evidence,
        route=QualityRoute.SUBJECT_CONFIRMATION_REQUIRED,
        reason_codes=["subject_threshold_provisional"],
    )
    assert provisional.subject_match_confidence is None

    with pytest.raises(ValidationError, match="cannot masquerade as confidence"):
        make_quality(subject_match_evidence=evidence)


def test_content_safety_must_run_before_a_photo_can_continue() -> None:
    result = make_quality(
        content_safety_status=ContentSafetyStatus.NOT_EVALUATED,
        content_safety_evidence=None,
        route=QualityRoute.SAFETY_CHECK_REQUIRED,
        reason_codes=["safety_not_evaluated"],
    )

    assert result.route == QualityRoute.SAFETY_CHECK_REQUIRED


def test_completed_content_safety_status_requires_a_real_evidence_snapshot() -> None:
    with pytest.raises(ValidationError, match="auditable evidence snapshot"):
        make_quality(content_safety_evidence=None)


def test_multiface_requires_selection_then_isolation_or_user_crop() -> None:
    select = make_quality(
        face_count=2,
        isolation_status=IsolationStatus.USER_SELECTION_REQUIRED,
        route=QualityRoute.SELECT_FACE,
        quality_flags=[QualityFlag.MULTIPLE_FACES],
    )
    crop = make_quality(
        face_count=2,
        selected_face_ref="face_002",
        isolation_status=IsolationStatus.FAILED,
        route=QualityRoute.REQUIRE_USER_CROP,
        quality_flags=[QualityFlag.MULTIPLE_FACES],
        reason_codes=["isolation_failed"],
    )

    assert select.route == QualityRoute.SELECT_FACE
    assert crop.route == QualityRoute.REQUIRE_USER_CROP


def test_high_confidence_execute_still_requires_bounded_confirmation() -> None:
    with pytest.raises(ValidationError, match="bounded confirmation scope"):
        IntentFrame(
            intent_id="intent_001",
            session_id="session_001",
            turn=1,
            goal=IntentGoal.ALIGN_TO_PROFILE,
            route=Route.SINGLE,
            action=IntentAction.EXECUTE,
            target_scope=TargetScope.CURRENT_PHOTO,
            reference_source=ReferenceSource.EXISTING_PROFILE,
            target_refs=["photo_001"],
            output_preferences=[OutputPreference.EDITED_IMAGES],
            intent_confidence=0.99,
            confirmation_status=ConfirmationStatus.PENDING,
            parser_mode=ParserMode.LLM,
            model_provider="example-provider",
            model_version="model-v1",
        )

    intent = IntentFrame(
        intent_id="intent_001",
        session_id="session_001",
        turn=1,
        goal=IntentGoal.ALIGN_TO_PROFILE,
        route=Route.SINGLE,
        action=IntentAction.EXECUTE,
        target_scope=TargetScope.CURRENT_PHOTO,
        reference_source=ReferenceSource.EXISTING_PROFILE,
        target_refs=["photo_001"],
        output_preferences=[OutputPreference.REPORT, OutputPreference.EDITED_IMAGES],
        allowed_features=[EditableFeature.FACE_LIFTING, EditableFeature.EYE_ENLARGING],
        requested_max_rounds=3,
        batch_failure_policy=BatchFailurePolicy.CONTINUE_VALID,
        intent_confidence=0.99,
        confirmation_status=ConfirmationStatus.PENDING,
        confirmation_scope=make_confirmation_scope(),
        confirmation_ref="confirm_001",
        parser_mode=ParserMode.LLM,
        model_provider="example-provider",
        model_version="model-v1",
    )
    assert intent.confirmation_status == ConfirmationStatus.PENDING


def test_tencent_parameters_are_explicit_and_never_exceed_provider_range() -> None:
    assert TencentBeautifyParams().model_dump() == {
        "contract_version": "0.4",
        "face_lifting": 0,
        "eye_enlarging": 0,
        "whitening": 0,
        "smoothing": 0,
    }
    with pytest.raises(ValidationError):
        TencentBeautifyParams(face_lifting=101)


def test_edit_plan_round_limit_comes_from_policy_not_round_type() -> None:
    configurable_policy = build_v0_safety_policy().model_copy(
        update={"policy_id": "safety_future", "max_provider_rounds": 5}
    )
    future_plan = make_plan(iteration=4, safety_policy=configurable_policy)
    assert future_plan.iteration == 4

    with pytest.raises(ValidationError, match="applied configurable safety policy"):
        make_plan(iteration=4)


def test_suggestion_only_feature_does_not_block_supported_execution() -> None:
    plan = make_plan()

    assert plan.executable_changes[0].feature == EditableFeature.FACE_LIFTING
    assert plan.suggestion_only_changes[0].feature == EditableFeature.LIPS_THICKNESS
    assert plan.provider_card_version == "reviewed_2026-08-27"
    assert "expected_index_gain" not in type(plan).model_fields


def test_current_tencent_plan_cannot_execute_an_unsupported_future_feature() -> None:
    unsupported_change = ExecutableChange(
        feature=EditableFeature.LIPS_THICKNESS,
        provider_parameter="LipsThickness",
        user_delta=4,
        current_absolute=0,
        proposed_absolute=4,
        expected_direction=ChangeDirection.INCREASE,
        rationale_codes=["lip_gap"],
    )
    with pytest.raises(ValidationError, match="Provider Card features"):
        make_plan(
            executable_changes=[unsupported_change],
            constraints_snapshot=PlanConstraintsSnapshot(
                allowed_features=[EditableFeature.LIPS_THICKNESS],
                adjustment_mode=AdjustmentMode.BALANCED,
            ),
        )


def test_edit_plan_can_snapshot_a_tencent_effect_web_provider() -> None:
    plan = make_plan(
        provider="tencent_effect_web",
        provider_api_version="web_sdk_current",
        provider_card_id="tencent-effect-web",
        provider_card_version="web_candidate_2026-09-01",
        executable_changes=[
            ExecutableChange(
                feature=EditableFeature.FACE_LIFTING,
                provider_parameter="lift",
                user_delta=8,
                current_absolute=0,
                proposed_absolute=8,
                expected_direction=ChangeDirection.INCREASE,
                rationale_codes=["face_width_gap"],
            )
        ],
        provider_absolute_params=TencentEffectWebParams(lift=0.08),
    )

    assert plan.provider == "tencent_effect_web"
    assert isinstance(plan.provider_absolute_params, TencentEffectWebParams)
    assert plan.provider_absolute_params.lift == 0.08


def test_edit_plan_rejects_web_product_strength_scale_mismatch() -> None:
    with pytest.raises(ValidationError, match="planned absolute value"):
        make_plan(
            provider="tencent_effect_web",
            provider_api_version="web_sdk_current",
            provider_card_id="tencent-effect-web",
            provider_card_version="web_candidate_2026-09-01",
            executable_changes=[
                ExecutableChange(
                    feature=EditableFeature.FACE_LIFTING,
                    provider_parameter="lift",
                    user_delta=8,
                    current_absolute=0,
                    proposed_absolute=8,
                    expected_direction=ChangeDirection.INCREASE,
                    rationale_codes=["face_width_gap"],
                )
            ],
            provider_absolute_params=TencentEffectWebParams(lift=0.1),
        )


def test_whitening_must_be_explicitly_allowed() -> None:
    with pytest.raises(ValidationError, match="whitening requires explicit permission"):
        make_plan(provider_absolute_params=TencentBeautifyParams(face_lifting=8, whitening=10))


def test_successful_provider_run_requires_complete_factual_receipt() -> None:
    run = make_provider_run()
    assert run.provider_request_id == "request-001"
    assert run.request_params.face_lifting == 8

    with pytest.raises(ValidationError, match="complete provider and artifact receipt"):
        make_provider_run(result_artifact_sha256=None)


def test_failed_provider_run_requires_structured_error_and_separate_attempt() -> None:
    failed = make_provider_run(
        run_id="run_002",
        attempt_number=2,
        parent_run_id="run_001",
        status=ProviderRunStatus.TIMEOUT,
        provider_request_id=None,
        result_artifact_ref=None,
        result_artifact_sha256=None,
        artifact_lifecycle=None,
        error=ProviderErrorDetail(
            phase=ErrorPhase.NETWORK,
            category=ErrorCategory.TIMEOUT,
            provider_code="RequestTimeout",
            safe_message="Provider request timed out.",
            retryable=True,
        ),
    )

    assert failed.attempt_number == 2
    assert failed.error is not None and failed.error.retryable


def test_verification_uses_measured_feature_trends_not_an_index() -> None:
    result = make_verification()
    payload = result.model_dump(mode="json")

    assert payload["feature_comparisons"][0]["trend"] == "improved"
    assert "before_index" not in payload
    assert "after_index" not in payload
    assert "acceptance_probability" not in payload


def test_verification_replan_stops_when_configurable_policy_is_exhausted() -> None:
    with pytest.raises(ValidationError, match="replan is forbidden"):
        make_verification(round_number=2, no_improvement_streak=2)

    stopped = make_verification(
        round_number=2,
        no_improvement_streak=2,
        decision=VerificationDecision.STOP,
        stop_reason=StopReason.NO_IMPROVEMENT,
    )
    assert stopped.stop_reason == StopReason.NO_IMPROVEMENT


def test_user_accepted_stop_requires_explicit_human_feedback() -> None:
    feedback = UserFeedback(
        status=FeedbackStatus.ACCEPTED,
        label_source=FeedbackLabelSource.HUMAN_GOLD,
        explicit=True,
        evidence_strength=FeedbackEvidenceStrength.STRONG_FEEDBACK,
        recorded_at=NOW,
    )
    result = make_verification(
        decision=VerificationDecision.STOP,
        stop_reason=StopReason.USER_ACCEPTED,
        user_feedback=feedback,
    )
    assert result.user_feedback.explicit


def test_feedback_keeps_intent_and_satisfaction_separate() -> None:
    first_prompt = UserFeedback(
        status=FeedbackStatus.UNKNOWN,
        label_source=FeedbackLabelSource.USER_EXPLICIT,
        explicit=True,
        signal=FeedbackSignal.FIRST_PROMPT,
        evidence_strength=FeedbackEvidenceStrength.STRONG_INTENT,
        recorded_at=NOW,
    )

    assert first_prompt.status == FeedbackStatus.UNKNOWN
    with pytest.raises(ValidationError, match="not satisfaction labels"):
        UserFeedback(
            status=FeedbackStatus.ACCEPTED,
            label_source=FeedbackLabelSource.USER_EXPLICIT,
            explicit=True,
            signal=FeedbackSignal.FIRST_PROMPT,
            evidence_strength=FeedbackEvidenceStrength.STRONG_FEEDBACK,
            recorded_at=NOW,
        )


def test_manual_review_is_a_developer_queue_with_separate_photo_authorization() -> None:
    result = make_verification(
        decision=VerificationDecision.MANUAL_REVIEW,
        manual_review=ManualReviewRequest(
            reason_codes=["suspected_system_bug"],
            original_image_access_authorized=True,
            original_image_authorization_ref="review_auth_001",
        ),
    )

    assert result.manual_review is not None
    assert result.manual_review.reviewer == "project_developer"
