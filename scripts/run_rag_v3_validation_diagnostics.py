#!/usr/bin/env python3
"""Run the explicit owner-unlocked V3 validation diagnostics.

This command is offline and proposal-only.  It produces a full per-case
diagnostic/trace report from the derived validation package, while preserving
the original one-time blind Holdout-A artifact outside the workspace.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from portrait_consistency_agent.services.rag_v3_validation_diagnostics import (
    build_v3_validation_diagnostics,
    write_v3_validation_diagnostics,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = PROJECT_ROOT / "data/evaluation/rag_v3_validation_cases_v1.json"
DEFAULT_ANNOTATIONS = PROJECT_ROOT / "data/evaluation/rag_v3_validation_annotations_v1.json"
DEFAULT_REGRESSION_CASES = PROJECT_ROOT / "data/evaluation/rag_gold_v2_public.json"
DEFAULT_REGRESSION_ANNOTATIONS = PROJECT_ROOT / "data/evaluation/rag_gold_v2_annotations.json"
DEFAULT_JSON = PROJECT_ROOT / "reports/rag_v3_validation_diagnostics_v1.json"
DEFAULT_HTML = PROJECT_ROOT / "reports/rag_v3_validation_diagnostics_v1.html"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--annotations", type=Path, default=DEFAULT_ANNOTATIONS)
    parser.add_argument("--regression-cases", type=Path, default=DEFAULT_REGRESSION_CASES)
    parser.add_argument(
        "--regression-annotations", type=Path, default=DEFAULT_REGRESSION_ANNOTATIONS
    )
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--html-out", type=Path, default=DEFAULT_HTML)
    return parser


def main() -> int:
    args = _parser().parse_args()
    report = build_v3_validation_diagnostics(
        cases_path=args.cases,
        annotations_path=args.annotations,
        regression_cases_path=args.regression_cases,
        regression_annotations_path=args.regression_annotations,
    )
    write_v3_validation_diagnostics(report, json_path=args.json_out, html_path=args.html_out)
    final = report["generations"][-1]
    metrics = final.get("metrics", {}) if isinstance(final, dict) else {}
    print(
        json.dumps(
            {
                "status": report.get("status"),
                "dataset_version": report.get("dataset_version"),
                "generation_ids": report.get("generation_ids"),
                "final_metrics": metrics,
                "final_failure_counts": report.get("final_failure_counts"),
                "json_out": str(args.json_out),
                "html_out": str(args.html_out),
                "active_baseline_changed": report.get("policy", {}).get("active_baseline_changed"),
                "proposal_only": report.get("policy", {}).get("proposal_only"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
