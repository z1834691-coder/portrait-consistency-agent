#!/usr/bin/env python3
"""Owner-authorised, aggregate-only V5 failure analysis."""

from __future__ import annotations

import argparse
from pathlib import Path

from portrait_consistency_agent.services.rag_v5_failure_analysis import (
    build_v5_failure_analysis,
    write_v5_failure_analysis_report,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = Path(
    "/Users/fengzihan/Documents/Codex/portrait-consistency-agent-v5-holdout-owner-review-2026-09-02"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime", type=Path, default=DEFAULT_ROOT / "v5_holdout_runtime_answerless.json"
    )
    parser.add_argument(
        "--predictions", type=Path, default=DEFAULT_ROOT / "v5_blind_predictions.json"
    )
    parser.add_argument("--trace", type=Path, default=DEFAULT_ROOT / "v5_blind_trace.json")
    parser.add_argument(
        "--private-answer-key",
        type=Path,
        default=DEFAULT_ROOT / "v5_holdout_answer_key_owner_only.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "reports/rag_v5_failure_analysis_v1.json",
    )
    parser.add_argument(
        "--html-output",
        type=Path,
        default=PROJECT_ROOT / "reports/rag_v5_failure_analysis_v1.html",
    )
    parser.add_argument("--owner-approved", action="store_true")
    args = parser.parse_args()
    report = build_v5_failure_analysis(
        runtime_path=args.runtime,
        predictions_path=args.predictions,
        trace_path=args.trace,
        answer_key_path=args.private_answer_key,
        owner_approved=args.owner_approved,
    )
    write_v5_failure_analysis_report(report, json_path=args.output, html_path=args.html_output)
    print(
        {
            "status": "complete",
            "scope": report["scope"],
            "case_count": report["case_count"],
            "trace_gate": report["process_integrity"]["trace_gate"],
            "output": str(args.output),
            "html_output": str(args.html_output),
            "private_key_emitted": False,
            "case_rows_emitted": False,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
