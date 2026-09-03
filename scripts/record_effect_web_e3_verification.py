"""Merge redacted browser E3 receipt downloads into the local live manifest.

The Streamlit Cloud page cannot persist to this repository.  It therefore
offers one small JSON projection per target after the shared verifier runs.
This command accepts those projections (and never accepts image bytes/data
URLs), replaces the matching sample rows, rebuilds the E3 evidence report and
leaves promotion to the separate fail-closed command.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from portrait_consistency_agent.services.tencent_effect_web_e3 import (  # noqa: E402
    E3LiveReceipt,
)


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    forbidden = {"output_data_url", "image_bytes", "data_url", "raw_output_data_url"}
    if forbidden & set(value):
        raise ValueError(f"{path.name} contains an image payload field")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge redacted E3 browser verification receipts")
    parser.add_argument(
        "receipts", nargs="+", type=Path, help="Downloaded redacted receipt JSON files"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=PROJECT_ROOT / "reports/effect_web_e3_live_manifest_v1.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = _object(args.manifest)
    rows = manifest.get("rows")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("manifest must contain a rows list of objects")
    parsed = [E3LiveReceipt.from_mapping(row) for row in rows]
    by_sample = {row.sample_id: row for row in parsed}
    for receipt_path in args.receipts:
        incoming = E3LiveReceipt.from_mapping(_object(receipt_path))
        by_sample[incoming.sample_id] = incoming
    # Normalize through projection-like JSON fields expected by
    # E3LiveReceipt.  This keeps the manifest explicitly redacted even if the
    # dataclass gains an internal helper field in a later version.
    manifest["rows"] = [
        {
            "sample_id": row.sample_id,
            "receipt_id": row.receipt_id,
            "request_ref": row.request_ref,
            "input_sha256": row.input_sha256,
            "status": row.status,
            "elapsed_ms": row.elapsed_ms,
            "output_sha256": row.output_sha256,
            "output_width": row.output_width,
            "output_height": row.output_height,
            "handoff_accepted": row.handoff_accepted,
            "result_retention": row.result_retention,
            "verification_status": row.verification_status,
            "verification_id": row.verification_id,
            "verification_decision": row.verification_decision,
            "overall_trend": row.overall_trend,
            "target_evidence_sufficient": row.target_evidence_sufficient,
            "measured_feature_count": row.measured_feature_count,
            "note": row.note,
        }
        for row in by_sample.values()
    ]
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "updated_samples": [
                    E3LiveReceipt.from_mapping(_object(path)).sample_id for path in args.receipts
                ],
                "manifest": str(args.manifest),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
