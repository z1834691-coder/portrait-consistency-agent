"""Common Web-SDK result handoff followed by the existing 8C verifier.

The browser component owns the actual Tencent Effect Web edit.  This module
owns the seam after the browser returns: it accepts the one-time result through
``accept_effect_web_browser_result`` and immediately feeds the in-memory bytes
to the same ``VerificationResult`` implementation used by the REST baseline.
No image bytes, data URLs, or raw coordinates are written by this module.

Keeping this as a small service (rather than duplicating the logic in a
Streamlit page) makes the Web path testable and prevents the demo UI from
quietly inventing a second verification contract.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from portrait_consistency_agent.core.contracts import (
    EditPlan,
    IntentFrame,
    PhotoQualityResult,
    ProviderRun,
    ReferenceProfile,
    UserFeedback,
    VerificationResult,
)
from portrait_consistency_agent.core.policies import ExecutionPolicy, VerificationPolicy
from portrait_consistency_agent.core.rag_contracts import RagAdvisoryDecision
from portrait_consistency_agent.services.execution import (
    ExecutionResult,
    accept_effect_web_browser_result,
)
from portrait_consistency_agent.services.verification import VerificationRunResult, verify_result
from portrait_consistency_agent.storage.local_store import LocalTraceStore


@dataclass(frozen=True)
class EffectWebE3FlowResult:
    """One browser result plus its common post-edit verification evidence."""

    execution: ExecutionResult
    verification_run: VerificationRunResult | None
    trace: tuple[dict[str, object], ...]

    @property
    def provider_run(self) -> ProviderRun | None:
        return self.execution.provider_run

    @property
    def verification(self) -> VerificationResult | None:
        return self.verification_run.verification if self.verification_run else None


def accept_and_verify_effect_web_result(
    *,
    confirmed_plan: EditPlan,
    execution_intent: IntentFrame,
    target_image_bytes: bytes,
    target_photo_id: str,
    profile: ReferenceProfile,
    quality_result: PhotoQualityResult,
    prepared_request: Mapping[str, object],
    browser_receipt: Mapping[str, object],
    browser_result: Mapping[str, object] | None,
    store: LocalTraceStore | None = None,
    now: datetime | None = None,
    policy: ExecutionPolicy | None = None,
    verification_policy: VerificationPolicy | None = None,
    round_number: int | None = None,
    prior_no_improvement_streak: int = 0,
    previous_verification_id: str | None = None,
    previous_cumulative_improvement: bool | None = None,
    plan_family_id: str | None = None,
    last_known_good_artifact_ref: str | None = None,
    user_feedback: UserFeedback | None = None,
    rag_advice: RagAdvisoryDecision | None = None,
    verification_id: str | None = None,
    allow_candidate_trial: bool = True,
) -> EffectWebE3FlowResult:
    """Accept one Web receipt and, when possible, run common 8C verification.

    ``allow_candidate_trial`` defaults to ``True`` because E3 is the evidence
    harness for the still-candidate Web Card.  Once promotion is complete, the
    caller can pass ``False`` to require the normal promoted-card path.
    """

    execution = accept_effect_web_browser_result(
        confirmed_plan=confirmed_plan,
        execution_intent=execution_intent,
        target_image_bytes=target_image_bytes,
        target_photo_id=target_photo_id,
        profile=profile,
        quality_result=quality_result,
        prepared_request=prepared_request,
        browser_receipt=browser_receipt,
        browser_result=browser_result,
        store=store,
        now=now,
        policy=policy,
        allow_candidate_trial=allow_candidate_trial,
    )
    trace = list(execution.trace)

    if (
        execution.route != "succeeded"
        or execution.provider_run is None
        or execution.result_image_bytes is None
    ):
        trace.append(
            {
                "step": "web_to_verification_handoff",
                "status": "skipped",
                "reason": "execution_not_succeeded_or_result_not_available",
                "result_bytes_persisted": False,
            }
        )
        return EffectWebE3FlowResult(
            execution=execution,
            verification_run=None,
            trace=tuple(trace),
        )

    verification_run = verify_result(
        profile=profile,
        plan=confirmed_plan,
        provider_run=execution.provider_run,
        result_image_bytes=execution.result_image_bytes,
        round_number=round_number,
        prior_no_improvement_streak=prior_no_improvement_streak,
        previous_verification_id=previous_verification_id,
        previous_cumulative_improvement=previous_cumulative_improvement,
        plan_family_id=plan_family_id,
        last_known_good_artifact_ref=last_known_good_artifact_ref,
        user_feedback=user_feedback,
        rag_advice=rag_advice,
        policy=verification_policy,
        store=store,
        verification_id=verification_id,
    )
    trace.extend(verification_run.trace)
    trace.append(
        {
            "step": "web_to_verification_handoff",
            "status": "completed",
            "provider_run_id": execution.provider_run.run_id,
            "verification_id": verification_run.verification.verification_id,
            "selected_strategy": verification_run.strategy_proposal.selected_strategy.value,
            "result_bytes_in_memory": True,
            "result_bytes_persisted": False,
            "rag_execution_authorized": False,
        }
    )
    if store is not None:
        store.record_event(
            confirmed_plan.session_id,
            "web_verification_handoff_completed",
            {
                "provider_run_id": execution.provider_run.run_id,
                "verification_id": verification_run.verification.verification_id,
                "decision": verification_run.verification.decision.value,
                "overall_trend": verification_run.verification.overall_trend.value,
                "result_bytes_persisted": False,
            },
        )
    return EffectWebE3FlowResult(
        execution=execution,
        verification_run=verification_run,
        trace=tuple(trace),
    )
