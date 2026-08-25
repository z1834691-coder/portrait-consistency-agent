"""Local SQLite + JSONL audit storage for the non-production demo runtime."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from portrait_consistency_agent.core.contracts import IntentFrame, ProviderRun


SENSITIVE_KEY_FRAGMENTS = (
    "secret",
    "password",
    "authorization",
    "confirmation_token",
    "image_base64",
    "raw_image",
    "image_payload",
    "result_url",
)
REDACTED = "[REDACTED]"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def redact_for_trace(value: Any, *, key: str | None = None) -> Any:
    """Return a JSON-safe audit projection without image bytes, tokens, or secrets."""

    if key and any(fragment in key.lower() for fragment in SENSITIVE_KEY_FRAGMENTS):
        return REDACTED
    if isinstance(value, BaseModel):
        return redact_for_trace(value.model_dump(mode="json"))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {
            str(item_key): redact_for_trace(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_for_trace(item) for item in value]
    return value


@dataclass(frozen=True)
class SessionRecord:
    session_id: str
    state: str
    created_at: str


class LocalTraceStore:
    """Simple append-oriented store for the local Streamlit prototype.

    It is intentionally not a multi-user or production database. Photo bytes are
    never accepted by this class; callers may only register hashes and metadata.
    """

    def __init__(self, database_path: Path, trace_path: Path) -> None:
        self.database_path = database_path
        self.trace_path = trace_path

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS intent_frames (
                    session_id TEXT NOT NULL,
                    turn INTEGER NOT NULL,
                    intent_payload_redacted_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (session_id, turn),
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                );

                CREATE TABLE IF NOT EXISTS provider_runs (
                    run_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    provider_run_payload_redacted_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                );

                CREATE TABLE IF NOT EXISTS trace_events (
                    event_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_redacted_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                );
                """
            )

    def create_session(self, *, state: str = "FOUNDATION") -> SessionRecord:
        session_id = f"session_{uuid.uuid4().hex}"
        created_at = utc_now().isoformat()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO sessions (session_id, state, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, state, created_at, created_at),
            )
        self.record_event(session_id, "session_created", {"state": state})
        return SessionRecord(session_id=session_id, state=state, created_at=created_at)

    def save_intent_frame(self, intent_frame: IntentFrame) -> None:
        self._require_session(intent_frame.session_id)
        payload = redact_for_trace(intent_frame)
        created_at = utc_now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO intent_frames (session_id, turn, intent_payload_redacted_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    intent_frame.session_id,
                    intent_frame.turn,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    created_at,
                ),
            )
            connection.execute(
                "UPDATE sessions SET state = ?, updated_at = ? WHERE session_id = ?",
                ("INTENT_CAPTURED", created_at, intent_frame.session_id),
            )
        self.record_event(
            intent_frame.session_id,
            "intent_frame_saved",
            {
                "turn": intent_frame.turn,
                "goal": intent_frame.goal,
                "route": intent_frame.route,
                "action": intent_frame.action,
                "model_provider": intent_frame.model_provider,
                "prompt_version": intent_frame.prompt_version,
                "missing_slots": intent_frame.missing_slots,
            },
        )

    def next_intent_turn(self, session_id: str) -> int:
        self._require_session(session_id)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(turn), 0) AS max_turn FROM intent_frames WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return int(row["max_turn"]) + 1

    def save_provider_run(self, provider_run: ProviderRun) -> None:
        """Persist a redacted provider audit projection after a real adapter attempt."""

        self._require_session(provider_run.session_id)
        payload = redact_for_trace(provider_run)
        created_at = utc_now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO provider_runs (run_id, session_id, plan_id, provider_run_payload_redacted_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    provider_run.run_id,
                    provider_run.session_id,
                    provider_run.plan_id,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    created_at,
                ),
            )
        self.record_event(
            provider_run.session_id,
            "provider_run_saved",
            {
                "run_id": provider_run.run_id,
                "plan_id": provider_run.plan_id,
                "status": provider_run.status,
                "provider_request_id": provider_run.provider_request_id,
                "error_code": provider_run.error_code,
            },
        )

    def record_event(self, session_id: str, event_type: str, payload: dict[str, Any]) -> None:
        self._require_session(session_id)
        event_id = f"event_{uuid.uuid4().hex}"
        created_at = utc_now().isoformat()
        safe_payload = redact_for_trace(payload)
        event = {
            "event_id": event_id,
            "session_id": session_id,
            "event_type": event_type,
            "payload": safe_payload,
            "created_at": created_at,
        }
        serialized_payload = json.dumps(
            safe_payload, ensure_ascii=False, sort_keys=True, default=str
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO trace_events (event_id, session_id, event_type, payload_redacted_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event_id, session_id, event_type, serialized_payload, created_at),
            )
        with self.trace_path.open("a", encoding="utf-8") as trace_file:
            trace_file.write(
                json.dumps(event, ensure_ascii=False, sort_keys=True, default=str) + "\n"
            )

    def recent_events(self, session_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        self._require_session(session_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT event_id, event_type, payload_redacted_json, created_at
                FROM trace_events
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [
            {
                "event_id": row["event_id"],
                "event_type": row["event_type"],
                "payload": json.loads(row["payload_redacted_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def _require_session(self, session_id: str) -> None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT session_id FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"Unknown local session: {session_id}")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection
