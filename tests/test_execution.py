"""Checkpoint 8B tests: explicit confirmation, one call, and factual receipts."""

from __future__ import annotations

import base64
import hashlib
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from portrait_consistency_agent.core.contracts import (
    IntentAction,
    ParserMode,
    PhotoRole,
    PlanStatus,
    ProviderRunStatus,
    SubjectMatchStatus,
)
from portrait_consistency_agent.core.policies import (
    build_v0_execution_policy,
    build_v0_safety_policy,
)
from portrait_consistency_agent.core.settings import AppSettings
from portrait_consistency_agent.services.edit_planner import diagnose_and_plan
from portrait_consistency_agent.services.execution import (
    accept_effect_web_browser_result,
    cancel_execution_plan,
    confirm_execution,
    execute_confirmed_plan,
)
from portrait_consistency_agent.services.tencent_beautify import (
    TencentBeautifyApiError,
    TencentBeautifyResponse,
)
from portrait_consistency_agent.services.tencent_effect_web import (
    EffectWebBrowserReceipt,
    TencentEffectWebAdapter,
)
from portrait_consistency_agent.services.verification import verify_result
from portrait_consistency_agent.storage.local_store import LocalTraceStore
from tests.test_edit_planner import (
    make_intent,
    make_observation,
    make_profile,
    make_target_quality,
)

TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/"
    "aK8VYQAAAABJRU5ErkJggg=="
)


class FakeBeautifyClient:
    """A local provider double; tests never call Tencent."""

    def __init__(self, *, response: TencentBeautifyResponse | Exception) -> None:
        self.response = response
        self.calls: list[tuple[str, object]] = []
        self.settings = SimpleNamespace(
            tencent_region="ap-guangzhou",
            tencent_beautify_endpoint="fmu.tencentcloudapi.com",
        )

    def beautify_base64(self, image_base64: str, params: object) -> TencentBeautifyResponse:
        self.calls.append((image_base64, params))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _bundle(*, session_id: str = "session_001", uncertain_subject: bool = False):
    target_bytes = b"authorized-target-image-bytes"
    target = replace(
        make_observation(
            "photo_target",
            PhotoRole.TARGET,
            face_width=540,
            eye_boxes=((0.28, 0.36, 0.11, 0.07), (0.60, 0.37, 0.11, 0.07)),
        ),
        photo_sha256=hashlib.sha256(target_bytes).hexdigest(),
    )
    quality_kwargs: dict[str, object] = {}
    if uncertain_subject:
        base_quality = make_target_quality(target)
        assert base_quality.subject_match_evidence is not None
        quality_kwargs = {
            "subject_match_status": SubjectMatchStatus.UNCERTAIN,
            "subject_match_evidence": base_quality.subject_match_evidence.model_copy(
                update={"raw_score": 56.23}
            ),
        }
    quality = make_target_quality(target, **quality_kwargs).model_copy(
        update={"session_id": session_id}
    )
    intent = make_intent(
        session_id=session_id,
        target_refs=[target.photo_id],
    )
    plan_result = diagnose_and_plan(
        profile=make_profile(),
        target_observation=target,
        quality_result=quality,
        intent=intent,
        subject_match_uncertain_acknowledged=uncertain_subject,
        plan_id="plan_execution_001",
    )
    assert plan_result.plan is not None
    # The planner timestamps a plan at real runtime.  Anchor test time just
    # after it so confirmation expiry remains semantically valid.
    now = plan_result.plan.created_at + timedelta(seconds=1)
    confirmation = confirm_execution(
        source_intent=intent,
        proposed_plan=plan_result.plan,
        next_turn=2,
        subject_match_uncertain_acknowledged=uncertain_subject,
        now=now,
    )
    return {
        "target_bytes": target_bytes,
        "target": target,
        "quality": quality,
        "profile": make_profile(),
        "intent": intent,
        "plan": plan_result.plan,
        "confirmation": confirmation,
        "now": now,
    }


def _store(tmp_path: Path) -> tuple[LocalTraceStore, str]:
    store = LocalTraceStore(tmp_path / "demo.sqlite3", tmp_path / "events.jsonl")
    store.initialize()
    session = store.create_session()
    return store, session.session_id


def test_confirmation_creates_a_new_user_structured_intent_and_immutable_plan_revision() -> None:
    bundle = _bundle()
    confirmation = bundle["confirmation"]

    assert confirmation.execution_intent.action == IntentAction.EXECUTE
    assert confirmation.execution_intent.parser_mode == ParserMode.USER_STRUCTURED_INPUT
    assert confirmation.execution_intent.supersedes_intent_id == bundle["intent"].intent_id
    assert confirmation.confirmed_plan.status == PlanStatus.CONFIRMED
    assert confirmation.confirmed_plan.revision == bundle["plan"].revision + 1
    assert confirmation.confirmed_plan.intent_id == confirmation.execution_intent.intent_id
    assert (
        confirmation.confirmed_plan.confirmation_scope_hash == confirmation.confirmation_scope_hash
    )
    assert "腾讯云 BeautifyPic" in confirmation.user_confirmation_copy
    assert "上一轮腾讯返回的结果图可能作为下一轮输入" in confirmation.user_confirmation_copy
    assert build_v0_execution_policy().confirmation_ttl_minutes == 10
    assert build_v0_safety_policy().max_attempts_per_plan == 1


def test_successful_execution_saves_only_redacted_receipt_and_keeps_result_bytes_in_memory(
    tmp_path: Path,
) -> None:
    store, session_id = _store(tmp_path)
    bundle = _bundle(session_id=session_id)
    client = FakeBeautifyClient(
        response=TencentBeautifyResponse(
            request_id="request-success-001",
            result_image_base64=base64.b64encode(TINY_PNG).decode("ascii"),
            result_url=None,
        )
    )

    result = execute_confirmed_plan(
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

    assert result.route == "succeeded"
    assert result.provider_run is not None
    assert result.provider_run.status == ProviderRunStatus.SUCCEEDED
    assert result.provider_run.provider_request_id == "request-success-001"
    assert result.provider_run.result_artifact_ref.startswith("session_memory_")
    assert result.result_image_bytes == TINY_PNG
    assert result.final_plan.status == PlanStatus.EXECUTED
    assert len(client.calls) == 1
    authorization_trace = next(
        item for item in result.trace if item["step"] == "authorization_check"
    )
    assert authorization_trace["execution_trigger"] == "initial_user_confirmation"
    assert authorization_trace["user_round_confirmation_required"] is True
    trace_text = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert base64.b64encode(TINY_PNG).decode("ascii") not in trace_text
    assert "authorized-target-image-bytes" not in trace_text
    assert store.has_provider_run_idempotency_key(result.provider_run.idempotency_key)

    repeated = execute_confirmed_plan(
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
    assert repeated.route == "blocked"
    assert repeated.provider_run is None
    assert len(client.calls) == 1


def _web_bundle(*, session_id: str = "session_web_001"):
    target_bytes = b"authorized-web-target-image-bytes"
    target = replace(
        make_observation(
            "photo_web_target",
            PhotoRole.TARGET,
            face_width=540,
            eye_boxes=((0.28, 0.36, 0.11, 0.07), (0.60, 0.37, 0.11, 0.07)),
        ),
        photo_sha256=hashlib.sha256(target_bytes).hexdigest(),
    )
    quality = make_target_quality(target, session_id=session_id)
    intent = make_intent(
        session_id=session_id,
        target_refs=[target.photo_id],
    )
    profile = make_profile()
    planned = diagnose_and_plan(
        profile=profile,
        target_observation=target,
        quality_result=quality,
        intent=intent,
        provider_id="tencent_effect_web",
        plan_id="plan_web_execution_001",
    )
    assert planned.plan is not None
    now = planned.plan.created_at + timedelta(seconds=1)
    confirmation = confirm_execution(
        source_intent=intent,
        proposed_plan=planned.plan,
        next_turn=2,
        now=now,
    )
    adapter = TencentEffectWebAdapter(AppSettings(_env_file=None))
    web_params = confirmation.confirmed_plan.provider_absolute_params
    request = adapter.prepare_request(
        request_ref="effect_web_execution_request_001",
        input_artifact_ref="upload_photo_web_target",
        input_artifact_sha256=hashlib.sha256(target_bytes).hexdigest(),
        parameters={
            "face_lifting": web_params.lift * 100,
            "eye_enlarging": web_params.eye * 100,
        },
        input_source="data_url",
    )
    output_hash = hashlib.sha256(TINY_PNG).hexdigest()
    receipt = EffectWebBrowserReceipt(
        status="succeeded",
        receipt_id="web_execution_receipt_001",
        request_ref=request.request_ref,
        sdk_version="fixture-web-sdk",
        input_sha256=request.input_artifact_sha256,
        output_sha256=output_hash,
        input_width=640,
        input_height=480,
        output_width=1,
        output_height=1,
        elapsed_ms=23,
        created_at="2026-09-02T00:00:00+00:00",
    )
    result_payload = {
        "request_ref": request.request_ref,
        "input_sha256": request.input_artifact_sha256,
        "output_sha256": output_hash,
        "output_data_url": "data:image/png;base64," + base64.b64encode(TINY_PNG).decode(),
        "output_width": 1,
        "output_height": 1,
        "result_retention": "python_memory_only",
        "created_at": "2026-09-02T00:00:00+00:00",
    }
    return {
        "target_bytes": target_bytes,
        "target": target,
        "quality": quality,
        "profile": profile,
        "intent": intent,
        "confirmation": confirmation,
        "request": request,
        "receipt": receipt,
        "result_payload": result_payload,
        "now": now,
    }


def test_web_b_result_enters_common_provider_run_and_verification_in_memory(
    tmp_path: Path,
) -> None:
    store, session_id = _store(tmp_path)
    bundle = _web_bundle(session_id=session_id)
    confirmation = bundle["confirmation"]

    result = accept_effect_web_browser_result(
        confirmed_plan=confirmation.confirmed_plan,
        execution_intent=confirmation.execution_intent,
        target_image_bytes=bundle["target_bytes"],
        target_photo_id=bundle["target"].photo_id,
        profile=bundle["profile"],
        quality_result=bundle["quality"],
        prepared_request=bundle["request"].model_dump(mode="json"),
        browser_receipt=bundle["receipt"].model_dump(mode="json"),
        browser_result=bundle["result_payload"],
        store=store,
        now=bundle["now"],
        allow_candidate_trial=True,
    )

    assert result.route == "succeeded"
    assert result.provider_run is not None
    assert result.provider_run.provider == "tencent_effect_web"
    assert result.provider_run.plan_revision == confirmation.confirmed_plan.revision
    assert result.result_image_bytes == TINY_PNG
    verification = verify_result(
        profile=bundle["profile"],
        plan=confirmation.confirmed_plan,
        provider_run=result.provider_run,
        result_image_bytes=result.result_image_bytes,
    )
    assert verification.verification.decision.value == "reshoot"
    trace_text = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert "output_data_url" not in trace_text
    assert "python_memory_only" in trace_text


def test_web_candidate_trial_is_blocked_without_explicit_trial_flag() -> None:
    bundle = _web_bundle()
    confirmation = bundle["confirmation"]

    result = accept_effect_web_browser_result(
        confirmed_plan=confirmation.confirmed_plan,
        execution_intent=confirmation.execution_intent,
        target_image_bytes=bundle["target_bytes"],
        target_photo_id=bundle["target"].photo_id,
        profile=bundle["profile"],
        quality_result=bundle["quality"],
        prepared_request=bundle["request"].model_dump(mode="json"),
        browser_receipt=bundle["receipt"].model_dump(mode="json"),
        browser_result=bundle["result_payload"],
        allow_candidate_trial=False,
    )

    assert result.route == "blocked"
    assert result.provider_run is None
    assert result.trace[0]["reason_codes"] == ["web_card_not_promoted"]


def test_uncertain_subject_ack_is_carried_by_scope_and_allows_one_execution(
    tmp_path: Path,
) -> None:
    store, session_id = _store(tmp_path)
    bundle = _bundle(session_id=session_id, uncertain_subject=True)
    confirmation = bundle["confirmation"]
    assert confirmation.execution_intent.confirmation_scope is not None
    assert confirmation.execution_intent.confirmation_scope.subject_match_uncertain_acknowledged

    client = FakeBeautifyClient(
        response=TencentBeautifyResponse(
            request_id="request-uncertain-001",
            result_image_base64=base64.b64encode(TINY_PNG).decode("ascii"),
            result_url=None,
        )
    )
    result = execute_confirmed_plan(
        confirmed_plan=confirmation.confirmed_plan,
        execution_intent=confirmation.execution_intent,
        target_image_bytes=bundle["target_bytes"],
        target_photo_id=bundle["target"].photo_id,
        profile=bundle["profile"],
        quality_result=bundle["quality"],
        client=client,
        store=store,
        now=bundle["now"],
    )

    assert result.route == "succeeded"
    authorization_trace = next(
        item for item in result.trace if item["step"] == "authorization_check"
    )
    assert authorization_trace["subject_match_uncertain_acknowledged"] is True
    assert len(client.calls) == 1


def test_expired_confirmation_never_calls_provider(tmp_path: Path) -> None:
    store, session_id = _store(tmp_path)
    bundle = _bundle(session_id=session_id)
    client = FakeBeautifyClient(
        response=TencentBeautifyResponse(
            request_id="should-not-run",
            result_image_base64=base64.b64encode(TINY_PNG).decode("ascii"),
            result_url=None,
        )
    )
    expires_at = bundle["confirmation"].execution_intent.confirmation_scope.expires_at

    result = execute_confirmed_plan(
        confirmed_plan=bundle["confirmation"].confirmed_plan,
        execution_intent=bundle["confirmation"].execution_intent,
        target_image_bytes=bundle["target_bytes"],
        target_photo_id=bundle["target"].photo_id,
        profile=bundle["profile"],
        quality_result=bundle["quality"],
        client=client,
        store=store,
        now=expires_at,
    )

    assert result.route == "blocked"
    assert result.provider_run is None
    assert result.final_plan.status == PlanStatus.EXPIRED
    assert client.calls == []


def test_changed_input_hash_never_calls_provider() -> None:
    bundle = _bundle()
    client = FakeBeautifyClient(
        response=TencentBeautifyResponse(
            request_id="should-not-run",
            result_image_base64=base64.b64encode(TINY_PNG).decode("ascii"),
            result_url=None,
        )
    )

    result = execute_confirmed_plan(
        confirmed_plan=bundle["confirmation"].confirmed_plan,
        execution_intent=bundle["confirmation"].execution_intent,
        target_image_bytes=b"different-photo-bytes",
        target_photo_id=bundle["target"].photo_id,
        profile=bundle["profile"],
        quality_result=bundle["quality"],
        client=client,
        now=bundle["now"],
    )

    assert result.route == "blocked"
    assert result.provider_run is None
    assert result.final_plan.status == PlanStatus.SUPERSEDED
    assert client.calls == []


def test_timeout_creates_one_failed_receipt_without_automatic_retry(tmp_path: Path) -> None:
    store, session_id = _store(tmp_path)
    bundle = _bundle(session_id=session_id)
    client = FakeBeautifyClient(
        response=TencentBeautifyApiError(
            "FailedOperation.RequestTimeout",
            "provider timeout",
            request_id="request-timeout-001",
        )
    )

    result = execute_confirmed_plan(
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

    assert result.route == "failed"
    assert result.provider_run is not None
    assert result.provider_run.status == ProviderRunStatus.TIMEOUT
    assert result.provider_run.error is not None
    assert result.provider_run.error.retryable is False
    assert result.final_plan.status == PlanStatus.SUPERSEDED
    assert len(client.calls) == 1


def test_user_cancellation_creates_no_provider_receipt() -> None:
    bundle = _bundle()

    cancelled = cancel_execution_plan(bundle["plan"])

    assert cancelled.status == PlanStatus.CANCELLED
    assert cancelled.revision == bundle["plan"].revision + 1
