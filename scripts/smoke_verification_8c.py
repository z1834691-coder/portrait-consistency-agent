#!/usr/bin/env python3
"""Offline 8C smoke: strategy proposal, trend routing, and redacted Trace.

This script deliberately uses a fixture observer instead of a real provider
image.  It proves the 8C contract/control path without sending a photo or
claiming that Tencent's returned pixels improved.  The Streamlit button is the
path that observes a real returned image in a user's session.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from portrait_consistency_agent.core.contracts import (
    AdjustmentMode,
    ArtifactLifecycle,
    ChangeDirection,
    EditableFeature,
    EditPlan,
    FeatureDifference,
    MeasurementStatus,
    MeasurementUnit,
    NormalizedFeature,
    PlanConstraintsSnapshot,
    PlanStatus,
    ProfileStatus,
    ProviderRun,
    ProviderRunStatus,
    ReferenceProfile,
    TencentBeautifyParams,
)
from portrait_consistency_agent.core.policies import build_v0_safety_policy
from portrait_consistency_agent.services import verification
from portrait_consistency_agent.services.verification import ResultObservation, verify_result

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
SHA = "a" * 64
OTHER_SHA = "b" * 64


def fixture_profile() -> ReferenceProfile:
    return ReferenceProfile(
        profile_id="profile_smoke",
        user_id="user_smoke",
        version=1,
        status=ProfileStatus.GEOMETRY_ONLY,
        feature_snapshot_ref="snapshot_smoke",
        normalized_features=[
            NormalizedFeature(
                feature_code="face_width_height_ratio",
                value=0.72,
                unit=MeasurementUnit.NORMALIZED_RATIO,
                status=MeasurementStatus.MEASURED,
                confidence=0.92,
            )
        ],
        reference_quality_result_id="quality_reference_smoke",
        allowed_features=[EditableFeature.FACE_LIFTING],
        adjustment_mode=AdjustmentMode.BALANCED,
        profile_schema_version="profile-v0.3",
        extractor_version="fixture-extractor-v0",
        canonicalization_version="canonical-v0",
        consent_policy_version="consent-v0",
        created_at=NOW,
        updated_at=NOW,
    )


def fixture_plan() -> EditPlan:
    return EditPlan(
        plan_id="plan_8c_smoke",
        revision=1,
        session_id="session_8c_smoke",
        profile_id="profile_smoke",
        profile_version=1,
        photo_id="photo_8c_smoke",
        photo_sha256=SHA,
        intent_id="intent_8c_smoke",
        quality_result_id="quality_target_smoke",
        iteration=1,
        provider_api_version="2019-12-13",
        provider_card_id="tencent-beautify-pic-2019-12-13",
        provider_card_version="reviewed_2026-08-27",
        baseline_feature_differences=[
            FeatureDifference(
                feature_code="face_width_height_ratio",
                reference_value=0.72,
                observed_value=0.8064,
                normalized_gap=0.12,
                measurement_confidence=0.92,
                editable=True,
                reason_codes=["mapped_feature"],
            )
        ],
        executable_changes=[
            {
                "feature": EditableFeature.FACE_LIFTING,
                "provider_parameter": "FaceLifting",
                "user_delta": 8,
                "current_absolute": 0,
                "proposed_absolute": 8,
                "expected_direction": ChangeDirection.INCREASE,
                "rationale_codes": ["measured_geometry_gap"],
            }
        ],
        provider_absolute_params=TencentBeautifyParams(face_lifting=8),
        constraints_snapshot=PlanConstraintsSnapshot(
            allowed_features=[EditableFeature.FACE_LIFTING],
            adjustment_mode=AdjustmentMode.BALANCED,
        ),
        safety_policy=build_v0_safety_policy(),
        requires_confirmation=True,
        status=PlanStatus.CONFIRMED,
        confirmation_ref="confirmation_8c_smoke",
        confirmation_scope_hash=OTHER_SHA,
        planner_version="planner-v0",
        mapping_policy_version="mapping-v0",
        created_at=NOW,
    )


def fixture_run() -> ProviderRun:
    return ProviderRun(
        run_id="run_8c_smoke",
        trace_id="trace_8c_smoke",
        plan_id="plan_8c_smoke",
        plan_revision=1,
        session_id="session_8c_smoke",
        photo_id="photo_8c_smoke",
        attempt_number=1,
        provider_api_version="2019-12-13",
        region="ap-guangzhou",
        endpoint="fmu.tencentcloudapi.com",
        provider_card_id="tencent-beautify-pic-2019-12-13",
        provider_card_version="reviewed_2026-08-27",
        idempotency_key="idempotency_8c_smoke",
        request_hash=SHA,
        request_params=TencentBeautifyParams(face_lifting=8),
        input_artifact_ref="input_8c_smoke",
        input_artifact_sha256=SHA,
        confirmation_ref="confirmation_8c_smoke",
        confirmation_scope_hash=OTHER_SHA,
        consent_policy_version="consent-v0",
        status=ProviderRunStatus.SUCCEEDED,
        provider_request_id="request_8c_smoke",
        result_artifact_ref="session_memory_8c_smoke",
        result_artifact_sha256=OTHER_SHA,
        artifact_lifecycle=ArtifactLifecycle(expires_at=NOW + timedelta(minutes=10)),
        started_at=NOW,
        completed_at=NOW + timedelta(milliseconds=250),
        network_latency_ms=250,
        total_latency_ms=250,
    )


def fixture_observation(value: float) -> ResultObservation:
    return ResultObservation(
        photo_id="photo_8c_smoke",
        photo_sha256=OTHER_SHA,
        decode_ok=True,
        face_count=1,
        normalized_features=(
            NormalizedFeature(
                feature_code="face_width_height_ratio",
                value=value,
                unit=MeasurementUnit.NORMALIZED_RATIO,
                status=MeasurementStatus.MEASURED,
                confidence=0.92,
            ),
        ),
        analysis_version="fixture-observer-v0",
    )


def main() -> None:
    original_observer = verification.observe_result_bytes
    plan = fixture_plan()
    provider_run = fixture_run()
    profile = fixture_profile()
    cases = {
        "improved_replan": (0.756, None),
        "target_evidence_close": (0.7416, None),
        "worsened_manual_review": (0.864, None),
        "worsened_stop_with_fallback": (0.864, "session_memory_previous"),
    }
    outputs: dict[str, object] = {"fixture_only": True, "network_called": False, "cases": {}}
    try:
        for case_name, (value, fallback_ref) in cases.items():
            verification.observe_result_bytes = lambda result_image_bytes, photo_id, value=value: (
                fixture_observation(value)
            )
            result = verify_result(
                profile=profile,
                plan=plan,
                provider_run=provider_run.model_copy(update={"run_id": f"run_{case_name}"}),
                result_image_bytes=b"fixture-result-not-a-real-image",
                plan_family_id="family_8c_smoke",
                last_known_good_artifact_ref=fallback_ref,
                verification_id=f"verification_{case_name}",
            )
            outputs["cases"][case_name] = {
                "overall_trend": result.verification.overall_trend.value,
                "decision": result.verification.decision.value,
                "stop_reason": (
                    result.verification.stop_reason.value
                    if result.verification.stop_reason
                    else None
                ),
                "strategy": result.strategy_proposal.selected_strategy.value,
                "trace": list(result.trace),
            }
    finally:
        verification.observe_result_bytes = original_observer
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
