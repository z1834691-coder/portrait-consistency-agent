"""Build a redacted E3 evidence report from real browser receipt metadata.

The live manifest is intentionally hand-curated from the browser page.  It
contains hashes and receipt metadata only; image bytes, data URLs, credentials
and local paths are never accepted.  The command does not call Tencent and it
never promotes the Provider Card.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from portrait_consistency_agent.services.tencent_effect_web_e3 import (  # noqa: E402
    E3LiveReceipt,
    build_e3_evidence_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a redacted Tencent Effect Web E3 report")
    parser.add_argument(
        "--preflight",
        type=Path,
        default=PROJECT_ROOT / "reports/effect_web_e3_preflight_v1.json",
    )
    parser.add_argument(
        "--live-manifest",
        type=Path,
        default=PROJECT_ROOT / "reports/effect_web_e3_live_manifest_v1.json",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=PROJECT_ROOT / "reports/effect_web_e3_evidence_v1.json",
    )
    parser.add_argument(
        "--output-html",
        type=Path,
        default=PROJECT_ROOT / "reports/effect_web_e3_evidence_v1.html",
    )
    return parser.parse_args()


def _load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def main() -> int:
    args = parse_args()
    preflight = _load_object(args.preflight)
    manifest = _load_object(args.live_manifest)
    raw_rows = manifest.get("rows")
    if not isinstance(raw_rows, list):
        raise ValueError("live manifest must contain a rows list")
    rows = [E3LiveReceipt.from_mapping(row) for row in raw_rows if isinstance(row, dict)]
    if len(rows) != len(raw_rows):
        raise ValueError("every live manifest row must be a JSON object")

    regression = manifest.get("offline_contract_regression", {})
    if not isinstance(regression, dict):
        raise ValueError("offline_contract_regression must be an object")
    formal = manifest.get("formal_admission_evidence", {})
    if not isinstance(formal, dict):
        raise ValueError("formal_admission_evidence must be an object")
    report = build_e3_evidence_report(
        preflight,
        rows,
        offline_contract_regression_passed=bool(regression.get("passed", False)),
        batch_failure_isolation_verified=bool(
            regression.get("batch_failure_isolation_verified", False)
        ),
        formal_admission_evidence={
            str(key): bool(value) for key, value in formal.items() if isinstance(key, str)
        },
    )
    payload = report.projection()
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_html.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.output_html.write_text(report.to_html(), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    # A report is useful even while the Card remains candidate.  Exit status
    # signals report construction, not provider promotion.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
