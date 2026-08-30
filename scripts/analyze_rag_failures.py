"""Generate the aggregate-only RAG failure analysis report."""

from __future__ import annotations

import argparse
from pathlib import Path

from portrait_consistency_agent.services.rag_failure_analysis import (
    build_failure_analysis,
    write_failure_analysis_report,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--public-cases",
        type=Path,
        default=PROJECT_ROOT / "data/evaluation/rag_gold_v2_public.json",
    )
    parser.add_argument(
        "--public-annotations",
        type=Path,
        default=PROJECT_ROOT / "data/evaluation/rag_gold_v2_annotations.json",
    )
    parser.add_argument(
        "--public-predictions",
        type=Path,
        default=PROJECT_ROOT / "reports/rag_gold_v2_baseline_predictions.json",
    )
    parser.add_argument(
        "--private-aggregate",
        type=Path,
        default=PROJECT_ROOT / "reports/rag_gold_v2_holdout_private_aggregate.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "reports/rag_failure_patterns_v1.json",
    )
    parser.add_argument(
        "--html",
        type=Path,
        default=PROJECT_ROOT / "reports/rag_failure_patterns_v1.html",
    )
    args = parser.parse_args()
    report = build_failure_analysis(
        public_cases_path=args.public_cases,
        public_annotations_path=args.public_annotations,
        public_predictions_path=args.public_predictions,
        private_aggregate_path=args.private_aggregate,
    )
    write_failure_analysis_report(report, json_path=args.output, html_path=args.html)
    print(
        {
            "status": "complete",
            "output": str(args.output),
            "html": str(args.html),
            "scope": report["scope"],
            "private_answer_key_read": report["policy"]["private_answer_key_read"],
            "network_called": report["policy"]["network_called"],
        }
    )


if __name__ == "__main__":
    main()
