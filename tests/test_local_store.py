import json
import sqlite3

from portrait_consistency_agent.core.contracts import (
    IntentAction,
    IntentFrame,
    IntentGoal,
    OutputPreference,
    ParserMode,
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

    assert all(count == 1 for count in counts.values())
    assert migration == ("contract_v0_2_tables",)
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
        "contract_version": "0.2",
        "feature_body_deleted": True,
        "profile_id": "profile_001",
        "status": "superseded",
        "version": 1,
    }
    assert rows[1]["active"] == 1
    assert audit_count == 1
