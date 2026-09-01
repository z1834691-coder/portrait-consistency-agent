import json
import sqlite3

import pytest

from portrait_consistency_agent.core.contracts import (
    FeedbackEvidenceStrength,
    IntentAction,
    IntentFrame,
    IntentGoal,
    InteractionOutcome,
    InteractionStage,
    OutputPreference,
    ParserMode,
    ProductEvent,
    ProductEventType,
    ReferenceSource,
    Route,
    TargetScope,
)
from portrait_consistency_agent.storage.local_store import LocalTraceStore, redact_for_trace
from tests.test_contracts import (
    make_plan,
    make_profile,
    make_provider_run,
    make_quality,
    make_verification,
)


def test_redaction_removes_tokens_biometric_refs_and_image_payloads() -> None:
    safe_payload = redact_for_trace(
        {
            "confirmation_ref": "do-not-store",
            "image_base64": "do-not-store",
            "image_sha256": "allowed-hash",
            "subject_anchor": {"anchor_ref": "do-not-store"},
            "input_artifact_ref": "do-not-store",
            "nested": {"secret_key": "do-not-store"},
        }
    )

    assert safe_payload["confirmation_ref"] == "[REDACTED]"
    assert safe_payload["image_base64"] == "[REDACTED]"
    assert safe_payload["image_sha256"] == "allowed-hash"
    assert safe_payload["subject_anchor"] == "[REDACTED]"
    assert safe_payload["input_artifact_ref"] == "[REDACTED]"
    assert safe_payload["nested"]["secret_key"] == "[REDACTED]"


def test_store_persists_all_six_contracts_and_trace(tmp_path) -> None:
    database_path = tmp_path / "demo.sqlite3"
    trace_path = tmp_path / "events.jsonl"
    store = LocalTraceStore(database_path, trace_path)
    store.initialize()
    session = store.create_session()

    profile = make_profile()
    quality = make_quality(session_id=session.session_id)
    intent = IntentFrame(
        intent_id="intent_001",
        session_id=session.session_id,
        turn=1,
        goal=IntentGoal.DIAGNOSE,
        route=Route.SINGLE,
        action=IntentAction.DIAGNOSE,
        target_scope=TargetScope.CURRENT_PHOTO,
        reference_source=ReferenceSource.EXISTING_PROFILE,
        target_refs=["photo_001"],
        output_preferences=[OutputPreference.REPORT],
        intent_confidence=0.0,
        parser_mode=ParserMode.TEMPLATE_FALLBACK,
    )
    plan = make_plan(session_id=session.session_id)
    provider_run = make_provider_run(session_id=session.session_id)
    verification = make_verification(session_id=session.session_id)

    store.save_reference_profile(profile)
    store.save_photo_quality_result(quality)
    store.save_intent_frame(intent)
    store.save_edit_plan(plan)
    store.save_provider_run(provider_run)
    store.save_verification_result(verification)
    store.record_event(
        session.session_id,
        "redaction_probe",
        {"confirmation_ref": "confirm_001", "input_artifact_ref": "input_artifact_001"},
    )

    with sqlite3.connect(database_path) as connection:
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "reference_profiles",
                "photo_quality_results",
                "intent_frames",
                "edit_plans",
                "provider_runs",
                "verification_results",
            )
        }
        migration = connection.execute(
            "SELECT migration_id FROM schema_migrations WHERE migration_id = ?",
            ("contract_v0_2_tables",),
        ).fetchone()
        analytics_migration = connection.execute(
            "SELECT migration_id FROM schema_migrations WHERE migration_id = ?",
            ("contract_v0_3_analytics_lifecycle",),
        ).fetchone()
        verification_migration = connection.execute(
            "SELECT migration_id FROM schema_migrations WHERE migration_id = ?",
            ("contract_v0_4_verification_observation",),
        ).fetchone()
        subject_ack_migration = connection.execute(
            "SELECT migration_id FROM schema_migrations WHERE migration_id = ?",
            ("contract_v0_4_subject_uncertain_ack",),
        ).fetchone()

    assert all(count == 1 for count in counts.values())
    assert migration == ("contract_v0_2_tables",)
    assert analytics_migration == ("contract_v0_3_analytics_lifecycle",)
    assert verification_migration == ("contract_v0_4_verification_observation",)
    assert subject_ack_migration == ("contract_v0_4_subject_uncertain_ack",)
    assert store.next_intent_turn(session.session_id) == 2

    event_types = {event["event_type"] for event in store.recent_events(session.session_id)}
    assert event_types >= {
        "session_created",
        "photo_quality_result_saved",
        "intent_frame_saved",
        "edit_plan_saved",
        "provider_run_saved",
        "verification_result_saved",
    }

    trace_text = trace_path.read_text(encoding="utf-8")
    assert "confirm_001" not in trace_text
    assert "input_artifact_001" not in trace_text
    assert "[REDACTED]" in trace_text
    parsed_lines = [json.loads(line) for line in trace_text.splitlines()]
    assert all(line["session_id"] == session.session_id for line in parsed_lines)


def test_profile_replacement_deletes_old_feature_body_but_keeps_audit(tmp_path) -> None:
    database_path = tmp_path / "demo.sqlite3"
    trace_path = tmp_path / "events.jsonl"
    store = LocalTraceStore(database_path, trace_path)
    store.initialize()

    store.save_reference_profile(make_profile(profile_id="profile_001", version=1))
    store.save_reference_profile(make_profile(profile_id="profile_002", version=2))

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT profile_id, version, active, profile_payload_redacted_json, "
            "feature_body_deleted_at FROM reference_profiles ORDER BY version"
        ).fetchall()
        audit_count = connection.execute(
            "SELECT COUNT(*) FROM profile_audit_events WHERE event_type = ?",
            ("profile_feature_body_deleted",),
        ).fetchone()[0]

    old_payload = json.loads(rows[0]["profile_payload_redacted_json"])
    assert rows[0]["active"] == 0
    assert rows[0]["feature_body_deleted_at"] is not None
    assert old_payload == {
        "contract_version": "0.4",
        "feature_body_deleted": True,
        "profile_id": "profile_001",
        "status": "superseded",
        "version": 1,
    }
    assert rows[1]["active"] == 1
    assert audit_count == 1


def test_reusing_identical_photo_quality_contract_is_idempotent(tmp_path) -> None:
    store = LocalTraceStore(tmp_path / "demo.sqlite3", tmp_path / "events.jsonl")
    store.initialize()
    session = store.create_session()
    quality = make_quality(session_id=session.session_id)

    store.save_photo_quality_result(quality)
    # A Streamlit rerun can reach the same deterministic quality id again.
    store.save_photo_quality_result(quality)

    with sqlite3.connect(store.database_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM photo_quality_results WHERE quality_result_id = ?",
            (quality.quality_result_id,),
        ).fetchone()[0]
    assert count == 1
    event_types = [event["event_type"] for event in store.recent_events(session.session_id)]
    assert "photo_quality_result_saved" in event_types
    assert "photo_quality_result_reused" in event_types


def test_reusing_contract_identity_with_changed_payload_fails_closed(tmp_path) -> None:
    store = LocalTraceStore(tmp_path / "demo.sqlite3", tmp_path / "events.jsonl")
    store.initialize()
    session = store.create_session()
    quality = make_quality(session_id=session.session_id)
    store.save_photo_quality_result(quality)

    changed = quality.model_copy(update={"quality_confidence": 0.89})
    # Keep the same identity tuple but alter the payload.  A rerun must not
    # overwrite the original evidence or silently merge a second result.
    with pytest.raises(ValueError, match="different payload"):
        store.save_photo_quality_result(changed)

    changed_context = quality.model_copy(update={"photo_id": "photo_changed"})
    # The photo id participates in the lookup context but is not part of the
    # SQLite primary key.  The contract id must still fail closed with the
    # same actionable conflict instead of leaking sqlite3.IntegrityError.
    with pytest.raises(ValueError, match="different payload"):
        store.save_photo_quality_result(changed_context)

    with sqlite3.connect(store.database_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM photo_quality_results WHERE quality_result_id = ?",
            (quality.quality_result_id,),
        ).fetchone()[0]
    assert count == 1


def test_product_events_feed_a_redacted_dashboard_snapshot(tmp_path) -> None:
    store = LocalTraceStore(tmp_path / "demo.sqlite3", tmp_path / "events.jsonl")
    store.initialize()
    first_session = store.create_session()
    second_session = store.create_session(anonymous_user_id=first_session.anonymous_user_id)

    store.record_product_event(
        ProductEvent(
            event_id="product_event_feedback_001",
            session_id=second_session.session_id,
            anonymous_user_id=first_session.anonymous_user_id,
            event_type=ProductEventType.FEEDBACK_LIKED,
            stage=InteractionStage.VERIFICATION,
            evidence_strength=FeedbackEvidenceStrength.STRONG_FEEDBACK,
            outcome=InteractionOutcome.COMPLETED,
            reason_codes=["user_explicit_like"],
        )
    )
    snapshot = store.dashboard_snapshot()

    assert snapshot["total_sessions"] == 2
    assert snapshot["explicit_feedback"] == 1
    assert snapshot["wau"] == 1
    rows = store.recent_product_events()
    assert all("anonymous_user_id" not in row for row in rows)
    assert any(row["event_type"] == "feedback_liked" for row in rows)
