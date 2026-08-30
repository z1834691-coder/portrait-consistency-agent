"""Local SQLite + JSONL audit storage for the non-production demo runtime."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from portrait_consistency_agent.core.contracts import (
    EditPlan,
    FeedbackEvidenceStrength,
    IntentFrame,
    InteractionOutcome,
    InteractionStage,
    PhotoQualityResult,
    ProductEvent,
    ProductEventType,
    ProfileStatus,
    ProviderRun,
    ReferenceProfile,
    VerificationResult,
)

SENSITIVE_KEY_FRAGMENTS = (
    "secret",
    "password",
    "authorization",
    "confirmation_token",
    "confirmation_ref",
    "subject_anchor",
    "anchor_ref",
    "consent_record_ref",
    "input_artifact_ref",
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
    anonymous_user_id: str
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
                    anonymous_user_id TEXT,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS schema_migrations (
                    migration_id TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS reference_profiles (
                    profile_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    active INTEGER NOT NULL,
                    profile_payload_redacted_json TEXT NOT NULL,
                    feature_body_deleted_at TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (profile_id, version)
                );

                CREATE UNIQUE INDEX IF NOT EXISTS one_active_profile_per_user
                ON reference_profiles(user_id)
                WHERE active = 1;

                CREATE TABLE IF NOT EXISTS profile_audit_events (
                    event_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    profile_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_redacted_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS photo_quality_results (
                    quality_result_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    photo_id TEXT NOT NULL,
                    quality_payload_redacted_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
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
                    idempotency_key TEXT,
                    provider_run_payload_redacted_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                );

                CREATE TABLE IF NOT EXISTS edit_plans (
                    plan_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    session_id TEXT NOT NULL,
                    photo_id TEXT NOT NULL,
                    plan_payload_redacted_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (plan_id, revision),
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                );

                CREATE TABLE IF NOT EXISTS verification_results (
                    verification_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    provider_run_id TEXT NOT NULL,
                    verification_payload_redacted_json TEXT NOT NULL,
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

                CREATE TABLE IF NOT EXISTS product_events (
                    event_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    anonymous_user_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    evidence_strength TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    related_contract_ref TEXT,
                    reason_codes_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                );

                CREATE INDEX IF NOT EXISTS product_events_by_user_time
                ON product_events(anonymous_user_id, created_at);
                """
            )
            self._ensure_column(connection, "sessions", "anonymous_user_id", "TEXT")
            self._ensure_column(connection, "provider_runs", "idempotency_key", "TEXT")
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS provider_runs_idempotency_key_unique
                ON provider_runs(idempotency_key)
                WHERE idempotency_key IS NOT NULL
                """
            )
            connection.execute(
                """
                UPDATE sessions
                SET anonymous_user_id = 'legacy_' || substr(session_id, 1, 32)
                WHERE anonymous_user_id IS NULL OR anonymous_user_id = ''
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations (migration_id, applied_at) VALUES (?, ?)",
                ("contract_v0_2_tables", utc_now().isoformat()),
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations (migration_id, applied_at) VALUES (?, ?)",
                ("contract_v0_3_analytics_lifecycle", utc_now().isoformat()),
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations (migration_id, applied_at) VALUES (?, ?)",
                ("checkpoint_8b_execution_idempotency", utc_now().isoformat()),
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations (migration_id, applied_at) VALUES (?, ?)",
                ("contract_v0_4_verification_observation", utc_now().isoformat()),
            )

    def create_session(
        self,
        *,
        state: str = "FOUNDATION",
        anonymous_user_id: str | None = None,
    ) -> SessionRecord:
        session_id = f"session_{uuid.uuid4().hex}"
        user_id = anonymous_user_id or f"user_{uuid.uuid4().hex}"
        created_at = utc_now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (session_id, anonymous_user_id, state, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, user_id, state, created_at, created_at),
            )
        self.record_event(session_id, "session_created", {"state": state})
        self.record_product_event(
            ProductEvent(
                event_id=f"product_event_{uuid.uuid4().hex}",
                session_id=session_id,
                anonymous_user_id=user_id,
                event_type=ProductEventType.SESSION_STARTED,
                stage=InteractionStage.ONBOARDING,
                evidence_strength=FeedbackEvidenceStrength.UNKNOWN,
            )
        )
        return SessionRecord(
            session_id=session_id,
            anonymous_user_id=user_id,
            state=state,
            created_at=created_at,
        )

    def save_intent_frame(self, intent_frame: IntentFrame) -> None:
        self._require_session(intent_frame.session_id)
        payload = redact_for_trace(intent_frame)
        created_at = utc_now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO intent_frames (
                    session_id, turn, intent_payload_redacted_json, created_at
                )
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
                "intent_id": intent_frame.intent_id,
                "intent_confidence": intent_frame.intent_confidence,
                "model_provider": intent_frame.model_provider,
                "prompt_version": intent_frame.prompt_version,
                "missing_slots": intent_frame.missing_slots,
            },
        )
        self._record_product_event_for_session(
            session_id=intent_frame.session_id,
            event_type=ProductEventType.INTENT_SUBMITTED,
            stage=InteractionStage.DIAGNOSIS,
            evidence_strength=FeedbackEvidenceStrength.STRONG_INTENT,
            related_contract_ref=intent_frame.intent_id,
        )

    def save_reference_profile(self, profile: ReferenceProfile) -> None:
        """Atomically activate a profile and tombstone the prior feature body.

        If inserting the new profile fails, SQLite rolls the transaction back and
        leaves the previous active profile unchanged.
        """

        payload = redact_for_trace(profile)
        created_at = utc_now().isoformat()
        is_active = profile.status in {ProfileStatus.ACTIVE, ProfileStatus.GEOMETRY_ONLY}
        superseded_profiles: list[tuple[str, int]] = []
        with self._connect() as connection:
            if is_active:
                rows = connection.execute(
                    "SELECT profile_id, version FROM reference_profiles "
                    "WHERE user_id = ? AND active = 1",
                    (profile.user_id,),
                ).fetchall()
                superseded_profiles = [
                    (str(row["profile_id"]), int(row["version"])) for row in rows
                ]
                tombstone_time = utc_now().isoformat()
                for old_profile_id, old_version in superseded_profiles:
                    tombstone = {
                        "contract_version": profile.contract_version,
                        "profile_id": old_profile_id,
                        "version": old_version,
                        "status": ProfileStatus.SUPERSEDED.value,
                        "feature_body_deleted": True,
                    }
                    connection.execute(
                        """
                        UPDATE reference_profiles
                        SET status = ?, active = 0, profile_payload_redacted_json = ?,
                            feature_body_deleted_at = ?
                        WHERE profile_id = ? AND version = ?
                        """,
                        (
                            ProfileStatus.SUPERSEDED.value,
                            json.dumps(tombstone, ensure_ascii=False, sort_keys=True),
                            tombstone_time,
                            old_profile_id,
                            old_version,
                        ),
                    )
            connection.execute(
                """
                INSERT INTO reference_profiles (
                    profile_id, version, user_id, status, active,
                    profile_payload_redacted_json, feature_body_deleted_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?)
                """,
                (
                    profile.profile_id,
                    profile.version,
                    profile.user_id,
                    profile.status.value,
                    int(is_active),
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    created_at,
                ),
            )
        for old_profile_id, old_version in superseded_profiles:
            self._record_profile_event(
                profile.user_id,
                old_profile_id,
                "profile_feature_body_deleted",
                {
                    "version": old_version,
                    "replacement_profile_id": profile.profile_id,
                    "replacement_version": profile.version,
                },
            )
        self._record_profile_event(
            profile.user_id,
            profile.profile_id,
            "profile_saved",
            {"version": profile.version, "status": profile.status},
        )

    def save_photo_quality_result(self, result: PhotoQualityResult) -> None:
        self._require_session(result.session_id)
        self._insert_session_contract(
            table="photo_quality_results",
            columns=("quality_result_id", "session_id", "photo_id"),
            values=(result.quality_result_id, result.session_id, result.photo_id),
            payload_column="quality_payload_redacted_json",
            payload=result,
        )
        self.record_event(
            result.session_id,
            "photo_quality_result_saved",
            {
                "quality_result_id": result.quality_result_id,
                "photo_id": result.photo_id,
                "route": result.route,
                "subject_match_status": result.subject_match_status,
                "provider_card_version": result.provider_card_version,
            },
        )

    def save_edit_plan(self, plan: EditPlan) -> None:
        self._require_session(plan.session_id)
        self._insert_session_contract(
            table="edit_plans",
            columns=("plan_id", "revision", "session_id", "photo_id"),
            values=(plan.plan_id, plan.revision, plan.session_id, plan.photo_id),
            payload_column="plan_payload_redacted_json",
            payload=plan,
        )
        self.record_event(
            plan.session_id,
            "edit_plan_saved",
            {
                "plan_id": plan.plan_id,
                "revision": plan.revision,
                "photo_id": plan.photo_id,
                "status": plan.status,
                "provider_card_id": plan.provider_card_id,
                "provider_card_version": plan.provider_card_version,
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
                INSERT INTO provider_runs (
                    run_id, session_id, plan_id, idempotency_key,
                    provider_run_payload_redacted_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    provider_run.run_id,
                    provider_run.session_id,
                    provider_run.plan_id,
                    provider_run.idempotency_key,
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
                "error_code": (
                    provider_run.error.provider_code if provider_run.error is not None else None
                ),
            },
        )
        if provider_run.status.value == "succeeded":
            self._record_product_event_for_session(
                session_id=provider_run.session_id,
                event_type=ProductEventType.PROVIDER_SUCCEEDED,
                stage=InteractionStage.EXECUTION,
                evidence_strength=FeedbackEvidenceStrength.UNKNOWN,
                related_contract_ref=provider_run.run_id,
                outcome=InteractionOutcome.COMPLETED,
            )

    def has_provider_run_idempotency_key(self, idempotency_key: str) -> bool:
        """Return whether this local process has already persisted one attempt.

        The key prevents a repeated button click from creating a second paid
        request after a factual receipt has been saved.  It is deliberately not
        advertised as crash-safe distributed idempotency: Tencent's public
        BeautifyPic API does not expose a server-side idempotency token here.
        """

        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM provider_runs WHERE idempotency_key = ? LIMIT 1",
                (idempotency_key,),
            ).fetchone()
        return row is not None

    def save_verification_result(self, result: VerificationResult) -> None:
        self._require_session(result.session_id)
        self._insert_session_contract(
            table="verification_results",
            columns=("verification_id", "session_id", "plan_id", "provider_run_id"),
            values=(
                result.verification_id,
                result.session_id,
                result.plan_id,
                result.provider_run_id,
            ),
            payload_column="verification_payload_redacted_json",
            payload=result,
        )
        self.record_event(
            result.session_id,
            "verification_result_saved",
            {
                "verification_id": result.verification_id,
                "plan_id": result.plan_id,
                "provider_run_id": result.provider_run_id,
                "overall_trend": result.overall_trend,
                "decision": result.decision,
            },
        )
        self._record_product_event_for_session(
            session_id=result.session_id,
            event_type=ProductEventType.VERIFICATION_COMPLETED,
            stage=InteractionStage.VERIFICATION,
            evidence_strength=FeedbackEvidenceStrength.UNKNOWN,
            related_contract_ref=result.verification_id,
            outcome=InteractionOutcome.COMPLETED,
        )

    def record_product_event(self, event: ProductEvent) -> None:
        """Persist one redacted operational event for metrics, never raw user data."""

        self._require_session(event.session_id)
        session_user_id = self._session_user_id(event.session_id)
        if session_user_id != event.anonymous_user_id:
            raise ValueError("product event user must match the session's anonymous user")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO product_events (
                    event_id, session_id, anonymous_user_id, event_type, stage,
                    evidence_strength, outcome, related_contract_ref, reason_codes_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.session_id,
                    event.anonymous_user_id,
                    event.event_type.value,
                    event.stage.value,
                    event.evidence_strength.value,
                    event.outcome.value,
                    event.related_contract_ref,
                    json.dumps(event.reason_codes, ensure_ascii=False),
                    event.occurred_at.isoformat(),
                ),
            )
        self.record_event(
            event.session_id,
            "product_event_recorded",
            {
                "product_event_id": event.event_id,
                "event_type": event.event_type,
                "stage": event.stage,
                "evidence_strength": event.evidence_strength,
                "outcome": event.outcome,
                "related_contract_ref": event.related_contract_ref,
                "reason_codes": event.reason_codes,
            },
        )

    def dashboard_snapshot(self, *, now: datetime | None = None) -> dict[str, int]:
        """Return only aggregate metrics for the local administrator dashboard.

        The current store is an operational ledger. These counts are not an
        outcome study, an experiment, or evidence of product-market fit.
        """

        current_time = now or utc_now()
        seven_days_ago = current_time - timedelta(days=7)
        thirty_days_ago = current_time - timedelta(days=30)
        with self._connect() as connection:

            def count_events(event_type: ProductEventType) -> int:
                row = connection.execute(
                    "SELECT COUNT(*) AS count FROM product_events WHERE event_type = ?",
                    (event_type.value,),
                ).fetchone()
                return int(row["count"])

            def active_users_since(cutoff: datetime) -> int:
                row = connection.execute(
                    """
                    SELECT COUNT(DISTINCT anonymous_user_id) AS count
                    FROM product_events
                    WHERE created_at >= ?
                    """,
                    (cutoff.isoformat(),),
                ).fetchone()
                return int(row["count"])

            total_sessions = connection.execute("SELECT COUNT(*) AS count FROM sessions").fetchone()
            explicit_feedback = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM product_events
                WHERE event_type IN (?, ?)
                """,
                (ProductEventType.FEEDBACK_LIKED.value, ProductEventType.FEEDBACK_DISLIKED.value),
            ).fetchone()
            return {
                "total_sessions": int(total_sessions["count"]),
                "profile_created": count_events(ProductEventType.PROFILE_CREATED),
                "intent_submitted": count_events(ProductEventType.INTENT_SUBMITTED),
                "provider_succeeded": count_events(ProductEventType.PROVIDER_SUCCEEDED),
                "verification_completed": count_events(ProductEventType.VERIFICATION_COMPLETED),
                "explicit_feedback": int(explicit_feedback["count"]),
                "reupload_required": count_events(ProductEventType.REUPLOAD_REQUIRED),
                "wau": active_users_since(seven_days_ago),
                "mau": active_users_since(thirty_days_ago),
            }

    def recent_product_events(self, *, limit: int = 50) -> list[dict[str, Any]]:
        """Return redacted event metadata for the local administrator only."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT event_id, session_id, event_type, stage, evidence_strength,
                       outcome, related_contract_ref, reason_codes_json, created_at
                FROM product_events
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "event_id": row["event_id"],
                "session_id": row["session_id"],
                "event_type": row["event_type"],
                "stage": row["stage"],
                "evidence_strength": row["evidence_strength"],
                "outcome": row["outcome"],
                "related_contract_ref": row["related_contract_ref"],
                "reason_codes": json.loads(row["reason_codes_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

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
                INSERT INTO trace_events (
                    event_id, session_id, event_type, payload_redacted_json, created_at
                )
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

    def _record_product_event_for_session(
        self,
        *,
        session_id: str,
        event_type: ProductEventType,
        stage: InteractionStage,
        evidence_strength: FeedbackEvidenceStrength,
        related_contract_ref: str | None = None,
        outcome: InteractionOutcome = InteractionOutcome.UNKNOWN,
        reason_codes: list[str] | None = None,
    ) -> None:
        self.record_product_event(
            ProductEvent(
                event_id=f"product_event_{uuid.uuid4().hex}",
                session_id=session_id,
                anonymous_user_id=self._session_user_id(session_id),
                event_type=event_type,
                stage=stage,
                evidence_strength=evidence_strength,
                outcome=outcome,
                related_contract_ref=related_contract_ref,
                reason_codes=reason_codes or [],
            )
        )

    def _session_user_id(self, session_id: str) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT anonymous_user_id FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None or row["anonymous_user_id"] is None:
            raise ValueError(f"Unknown local session: {session_id}")
        return str(row["anonymous_user_id"])

    def _require_session(self, session_id: str) -> None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT session_id FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"Unknown local session: {session_id}")

    @staticmethod
    def _ensure_column(
        connection: sqlite3.Connection,
        table: str,
        column: str,
        definition: str,
    ) -> None:
        """Apply the only additive local migration needed by the prototype."""

        existing_columns = {
            str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in existing_columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _insert_session_contract(
        self,
        *,
        table: str,
        columns: tuple[str, ...],
        values: tuple[Any, ...],
        payload_column: str,
        payload: BaseModel,
    ) -> None:
        allowed_tables = {
            "photo_quality_results",
            "edit_plans",
            "verification_results",
        }
        if table not in allowed_tables:
            raise ValueError(f"Unsupported contract table: {table}")
        safe_payload = json.dumps(
            redact_for_trace(payload), ensure_ascii=False, sort_keys=True, default=str
        )
        column_sql = ", ".join((*columns, payload_column, "created_at"))
        placeholder_sql = ", ".join("?" for _ in range(len(values) + 2))
        with self._connect() as connection:
            connection.execute(
                f"INSERT INTO {table} ({column_sql}) VALUES ({placeholder_sql})",
                (*values, safe_payload, utc_now().isoformat()),
            )

    def _record_profile_event(
        self,
        user_id: str,
        profile_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        event_id = f"profile_event_{uuid.uuid4().hex}"
        created_at = utc_now().isoformat()
        safe_payload = json.dumps(
            redact_for_trace(payload), ensure_ascii=False, sort_keys=True, default=str
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO profile_audit_events (
                    event_id, user_id, profile_id, event_type,
                    payload_redacted_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (event_id, user_id, profile_id, event_type, safe_payload, created_at),
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
