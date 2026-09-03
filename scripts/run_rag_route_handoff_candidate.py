#!/usr/bin/env python3
"""Run the public-only route-handoff and evidence-specificity candidates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from portrait_consistency_agent.services.rag_route_handoff_evaluation import (
    build_route_handoff_evaluation_report,
    write_route_handoff_evaluation_report,
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
        default=PROJECT_ROOT / "reports/rag_route_handoff_candidate_v1.json",
    )
    parser.add_argument(
        "--html-output",
        type=Path,
        default=PROJECT_ROOT / "reports/rag_route_handoff_candidate_v1.html",
    )
    parser.add_argument(
        "--trace-output",
        type=Path,
        default=PROJECT_ROOT / "reports/rag_route_handoff_candidate_v1_traces.json",
    )
    args = parser.parse_args()
    report, traces = build_route_handoff_evaluation_report(
        cases_path=args.cases,
        annotations_path=args.annotations,
        regression_cases_path=args.regression_cases,
        regression_annotations_path=args.regression_annotations,
    )
    write_route_handoff_evaluation_report(
        report,
        traces,
        json_path=args.output,
        html_path=args.html_output,
        trace_path=args.trace_output,
    )
    development = report.get("datasets", {}).get("development", {})
    development = development if isinstance(development, dict) else {}
    print(
        json.dumps(
            {
                "status": "complete",
                "output": str(args.output),
                "html_output": str(args.html_output),
                "trace_output": str(args.trace_output),
                "changed_prediction_count_route_handoff": development.get(
                    "changed_prediction_count_route_handoff"
                ),
                "changed_prediction_count_specificity": development.get(
                    "changed_prediction_count_specificity"
                ),
                "promotion_decision": report["policy"]["promotion_decision"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
