#!/usr/bin/env python3
"""Run one explicit, text-only DeepSeek IntentFrame smoke test.

Default behaviour is deliberately offline.  ``--allow-live`` is required
before the script reads a configured DeepSeek key and makes a network request.
It never accepts photos, Base64, vectors, or provider secrets as arguments.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from portrait_consistency_agent.agent.intent_adapter import (  # noqa: E402
    DeepSeekIntentAdapter,
    IntentParsingContext,
)
from portrait_consistency_agent.core.contracts import (  # noqa: E402
    ParserMode,
    ReferenceSource,
)
from portrait_consistency_agent.core.settings import AppSettings  # noqa: E402
from portrait_consistency_agent.storage.local_store import LocalTraceStore  # noqa: E402

SAFE_SMOKE_TEXT = "请把当前照片向我的母版靠拢，保留妆面，先给我参数建议。"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-live",
        action="store_true",
        help="Explicitly allow one text-only DeepSeek request using local .env credentials.",
    )
    args = parser.parse_args()
    if not args.allow_live:
        print(
            json.dumps(
                {
                    "status": "offline_guarded",
                    "network_called": False,
                    "message": (
                        "No DeepSeek request was made. Re-run with --allow-live after "
                        "configuring local .env."
                    ),
                },
                ensure_ascii=False,
            )
        )
        return 0

    settings = AppSettings()
    if not settings.has_deepseek_credentials:
        print(
            json.dumps(
                {
                    "status": "credentials_missing",
                    "network_called": False,
                    "message": (
                        "Set DEEPSEEK_API_KEY in local .env yourself, then re-run this command."
                    ),
                },
                ensure_ascii=False,
            )
        )
        return 2

    store = LocalTraceStore(
        PROJECT_ROOT / settings.database_path,
        PROJECT_ROOT / settings.trace_path,
    )
    store.initialize()
    session = store.create_session(state="CHECKPOINT7_SMOKE")
    context = IntentParsingContext(
        session_id=session.session_id,
        turn=1,
        target_refs=["photo_smoke_target_001"],
        has_locked_profile=True,
        default_reference_source=ReferenceSource.EXISTING_PROFILE,
    )
    result = DeepSeekIntentAdapter(settings).parse(
        context=context,
        user_text=SAFE_SMOKE_TEXT,
        allow_remote=True,
    )
    store.save_intent_frame(result.intent_frame)
    store.record_event(
        session.session_id,
        "intent_parser_completed",
        {
            "intent_id": result.intent_frame.intent_id,
            "clarification_needed": result.clarification.needed,
            **result.receipt.trace_projection(),
        },
    )
    print(
        json.dumps(
            {
                "status": "passed"
                if result.intent_frame.parser_mode == ParserMode.LLM
                else "fallback_after_live_attempt",
                "session_id": session.session_id,
                "intent_id": result.intent_frame.intent_id,
                "intent_action": result.intent_frame.action.value,
                "parser_mode": result.intent_frame.parser_mode.value,
                "receipt": result.receipt.trace_projection(),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if result.intent_frame.parser_mode == ParserMode.LLM else 1


if __name__ == "__main__":
    raise SystemExit(main())
