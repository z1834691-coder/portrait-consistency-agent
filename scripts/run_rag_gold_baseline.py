#!/usr/bin/env python3
"""Generate deterministic RAG Gold Set v2 predictions from answerless inputs.

The runner deliberately has no annotation, LLM, Provider, image, network, or
private-answer-key argument.  In ``public`` mode it loads the answerless
dev/challenge package; in ``holdout`` mode it loads only the answerless
``case_id + query`` runtime package.  Both paths project each phrase in memory
to a safe ``RagQuery``, use the existing local P0-B/P0-C path with
deterministic offline test backends, and write redacted predictions plus a
raw-prompt-free trace artifact.

Score the resulting predictions in a separate step with
``scripts/evaluate_rag_gold_v2.py`` for public cases only.  Holdout predictions
must be scored by the product owner's separate private local script after an
explicit answer-key path is supplied; this runner never does.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from portrait_consistency_agent.services.rag_gold_baseline import (
    RAG_GOLD_BASELINE_VERSION,
    RagGoldDeterministicBaseline,
    baseline_predictions_payload,
    baseline_trace_payload,
    sha256_of_public_case_ids,
)
from portrait_consistency_agent.services.rag_gold_eval import (
    GoldSetFormatError,
    load_holdout_runtime_cases,
    load_public_cases,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = PROJECT_ROOT / "data/evaluation/rag_gold_v2_public.json"
DEFAULT_PREDICTIONS = PROJECT_ROOT / "reports/rag_gold_v2_baseline_predictions.json"
DEFAULT_TRACE = PROJECT_ROOT / "reports/rag_gold_v2_baseline_trace.json"
DEFAULT_HOLDOUT = PROJECT_ROOT / "data/evaluation/rag_gold_v2_holdout_runtime.json"
DEFAULT_HOLDOUT_PREDICTIONS = PROJECT_ROOT / "reports/rag_gold_v2_holdout_baseline_predictions.json"
DEFAULT_HOLDOUT_TRACE = PROJECT_ROOT / "reports/rag_gold_v2_holdout_baseline_trace.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("public", "holdout"), default="public")
    parser.add_argument(
        "--cases", type=Path, default=DEFAULT_CASES, help="Answerless public D*/X* case package."
    )
    parser.add_argument(
        "--holdout-runtime",
        type=Path,
        default=DEFAULT_HOLDOUT,
        help="Answerless H* holdout runtime input; no answer key is accepted here.",
    )
    parser.add_argument("--predictions-out", type=Path)
    parser.add_argument("--trace-out", type=Path)
    return parser


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.mode == "public":
            dataset_version, cases = load_public_cases(args.cases)
            run = RagGoldDeterministicBaseline().run(cases)
            predictions_out = args.predictions_out or DEFAULT_PREDICTIONS
            trace_out = args.trace_out or DEFAULT_TRACE
        else:
            dataset_version, cases = load_holdout_runtime_cases(args.holdout_runtime)
            run = RagGoldDeterministicBaseline().run_holdout(cases)
            predictions_out = args.predictions_out or DEFAULT_HOLDOUT_PREDICTIONS
            trace_out = args.trace_out or DEFAULT_HOLDOUT_TRACE
    except (GoldSetFormatError, ValueError) as exc:
        print(f"RAG Gold baseline input error: {exc}")
        return 2

    predictions = baseline_predictions_payload(run)
    predictions["dataset_version"] = dataset_version
    predictions["public_case_id_sha256"] = sha256_of_public_case_ids(cases)
    trace = baseline_trace_payload(run)
    trace["dataset_version"] = dataset_version
    trace["public_case_id_sha256"] = sha256_of_public_case_ids(cases)
    _write_json(predictions_out, predictions)
    _write_json(trace_out, trace)
    print(
        json.dumps(
            {
                "runner_version": RAG_GOLD_BASELINE_VERSION,
                "mode": args.mode,
                "dataset_version": dataset_version,
                "case_count": len(cases),
                "predictions_out": str(predictions_out),
                "trace_out": str(trace_out),
                "hidden_answer_key_read": False,
                "annotations_read": False,
                "llm_called": False,
                "photo_or_face_vector_read": False,
                "external_provider_called": False,
                "network_called": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
