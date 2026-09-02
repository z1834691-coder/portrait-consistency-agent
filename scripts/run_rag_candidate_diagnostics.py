#!/usr/bin/env python3
"""Render public per-case failure diagnostics for the current RAG candidate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from portrait_consistency_agent.services.rag_candidate_diagnostics import (
    build_candidate_diagnostics,
    write_candidate_diagnostics,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "reports/rag_policy_coverage_candidate_v2.json",
    )
    parser.add_argument(
        "--traces",
        type=Path,
        default=PROJECT_ROOT / "reports/rag_policy_coverage_candidate_v2_traces.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "reports/rag_candidate_diagnostics_v1.json",
    )
    parser.add_argument(
        "--html-output",
        type=Path,
        default=PROJECT_ROOT / "reports/rag_candidate_diagnostics_v1.html",
    )
    args = parser.parse_args()
    report = _read(args.report)
    traces = _read(args.traces)
    if not isinstance(report, dict) or not isinstance(traces, dict):
        raise SystemExit("candidate report/traces must be JSON objects")
    development_cases = _read(PROJECT_ROOT / "data/evaluation/rag_failure_driven_dev_v1.json")
    development_annotations = _read(
        PROJECT_ROOT / "data/evaluation/rag_failure_driven_dev_v1_annotations.json"
    )
    regression_cases = _read(PROJECT_ROOT / "data/evaluation/rag_gold_v2_public.json")
    regression_annotations = _read(PROJECT_ROOT / "data/evaluation/rag_gold_v2_annotations.json")
    if not all(
        isinstance(value, dict)
        for value in (
            development_cases,
            development_annotations,
            regression_cases,
            regression_annotations,
        )
    ):
        raise SystemExit("evaluation files must be JSON objects")
    diagnostics = build_candidate_diagnostics(
        report=report,
        traces=traces,
        development_cases=list(development_cases.get("cases", [])),
        development_annotations=list(development_annotations.get("annotations", [])),
        regression_cases=list(regression_cases.get("cases", [])),
        regression_annotations=list(regression_annotations.get("annotations", [])),
    )
    write_candidate_diagnostics(
        diagnostics,
        json_path=args.output,
        html_path=args.html_output,
    )
    print(
        json.dumps(
            {
                "status": "complete",
                "output": str(args.output),
                "html_output": str(args.html_output),
                "aggregate_root_cause_counts": diagnostics["aggregate_root_cause_counts"],
                "holdout_answers_read": diagnostics["holdout_answers_read"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
