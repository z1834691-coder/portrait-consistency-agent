#!/usr/bin/env python3
"""Run the proposal-only, versioned RAG failure-correction loop.

The default run is offline and reads only the public dev/challenge cases.  A
private holdout aggregate may be supplied for context; the script never
accepts a holdout answer key or per-case answer file.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from portrait_consistency_agent.services.rag_optimization_loop import (
    build_optimization_report,
    write_optimization_report,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
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
        help="Optional aggregate-only JSON; never pass a holdout answer key.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "reports/rag_optimization_loop_v1.json",
    )
    parser.add_argument(
        "--html",
        type=Path,
        default=PROJECT_ROOT / "reports/rag_optimization_loop_v1.html",
    )
    args = parser.parse_args()
    report = build_optimization_report(
        public_cases_path=args.public_cases,
        public_annotations_path=args.public_annotations,
        public_predictions_path=args.public_predictions,
        private_aggregate_path=args.private_aggregate,
    )
    write_optimization_report(report, json_path=args.output, html_path=args.html)
    print(
        {
            "status": report["status"],
            "output": str(args.output),
            "html": str(args.html),
            "executed_generations": report["executed_generations"],
            "stop_reason": report["stop_reason"],
            "anti_overfit": report["anti_overfit"]["status"],
            "same_v3_holdout_rerun": report["policy"]["same_v3_holdout_rerun"],
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
