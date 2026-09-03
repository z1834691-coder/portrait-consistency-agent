"""Offline smoke for the Provider Card -> Meta-Agent proposal boundary.

This smoke intentionally makes no image, credential, browser, LLM or provider
call.  It demonstrates the routing facts that should be visible in a Trace:
the Web card is relevant and is either a candidate proposal or a scoped
verified proposal, while the reviewed BeautifyPic card remains a separate
fallback/active baseline.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

# ruff: noqa: E402 - direct script execution bootstraps the src layout above.
from portrait_consistency_agent.services.meta_agent import MetaAgentStage, MetaAgentToolSelector


def main() -> None:
    proposal = MetaAgentToolSelector().propose(
        stage=MetaAgentStage.PLAN_EDIT,
        requested_features=["face_lifting", "eye_enlarging"],
        preferred_tool_id="tencent_effect_web",
        proposal_id="tool_proposal_smoke_001",
    )
    print(
        json.dumps(
            {
                "implemented": True,
                "network_called": False,
                "image_bytes_read": False,
                "provider_run_created": False,
                "proposal": proposal.model_dump(mode="json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
