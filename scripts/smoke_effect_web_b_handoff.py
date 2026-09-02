"""Offline smoke for the Web B handoff into the common 8C verifier.

The provider result is a tiny local fixture, not a Tencent call.  The smoke
proves the exact server-side path used after a browser result arrives:
receipt/result binding -> common ProviderRun -> existing VerificationResult.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    from portrait_consistency_agent.services.execution import accept_effect_web_browser_result
    from portrait_consistency_agent.services.meta_agent import MetaAgentStage, MetaAgentToolSelector
    from portrait_consistency_agent.services.verification import verify_result
    from portrait_consistency_agent.storage.local_store import LocalTraceStore
    from tests.test_execution import _web_bundle

    with tempfile.TemporaryDirectory(prefix="portrait_effect_web_b_") as temp_dir:
        temp = Path(temp_dir)
        store = LocalTraceStore(temp / "demo.sqlite3", temp / "events.jsonl")
        store.initialize()
        session = store.create_session()
        bundle = _web_bundle(session_id=session.session_id)
        confirmation = bundle["confirmation"]
        proposal = MetaAgentToolSelector().propose(
            stage=MetaAgentStage.PLAN_EDIT,
            requested_features=["face_lifting", "eye_enlarging"],
            preferred_tool_id="tencent_effect_web",
            proposal_id="tool_proposal_effect_web_b_smoke",
        )
        if proposal.selected_tool_id != confirmation.confirmed_plan.provider:
            raise RuntimeError("Meta-Agent proposal and Web EditPlan provider are not bound")
        if proposal.execution_authorized:
            raise RuntimeError("Meta-Agent proposal unexpectedly authorized execution")
        accepted = accept_effect_web_browser_result(
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
        if accepted.provider_run is None or accepted.result_image_bytes is None:
            raise RuntimeError("B handoff fixture did not produce a ProviderRun and result bytes")
        verified = verify_result(
            profile=bundle["profile"],
            plan=confirmation.confirmed_plan,
            provider_run=accepted.provider_run,
            result_image_bytes=accepted.result_image_bytes,
        )
        trace_text = (temp / "events.jsonl").read_text(encoding="utf-8")
        output = {
            "implemented": True,
            "fixture_only": True,
            "network_called": False,
            "result_bytes_persisted": False,
            "provider": accepted.provider_run.provider,
            "provider_operation": accepted.provider_run.operation,
            "meta_agent_proposal": {
                "proposal_id": proposal.proposal_id,
                "selected_tool_id": proposal.selected_tool_id,
                "route": proposal.route.value,
                "fallback_tool_id": proposal.fallback_tool_id,
                "execution_authorized": proposal.execution_authorized,
            },
            "provider_run_id": accepted.provider_run.run_id,
            "verification_decision": verified.verification.decision.value,
            "verification_overall_trend": verified.verification.overall_trend.value,
            "verification_trace": list(verified.trace),
            "handoff_trace": list(accepted.trace),
            "trace_contains_data_url": "output_data_url" in trace_text,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        if output["trace_contains_data_url"]:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
