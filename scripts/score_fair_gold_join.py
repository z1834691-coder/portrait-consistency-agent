#!/usr/bin/env python3
"""Score the fresh V3/V4 answerless runs against private Gold keys.

The process gate must already be PASS.  Both answer keys are read only in
memory; their paths, questions and case-level facts never enter the output.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from portrait_consistency_agent.services.rag_fair_gold_join import (
    build_fair_gold_join_report,
    render_fair_gold_join_html,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROCESS = PROJECT_ROOT / "reports/rag_fair_process_audit_v1.json"
DEFAULT_V3_RUNTIME = PROJECT_ROOT / "data/evaluation/rag_v3_validation_cases_v1.json"
DEFAULT_V3_PREDICTIONS = PROJECT_ROOT / "reports/rag_fair_v3_answerless_predictions_v1.json"
DEFAULT_V3_TRACE = PROJECT_ROOT / "reports/rag_fair_v3_answerless_trace_v1.json"
DEFAULT_V4_RUNTIME = PROJECT_ROOT / "data/evaluation/rag_v4_holdout_runtime.json"
DEFAULT_V4_PREDICTIONS = PROJECT_ROOT / "reports/rag_fair_v4_answerless_predictions_v1.json"
DEFAULT_V4_TRACE = PROJECT_ROOT / "reports/rag_fair_v4_answerless_trace_v1.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "reports/rag_fair_gold_join_v2.json"
DEFAULT_HTML = PROJECT_ROOT / "reports/rag_fair_gold_join_v2.html"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--process-report", type=Path, default=DEFAULT_PROCESS)
    parser.add_argument("--v3-runtime", type=Path, default=DEFAULT_V3_RUNTIME)
    parser.add_argument("--v3-predictions", type=Path, default=DEFAULT_V3_PREDICTIONS)
    parser.add_argument("--v3-trace", type=Path, default=DEFAULT_V3_TRACE)
    parser.add_argument("--v3-answer-key", type=Path, required=True)
    parser.add_argument("--v4-runtime", type=Path, default=DEFAULT_V4_RUNTIME)
    parser.add_argument("--v4-predictions", type=Path, default=DEFAULT_V4_PREDICTIONS)
    parser.add_argument("--v4-trace", type=Path, default=DEFAULT_V4_TRACE)
    parser.add_argument("--v4-answer-key", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML)
    return parser


def main() -> int:
    args = _parser().parse_args()
    report = build_fair_gold_join_report(
        process_report_path=args.process_report,
        v3_runtime_path=args.v3_runtime,
        v3_predictions_path=args.v3_predictions,
        v3_trace_path=args.v3_trace,
        v3_answer_key_path=args.v3_answer_key,
        v4_runtime_path=args.v4_runtime,
        v4_predictions_path=args.v4_predictions,
        v4_trace_path=args.v4_trace,
        v4_answer_key_path=args.v4_answer_key,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_fair_gold_join_html(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "complete",
                "output": str(args.output),
                "html_output": str(args.html_output),
                "answer_key_path_emitted": False,
                "questions_emitted": False,
                "gold_facts_emitted": False,
                "case_level_results_emitted": False,
                "network_called": False,
                "llm_called": False,
                "provider_api_called": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
