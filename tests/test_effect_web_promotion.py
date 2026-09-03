from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from portrait_consistency_agent.services.tencent_effect_web import (
    EffectWebAdmissionInput,
    evaluate_effect_web_admission,
)


def _all_evidence() -> EffectWebAdmissionInput:
    return EffectWebAdmissionInput(
        card_review_status="candidate",
        license_active=True,
        exact_domain_bound=True,
        provider_permission_granted=True,
        outbound_data_policy_approved=True,
        region_approved=True,
        estimated_cost_known=True,
        adapter_ready=True,
        static_image_smoke_succeeded=True,
        smoke_receipt_ref="receipt_001",
        multi_sample_regression_succeeded=True,
        batch_failure_isolation_verified=True,
        product_owner_approved=True,
    )


def test_admission_is_still_fail_closed_for_missing_visual_and_vendor_evidence() -> None:
    evidence = _all_evidence().model_copy(
        update={
            "region_approved": False,
            "estimated_cost_known": False,
            "multi_sample_regression_succeeded": False,
        }
    )
    decision = evaluate_effect_web_admission(evidence)
    assert decision.allowed is False
    assert decision.next_action == "keep_candidate"
    assert {
        "region_not_approved",
        "estimated_cost_unknown",
        "multi_sample_regression_not_passed",
    }.issubset(decision.reason_codes)


def test_promotion_script_writes_blocked_decision_without_changing_card(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    evidence = json.loads(
        (root / "reports/effect_web_e3_evidence_v1.json").read_text(encoding="utf-8")
    )
    card = json.loads(
        (root / "data/provider_cards/tencent_effect_web.json").read_text(encoding="utf-8")
    )
    evidence_path = tmp_path / "evidence.json"
    card_path = tmp_path / "card.json"
    output_path = tmp_path / "decision.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    card_path.write_text(json.dumps(card), encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            str(root / "scripts/promote_effect_web_card.py"),
            "--evidence",
            str(evidence_path),
            "--card",
            str(card_path),
            "--decision-output",
            str(output_path),
            "--owner-approved",
            "--write-if-allowed",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    decision = json.loads(output_path.read_text(encoding="utf-8"))
    unchanged = json.loads(card_path.read_text(encoding="utf-8"))
    assert decision["card_changed"] is False
    assert decision["promotion_write"] == "blocked_fail_closed"
    assert unchanged["review_status"] == "candidate"


def test_promotion_script_writes_private_demo_scope_and_version_when_all_gates_pass(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    evidence = json.loads(
        (root / "reports/effect_web_e3_evidence_v1.json").read_text(encoding="utf-8")
    )
    evidence["formal_admission_evidence"] = {
        "license_active": True,
        "exact_domain_bound": True,
        "provider_permission_granted": True,
        "outbound_data_policy_approved": True,
        "region_approved": True,
        "estimated_cost_known": True,
        "adapter_ready": True,
        "static_image_smoke_succeeded": True,
        "multi_sample_visual_review_complete": True,
        "product_owner_promotion_approved": True,
    }
    evidence["live_summary"] = {
        "all_target_receipts_present": True,
        "request_refs_recorded": True,
    }
    card = json.loads(
        (root / "data/provider_cards/tencent_effect_web.json").read_text(encoding="utf-8")
    )
    evidence_path = tmp_path / "evidence.json"
    card_path = tmp_path / "card.json"
    output_path = tmp_path / "decision.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    card_path.write_text(json.dumps(card), encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            str(root / "scripts/promote_effect_web_card.py"),
            "--evidence",
            str(evidence_path),
            "--card",
            str(card_path),
            "--decision-output",
            str(output_path),
            "--owner-approved",
            "--write-if-allowed",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    decision = json.loads(output_path.read_text(encoding="utf-8"))
    promoted = json.loads(card_path.read_text(encoding="utf-8"))
    assert decision["card_changed"] is True
    assert decision["promotion_write"] == "card_promoted"
    assert decision["promotion_scope"] == "private_demo_beta"
    assert promoted["review_status"] == "verified"
    assert promoted["promotion_scope"] == "private_demo_beta"
    assert promoted["card_version"] == "web_private_demo_2026-09-04"
