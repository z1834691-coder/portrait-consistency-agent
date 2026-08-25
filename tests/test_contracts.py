from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from portrait_consistency_agent.core.contracts import (
    AdjustmentMode,
    ConfirmationStatus,
    EditableFeature,
    EditPlan,
    FeatureDelta,
    IntentAction,
    IntentFrame,
    IntentGoal,
    PhotoQualityResult,
    PlanStatus,
    ProviderRun,
    ProviderRunStatus,
    QualityFlag,
    QualityStatus,
    ReferenceProfile,
    Route,
    StopReason,
    TencentBeautifyParams,
    VerificationDecision,
    VerificationResult,
)

NOW = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


def test_reference_profile_is_json_safe_and_hides_raw_feature_vector() -> None:
    profile = ReferenceProfile(
        profile_id="profile_001",
        user_id="user_001",
        version=1,
        feature_snapshot_ref="snapshot_001",
        allowed_features=[EditableFeature.FACE_LIFTING, EditableFeature.EYE_ENLARGING],
        blocked_features=[EditableFeature.MAKEUP],
        adjustment_mode=AdjustmentMode.BALANCED,
        created_at=NOW,
    )

    payload = profile.model_dump(mode="json")

    assert payload["feature_snapshot_ref"] == "snapshot_001"
    assert "raw_image" not in payload
    assert "feature_vector" not in payload


def test_rejected_photo_requires_a_reason() -> None:
    with pytest.raises(ValidationError, match="rejected photos need"):
        PhotoQualityResult(
            photo_id="photo_001",
            status=QualityStatus.REJECTED,
            face_count=0,
            confidence=0.95,
            analysis_version="quality-v0",
            created_at=NOW,
        )

    result = PhotoQualityResult(
        photo_id="photo_001",
        status=QualityStatus.REJECTED,
        face_count=0,
        quality_flags=[QualityFlag.NO_FACE],
        confidence=0.95,
        analysis_version="quality-v0",
        created_at=NOW,
    )
    assert result.status == QualityStatus.REJECTED


def test_execute_intent_requires_confirmation_token() -> None:
    with pytest.raises(ValidationError, match="confirmation token"):
        IntentFrame(
            session_id="session_001",
            turn=1,
            goal=IntentGoal.ALIGN_TO_PROFILE,
            route=Route.SINGLE,
            action=IntentAction.EXECUTE,
            confidence=0.9,
            confirmation_status=ConfirmationStatus.PENDING,
            created_at=NOW,
        )

    intent = IntentFrame(
        session_id="session_001",
        turn=1,
        goal=IntentGoal.ALIGN_TO_PROFILE,
        route=Route.SINGLE,
        action=IntentAction.EXECUTE,
        allowed_features=[EditableFeature.FACE_LIFTING],
        adjustment_mode=AdjustmentMode.BALANCED,
        max_rounds=2,
        confidence=0.9,
        confirmation_status=ConfirmationStatus.PENDING,
        confirmation_token="confirm_001",
        created_at=NOW,
    )
    assert intent.confirmation_status == ConfirmationStatus.PENDING


def test_edit_plan_has_explicit_tencent_defaults_and_confirmation_guard() -> None:
    params = TencentBeautifyParams()
    assert params.model_dump() == {
        "contract_version": "0.1",
        "face_lifting": 0,
        "eye_enlarging": 0,
        "whitening": 0,
        "smoothing": 0,
    }

    with pytest.raises(ValidationError, match="require a confirmation token"):
        EditPlan(
            plan_id="plan_001",
            session_id="session_001",
            profile_id="profile_001",
            photo_id="photo_001",
            iteration=1,
            provider_version="2019-12-13",
            user_deltas=[
                FeatureDelta(
                    feature=EditableFeature.FACE_LIFTING,
                    delta=8,
                    rationale_code="face_width_delta",
                )
            ],
            provider_absolute_params=TencentBeautifyParams(face_lifting=8),
            status=PlanStatus.CONFIRMED,
            planner_version="planner-v0",
            created_at=NOW,
        )


def test_successful_provider_run_requires_real_outcome_references() -> None:
    base = dict(
        run_id="run_001",
        plan_id="plan_001",
        session_id="session_001",
        provider_version="2019-12-13",
        idempotency_key="idem_001",
        request_hash="a" * 64,
        status=ProviderRunStatus.SUCCEEDED,
        started_at=NOW,
    )
    with pytest.raises(ValidationError, match="successful runs require"):
        ProviderRun(**base)

    run = ProviderRun(
        **base,
        provider_request_id="request-001",
        result_ref="storage/results/result_001.webp",
        latency_ms=420,
        completed_at=NOW,
    )
    assert run.status == ProviderRunStatus.SUCCEEDED


def test_verification_delta_must_be_measured_not_claimed() -> None:
    with pytest.raises(ValidationError, match="index_delta"):
        VerificationResult(
            verification_id="verify_001",
            session_id="session_001",
            plan_id="plan_001",
            before_index=70.0,
            after_index=76.0,
            index_delta=10.0,
            confidence=0.8,
            decision=VerificationDecision.STOP,
            stop_reason=StopReason.GOAL_MET,
            verification_version="verify-v0",
            result_photo_ref="storage/results/result_001.webp",
            created_at=NOW,
        )

    result = VerificationResult(
        verification_id="verify_001",
        session_id="session_001",
        plan_id="plan_001",
        before_index=70.0,
        after_index=76.0,
        index_delta=6.0,
        confidence=0.8,
        decision=VerificationDecision.STOP,
        stop_reason=StopReason.GOAL_MET,
        verification_version="verify-v0",
        result_photo_ref="storage/results/result_001.webp",
        created_at=NOW,
    )
    assert result.index_delta == 6.0
