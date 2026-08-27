from __future__ import annotations

from datetime import datetime, timezone

from portrait_consistency_agent.core.contracts import (
    PhotoRole,
)
from portrait_consistency_agent.services import checkpoint6
from portrait_consistency_agent.services.photo_quality import FaceObservation, PhotoObservation
from portrait_consistency_agent.services.tencent_safety import (
    ContentSafetyDecision,
    TencentImageModerationResponse,
    build_content_safety_decision,
)
from portrait_consistency_agent.services.tencent_subject import TencentCompareFaceResponse
from portrait_consistency_agent.storage.local_store import LocalTraceStore

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
SHA = "a" * 64


def make_observation(photo_id: str, role: PhotoRole) -> PhotoObservation:
    return PhotoObservation(
        photo_id=photo_id,
        photo_sha256=SHA,
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
                width=500,
                height=620,
                eye_count=2,
                eye_centers=((0.35, 0.42), (0.65, 0.43)),
            ),
        ),
        selected_face_ref=f"{photo_id}_face_0",
        quality_confidence=0.94,
        editability_confidence=0.92,
    )


def pass_decision() -> ContentSafetyDecision:
    return build_content_safety_decision(
        TencentImageModerationResponse(
            request_id="safety_request_001",
            suggestion="Pass",
            label="Normal",
            sub_label=None,
            score=0.0,
        ),
        receipt_ref="safety_receipt_001",
    )


class FakeSubjectClient:
    def compare_base64(
        self,
        image_a: bytes,
        image_b: bytes,
        *,
        policy: object,
    ) -> TencentCompareFaceResponse:
        return TencentCompareFaceResponse(
            request_id="subject_request_001",
            raw_score=82.0,
            face_model_version="3.0",
        )


def test_checkpoint6_locks_profile_and_persists_quality_trace(tmp_path) -> None:
    database_path = tmp_path / "demo.sqlite3"
    trace_path = tmp_path / "events.jsonl"
    store = LocalTraceStore(database_path, trace_path)
    store.initialize()
    session = store.create_session()
    observation = make_observation("photo_reference", PhotoRole.REFERENCE)

    original_analyzer = checkpoint6.analyze_photo_bytes
    checkpoint6.analyze_photo_bytes = lambda *args, **kwargs: observation
    try:
        service = checkpoint6.Checkpoint6Service(store=store)
        preparation = service.prepare_reference(
            b"reference-image-bytes",
            session_id=session.session_id,
            photo_id="photo_reference",
            quality_result_id="quality_reference",
            safety_decision=pass_decision(),
        )
        result = service.lock_profile(
            preparation,
            user_id="user_001",
            profile_id="profile_001",
            version=1,
            feature_snapshot_ref="snapshot_001",
        )
    finally:
        checkpoint6.analyze_photo_bytes = original_analyzer

    assert result.profile.status.value == "geometry_only"
    assert len(result.profile.normalized_features) >= 10
    with store._connect() as connection:  # noqa: SLF001 - integration assertion
        assert connection.execute("SELECT COUNT(*) FROM reference_profiles").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM photo_quality_results").fetchone()[0] == 1
    events = {event["event_type"] for event in store.recent_events(session.session_id)}
    assert "reference_profile_locked" in events


def test_checkpoint6_current_session_match_saves_provider_evidence(tmp_path) -> None:
    database_path = tmp_path / "demo.sqlite3"
    trace_path = tmp_path / "events.jsonl"
    store = LocalTraceStore(database_path, trace_path)
    store.initialize()
    session = store.create_session()
    observations = iter(
        [
            make_observation("reference_current_session", PhotoRole.REFERENCE),
            make_observation("photo_target", PhotoRole.TARGET),
        ]
    )
    original_analyzer = checkpoint6.analyze_photo_bytes
    checkpoint6.analyze_photo_bytes = lambda *args, **kwargs: next(observations)
    try:
        service = checkpoint6.Checkpoint6Service(
            store=store,
            subject_client=FakeSubjectClient(),
        )
        result = service.validate_target_current_session(
            b"reference-image-bytes",
            b"target-image-bytes",
            session_id=session.session_id,
            target_photo_id="photo_target",
            quality_result_id="quality_target",
            safety_decision=pass_decision(),
            receipt_ref="subject_receipt_001",
        )
    finally:
        checkpoint6.analyze_photo_bytes = original_analyzer

    assert result.subject_decision is not None
    assert result.subject_decision.status.value == "match"
    assert result.quality_result is not None
    assert result.quality_result.subject_match_evidence is not None
    assert result.quality_result.subject_match_evidence.calibrated is False
    assert result.quality_result.subject_match_confidence is None
    events = {event["event_type"] for event in store.recent_events(session.session_id)}
    assert "subject_match_decision_created" in events
