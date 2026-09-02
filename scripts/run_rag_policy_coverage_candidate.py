#!/usr/bin/env python3
"""Run the isolated, public-only Policy Card coverage candidate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from portrait_consistency_agent.services.rag_policy_coverage_candidate import (
    build_policy_coverage_candidate_report,
    write_policy_coverage_candidate_report,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases",
        type=Path,
        default=PROJECT_ROOT / "data/evaluation/rag_failure_driven_dev_v1.json",
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        default=PROJECT_ROOT / "data/evaluation/rag_failure_driven_dev_v1_annotations.json",
    )
    parser.add_argument(
        "--regression-cases",
        type=Path,
        default=PROJECT_ROOT / "data/evaluation/rag_gold_v2_public.json",
    )
    parser.add_argument(
        "--regression-annotations",
        type=Path,
        default=PROJECT_ROOT / "data/evaluation/rag_gold_v2_annotations.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "reports/rag_policy_coverage_candidate_v2.json",
    )
    parser.add_argument(
        "--html-output",
        type=Path,
        default=PROJECT_ROOT / "reports/rag_policy_coverage_candidate_v2.html",
    )
    parser.add_argument(
        "--trace-output",
        type=Path,
        default=PROJECT_ROOT / "reports/rag_policy_coverage_candidate_v2_traces.json",
    )
    args = parser.parse_args()
    report, traces = build_policy_coverage_candidate_report(
        cases_path=args.cases,
        annotations_path=args.annotations,
        regression_cases_path=args.regression_cases,
        regression_annotations_path=args.regression_annotations,
    )
    write_policy_coverage_candidate_report(
        report,
        traces,
        json_path=args.output,
        html_path=args.html_output,
        trace_path=args.trace_output,
    )
    print(
        json.dumps(
            {
                "status": "complete",
                "output": str(args.output),
                "html_output": str(args.html_output),
                "trace_output": str(args.trace_output),
                "changed_prediction_count": report["changed_prediction_count"],
                "regression_changed_prediction_count": report[
                    "regression_changed_prediction_count"
                ],
                "scoped_candidate_changed_prediction_count": report[
                    "scoped_candidate_changed_prediction_count"
                ],
                "regression_scoped_candidate_changed_prediction_count": report[
                    "regression_scoped_candidate_changed_prediction_count"
                ],
                "promotion_decision": report["policy"]["promotion_decision"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
