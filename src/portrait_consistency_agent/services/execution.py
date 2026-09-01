"""Checkpoint 8B: bounded confirmation and one real image-edit attempt.

This module deliberately has a narrow job.  It does **not** decide facial
measurements or parameter values; those facts already exist in a proposed
``EditPlan`` from Checkpoint 8A.  It turns one explicit user click into a
short-lived, scope-bound authorization, validates that nothing material has
changed, calls the Tencent adapter exactly once, and records the factual
``ProviderRun`` receipt.

The returned image bytes are intentionally held only by the caller's current
Streamlit session.  They are never written to SQLite, JSONL, or a project
results directory by this service.  Verification belongs to the next
checkpoint, so a successful provider response is never described as a proven
improvement.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from portrait_consistency_agent.core.contracts import (
    ArtifactLifecycle,
    ComparisonTrend,
    ConfirmationScope,
    ConfirmationStatus,
    ContentSafetyStatus,
    EditPlan,
    ErrorCategory,
    ErrorPhase,
    FeedbackStatus,
    FieldSource,
    IntentAction,
    IntentFrame,
    OutputPreference,
    PhotoQualityResult,
    PlanStatus,
    ProviderErrorDetail,
    ProviderRun,
    ProviderRunStatus,
    ReferenceProfile,
    SubjectMatchStatus,
    VerificationDecision,
    VerificationResult,
)
from portrait_consistency_agent.core.policies import (
    ExecutionPolicy,
    build_v0_execution_policy,
)
from portrait_consistency_agent.services.tencent_beautify import (
    TencentBeautifyApiError,
    TencentBeautifyResponse,
    TencentCredentialsMissingError,
)
from portrait_consistency_agent.storage.local_store import LocalTraceStore

EXECUTION_SERVICE_VERSION = "execution-gate-v0.1"


def utc_now() -> datetime:
    """Return an aware timestamp so expiry decisions are reproducible."""

    return datetime.now(timezone.utc)


class BeautifyClient(Protocol):
    """Small adapter seam used by unit tests without reaching Tencent."""

    def beautify_base64(self, image_base64: str, params: object) -> TencentBeautifyResponse:
        """Execute the provider operation and return its factual response."""


class ExecutionBlockedError(RuntimeError):
    """Raised before the external call when bounded authorization is invalid."""

    def __init__(self, reason_codes: tuple[str, ...], user_message: str) -> None:
        super().__init__(user_message)
        self.reason_codes = reason_codes
        self.user_message = user_message


@dataclass(frozen=True)
class ConfirmationResult:
    """The immutable records created from one explicit confirmation action."""

    execution_intent: IntentFrame
    confirmed_plan: EditPlan
    confirmation_scope_hash: str
    user_confirmation_copy: str
    trace: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class ExecutionResult:
    """One user-visible outcome of the 8B executor.

    ``result_image_bytes`` is intentionally memory-only.  It is absent for a
    blocked/failed call and must not be sent to trace or persistent storage.
    """

    route: str
    final_plan: EditPlan
    provider_run: ProviderRun | None
    result_image_bytes: bytes | None
    trace: tuple[dict[str, object], ...]
    user_message: str


def canonical_scope_hash(scope: ConfirmationScope) -> str:
    """Hash a deterministic scope projection without placing the scope in Trace."""

    encoded = json.dumps(
        scope.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_request_hash(image_bytes: bytes, plan: EditPlan) -> str:
    """Hash image bytes and explicit provider parameters without retaining bytes."""

    material = {
        "input_sha256": hashlib.sha256(image_bytes).hexdigest(),
        "provider": plan.provider,
        "provider_api_version": plan.provider_api_version,
        "params": plan.provider_absolute_params.model_dump(mode="json"),
    }
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_idempotency_key(plan: EditPlan) -> str:
    """Derive one local key per confirmed plan revision and scope."""

    if plan.confirmation_scope_hash is None:
        raise ValueError("confirmed plan is missing confirmation_scope_hash")
    material = "|".join(
        [
            plan.plan_id,
            str(plan.revision),
            plan.photo_sha256,
            plan.confirmation_scope_hash,
            plan.provider_card_version,
        ]
    ).encode("utf-8")
    return f"idem_{hashlib.sha256(material).hexdigest()[:40]}"


def user_confirmation_copy(plan: EditPlan, *, expires_at: datetime) -> str:
    """Return the exact short consent shown before a provider call."""

    features = "、".join(change.feature.value for change in plan.executable_changes)
    params = plan.provider_absolute_params
    return (
        "我确认：仅将当前这张目标照片发送给腾讯云 BeautifyPic，"
        f"按本方案的 {features} 执行（瘦脸 {params.face_lifting}、"
        f"大眼 {params.eye_enlarging}、美白 {params.whitening}、磨皮 {params.smoothing}）。"
        "若修后复测显示仍可在同一受限计划族内继续，上一轮腾讯返回的结果图可能作为下一轮输入；"
        "在本次确认的照片、部位、用途、预算和轮次范围内，后续轮次可由 Agent 自动执行，"
        "不需要逐轮再次点击；若范围或授权发生变化，系统会停止并要求重新确认。"
        "结果图只在本次浏览器会话中临时展示，可由我主动下载；"
        f"本次确认将在 {expires_at.astimezone(timezone.utc).strftime('%H:%M UTC')} 失效。"
        "腾讯返回图片不等于已经验证更接近母版。"
    )


def confirm_execution(
    *,
    source_intent: IntentFrame,
    proposed_plan: EditPlan,
    next_turn: int,
    now: datetime | None = None,
    policy: ExecutionPolicy | None = None,
) -> ConfirmationResult:
    """Create a new user-structured execution intent and confirmed plan revision.

    The caller invokes this function only after the user ticks the disclosure
    box and presses the explicit confirmation button.  It is intentionally not
    part of the LLM adapter: a text model cannot manufacture external-editing
    permission.
    """

    policy = policy or build_v0_execution_policy()
    now = now or utc_now()
    _ensure_confirmable(source_intent=source_intent, proposed_plan=proposed_plan)

    executable_features = list(
        dict.fromkeys(change.feature for change in proposed_plan.executable_changes)
    )
    confirmation_ref = f"confirm_{uuid.uuid4().hex}"
    requested_rounds = (
        source_intent.requested_max_rounds or proposed_plan.safety_policy.max_provider_rounds
    )
    max_provider_rounds = min(requested_rounds, proposed_plan.safety_policy.max_provider_rounds)
    scope = ConfirmationScope(
        scope_id=f"scope_{uuid.uuid4().hex}",
        target_refs=[proposed_plan.photo_id],
        allowed_features=executable_features,
        max_provider_rounds=max_provider_rounds,
        whitening_allowed=proposed_plan.provider_absolute_params.whitening > 0,
        smoothing_allowed=proposed_plan.provider_absolute_params.smoothing > 0,
        budget_limit_cny=proposed_plan.safety_policy.max_cost_cny,
        safety_policy_id=proposed_plan.safety_policy.policy_id,
        created_at=now,
        expires_at=now + timedelta(minutes=policy.confirmation_ttl_minutes),
    )
    scope_hash = canonical_scope_hash(scope)
    source_payload = source_intent.model_dump(mode="json")
    sources = dict(source_payload["field_sources"])
    sources["action"] = FieldSource.USER_EXPLICIT.value
    sources["confirmation_scope"] = FieldSource.USER_EXPLICIT.value
    slot_confidence = dict(source_payload["slot_confidence"])
    slot_confidence["action"] = 1.0
    output_preferences = list(source_intent.output_preferences)
    if OutputPreference.EDITED_IMAGES not in output_preferences:
        output_preferences.append(OutputPreference.EDITED_IMAGES)
    reason_codes = list(dict.fromkeys([*source_intent.reason_codes, "user_confirmed_execution"]))[
        :16
    ]
    execution_intent = IntentFrame.model_validate(
        {
            **source_payload,
            "intent_id": (
                f"intent_{source_intent.session_id[-12:]}_{next_turn}_{uuid.uuid4().hex[:8]}"
            ),
            "turn": next_turn,
            "supersedes_intent_id": source_intent.intent_id,
            "action": IntentAction.EXECUTE.value,
            "target_refs": [proposed_plan.photo_id],
            "output_preferences": [item.value for item in output_preferences],
            "allowed_features": [item.value for item in executable_features],
            "field_sources": sources,
            "slot_confidence": slot_confidence,
            "missing_slots": [],
            "reason_codes": reason_codes,
            "confirmation_status": ConfirmationStatus.CONFIRMED.value,
            "confirmation_scope": scope.model_dump(mode="json"),
            "confirmation_ref": confirmation_ref,
            "parser_mode": "user_structured_input",
            "model_provider": None,
            "model_version": None,
            "prompt_version": EXECUTION_SERVICE_VERSION,
            "created_at": now,
        }
    )
    confirmed_plan = _transition_plan(
        proposed_plan,
        status=PlanStatus.CONFIRMED,
        revision=proposed_plan.revision + 1,
        intent_id=execution_intent.intent_id,
        confirmation_ref=confirmation_ref,
        confirmation_scope_hash=scope_hash,
        expires_at=scope.expires_at,
    )
    trace = (
        {
            "step": "user_confirmation",
            "status": "confirmed",
            "plan_id": confirmed_plan.plan_id,
            "plan_revision": confirmed_plan.revision,
            "allowed_features": [item.value for item in executable_features],
            "max_provider_rounds": scope.max_provider_rounds,
            "expires_at": scope.expires_at.isoformat(),
            "policy_version": policy.policy_version,
        },
    )
    return ConfirmationResult(
        execution_intent=execution_intent,
        confirmed_plan=confirmed_plan,
        confirmation_scope_hash=scope_hash,
        user_confirmation_copy=user_confirmation_copy(confirmed_plan, expires_at=scope.expires_at),
        trace=trace,
    )


def cancel_execution_plan(proposed_plan: EditPlan) -> EditPlan:
    """Record that a user declined a proposed plan without ever calling Tencent."""

    if proposed_plan.status != PlanStatus.PROPOSED:
        raise ValueError("only a proposed plan can be cancelled before execution")
    return _transition_plan(
        proposed_plan,
        status=PlanStatus.CANCELLED,
        revision=proposed_plan.revision + 1,
    )


def execute_confirmed_plan(
    *,
    confirmed_plan: EditPlan,
    execution_intent: IntentFrame,
    target_image_bytes: bytes,
    target_photo_id: str,
    profile: ReferenceProfile,
    quality_result: PhotoQualityResult,
    client: BeautifyClient,
    store: LocalTraceStore | None = None,
    now: datetime | None = None,
    policy: ExecutionPolicy | None = None,
    previous_provider_run: ProviderRun | None = None,
    previous_verification: VerificationResult | None = None,
) -> ExecutionResult:
    """Perform exactly one post-confirmation Tencent attempt or block safely.

    No retry loop exists here. The optional prior receipt + verification pair
    is only for a child EditPlan in an already confirmed plan family. It
    changes the input artifact from the original upload to the verified result
    image, but still performs exactly one chargeable provider call.  The child
    call is allowed by the inherited bounded confirmation and is marked in
    Trace as ``auto_bounded_followup``; it is not a new user confirmation.
    """

    policy = policy or build_v0_execution_policy()
    now = now or utc_now()
    trace: list[dict[str, object]] = []
    is_followup = previous_provider_run is not None or previous_verification is not None
    execution_trigger = "auto_bounded_followup" if is_followup else "initial_user_confirmation"
    try:
        _ensure_execution_allowed(
            confirmed_plan=confirmed_plan,
            execution_intent=execution_intent,
            target_image_bytes=target_image_bytes,
            target_photo_id=target_photo_id,
            profile=profile,
            quality_result=quality_result,
            now=now,
            previous_provider_run=previous_provider_run,
            previous_verification=previous_verification,
        )
        idempotency_key = build_idempotency_key(confirmed_plan)
        if store is not None and store.has_provider_run_idempotency_key(idempotency_key):
            raise ExecutionBlockedError(
                ("duplicate_execution_prevented",),
                "这份已确认计划已经发起过一次调用。为避免重复扣费，系统不会再次自动发送；"
                "请重新生成并确认新计划。",
            )
    except ExecutionBlockedError as exc:
        duplicate_execution = "duplicate_execution_prevented" in exc.reason_codes
        final_status = (
            PlanStatus.EXPIRED
            if "confirmation_expired" in exc.reason_codes
            else PlanStatus.SUPERSEDED
        )
        # A prior receipt may already have advanced this plan to an executed or
        # failed revision.  Do not create a competing state revision merely
        # because a second browser click arrived; the saved receipt is the
        # factual source of truth and the safe action is simply no new call.
        final_plan = (
            confirmed_plan
            if duplicate_execution
            else _transition_plan(
                confirmed_plan,
                status=final_status,
                revision=confirmed_plan.revision + 1,
                superseded_reason=(
                    "confirmation_expired"
                    if final_status == PlanStatus.EXPIRED
                    else "execution_preflight_blocked"
                ),
            )
        )
        trace.append(
            {
                "step": "authorization_check",
                "status": "blocked",
                "reason_codes": list(exc.reason_codes),
                "execution_trigger": execution_trigger,
                "auto_followup": is_followup,
            }
        )
        if store is not None and not duplicate_execution:
            store.save_edit_plan(final_plan)
            store.record_event(
                confirmed_plan.session_id,
                "execution_preflight_blocked",
                {"plan_id": confirmed_plan.plan_id, "reason_codes": list(exc.reason_codes)},
            )
        return ExecutionResult(
            route="blocked",
            final_plan=final_plan,
            provider_run=None,
            result_image_bytes=None,
            trace=tuple(trace),
            user_message=exc.user_message,
        )

    input_sha256 = hashlib.sha256(target_image_bytes).hexdigest()
    input_artifact_ref = (
        previous_provider_run.result_artifact_ref
        if is_followup and previous_provider_run is not None
        else f"upload_{confirmed_plan.photo_id}"
    )
    parent_run_id = previous_provider_run.run_id if previous_provider_run is not None else None
    if input_artifact_ref is None:
        raise RuntimeError("follow-up execution is missing its prior result artifact reference")
    idempotency_key = build_idempotency_key(confirmed_plan)
    request_hash = build_request_hash(target_image_bytes, confirmed_plan)
    run_id = f"run_{uuid.uuid4().hex}"
    started_at = now
    started_clock = time.perf_counter()
    trace.append(
        {
            "step": "authorization_check",
            "status": "passed",
            "plan_id": confirmed_plan.plan_id,
            "plan_revision": confirmed_plan.revision,
            "confirmation_expires_at": confirmed_plan.expires_at.isoformat()
            if confirmed_plan.expires_at
            else None,
            "automatic_retry": policy.automatic_retry_enabled,
            "execution_mode": "plan_family_followup" if is_followup else "first_round",
            "execution_trigger": execution_trigger,
            "user_round_confirmation_required": False if is_followup else True,
            "parent_run_id": parent_run_id,
        }
    )
    try:
        response = client.beautify_base64(
            base64.b64encode(target_image_bytes).decode("ascii"),
            confirmed_plan.provider_absolute_params,
        )
        if not response.result_image_base64:
            raise TencentBeautifyApiError(
                "MISSING_BASE64_RESULT",
                "Tencent returned no Base64 image result for the V0 session-only flow.",
                request_id=response.request_id,
            )
        result_image_bytes = base64.b64decode(response.result_image_base64, validate=True)
        if not result_image_bytes:
            raise TencentBeautifyApiError(
                "EMPTY_RESULT_IMAGE",
                "Tencent returned an empty image result.",
                request_id=response.request_id,
            )
    except (
        TencentCredentialsMissingError,
        TencentBeautifyApiError,
        ValueError,
        binascii.Error,
    ) as exc:
        latency_ms = round((time.perf_counter() - started_clock) * 1000)
        completed_at = _completed_at_not_before(started_at, latency_ms)
        error = _provider_error(exc, policy=policy)
        status = (
            ProviderRunStatus.TIMEOUT
            if error.category == ErrorCategory.TIMEOUT
            else ProviderRunStatus.FAILED
        )
        provider_run = ProviderRun(
            run_id=run_id,
            trace_id=f"trace_{run_id.removeprefix('run_')}",
            plan_id=confirmed_plan.plan_id,
            plan_revision=confirmed_plan.revision,
            session_id=confirmed_plan.session_id,
            photo_id=confirmed_plan.photo_id,
            attempt_number=1,
            parent_run_id=parent_run_id,
            provider_api_version=confirmed_plan.provider_api_version,
            region=_client_region(client),
            endpoint=_client_endpoint(client),
            provider_card_id=confirmed_plan.provider_card_id,
            provider_card_version=confirmed_plan.provider_card_version,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            request_params=confirmed_plan.provider_absolute_params,
            input_artifact_ref=input_artifact_ref,
            input_artifact_sha256=input_sha256,
            confirmation_ref=confirmed_plan.confirmation_ref or "missing_confirmation",
            confirmation_scope_hash=confirmed_plan.confirmation_scope_hash or "0" * 64,
            consent_policy_version=policy.consent_policy_version,
            status=status,
            provider_request_id=_provider_request_id(exc),
            started_at=started_at,
            completed_at=completed_at,
            network_latency_ms=latency_ms,
            total_latency_ms=latency_ms,
            budget_policy_version=policy.policy_version,
            error=error,
        )
        final_plan = _transition_plan(
            confirmed_plan,
            status=PlanStatus.SUPERSEDED,
            revision=confirmed_plan.revision + 1,
            superseded_reason="provider_attempt_failed_reconfirmation_required",
        )
        trace.append(
            {
                "step": "execute_beautify",
                "status": "failed",
                "provider_request_id": provider_run.provider_request_id,
                "error_category": error.category.value,
                "provider_code": error.provider_code,
                "automatic_retry": False,
                "execution_trigger": execution_trigger,
                "auto_followup": is_followup,
            }
        )
        if store is not None:
            store.save_provider_run(provider_run)
            store.save_edit_plan(final_plan)
            store.record_event(
                confirmed_plan.session_id,
                "execution_trace",
                {"plan_id": confirmed_plan.plan_id, "route": "failed", "trace": trace},
            )
        return ExecutionResult(
            route="failed",
            final_plan=final_plan,
            provider_run=provider_run,
            result_image_bytes=None,
            trace=tuple(trace),
            user_message=(
                "腾讯没有成功返回可用结果。系统没有自动重试，也不会把它说成已修好；"
                "如需再试，请重新确认一份新计划。"
            ),
        )

    latency_ms = round((time.perf_counter() - started_clock) * 1000)
    completed_at = _completed_at_not_before(started_at, latency_ms)
    result_sha256 = hashlib.sha256(result_image_bytes).hexdigest()
    provider_run = ProviderRun(
        run_id=run_id,
        trace_id=f"trace_{run_id.removeprefix('run_')}",
        plan_id=confirmed_plan.plan_id,
        plan_revision=confirmed_plan.revision,
        session_id=confirmed_plan.session_id,
        photo_id=confirmed_plan.photo_id,
        attempt_number=1,
        parent_run_id=parent_run_id,
        provider_api_version=confirmed_plan.provider_api_version,
        region=_client_region(client),
        endpoint=_client_endpoint(client),
        provider_card_id=confirmed_plan.provider_card_id,
        provider_card_version=confirmed_plan.provider_card_version,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        request_params=confirmed_plan.provider_absolute_params,
        input_artifact_ref=input_artifact_ref,
        input_artifact_sha256=input_sha256,
        confirmation_ref=confirmed_plan.confirmation_ref or "missing_confirmation",
        confirmation_scope_hash=confirmed_plan.confirmation_scope_hash or "0" * 64,
        consent_policy_version=policy.consent_policy_version,
        status=ProviderRunStatus.SUCCEEDED,
        provider_request_id=response.request_id,
        result_artifact_ref=f"session_memory_{run_id}",
        result_artifact_sha256=result_sha256,
        artifact_lifecycle=ArtifactLifecycle(
            expires_at=completed_at + timedelta(minutes=policy.result_memory_ttl_minutes)
        ),
        started_at=started_at,
        completed_at=completed_at,
        network_latency_ms=latency_ms,
        total_latency_ms=latency_ms,
        budget_policy_version=policy.policy_version,
    )
    final_plan = _transition_plan(
        confirmed_plan,
        status=PlanStatus.EXECUTED,
        revision=confirmed_plan.revision + 1,
    )
    trace.append(
        {
            "step": "execute_beautify",
            "status": "succeeded",
            "provider_request_id": provider_run.provider_request_id,
            "latency_ms": latency_ms,
            "result_retention": "session_memory_only",
            "result_expires_at": provider_run.artifact_lifecycle.expires_at.isoformat()
            if provider_run.artifact_lifecycle
            else None,
            "execution_mode": "plan_family_followup" if is_followup else "first_round",
            "execution_trigger": execution_trigger,
            "user_round_confirmation_required": False if is_followup else True,
            "parent_run_id": parent_run_id,
        }
    )
    if store is not None:
        store.save_provider_run(provider_run)
        store.save_edit_plan(final_plan)
        store.record_event(
            confirmed_plan.session_id,
            "execution_trace",
            {"plan_id": confirmed_plan.plan_id, "route": "succeeded", "trace": trace},
        )
    return ExecutionResult(
        route="succeeded",
        final_plan=final_plan,
        provider_run=provider_run,
        result_image_bytes=result_image_bytes,
        trace=tuple(trace),
        user_message=(
            "腾讯已返回一张结果图，且真实调用回执已保存。它尚未经过修后复测，"
            "因此系统不会把这一步称为“已达到母版一致”。"
            if not is_followup
            else "腾讯已返回计划族下一轮的结果图，且父子回执关系已保存。"
            "它仍需经过 8C 复测，系统不会把它直接称为已达到母版一致。"
        ),
    )


def execute_followup_plan(
    *,
    confirmed_plan: EditPlan,
    execution_intent: IntentFrame,
    result_image_bytes: bytes,
    target_photo_id: str,
    profile: ReferenceProfile,
    original_quality_result: PhotoQualityResult,
    previous_provider_run: ProviderRun,
    previous_verification: VerificationResult,
    client: BeautifyClient,
    store: LocalTraceStore | None = None,
    now: datetime | None = None,
    policy: ExecutionPolicy | None = None,
) -> ExecutionResult:
    """Execute one already-confirmed child plan on a verified result image.

    The original quality gate proves the original target photo was authorized.
    It is intentionally not compared byte-for-byte with the current result
    image; separate lineage checks below prove the child input came from the
    immediately previous result receipt.
    """

    return execute_confirmed_plan(
        confirmed_plan=confirmed_plan,
        execution_intent=execution_intent,
        target_image_bytes=result_image_bytes,
        target_photo_id=target_photo_id,
        profile=profile,
        quality_result=original_quality_result,
        client=client,
        store=store,
        now=now,
        policy=policy,
        previous_provider_run=previous_provider_run,
        previous_verification=previous_verification,
    )


def _ensure_confirmable(*, source_intent: IntentFrame, proposed_plan: EditPlan) -> None:
    reasons: list[str] = []
    if proposed_plan.status != PlanStatus.PROPOSED:
        reasons.append("plan_not_proposed")
    if not proposed_plan.requires_confirmation:
        reasons.append("plan_does_not_require_confirmation")
    if proposed_plan.session_id != source_intent.session_id:
        reasons.append("session_mismatch")
    if proposed_plan.intent_id != source_intent.intent_id:
        reasons.append("plan_intent_mismatch")
    if source_intent.missing_slots:
        reasons.append("intent_missing_slots")
    if not proposed_plan.executable_changes:
        reasons.append("no_executable_changes")
    if reasons:
        raise ExecutionBlockedError(
            tuple(reasons),
            "当前方案没有满足外部执行条件；系统不会调用腾讯。请查看诊断或重新生成方案。",
        )


def _ensure_execution_allowed(
    *,
    confirmed_plan: EditPlan,
    execution_intent: IntentFrame,
    target_image_bytes: bytes,
    target_photo_id: str,
    profile: ReferenceProfile,
    quality_result: PhotoQualityResult,
    now: datetime,
    previous_provider_run: ProviderRun | None = None,
    previous_verification: VerificationResult | None = None,
) -> None:
    reasons: list[str] = []
    scope = execution_intent.confirmation_scope
    is_followup = previous_provider_run is not None or previous_verification is not None
    if confirmed_plan.status != PlanStatus.CONFIRMED:
        reasons.append("plan_not_confirmed")
    if execution_intent.confirmation_status != ConfirmationStatus.CONFIRMED or scope is None:
        reasons.append("confirmation_not_confirmed")
    if execution_intent.confirmation_ref != confirmed_plan.confirmation_ref:
        reasons.append("confirmation_ref_mismatch")
    if scope is not None:
        if canonical_scope_hash(scope) != confirmed_plan.confirmation_scope_hash:
            reasons.append("confirmation_scope_mismatch")
        if now >= scope.expires_at:
            reasons.append("confirmation_expired")
        if target_photo_id not in scope.target_refs:
            reasons.append("confirmation_photo_out_of_scope")
        executable_features = {change.feature for change in confirmed_plan.executable_changes}
        if not executable_features.issubset(set(scope.allowed_features)):
            reasons.append("confirmation_feature_out_of_scope")
    if confirmed_plan.expires_at is not None and now >= confirmed_plan.expires_at:
        reasons.append("confirmation_expired")
    if confirmed_plan.photo_id != target_photo_id:
        reasons.append("target_photo_id_mismatch")
    if hashlib.sha256(target_image_bytes).hexdigest() != confirmed_plan.photo_sha256:
        reasons.append("target_photo_hash_mismatch")
    if (
        profile.profile_id != confirmed_plan.profile_id
        or profile.version != confirmed_plan.profile_version
    ):
        reasons.append("profile_changed")
    if quality_result.session_id != confirmed_plan.session_id:
        reasons.append("quality_session_mismatch")
    if quality_result.quality_result_id != confirmed_plan.quality_result_id:
        reasons.append("quality_result_changed")
    if quality_result.photo_id != confirmed_plan.photo_id:
        reasons.append("quality_photo_mismatch")
    if not is_followup and quality_result.photo_sha256 != confirmed_plan.photo_sha256:
        reasons.append("quality_hash_mismatch")
    if quality_result.content_safety_status != ContentSafetyStatus.PASSED:
        reasons.append("content_safety_not_passed")
    if quality_result.subject_match_status != SubjectMatchStatus.MATCH:
        reasons.append("subject_match_not_confirmed")
    if quality_result.route.value not in {"continue", "warn_continue"}:
        reasons.append("quality_route_not_continuable")
    if quality_result.face_count != 1:
        reasons.append("single_face_required_for_v0_execution")
    if confirmed_plan.iteration > confirmed_plan.safety_policy.max_provider_rounds:
        reasons.append("round_limit_exceeded")
    if scope is not None and confirmed_plan.iteration > scope.max_provider_rounds:
        reasons.append("confirmation_round_limit_exceeded")
    if not confirmed_plan.executable_changes:
        reasons.append("no_executable_changes")
    if is_followup:
        if previous_provider_run is None or previous_verification is None:
            reasons.append("incomplete_followup_lineage")
        else:
            if confirmed_plan.parent_plan_id != previous_provider_run.plan_id:
                reasons.append("parent_plan_run_mismatch")
            if previous_provider_run.status != ProviderRunStatus.SUCCEEDED:
                reasons.append("previous_provider_run_not_succeeded")
            if previous_provider_run.session_id != confirmed_plan.session_id:
                reasons.append("previous_run_session_mismatch")
            if previous_provider_run.photo_id != confirmed_plan.photo_id:
                reasons.append("previous_run_photo_mismatch")
            if previous_provider_run.result_artifact_sha256 != confirmed_plan.photo_sha256:
                reasons.append("previous_result_hash_mismatch")
            if not previous_provider_run.result_artifact_ref:
                reasons.append("previous_result_artifact_ref_missing")
            if previous_verification.provider_run_id != previous_provider_run.run_id:
                reasons.append("verification_provider_run_mismatch")
            if previous_verification.plan_id != previous_provider_run.plan_id:
                reasons.append("verification_parent_plan_mismatch")
            if previous_verification.plan_revision != previous_provider_run.plan_revision:
                reasons.append("verification_parent_plan_revision_mismatch")
            if previous_verification.decision != VerificationDecision.REPLAN:
                reasons.append("verification_not_replan")
            if previous_verification.overall_trend != ComparisonTrend.IMPROVED:
                reasons.append("previous_round_not_improved")
            if not previous_verification.cumulative_improvement:
                reasons.append("cumulative_improvement_not_evidenced")
            if previous_verification.target_evidence_sufficient:
                reasons.append("target_evidence_already_sufficient")
            if previous_verification.result_quality_flags:
                reasons.append("result_quality_flags_block_followup")
            if not previous_verification.result_artifact_available:
                reasons.append("result_artifact_not_comparable")
            if previous_verification.user_feedback.status == FeedbackStatus.REJECTED:
                reasons.append("explicit_user_dissatisfaction")
            if previous_verification.round_number + 1 != confirmed_plan.iteration:
                reasons.append("followup_iteration_mismatch")
    if reasons:
        unique_reasons = tuple(dict.fromkeys(reasons))
        user_message = (
            "这份确认已失效或当前照片/约束发生变化，系统不会调用腾讯。请重新生成并确认方案。"
            if "confirmation_expired" in unique_reasons
            else "当前输入与已确认方案不一致，系统没有调用腾讯。请重新生成并确认方案。"
        )
        raise ExecutionBlockedError(unique_reasons, user_message)


def _transition_plan(
    plan: EditPlan,
    *,
    status: PlanStatus,
    revision: int,
    intent_id: str | None = None,
    confirmation_ref: str | None = None,
    confirmation_scope_hash: str | None = None,
    expires_at: datetime | None = None,
    superseded_reason: str | None = None,
) -> EditPlan:
    payload = plan.model_dump(mode="json")
    payload.update(
        {
            "revision": revision,
            "intent_id": intent_id or plan.intent_id,
            "status": status.value,
            "confirmation_ref": confirmation_ref
            if confirmation_ref is not None
            else plan.confirmation_ref,
            "confirmation_scope_hash": confirmation_scope_hash
            if confirmation_scope_hash is not None
            else plan.confirmation_scope_hash,
            "expires_at": expires_at if expires_at is not None else plan.expires_at,
            "superseded_reason": superseded_reason,
        }
    )
    return EditPlan.model_validate(payload)


def _provider_error(
    exc: Exception,
    *,
    policy: ExecutionPolicy,
) -> ProviderErrorDetail:
    if isinstance(exc, TencentCredentialsMissingError):
        return ProviderErrorDetail(
            phase=ErrorPhase.PREFLIGHT,
            category=ErrorCategory.AUTHORIZATION,
            provider_code="TENCENT_CREDENTIALS_MISSING",
            safe_message=(
                "当前运行环境没有可用的腾讯密钥；请在本机 .env 或 Streamlit Cloud "
                "App Settings → Secrets 配置 TENCENT_SECRET_ID 和 TENCENT_SECRET_KEY。"
            ),
            retryable=False,
        )
    if isinstance(exc, (ValueError, binascii.Error)):
        return ProviderErrorDetail(
            phase=ErrorPhase.RESULT_DECODE,
            category=ErrorCategory.MISSING_RESULT,
            provider_code="RESULT_DECODE_FAILED",
            safe_message="腾讯返回的结果图无法在本机安全读取，本次不展示为成功。",
            retryable=False,
        )
    assert isinstance(exc, TencentBeautifyApiError)
    code = exc.error_code
    normalized = code.lower()
    if "timeout" in normalized:
        category = ErrorCategory.TIMEOUT
    elif "server" in normalized or "rpcfail" in normalized or "innererror" in normalized:
        category = ErrorCategory.PROVIDER_5XX
    elif "unauthorized" in normalized or "authfailure" in normalized:
        category = ErrorCategory.AUTHORIZATION
    elif "illegal" in normalized or "invalidparameter" in normalized:
        category = ErrorCategory.INVALID_PARAMETER
    elif "image" in normalized or "face" in normalized:
        category = ErrorCategory.UNSUPPORTED_INPUT
    elif "missing" in normalized or "empty" in normalized:
        category = ErrorCategory.MISSING_RESULT
    else:
        category = ErrorCategory.UNKNOWN
    # ``retryable`` means the system itself will retry.  The user explicitly
    # froze no automatic retry for paid image editing, even if the provider
    # failure is transient and may be retried later with a new confirmation.
    return ProviderErrorDetail(
        phase=ErrorPhase.PROVIDER,
        category=category,
        provider_code=code,
        safe_message=(
            "腾讯本次未返回可用结果。系统不会自动重试；如需再试，请重新确认。"
            if not policy.automatic_retry_enabled
            else "腾讯本次未返回可用结果。"
        ),
        retryable=policy.automatic_retry_enabled,
    )


def _provider_request_id(exc: Exception) -> str | None:
    return exc.request_id if isinstance(exc, TencentBeautifyApiError) else None


def _completed_at_not_before(started_at: datetime, latency_ms: int) -> datetime:
    """Keep receipts temporally valid when a deterministic test clock is used."""

    observed_now = utc_now()
    logical_end = started_at + timedelta(milliseconds=latency_ms)
    return max(observed_now, logical_end)


def _client_region(client: BeautifyClient) -> str:
    settings = getattr(client, "settings", None)
    return str(getattr(settings, "tencent_region", "unknown-region"))


def _client_endpoint(client: BeautifyClient) -> str:
    settings = getattr(client, "settings", None)
    return str(getattr(settings, "tencent_beautify_endpoint", "fmu.tencentcloudapi.com"))
