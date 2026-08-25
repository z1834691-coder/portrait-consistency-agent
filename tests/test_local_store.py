import json

from portrait_consistency_agent.core.contracts import (
    IntentAction,
    IntentFrame,
    IntentGoal,
    ProviderRun,
    ProviderRunStatus,
    Route,
)
from portrait_consistency_agent.storage.local_store import LocalTraceStore, redact_for_trace


def test_redaction_removes_tokens_and_image_payloads() -> None:
    safe_payload = redact_for_trace(
        {
            "confirmation_token": "do-not-store",
            "image_base64": "do-not-store",
            "image_sha256": "allowed-hash",
            "nested": {"secret_key": "do-not-store"},
        }
    )

    assert safe_payload["confirmation_token"] == "[REDACTED]"
    assert safe_payload["image_base64"] == "[REDACTED]"
    assert safe_payload["image_sha256"] == "allowed-hash"
    assert safe_payload["nested"]["secret_key"] == "[REDACTED]"


def test_store_persists_redacted_intent_and_trace(tmp_path) -> None:
    database_path = tmp_path / "demo.sqlite3"
    trace_path = tmp_path / "events.jsonl"
    store = LocalTraceStore(database_path, trace_path)
    store.initialize()
    session = store.create_session()
    intent = IntentFrame(
        session_id=session.session_id,
        turn=1,
        goal=IntentGoal.DIAGNOSE,
        route=Route.SINGLE,
        action=IntentAction.DIAGNOSE,
        confidence=0.0,
    )

    store.save_intent_frame(intent)
    assert store.next_intent_turn(session.session_id) == 2
    provider_run = ProviderRun(
        run_id="run_001",
        plan_id="plan_001",
        session_id=session.session_id,
        provider_version="2019-12-13",
        idempotency_key="idem_001",
        request_hash="a" * 64,
        status=ProviderRunStatus.PENDING,
    )
    store.save_provider_run(provider_run)
    store.record_event(
        session.session_id,
        "test_sensitive_event",
        {"confirmation_token": "do-not-store", "image_base64": "do-not-store"},
    )

    events = store.recent_events(session.session_id)
    assert {event["event_type"] for event in events} >= {
        "session_created",
        "intent_frame_saved",
        "provider_run_saved",
        "test_sensitive_event",
    }
    assert trace_path.is_file()
    trace_text = trace_path.read_text(encoding="utf-8")
    assert "do-not-store" not in trace_text
    assert "[REDACTED]" in trace_text
    assert b"do-not-store" not in database_path.read_bytes()

    parsed_lines = [json.loads(line) for line in trace_text.splitlines()]
    assert all(line["session_id"] == session.session_id for line in parsed_lines)
