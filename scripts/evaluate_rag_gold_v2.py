#!/usr/bin/env python3
"""Run the RAG Gold Set v2 offline scoring harness.

Examples (all modes are local-only)::

    # Create a blank redacted prediction template for manual/system runners.
    uv run python scripts/evaluate_rag_gold_v2.py --emit-template /tmp/rag_predictions.json

    # Score a completed dev/challenge prediction file.
    uv run python scripts/evaluate_rag_gold_v2.py \
      --predictions /tmp/rag_predictions.json \
      --output /tmp/rag_eval.json --markdown /tmp/rag_eval.md --html /tmp/rag_eval.html

    # Prepare a holdout input package.  This command never opens an answer key.
    uv run python scripts/evaluate_rag_gold_v2.py --mode holdout \
      --output /tmp/rag_holdout_input.json

The script only scores a redacted prediction artifact.  It does not execute
the retriever, inspect images, call Tencent/DeepSeek/OpenRouter, or download
embedding weights.  A future live LLM Judge is deliberately disabled unless a
separate adapter and explicit opt-in are implemented.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from portrait_consistency_agent.services.rag_gold_eval import (
    GoldSetFormatError,
    build_blind_judge_input,
    build_holdout_input_report,
    evaluate,
    load_annotations,
    load_holdout_runtime_cases,
    load_predictions,
    load_public_cases,
    prediction_template,
    render_html,
    render_markdown,
    run_fake_judge,
    run_live_judge,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = PROJECT_ROOT / "data/evaluation/rag_gold_v2_public.json"
DEFAULT_ANNOTATIONS = PROJECT_ROOT / "data/evaluation/rag_gold_v2_annotations.json"
DEFAULT_HOLDOUT = PROJECT_ROOT / "data/evaluation/rag_gold_v2_holdout_runtime.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("public", "holdout"), default="public")
    parser.add_argument(
        "--cases", type=Path, default=DEFAULT_CASES, help="Answerless dev/challenge case JSON."
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        default=DEFAULT_ANNOTATIONS,
        help="Separate dev/challenge answer key; never use in holdout mode.",
    )
    parser.add_argument(
        "--holdout-runtime",
        type=Path,
        default=DEFAULT_HOLDOUT,
        help="Input-only holdout JSON with case_id/query fields.",
    )
    parser.add_argument("--predictions", type=Path, help="Redacted runner predictions JSON.")
    parser.add_argument("--split", choices=("all", "dev", "challenge"), default="all")
    parser.add_argument("--output", type=Path, help="Write JSON report to this path.")
    parser.add_argument("--markdown", type=Path, help="Write a PM-readable Markdown report.")
    parser.add_argument("--html", type=Path, help="Write a standalone HTML report.")
    parser.add_argument("--emit-template", type=Path, help="Write a blank prediction template.")
    parser.add_argument(
        "--judge",
        choices=("none", "fake", "live"),
        default="none",
        help="Optional blind-judge seam. fake is local-only; live is disabled by default.",
    )
    parser.add_argument(
        "--allow-live",
        action="store_true",
        help="Explicit opt-in flag; live Judge still raises until a reviewed adapter exists.",
    )
    return parser


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.mode == "holdout":
            if args.predictions or args.annotations != DEFAULT_ANNOTATIONS:
                raise GoldSetFormatError(
                    "holdout mode accepts only the input package; do not provide an answer key"
                )
            dataset_version, cases = load_holdout_runtime_cases(args.holdout_runtime)
            payload = build_holdout_input_report(dataset_version=dataset_version, cases=cases)
            if args.output:
                _write_json(args.output, payload)
            else:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0

        dataset_version, cases = load_public_cases(args.cases)
        if args.emit_template:
            _write_json(args.emit_template, prediction_template(cases))
        annotations = load_annotations(
            args.annotations, allowed_case_ids=(case.case_id for case in cases)
        )
        predictions = load_predictions(args.predictions) if args.predictions else None
        report = evaluate(
            cases=cases,
            annotations=annotations,
            predictions=predictions,
            dataset_version=dataset_version,
            split=args.split,
        )
        payload: dict[str, object] = report.to_dict()
        if args.judge != "none" and predictions is not None:
            judge_rows: list[dict[str, object]] = []
            case_by_id = {case.case_id: case for case in cases}
            for case_id, prediction in predictions.items():
                case = case_by_id.get(case_id)
                if case is None:
                    continue
                judge_input = build_blind_judge_input(case, prediction)
                if args.judge == "fake":
                    judge_rows.append(run_fake_judge(judge_input).to_dict())
                else:
                    run_live_judge(judge_input=judge_input, allow_live=args.allow_live)
            payload["blind_judge"] = {
                "mode": args.judge,
                "rows": judge_rows,
                "gold_answer_key_read": False,
                "development_labels_read": False,
            }
        if args.output:
            _write_json(args.output, payload)
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        if args.markdown:
            args.markdown.parent.mkdir(parents=True, exist_ok=True)
            args.markdown.write_text(render_markdown(report), encoding="utf-8")
        if args.html:
            args.html.parent.mkdir(parents=True, exist_ok=True)
            args.html.write_text(render_html(report), encoding="utf-8")
        return 0
    except GoldSetFormatError as exc:
        print(f"RAG Gold Set format error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
