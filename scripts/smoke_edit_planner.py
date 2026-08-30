"""Offline smoke runner for Checkpoint 8A's deterministic planner.

This runner uses explicitly labelled geometry fixtures, not real photographs
and not a cloud API.  It demonstrates the full diagnosis -> mapping -> draft
plan -> redacted trace path without pretending that the mapping is calibrated.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from portrait_consistency_agent.core.contracts import (
    ContentSafetyEvidence,
    ContentSafetyStatus,
    EditableFeature,
    IntentAction,
    IntentFrame,
    IntentGoal,
    OutputPreference,
    ParserMode,
    PhotoRole,
    ReferenceSource,
    Route,
    SubjectMatchEvidence,
    SubjectMatchStatus,
    TargetScope,
)
from portrait_consistency_agent.core.policies import build_v0_quality_routing_policy
from portrait_consistency_agent.services.edit_planner import diagnose_and_plan
from portrait_consistency_agent.services.photo_quality import (
    FaceObservation,
    PhotoObservation,
    to_photo_quality_result,
)
from portrait_consistency_agent.services.reference_profile import build_reference_profile

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


def observation(
    photo_id: str, role: PhotoRole, *, face_width: int, eye_width: float
) -> PhotoObservation:
    return PhotoObservation(
        photo_id=photo_id,
        photo_sha256=("a" if role == PhotoRole.REFERENCE else "b") * 64,
        photo_role=role,
        width=1000,
        height=1200,
        image_format="JPEG",
        face_count=1,
        faces=(
            FaceObservation(
                index=0,
                x=250,
                y=180,
                width=face_width,
                height=620,
                eye_count=2,
                eye_centers=((0.35, 0.42), (0.65, 0.43)),
                eye_boxes=(
                    (0.28, 0.36, eye_width, 0.07),
                    (0.60, 0.37, eye_width, 0.07),
                ),
            ),
        ),
        selected_face_ref=f"{photo_id}_face_0",
        quality_confidence=0.94,
        editability_confidence=0.92,
        analysis_version="opencv-haar-quality-v0",
    )


def intent() -> IntentFrame:
    return IntentFrame(
        intent_id="intent_smoke",
        session_id="session_smoke",
        turn=1,
        goal=IntentGoal.ALIGN_TO_PROFILE,
        route=Route.SINGLE,
        action=IntentAction.PROVIDE_PLAN,
        target_scope=TargetScope.CURRENT_PHOTO,
        reference_source=ReferenceSource.EXISTING_PROFILE,
        target_refs=["photo_target"],
        output_preferences=[OutputPreference.MANUAL_PARAMETERS],
        allowed_features=[EditableFeature.FACE_LIFTING, EditableFeature.EYE_ENLARGING],
        intent_confidence=0.93,
        parser_mode=ParserMode.USER_STRUCTURED_INPUT,
    )


def main() -> int:
    reference = observation("photo_reference", PhotoRole.REFERENCE, face_width=500, eye_width=0.12)
    reference_quality = to_photo_quality_result(
        reference,
        session_id="session_smoke",
        quality_result_id="quality_reference_smoke",
        content_safety_status=ContentSafetyStatus.PASSED,
        content_safety_evidence=ContentSafetyEvidence(
            provider="fixture_safety",
            operation="ImageModeration",
            provider_version="2020-12-29",
            policy_version="safety-v0",
            receipt_ref="safety_reference_smoke",
            evaluated_at=NOW,
        ),
    )
    profile = build_reference_profile(
        reference,
        reference_quality,
        user_id="user_smoke",
        profile_id="profile_smoke",
        version=1,
        feature_snapshot_ref="snapshot_smoke",
    )
    target = observation("photo_target", PhotoRole.TARGET, face_width=540, eye_width=0.11)
    target_quality = to_photo_quality_result(
        target,
        session_id="session_smoke",
        quality_result_id="quality_target_smoke",
        subject_match_status=SubjectMatchStatus.MATCH,
        subject_match_evidence=SubjectMatchEvidence(
            provider="fixture_subject",
            operation="CompareFace",
            model_version="3.0",
            threshold_policy_version="subject-v0",
            receipt_ref="subject_smoke",
            raw_score=88.0,
            raw_score_min=0.0,
            raw_score_max=100.0,
            calibrated=False,
            evaluated_at=NOW,
        ),
        content_safety_status=ContentSafetyStatus.PASSED,
        content_safety_evidence=ContentSafetyEvidence(
            provider="fixture_safety",
            operation="ImageModeration",
            provider_version="2020-12-29",
            policy_version="safety-v0",
            receipt_ref="safety_target_smoke",
            evaluated_at=NOW,
        ),
        routing_policy=build_v0_quality_routing_policy(),
    )
    result = diagnose_and_plan(
        profile=profile,
        target_observation=target,
        quality_result=target_quality,
        intent=intent(),
        plan_id="plan_smoke",
    )
    payload = {
        "fixture_only": True,
        "route": result.route,
        "reason_codes": list(result.reason_codes),
        "user_message": result.user_message,
        "plan": (
            {
                "plan_id": result.plan.plan_id,
                "status": result.plan.status.value,
                "requires_confirmation": result.plan.requires_confirmation,
                "provider_absolute_params": result.plan.provider_absolute_params.model_dump(
                    mode="json"
                ),
                "executable_changes": [
                    change.model_dump(mode="json") for change in result.plan.executable_changes
                ],
            }
            if result.plan is not None
            else None
        ),
        "trace": list(result.trace),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
