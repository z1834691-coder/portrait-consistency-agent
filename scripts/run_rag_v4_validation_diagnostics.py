#!/usr/bin/env python3
"""Run owner-authorised V4 validation diagnostics after the blind snapshot.

The answerless runtime and blind prediction snapshot must already exist.  The
owner-only answer key is supplied explicitly and is never copied into the
workspace by this command; only the resulting diagnostic report is written.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from portrait_consistency_agent.services.rag_v4_validation_diagnostics import (
    build_v4_validation_diagnostics,
    write_v4_validation_diagnostics,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = PROJECT_ROOT / "data/evaluation/rag_v4_holdout_runtime.json"
DEFAULT_ANNOTATIONS = Path(
    "/Users/fengzihan/Documents/Codex/portrait-consistency-agent-v4-holdout-owner-only-2026-09-02/v4_holdout_answer_key_owner_only.json"
)
DEFAULT_REGRESSION_CASES = PROJECT_ROOT / "data/evaluation/rag_gold_v2_public.json"
DEFAULT_REGRESSION_ANNOTATIONS = PROJECT_ROOT / "data/evaluation/rag_gold_v2_annotations.json"
DEFAULT_BLIND_PREDICTIONS = PROJECT_ROOT / "reports/rag_v4_holdout_blind_predictions.json"
DEFAULT_JSON = PROJECT_ROOT / "reports/rag_v4_validation_diagnostics_v1.json"
DEFAULT_HTML = PROJECT_ROOT / "reports/rag_v4_validation_diagnostics_v1.html"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--annotations", type=Path, default=DEFAULT_ANNOTATIONS)
    parser.add_argument("--regression-cases", type=Path, default=DEFAULT_REGRESSION_CASES)
    parser.add_argument(
        "--regression-annotations", type=Path, default=DEFAULT_REGRESSION_ANNOTATIONS
    )
    parser.add_argument("--blind-predictions", type=Path, default=DEFAULT_BLIND_PREDICTIONS)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--html-out", type=Path, default=DEFAULT_HTML)
    return parser


def main() -> int:
    args = _parser().parse_args()
    report = build_v4_validation_diagnostics(
        cases_path=args.cases,
        annotations_path=args.annotations,
        regression_cases_path=args.regression_cases,
        regression_annotations_path=args.regression_annotations,
        blind_predictions_path=args.blind_predictions,
    )
    write_v4_validation_diagnostics(report, json_path=args.json_out, html_path=args.html_out)
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
                "blind_snapshot_match": report.get("policy", {}).get("blind_snapshot_match"),
                "semantic_diagnostic_gate": report.get("improvement_summary", {}).get(
                    "semantic_diagnostic_gate"
                ),
                "frozen_project_gate": report.get("improvement_summary", {}).get(
                    "frozen_project_gate"
                ),
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
