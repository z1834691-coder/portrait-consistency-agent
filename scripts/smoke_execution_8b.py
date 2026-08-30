"""Offline, reproducible Trace for Checkpoint 8B.

This script never reads a user photo, never loads local Tencent credentials and
never connects to Tencent.  A tiny fixture response stands in for the provider
solely to demonstrate the confirmation → execution → ProviderRun evidence
chain.  Use the Streamlit confirmation button—not this script—for a real
BeautifyPic request.
"""

from __future__ import annotations

import base64
import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    # The fixture is deliberately shared with the unit test.  This script is a
    # development smoke, not a production executable.
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    from portrait_consistency_agent.services.execution import execute_confirmed_plan
    from portrait_consistency_agent.services.tencent_beautify import TencentBeautifyResponse
    from portrait_consistency_agent.storage.local_store import LocalTraceStore
    from tests.test_execution import TINY_PNG, FakeBeautifyClient, _bundle

    with tempfile.TemporaryDirectory(prefix="portrait_execution_8b_") as temp_dir:
        temp_path = Path(temp_dir)
        store = LocalTraceStore(temp_path / "demo.sqlite3", temp_path / "events.jsonl")
        store.initialize()
        session = store.create_session()
        bundle = _bundle(session_id=session.session_id)
        client = FakeBeautifyClient(
            response=TencentBeautifyResponse(
                request_id="fixture-request-8b-001",
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
        assert result.provider_run is not None
        output = {
            "fixture_only": True,
            "network_called": False,
            "provider_double_calls": len(client.calls),
            "confirmation_trace": list(bundle["confirmation"].trace),
            "execution_trace": list(result.trace),
            "provider_run": {
                "status": result.provider_run.status.value,
                "provider_request_id": result.provider_run.provider_request_id,
                "request_params": result.provider_run.request_params.model_dump(mode="json"),
                "result_ref_kind": "session_memory_only",
                "total_latency_ms": result.provider_run.total_latency_ms,
            },
            "verification_started": False,
        }
        print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
