#!/usr/bin/env python3
"""Offline 8C-2 smoke: evidence-led plan family, lineage, and hard stop.

This is deliberately a fixture-only development trace. It calls a local fake
Beautify client twice, never loads Tencent credentials, and never sends a
photo to a network service. The first call represents the user's bounded
external-processing confirmation; the child call represents the constrained
automatic follow-up after the same scope passes preflight. A real provider
request must still use the same scope, safety and idempotency gates.
"""

from __future__ import annotations

import base64
import json
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    from portrait_consistency_agent.core.contracts import FeedbackSignal
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
    from portrait_consistency_agent.services.verification import verify_result
    from portrait_consistency_agent.storage.local_store import LocalTraceStore
    from tests.test_execution import TINY_PNG, FakeBeautifyClient, _bundle
    from tests.test_plan_family import _observation

    with tempfile.TemporaryDirectory(prefix="portrait_plan_family_8c2_") as temp_dir:
        temp_path = Path(temp_dir)
        store = LocalTraceStore(temp_path / "demo.sqlite3", temp_path / "events.jsonl")
        store.initialize()
        session = store.create_session()
        bundle = _bundle(session_id=session.session_id)
        first_client = FakeBeautifyClient(
            response=TencentBeautifyResponse(
                request_id="fixture-parent-8c2-001",
                result_image_base64=base64.b64encode(TINY_PNG).decode("ascii"),
                result_url=None,
            )
        )
        parent_execution = execute_confirmed_plan(
            confirmed_plan=bundle["confirmation"].confirmed_plan,
            execution_intent=bundle["confirmation"].execution_intent,
            target_image_bytes=bundle["target_bytes"],
            target_photo_id=bundle["target"].photo_id,
            profile=bundle["profile"],
            quality_result=bundle["quality"],
            client=first_client,
            store=store,
            now=bundle["now"],
        )
        assert parent_execution.provider_run is not None
        assert parent_execution.result_image_bytes is not None

        original_verify_observer = verification.observe_result_bytes
        original_followup_observer = plan_family.observe_result_bytes
        try:
            verification.observe_result_bytes = lambda result_image_bytes, photo_id: _observation()
            verified = verify_result(
                profile=bundle["profile"],
                plan=bundle["confirmation"].confirmed_plan,
                provider_run=parent_execution.provider_run,
                result_image_bytes=parent_execution.result_image_bytes,
                plan_family_id=f"family_{bundle['confirmation'].confirmed_plan.plan_id}",
                store=store,
                verification_id="verification_fixture_parent_8c2",
            )
            plan_family.observe_result_bytes = lambda result_image_bytes, photo_id: _observation(
                result_bytes=result_image_bytes
            )
            child = propose_followup_plan(
                previous_plan=bundle["confirmation"].confirmed_plan,
                previous_provider_run=parent_execution.provider_run,
                previous_verification=verified.verification,
                execution_intent=bundle["confirmation"].execution_intent,
                profile=bundle["profile"],
                result_image_bytes=parent_execution.result_image_bytes,
                store=store,
                now=bundle["now"] + timedelta(seconds=2),
                plan_id="plan_fixture_child_8c2",
            )
            assert child.plan is not None
            second_client = FakeBeautifyClient(
                response=TencentBeautifyResponse(
                    request_id="fixture-child-8c2-001",
                    result_image_base64=base64.b64encode(TINY_PNG).decode("ascii"),
                    result_url=None,
                )
            )
            child_execution = execute_followup_plan(
                confirmed_plan=child.plan,
                execution_intent=bundle["confirmation"].execution_intent,
                result_image_bytes=parent_execution.result_image_bytes,
                target_photo_id=bundle["target"].photo_id,
                profile=bundle["profile"],
                original_quality_result=bundle["quality"],
                previous_provider_run=parent_execution.provider_run,
                previous_verification=verified.verification,
                client=second_client,
                store=store,
                now=bundle["now"] + timedelta(seconds=3),
            )
            feedback = capture_explicit_feedback(
                session_id=session.session_id,
                anonymous_user_id=session.anonymous_user_id,
                verification=verified.verification,
                signal=FeedbackSignal.DISLIKE,
                store=store,
            )
            hard_stop = propose_followup_plan(
                previous_plan=bundle["confirmation"].confirmed_plan,
                previous_provider_run=parent_execution.provider_run,
                previous_verification=verified.verification.model_copy(
                    update={"user_feedback": feedback.feedback}
                ),
                execution_intent=bundle["confirmation"].execution_intent,
                profile=bundle["profile"],
                result_image_bytes=parent_execution.result_image_bytes,
            )
        finally:
            verification.observe_result_bytes = original_verify_observer
            plan_family.observe_result_bytes = original_followup_observer

        assert child_execution.provider_run is not None
        output = {
            "fixture_only": True,
            "network_called": False,
            "parent_provider_double_calls": len(first_client.calls),
            "child_provider_double_calls": len(second_client.calls),
            "round_1_verification": {
                "trend": verified.verification.overall_trend.value,
                "decision": verified.verification.decision.value,
                "cumulative_improvement": verified.verification.cumulative_improvement,
            },
            "round_2_plan": {
                "plan_id": child.plan.plan_id,
                "parent_plan_id": child.plan.parent_plan_id,
                "iteration": child.plan.iteration,
                "per_call_params": child.plan.provider_absolute_params.model_dump(mode="json"),
                "execution_mode": "auto_bounded_followup",
                "user_round_confirmation_required": False,
                "trace": list(child.trace),
            },
            "round_2_receipt": {
                "run_id": child_execution.provider_run.run_id,
                "parent_run_id": child_execution.provider_run.parent_run_id,
                "input_artifact_ref": child_execution.provider_run.input_artifact_ref,
                "trace": list(child_execution.trace),
            },
            "auto_followup_preflight": {
                "scope_reused": True,
                "provider_call_allowed": True,
                "execution_trigger": "auto_bounded_followup",
            },
            "explicit_dislike": {
                "status": feedback.feedback.status.value,
                "plan_family_route": hard_stop.route,
                "reason_codes": list(hard_stop.reason_codes),
                "feedback_trace": list(feedback.trace),
            },
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
