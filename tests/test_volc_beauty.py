from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from portrait_consistency_agent.services.provider_cards import load_volc_beauty_card
from portrait_consistency_agent.services.volc_beauty import (
    VolcBeautyAdapter,
    VolcBeautyGate,
    VolcBeautyRequest,
    request_from_image_bytes,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_candidate_card_is_explicitly_not_ready_for_execution() -> None:
    card = load_volc_beauty_card()

    assert card["provider"] == "volcengine"
    assert card["review_status"] == "candidate"
    assert card["admission"]["ready_for_execution"] is False
    assert card["parameters"]["eyes"]["provider_parameter"] == "eye"
    assert card["parameters"]["eyes"]["range"] == [-50, 50]
    assert "lip_thickness" in card["parameters"]["mouth"]["does_not_verify"]
    assert card["input"]["resource_per_task"] == 1
    assert card["privacy"]["data_outbound"] is True


def test_request_contract_contains_hash_metadata_but_rejects_raw_image_fields() -> None:
    request = request_from_image_bytes(
        b"authorized-in-memory-fixture",
        parameter_values={"face_shape_candidate": 1.0},
    )

    assert len(request.image_sha256) == 64
    assert request.image_bytes_size == len(b"authorized-in-memory-fixture")
    assert "image_base64" not in request.model_dump()

    with pytest.raises(ValidationError):
        VolcBeautyRequest.model_validate(
            {
                **request.model_dump(),
                "image_base64": "aGVsbG8=",
            }
        )


def test_default_preflight_is_fail_closed_and_does_not_send_image() -> None:
    request = request_from_image_bytes(b"fixture")
    receipt = VolcBeautyAdapter().execute(request, gate=VolcBeautyGate())

    assert receipt.status == "blocked"
    assert "provider_card_not_active" in receipt.reason_codes
    assert "allow_live_required" in receipt.reason_codes
    assert "credentials_missing" in receipt.reason_codes
    assert receipt.network_called is False
    assert receipt.image_sent is False
    assert receipt.provider_request_id is None


def test_candidate_is_still_blocked_even_if_synthetic_permission_and_budget_are_green() -> None:
    request = request_from_image_bytes(b"fixture")
    gate = VolcBeautyGate(
        allow_live=True,
        credentials_present=True,
        explicit_provider_consent=True,
        outbound_allowed=True,
        adapter_ready=True,
        requested_region="cn-north-1",
        estimated_cost_cny=0.10,
        spent_cost_cny=0.0,
        budget_limit_cny=1.0,
        # The request still deliberately carries the pending region/schema.
    )

    result = VolcBeautyAdapter().preflight(request, gate)

    assert result.allowed is False
    assert "provider_card_not_active" in result.reason_codes
    assert "provider_card_not_ready" in result.reason_codes
    assert "request_schema_unverified" in result.reason_codes
    assert result.network_called is False
    assert result.image_sent is False


def test_preflight_exposes_budget_and_batch_gates_without_network() -> None:
    request = request_from_image_bytes(b"fixture", batch_size=9)
    gate = VolcBeautyGate(
        allow_live=True,
        credentials_present=True,
        explicit_provider_consent=True,
        outbound_allowed=True,
        adapter_ready=True,
        requested_region="pending_vendor_confirmation",
        estimated_cost_cny=1.5,
        spent_cost_cny=0.75,
        budget_limit_cny=1.0,
    )

    result = VolcBeautyAdapter().preflight(request, gate)

    assert result.allowed is False
    assert "batch_limit_unverified" in result.reason_codes
    assert "budget_exceeded" in result.reason_codes
    assert result.budget_remaining_cny == 0.25
    assert result.network_called is False


def test_offline_smoke_default_does_not_read_supplied_image_or_call_network() -> None:
    image_path = PROJECT_ROOT / "tests" / "does-not-exist.jpg"
    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "smoke_volc_beauty.py"),
            "--image",
            str(image_path),
        ],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["status"] == "not_run"
    assert payload["network_called"] is False
    assert payload["image_read"] is False
    assert payload["image_sent"] is False
