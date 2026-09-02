# ruff: noqa: E501
"""Run the failure-driven RAG optimisation loop and render its Dashboard."""

from __future__ import annotations

import argparse
from pathlib import Path

from portrait_consistency_agent.services.rag_failure_driven_loop import (
    build_failure_driven_report,
    write_failure_driven_report,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
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
        "--regression-predictions",
        type=Path,
        default=PROJECT_ROOT / "reports/rag_gold_v2_baseline_predictions.json",
        help=(
            "Retained for CLI compatibility; regression is replayed from the active baseline runner."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "reports/rag_failure_driven_loop_v1.json",
    )
    parser.add_argument(
        "--html",
        type=Path,
        default=PROJECT_ROOT / "reports/rag_failure_driven_loop_v1.html",
    )
    args = parser.parse_args()
    # The regression prediction path is intentionally not read: the runner
    # recreates the active baseline so the report cannot silently mix versions.
    del args.regression_predictions
    report = build_failure_driven_report(
        cases_path=args.cases,
        annotations_path=args.annotations,
        regression_cases_path=args.regression_cases,
        regression_annotations_path=args.regression_annotations,
        regression_predictions_path=PROJECT_ROOT / "reports/rag_gold_v2_baseline_predictions.json",
    )
    write_failure_driven_report(report, json_path=args.output, html_path=args.html)
    print(
        {
            "status": report["status"],
            "output": str(args.output),
            "html": str(args.html),
            "executed_generations": report["executed_generations"],
            "stop_reason": report["stop_reason"],
            "hidden_answer_key_read": report["policy"]["hidden_answer_key_read"],
        }
    )


if __name__ == "__main__":
    main()
