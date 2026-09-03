"""Evaluate (and, only when safe, promote) the Tencent Effect Web Card.

The command is deliberately fail-closed.  A browser smoke or a product-owner
approval alone cannot promote a provider.  It reads only the redacted E3
evidence report and Card, writes a redacted decision report, and changes the
Card only when every admission field is true.  No image, data URL, credential,
or local path is read.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

PROMOTION_SCOPE = "private_demo_beta"
PROMOTED_CARD_VERSION = "web_private_demo_2026-09-04"

from portrait_consistency_agent.services.tencent_effect_web import (  # noqa: E402
    EffectWebAdmissionInput,
    evaluate_effect_web_admission,
)


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def _first_success_receipt(report: dict[str, Any]) -> str | None:
    for row in report.get("receipts", []):
        if isinstance(row, dict) and row.get("status") == "succeeded":
            value = row.get("receipt_id")
            if isinstance(value, str) and value:
                return value
    return None


def admission_from_report(
    report: dict[str, Any], *, owner_approved: bool
) -> EffectWebAdmissionInput:
    """Convert a redacted report into the typed admission checklist."""

    formal = report.get("formal_admission_evidence", {})
    if not isinstance(formal, dict):
        formal = {}
    live = report.get("live_summary", {})
    if not isinstance(live, dict):
        live = {}
    offline = report.get("offline_contract_regression", {})
    if not isinstance(offline, dict):
        offline = {}
    return EffectWebAdmissionInput(
        card_review_status="candidate",
        license_active=bool(formal.get("license_active", False)),
        exact_domain_bound=bool(formal.get("exact_domain_bound", False)),
        provider_permission_granted=bool(formal.get("provider_permission_granted", False)),
        outbound_data_policy_approved=bool(formal.get("outbound_data_policy_approved", False)),
        region_approved=bool(formal.get("region_approved", False)),
        estimated_cost_known=bool(formal.get("estimated_cost_known", False)),
        adapter_ready=bool(formal.get("adapter_ready", False)),
        static_image_smoke_succeeded=bool(formal.get("static_image_smoke_succeeded", False)),
        smoke_receipt_ref=_first_success_receipt(report),
        multi_sample_regression_succeeded=(
            bool(formal.get("multi_sample_visual_review_complete", False))
            and bool(live.get("all_target_receipts_present", False))
        ),
        batch_failure_isolation_verified=bool(
            offline.get("batch_failure_isolation_verified", False)
        ),
        product_owner_approved=owner_approved,
    )


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail-closed Tencent Effect Web Card admission")
    parser.add_argument(
        "--evidence",
        type=Path,
        default=PROJECT_ROOT / "reports/effect_web_e3_evidence_v1.json",
    )
    parser.add_argument(
        "--card",
        type=Path,
        default=PROJECT_ROOT / "data/provider_cards/tencent_effect_web.json",
    )
    parser.add_argument(
        "--decision-output",
        type=Path,
        default=PROJECT_ROOT / "reports/effect_web_promotion_decision_v1.json",
    )
    parser.add_argument(
        "--decision-output-html",
        type=Path,
        default=PROJECT_ROOT / "reports/effect_web_promotion_decision_v1.html",
    )
    parser.add_argument(
        "--write-if-allowed",
        action="store_true",
        help="write review_status=verified only when the checklist allows it",
    )
    parser.add_argument(
        "--owner-approved",
        action="store_true",
        help="use the owner's already supplied promotion approval; omitted means fail closed",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = _object(args.evidence)
    card = _object(args.card)
    evidence = admission_from_report(report, owner_approved=args.owner_approved)
    decision = evaluate_effect_web_admission(evidence)
    now = datetime.now(timezone.utc).isoformat()
    output: dict[str, Any] = {
        "decision_version": "effect_web_promotion_v0.1",
        "evaluated_at": now,
        "card_id": card.get("card_id"),
        "card_before_status": card.get("review_status"),
        "write_requested": bool(args.write_if_allowed),
        "admission_input": evidence.model_dump(mode="json"),
        "decision": decision.model_dump(mode="json"),
        "card_changed": False,
        "promotion_write": "not_requested",
        "promotion_scope": PROMOTION_SCOPE,
        "images_or_secrets_read": False,
    }
    if decision.allowed and args.write_if_allowed:
        card["review_status"] = "verified"
        card["card_version"] = PROMOTED_CARD_VERSION
        card["promotion_scope"] = PROMOTION_SCOPE
        card["reviewed_at"] = now[:10]
        evidence_block = card.setdefault("evidence", {})
        if isinstance(evidence_block, dict):
            evidence_block["promotion_status"] = "verified"
            evidence_block["promotion_decision_ref"] = str(args.decision_output)
            evidence_block["promotion_evaluated_at"] = now
            evidence_block["promotion_scope"] = PROMOTION_SCOPE
        _atomic_write_json(args.card, card)
        output["card_changed"] = True
        output["promotion_write"] = "card_promoted"
    elif decision.allowed:
        output["promotion_write"] = "allowed_but_not_written"
    else:
        output["promotion_write"] = "blocked_fail_closed"
    _atomic_write_json(args.decision_output, output)
    args.decision_output_html.parent.mkdir(parents=True, exist_ok=True)
    reason_items = "".join(f"<li>{html.escape(str(code))}</li>" for code in decision.reason_codes)
    verdict = "允许晋级" if decision.allowed else "保持 candidate"
    status_after = (
        "verified" if decision.allowed and args.write_if_allowed else str(card.get("review_status"))
    )
    args.decision_output_html.write_text(
        "<!doctype html><html lang='zh-CN'><meta charset='utf-8'>"
        "<title>Tencent Effect Web 准入决定</title>"
        "<style>body{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;"
        "max-width:960px;margin:32px auto;color:#202124}.box{padding:16px;"
        "background:#f7f4fb;border-left:4px solid #7952a8}li{margin:6px 0}"
        "code{word-break:break-all}</style><body>"
        "<h1>Tencent Effect Web｜确定性准入决定</h1>"
        f"<div class='box'><strong>结论：{html.escape(verdict)}</strong><br>"
        f"Card 状态：{html.escape(str(card.get('review_status')))} → "
        f"{html.escape(status_after)}</div>"
        "<p>本页只读取脱敏证据，不读取照片、结果图、密钥或本地路径。</p>"
        "<h2>未通过或待确认的 Gate</h2><ul>"
        f"{reason_items}</ul>"
        f"<p>写入动作：<code>{html.escape(str(output['promotion_write']))}</code></p>"
        "</body></html>\n",
        encoding="utf-8",
    )
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
