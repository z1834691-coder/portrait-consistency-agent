"""Offline smoke for the Tencent Effect Web adapter.

The default command does not read a photo, load a browser SDK, use a License,
or make a network call.  It proves the product-to-Web parameter mapping, card
shape and redacted request contract.  A live browser smoke is intentionally a
separate Streamlit page because Tencent Effect Web is a JavaScript/WebGL SDK,
not a Python REST endpoint.
"""

from __future__ import annotations

import argparse
import hashlib
import json

from portrait_consistency_agent.core.settings import AppSettings
from portrait_consistency_agent.services.provider_cards import load_tencent_effect_web_card
from portrait_consistency_agent.services.tencent_effect_web import TencentEffectWebAdapter

SAMPLE_URL = "https://webar-static.tencent-cloud.com/docs/test/m4-1080.jpg"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline Tencent Effect Web adapter smoke")
    parser.add_argument(
        "--allow-live",
        action="store_true",
        help="Reserved for the browser page; this script never makes a live call.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    card = load_tencent_effect_web_card()
    # The offline smoke needs settings only to construct the same adapter used
    # by the Streamlit page; it does not read or require Effect credentials.
    adapter = TencentEffectWebAdapter(AppSettings())
    request = adapter.prepare_request(
        request_ref="effect_web_smoke_001",
        input_artifact_ref="official_sample_url",
        input_artifact_sha256=hashlib.sha256(SAMPLE_URL.encode("utf-8")).hexdigest(),
        parameters={"face_lifting": 10, "eye_enlarging": 10},
        input_source="sample_url",
    )
    print(
        json.dumps(
            {
                "status": "not_run",
                "network_called": False,
                "browser_sdk_loaded": False,
                "live_flag_received": args.allow_live,
                "card": {
                    "card_id": card["card_id"],
                    "card_version": card["card_version"],
                    "review_status": card["review_status"],
                    "static_image_status": card["static_image"]["status"],
                },
                "request": {
                    "request_ref": request.request_ref,
                    "input_source": request.input_source,
                    "input_artifact_sha256": request.input_artifact_sha256,
                    "parameters": request.parameters.model_dump(
                        mode="json", exclude={"contract_version"}
                    ),
                    "token_included": False,
                },
                "next_step": "open Streamlit page 6 and run the official sample in a bound domain",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
