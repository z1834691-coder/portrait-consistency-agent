from datetime import datetime, timezone

from portrait_consistency_agent.core.contracts import (
    AdjustmentMode,
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
from portrait_consistency_agent.services.edit_planner import (
    diagnose_and_plan,
)
from portrait_consistency_agent.services.photo_quality import (
    FaceObservation,
    PhotoObservation,
    to_photo_quality_result,
)
from portrait_consistency_agent.services.reference_profile import build_reference_profile
from portrait_consistency_agent.storage.local_store import LocalTraceStore

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


def make_observation(
    photo_id: str,
    role: PhotoRole,
    *,
    face_width: int = 500,
    eye_boxes: tuple[tuple[float, float, float, float], ...] = (
        (0.28, 0.36, 0.12, 0.07),
        (0.60, 0.37, 0.12, 0.07),
    ),
    eye_count: int = 2,
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
                eye_count=eye_count,
                eye_centers=((0.35, 0.42), (0.65, 0.43)) if eye_count >= 2 else ((0.35, 0.42),),
                eye_boxes=eye_boxes,
            ),
        ),
        selected_face_ref=f"{photo_id}_face_0",
        quality_confidence=0.94,
        editability_confidence=0.92,
        analysis_version="opencv-haar-quality-v0",
    )


def make_intent(**overrides: object) -> IntentFrame:
    values: dict[str, object] = {
        "intent_id": "intent_001",
        "session_id": "session_001",
        "turn": 1,
        "goal": IntentGoal.ALIGN_TO_PROFILE,
        "route": Route.SINGLE,
        "action": IntentAction.PROVIDE_PLAN,
        "target_scope": TargetScope.CURRENT_PHOTO,
        "reference_source": ReferenceSource.EXISTING_PROFILE,
        "target_refs": ["photo_target"],
        "output_preferences": [OutputPreference.MANUAL_PARAMETERS],
        "allowed_features": [EditableFeature.FACE_LIFTING, EditableFeature.EYE_ENLARGING],
        "blocked_features": [],
        "adjustment_mode": AdjustmentMode.BALANCED,
        "intent_confidence": 0.93,
        "parser_mode": ParserMode.USER_STRUCTURED_INPUT,
    }
    values.update(overrides)
    return IntentFrame(**values)


def make_target_quality(observation: PhotoObservation, **overrides: object):
    values: dict[str, object] = {
        "session_id": "session_001",
        "quality_result_id": "quality_target",
        "subject_match_status": SubjectMatchStatus.MATCH,
        "subject_match_evidence": SubjectMatchEvidence(
            provider="fixture_subject",
            operation="CompareFace",
            model_version="3.0",
            threshold_policy_version="subject-v0",
            receipt_ref="subject_receipt",
            raw_score=88.0,
            raw_score_min=0.0,
            raw_score_max=100.0,
            calibrated=False,
            evaluated_at=NOW,
        ),
        "content_safety_status": ContentSafetyStatus.PASSED,
        "content_safety_evidence": ContentSafetyEvidence(
            provider="fixture_safety",
            operation="ImageModeration",
            provider_version="2020-12-29",
            policy_version="safety-v0",
            receipt_ref="safety_receipt",
            evaluated_at=NOW,
        ),
        "routing_policy": build_v0_quality_routing_policy(),
    }
    values.update(overrides)
    return to_photo_quality_result(observation, **values)


def make_profile():
    reference = make_observation("photo_reference", PhotoRole.REFERENCE)
    quality = to_photo_quality_result(
        reference,
        session_id="session_001",
        quality_result_id="quality_reference",
        content_safety_status=ContentSafetyStatus.PASSED,
        content_safety_evidence=ContentSafetyEvidence(
            provider="fixture_safety",
            operation="ImageModeration",
            provider_version="2020-12-29",
            policy_version="safety-v0",
            receipt_ref="safety_reference",
            evaluated_at=NOW,
        ),
    )
    return build_reference_profile(
        reference,
        quality,
        user_id="user_001",
        profile_id="profile_001",
        version=1,
        feature_snapshot_ref="snapshot_001",
    )


def test_planner_generates_two_bounded_executable_changes_and_trace() -> None:
    profile = make_profile()
    target = make_observation(
        "photo_target",
        PhotoRole.TARGET,
        face_width=540,
        eye_boxes=((0.28, 0.36, 0.11, 0.07), (0.60, 0.37, 0.11, 0.07)),
    )
    result = diagnose_and_plan(
        profile=profile,
        target_observation=target,
        quality_result=make_target_quality(target),
        intent=make_intent(),
        plan_id="plan_001",
    )

    assert result.route == "plan_ready"
    assert result.plan is not None
    assert {change.feature for change in result.plan.executable_changes} == {
        EditableFeature.FACE_LIFTING,
        EditableFeature.EYE_ENLARGING,
    }
    assert result.plan.provider_absolute_params.whitening == 0
    assert result.plan.provider_absolute_params.smoothing == 0
    assert result.plan.requires_confirmation is True
    assert result.plan.mapping_policy_version == "2026-08-28"
    assert result.trace[2]["mapping_policy_id"] == "mapping_policy_v0.1"
    assert [item["step"] for item in result.trace] == [
        "preflight",
        "measure",
        "map",
        "persist_plan",
    ]


def test_planner_returns_diagnosis_only_inside_tolerance() -> None:
    profile = make_profile()
    target = make_observation(
        "photo_target",
        PhotoRole.TARGET,
        face_width=502,
        eye_boxes=((0.28, 0.36, 0.119, 0.07), (0.60, 0.37, 0.119, 0.07)),
    )
    result = diagnose_and_plan(
        profile=profile,
        target_observation=target,
        quality_result=make_target_quality(target),
        intent=make_intent(),
    )

    assert result.route == "diagnosis_only"
    assert result.plan is not None
    assert result.plan.executable_changes == []
    assert result.plan.provider_absolute_params.face_lifting == 0
    assert result.plan.provider_absolute_params.eye_enlarging == 0


def test_planner_does_not_fake_an_unachievable_direction() -> None:
    profile = make_profile()
    target = make_observation(
        "photo_target",
        PhotoRole.TARGET,
        face_width=460,
        eye_boxes=((0.28, 0.36, 0.14, 0.08), (0.60, 0.37, 0.14, 0.08)),
    )
    result = diagnose_and_plan(
        profile=profile,
        target_observation=target,
        quality_result=make_target_quality(target),
        intent=make_intent(),
    )

    assert result.plan is not None
    assert result.plan.executable_changes == []
    assert all(
        "provider_cannot_move_toward_reference" in item.reason_codes
        for item in result.feature_differences
        if item.feature_code in {"face_width_height_ratio", "eye_area_mean_face_ratio"}
    )


def test_planner_degrades_eye_plan_when_eye_area_is_unavailable() -> None:
    profile = make_profile()
    target = make_observation("photo_target", PhotoRole.TARGET, eye_boxes=(), eye_count=1)
    result = diagnose_and_plan(
        profile=profile,
        target_observation=target,
        quality_result=make_target_quality(target),
        intent=make_intent(),
    )

    eye_difference = next(
        item
        for item in result.feature_differences
        if item.feature_code == "eye_area_mean_face_ratio"
    )
    assert eye_difference.normalized_gap is None
    assert any(
        change.feature == EditableFeature.EYE_ENLARGING
        for change in result.plan.suggestion_only_changes
    )


def test_planner_respects_user_block_and_persists_redacted_plan(tmp_path) -> None:
    store = LocalTraceStore(tmp_path / "demo.sqlite3", tmp_path / "events.jsonl")
    store.initialize()
    session = store.create_session(anonymous_user_id="user_001")
    profile = make_profile()
    target = make_observation("photo_target", PhotoRole.TARGET, face_width=540)
    quality = make_target_quality(target, session_id=session.session_id)
    intent = make_intent(
        session_id=session.session_id,
        blocked_features=[EditableFeature.FACE_LIFTING],
        allowed_features=[EditableFeature.EYE_ENLARGING],
    )
    result = diagnose_and_plan(
        profile=profile,
        target_observation=target,
        quality_result=quality,
        intent=intent,
        store=store,
        plan_id="plan_store",
    )

    assert result.plan is not None
    assert result.plan.provider_absolute_params.face_lifting == 0
    assert any(
        "feature_blocked_by_user" in item.reason_codes
        for item in result.feature_differences
        if item.feature_code == "face_width_height_ratio"
    )
    events = {event["event_type"] for event in store.recent_events(session.session_id)}
    assert "edit_plan_saved" in events
    assert "edit_plan_trace" in events
