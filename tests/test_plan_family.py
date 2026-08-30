"""Checkpoint 8C-2 tests: next-round lineage, hard stops, and feedback facts."""

from __future__ import annotations

import base64
import hashlib
from datetime import timedelta
from pathlib import Path

from portrait_consistency_agent.core.contracts import (
    ComparisonTrend,
    EditableFeature,
    FeedbackSignal,
    MeasurementStatus,
    MeasurementUnit,
    NormalizedFeature,
    VerificationDecision,
)
from portrait_consistency_agent.services import plan_family, verification
from portrait_consistency_agent.services.execution import (
    execute_confirmed_plan,
    execute_followup_plan,
)
from portrait_consistency_agent.services.plan_family import (
    capture_explicit_feedback,
    propose_followup_plan,
)
from portrait_consistency_agent.services.tencent_beautify import TencentBeautifyResponse
from portrait_consistency_agent.services.verification import ResultObservation, verify_result
from portrait_consistency_agent.storage.local_store import LocalTraceStore
from tests.test_execution import TINY_PNG, FakeBeautifyClient, _bundle


def _observation(*, result_bytes: bytes | None = None) -> ResultObservation:
    return ResultObservation(
        photo_id="photo_target",
        photo_sha256=(
            hashlib.sha256(result_bytes).hexdigest() if result_bytes is not None else "d" * 64
        ),
        decode_ok=True,
        face_count=1,
        normalized_features=(
            NormalizedFeature(
                feature_code="face_width_height_ratio",
                # Parent profile is 0.80645 and the initial gap is 8%.
                # This leaves a measurable 5% gap after an improvement.
                value=0.7661290322580645,
                unit=MeasurementUnit.NORMALIZED_RATIO,
                status=MeasurementStatus.MEASURED,
                confidence=0.92,
            ),
            NormalizedFeature(
                feature_code="eye_area_mean_face_ratio",
                # Parent profile is 0.0084; the original target was 8.33%
                # smaller. This fixture leaves a 5% gap after improvement.
                value=0.00798,
                unit=MeasurementUnit.NORMALIZED_RATIO,
                status=MeasurementStatus.MEASURED,
                confidence=0.92,
            ),
        ),
        analysis_version="fixture-observer-v0",
    )


def _store(tmp_path: Path) -> tuple[LocalTraceStore, str]:
    store = LocalTraceStore(tmp_path / "demo.sqlite3", tmp_path / "events.jsonl")
    store.initialize()
    session = store.create_session()
    return store, session.session_id


def _first_round_and_replan(monkeypatch, tmp_path: Path):
    store, session_id = _store(tmp_path)
    bundle = _bundle(session_id=session_id)
    client = FakeBeautifyClient(
        response=TencentBeautifyResponse(
            request_id="request-parent-001",
            result_image_base64=base64.b64encode(TINY_PNG).decode("ascii"),
            result_url=None,
        )
    )
    parent_result = execute_confirmed_plan(
        confirmed_plan=bundle["confirmation"].confirmed_plan,
        execution_intent=bundle["confirmation"].execution_intent,
        target_image_bytes=bundle["target_bytes"],
        target_photo_id=bundle["target"].photo_id,
        profile=bundle["profile"],
        quality_result=bundle["quality"],
        client=client,
        store=store,
        now=bundle["now"],
    )
    assert parent_result.provider_run is not None
    assert parent_result.result_image_bytes is not None
    monkeypatch.setattr(
        verification,
        "observe_result_bytes",
        lambda result_image_bytes, photo_id: _observation(),
    )
    verified = verify_result(
        profile=bundle["profile"],
        plan=bundle["confirmation"].confirmed_plan,
        provider_run=parent_result.provider_run,
        result_image_bytes=parent_result.result_image_bytes,
        plan_family_id=f"family_{bundle['confirmation'].confirmed_plan.plan_id}",
        store=store,
        verification_id="verification_parent_improved",
    )
    assert verified.verification.decision == VerificationDecision.REPLAN
    assert verified.verification.overall_trend == ComparisonTrend.IMPROVED
    return store, session_id, bundle, parent_result, verified


def test_followup_plan_is_new_lineage_and_uses_small_new_input_strength(
    monkeypatch, tmp_path: Path
) -> None:
    store, _, bundle, parent_result, verified = _first_round_and_replan(monkeypatch, tmp_path)
    monkeypatch.setattr(
        plan_family,
        "observe_result_bytes",
        lambda result_image_bytes, photo_id: _observation(result_bytes=result_image_bytes),
    )
    followup = propose_followup_plan(
        previous_plan=bundle["confirmation"].confirmed_plan,
        previous_provider_run=parent_result.provider_run,
        previous_verification=verified.verification,
        execution_intent=bundle["confirmation"].execution_intent,
        profile=bundle["profile"],
        result_image_bytes=parent_result.result_image_bytes,
        store=store,
        now=bundle["now"] + timedelta(seconds=2),
        plan_id="plan_child_001",
    )

    assert followup.route == "followup_plan_ready"
    assert followup.plan is not None
    assert followup.plan.parent_plan_id == bundle["confirmation"].confirmed_plan.plan_id
    assert followup.plan.iteration == 2
    assert followup.plan.status.value == "confirmed"
    assert followup.plan.photo_sha256 == parent_result.provider_run.result_artifact_sha256
    assert followup.plan.provider_absolute_params.face_lifting == 2
    assert followup.plan.executable_changes[0].current_absolute == 0
    assert followup.plan.executable_changes[0].proposed_absolute == 2
    assert any(item["step"] == "derive_followup_parameters" for item in followup.trace)
    persist_trace = next(item for item in followup.trace if item["step"] == "persist_followup_plan")
    assert persist_trace["execution_mode"] == "auto_bounded_followup"
    assert persist_trace["user_round_confirmation_required"] is False
    assert persist_trace["inherited_confirmation_scope"] is True


def test_followup_execution_links_parent_run_and_never_reuses_original_upload(
    monkeypatch, tmp_path: Path
) -> None:
    store, _, bundle, parent_result, verified = _first_round_and_replan(monkeypatch, tmp_path)
    monkeypatch.setattr(
        plan_family,
        "observe_result_bytes",
        lambda result_image_bytes, photo_id: _observation(result_bytes=result_image_bytes),
    )
    followup = propose_followup_plan(
        previous_plan=bundle["confirmation"].confirmed_plan,
        previous_provider_run=parent_result.provider_run,
        previous_verification=verified.verification,
        execution_intent=bundle["confirmation"].execution_intent,
        profile=bundle["profile"],
        result_image_bytes=parent_result.result_image_bytes,
        store=store,
        now=bundle["now"] + timedelta(seconds=2),
        plan_id="plan_child_002",
    )
    assert followup.plan is not None
    client = FakeBeautifyClient(
        response=TencentBeautifyResponse(
            request_id="request-child-001",
            result_image_base64=base64.b64encode(TINY_PNG).decode("ascii"),
            result_url=None,
        )
    )

    child_result = execute_followup_plan(
        confirmed_plan=followup.plan,
        execution_intent=bundle["confirmation"].execution_intent,
        result_image_bytes=parent_result.result_image_bytes,
        target_photo_id=bundle["target"].photo_id,
        profile=bundle["profile"],
        original_quality_result=bundle["quality"],
        previous_provider_run=parent_result.provider_run,
        previous_verification=verified.verification,
        client=client,
        store=store,
        now=bundle["now"] + timedelta(seconds=3),
    )

    assert child_result.route == "succeeded"
    assert child_result.provider_run is not None
    assert child_result.provider_run.parent_run_id == parent_result.provider_run.run_id
    assert (
        child_result.provider_run.input_artifact_ref
        == parent_result.provider_run.result_artifact_ref
    )
    assert (
        child_result.provider_run.input_artifact_sha256
        == parent_result.provider_run.result_artifact_sha256
    )
    assert len(client.calls) == 1
    authorization_trace = next(
        item for item in child_result.trace if item["step"] == "authorization_check"
    )
    assert authorization_trace["execution_trigger"] == "auto_bounded_followup"
    assert authorization_trace["user_round_confirmation_required"] is False
    execution_trace = next(
        item for item in child_result.trace if item["step"] == "execute_beautify"
    )
    assert execution_trace["execution_trigger"] == "auto_bounded_followup"


def test_followup_scope_change_fails_closed_before_provider_call(
    monkeypatch, tmp_path: Path
) -> None:
    store, _, bundle, parent_result, verified = _first_round_and_replan(monkeypatch, tmp_path)
    monkeypatch.setattr(
        plan_family,
        "observe_result_bytes",
        lambda result_image_bytes, photo_id: _observation(result_bytes=result_image_bytes),
    )
    followup = propose_followup_plan(
        previous_plan=bundle["confirmation"].confirmed_plan,
        previous_provider_run=parent_result.provider_run,
        previous_verification=verified.verification,
        execution_intent=bundle["confirmation"].execution_intent,
        profile=bundle["profile"],
        result_image_bytes=parent_result.result_image_bytes,
        store=store,
        now=bundle["now"] + timedelta(seconds=2),
        plan_id="plan_child_scope_change",
    )
    assert followup.plan is not None
    scope = bundle["confirmation"].execution_intent.confirmation_scope
    assert scope is not None
    changed_scope = scope.model_copy(
        update={
            "allowed_features": [
                EditableFeature.FACE_LIFTING,
                EditableFeature.EYE_ENLARGING,
                EditableFeature.LIPS_THICKNESS,
            ]
        }
    )
    changed_intent = bundle["confirmation"].execution_intent.model_copy(
        update={"confirmation_scope": changed_scope}
    )
    client = FakeBeautifyClient(
        response=TencentBeautifyResponse(
            request_id="request-child-scope-change-should-not-run",
            result_image_base64=base64.b64encode(TINY_PNG).decode("ascii"),
            result_url=None,
        )
    )

    blocked = execute_followup_plan(
        confirmed_plan=followup.plan,
        execution_intent=changed_intent,
        result_image_bytes=parent_result.result_image_bytes,
        target_photo_id=bundle["target"].photo_id,
        profile=bundle["profile"],
        original_quality_result=bundle["quality"],
        previous_provider_run=parent_result.provider_run,
        previous_verification=verified.verification,
        client=client,
        store=store,
        now=bundle["now"] + timedelta(seconds=3),
    )

    assert blocked.route == "blocked"
    assert client.calls == []
    blocked_trace = blocked.trace[0]
    assert "confirmation_scope_mismatch" in blocked_trace["reason_codes"]


def test_explicit_dislike_blocks_followup_before_any_external_call(
    monkeypatch, tmp_path: Path
) -> None:
    _, _, bundle, parent_result, verified = _first_round_and_replan(monkeypatch, tmp_path)
    dislike = capture_explicit_feedback(
        session_id=bundle["confirmation"].confirmed_plan.session_id,
        anonymous_user_id="user_unused",
        verification=verified.verification,
        signal=FeedbackSignal.DISLIKE,
    )
    monkeypatch.setattr(
        plan_family,
        "observe_result_bytes",
        lambda result_image_bytes, photo_id: _observation(result_bytes=result_image_bytes),
    )
    blocked = propose_followup_plan(
        previous_plan=bundle["confirmation"].confirmed_plan,
        previous_provider_run=parent_result.provider_run,
        previous_verification=verified.verification.model_copy(
            update={"user_feedback": dislike.feedback}
        ),
        execution_intent=bundle["confirmation"].execution_intent,
        profile=bundle["profile"],
        result_image_bytes=parent_result.result_image_bytes,
    )

    assert blocked.plan is None
    assert blocked.route == "blocked"
    assert "explicit_user_dissatisfaction" in blocked.reason_codes


def test_followup_stops_at_the_confirmed_family_round_limit(monkeypatch, tmp_path: Path) -> None:
    _, _, bundle, parent_result, verified = _first_round_and_replan(monkeypatch, tmp_path)
    monkeypatch.setattr(
        plan_family,
        "observe_result_bytes",
        lambda result_image_bytes, photo_id: _observation(result_bytes=result_image_bytes),
    )
    last_allowed_parent = bundle["confirmation"].confirmed_plan.model_copy(update={"iteration": 3})
    last_allowed_verification = verified.verification.model_copy(update={"round_number": 3})
    blocked = propose_followup_plan(
        previous_plan=last_allowed_parent,
        previous_provider_run=parent_result.provider_run,
        previous_verification=last_allowed_verification,
        execution_intent=bundle["confirmation"].execution_intent,
        profile=bundle["profile"],
        result_image_bytes=parent_result.result_image_bytes,
    )

    assert blocked.plan is None
    assert blocked.route == "blocked"
    assert "confirmation_round_limit_exceeded" in blocked.reason_codes
    assert "safety_round_limit_exceeded" in blocked.reason_codes


def test_text_feedback_is_hashed_and_does_not_persist_raw_comment(tmp_path: Path) -> None:
    store, session_id = _store(tmp_path)
    # A minimal real VerificationResult is unnecessary for the feedback fact;
    # use the fixture from the existing contract builder to keep this test
    # focused on redaction behavior.
    from tests.test_contracts import make_verification

    verification_result = make_verification(session_id=session_id)
    result = capture_explicit_feedback(
        session_id=session_id,
        anonymous_user_id=store._session_user_id(session_id),
        verification=verification_result,
        signal=FeedbackSignal.TEXT_COMMENT,
        comment_text="眼睛还是有点不自然",
        store=store,
    )

    assert result.feedback.status.value == "unknown"
    assert result.feedback.signal == FeedbackSignal.TEXT_COMMENT
    trace_text = store.trace_path.read_text(encoding="utf-8")
    assert "眼睛还是有点不自然" not in trace_text
    assert "comment_sha256" in trace_text
