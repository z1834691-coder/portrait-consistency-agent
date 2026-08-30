"""Offline smoke stub for the candidate Volcengine Beauty API V2 adapter.

The default path does not read an image, inspect credentials, or make a
network call.  ``--allow-live`` is an explicit future switch, but this script
still refuses to send a photo because the candidate card, vendor schema,
authentication, budget and adapter are not verified yet.  It exists to prove
the fail-closed permission/budget boundary and to provide a reproducible
redacted receipt for later replacement by a real smoke test.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from portrait_consistency_agent.services.volc_beauty import (
    VolcBeautyAdapter,
    VolcBeautyGate,
    VolcBeautyRunReceipt,
    request_from_image_bytes,
)


def print_status(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline Volcengine Beauty API V2 candidate smoke")
    parser.add_argument(
        "--allow-live",
        action="store_true",
        help="Explicit future live switch; candidate adapter still refuses network calls",
    )
    parser.add_argument(
        "--image", type=Path, help="Future authorized image path; never read by this stub"
    )
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--estimated-cost-cny", type=float)
    parser.add_argument("--budget-limit-cny", type=float)
    parser.add_argument("--spent-cost-cny", type=float, default=0.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.allow_live:
        print_status(
            {
                "status": "not_run",
                "reason_codes": ["allow_live_required"],
                "network_called": False,
                "image_read": False,
                "image_sent": False,
                "next_step": "vendor_schema_auth_and_budget_gate",
            }
        )
        return 0

    # Even with --allow-live, never read an image until target-account
    # entitlement, pricing, privacy and a real adapter are verified. A generic
    # credential *reference* is used only as a future deployment-secret
    # presence probe; its value is never printed and is not an API credential
    # contract.
    credential_ref_present = bool(os.getenv("VOLC_BEAUTY_CREDENTIAL_REF", "").strip())
    if not credential_ref_present:
        print_status(
            {
                "status": "blocked",
                "reason_codes": ["credentials_missing", "image_not_read"],
                "network_called": False,
                "image_read": False,
                "image_sent": False,
            }
        )
        return 2

    # The candidate adapter has no target-account/live request validation, so
    # it accepts only a safe synthetic fixture. A supplied image path is
    # intentionally not opened or sent.
    request = request_from_image_bytes(
        b"offline-volc-beauty-fixture",
        batch_size=args.batch_size,
    )
    gate = VolcBeautyGate(
        allow_live=True,
        credentials_present=True,
        explicit_provider_consent=False,
        outbound_allowed=False,
        adapter_ready=False,
        estimated_cost_cny=args.estimated_cost_cny,
        spent_cost_cny=args.spent_cost_cny,
        budget_limit_cny=args.budget_limit_cny,
    )
    receipt: VolcBeautyRunReceipt = VolcBeautyAdapter().execute(request, gate=gate)
    print_status(
        {
            "status": receipt.status,
            "reason_codes": list(receipt.reason_codes),
            "network_called": receipt.network_called,
            "image_read": False,
            "image_sent": receipt.image_sent,
            "image_path_supplied": args.image is not None,
            "note": "Candidate shell only; no provider RequestId or result exists.",
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
