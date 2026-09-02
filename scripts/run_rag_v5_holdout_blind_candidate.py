#!/usr/bin/env python3
"""Run the current RAG candidate on a new answerless V5 Holdout.

This command is intentionally answer-key blind.  It only reads the runtime
questions, runs the candidate query compiler/retriever, and writes predictions,
full redacted traces, and a process-supervisor report outside the project
workspace.  Scoring is a separate owner-authorised command after review.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from portrait_consistency_agent.services.rag_fair_dev_candidate import _retrieval_predictions
from portrait_consistency_agent.services.rag_gold_eval import load_holdout_runtime_cases
from portrait_consistency_agent.services.rag_policy_coverage_candidate import (
    POLICY_OPERATION_COVERAGE_CANDIDATE_VERSION,
    policy_candidate_query_builder_multi_operation,
    policy_query_term_expander,
    policy_relation_resolver_v3,
    seed_reviewed_policy_knowledge_candidate,
)
from portrait_consistency_agent.services.rag_process_supervisor import (
    RagFairEvaluationRunner,
    audit_fair_run,
)
from portrait_consistency_agent.services.rag_query_compiler_candidate import (
    compile_generalized_projection_v3,
)

DEFAULT_RUNTIME = Path(
    "/Users/fengzihan/Documents/Codex/portrait-consistency-agent-v5-holdout-owner-review-2026-09-02/v5_holdout_runtime_answerless.json"
)
DEFAULT_OUT_DIR = DEFAULT_RUNTIME.parent
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT_AUDIT = PROJECT_ROOT / "reports/rag_v5_holdout_process_audit.json"
DEFAULT_PROJECT_AUDIT_HTML = PROJECT_ROOT / "reports/rag_v5_holdout_process_audit.html"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--project-audit-json", type=Path, default=DEFAULT_PROJECT_AUDIT)
    parser.add_argument("--project-audit-html", type=Path, default=DEFAULT_PROJECT_AUDIT_HTML)
    return parser


def _prediction_payload(prediction: object) -> dict[str, object]:
    return {
        "case_id": prediction.case_id,
        "route": prediction.route,
        "evidence_refs": list(prediction.evidence_refs),
        "evidence_relations": dict(prediction.evidence_relations),
        "observed_events": list(prediction.observed_events),
        "trace_ref": prediction.trace_ref,
        "machine_score_summary": dict(prediction.machine_score_summary),
    }


def main() -> int:
    args = _parser().parse_args()
    dataset_version, cases = load_holdout_runtime_cases(args.runtime)
    runner = RagFairEvaluationRunner()
    run = runner.run(
        cases,
        dataset_version=dataset_version,
        runtime_mode="holdout_input_only",
        projection_compiler=compile_generalized_projection_v3,
        compiler_version=POLICY_OPERATION_COVERAGE_CANDIDATE_VERSION,
        knowledge_seeder=seed_reviewed_policy_knowledge_candidate,
        query_builder=policy_candidate_query_builder_multi_operation,
        relation_resolver=policy_relation_resolver_v3,
        query_term_expander=policy_query_term_expander,
        operation_coverage=True,
    )
    audit = audit_fair_run(run, run_id=f"{POLICY_OPERATION_COVERAGE_CANDIDATE_VERSION}-v5-process")
    predictions = _retrieval_predictions(run)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    prediction_path = args.output_dir / "v5_blind_predictions.json"
    trace_path = args.output_dir / "v5_blind_trace.json"
    audit_path = args.output_dir / "v5_process_audit.json"
    safe_audit = audit.to_dict(redact_case_ids=True)
    prediction_path.write_text(
        json.dumps(
            {
                "runner_version": POLICY_OPERATION_COVERAGE_CANDIDATE_VERSION,
                "dataset_version": dataset_version,
                "answerless_runtime": True,
                "answer_key_read": False,
                "annotations_read": False,
                "rows": [_prediction_payload(row) for row in predictions],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    trace_path.write_text(
        json.dumps(
            {
                "runner_version": POLICY_OPERATION_COVERAGE_CANDIDATE_VERSION,
                "dataset_version": dataset_version,
                "answerless_runtime": True,
                "answer_key_read": False,
                "annotations_read": False,
                "traces": list(run.traces),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    audit_path.write_text(
        json.dumps(audit.to_dict(redact_case_ids=False), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.project_audit_json.parent.mkdir(parents=True, exist_ok=True)
    args.project_audit_html.parent.mkdir(parents=True, exist_ok=True)
    args.project_audit_json.write_text(
        json.dumps(safe_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary_rows = "".join(
        f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(str(value))}</td></tr>"
        for key, value in (
            ("数据版本", dataset_version),
            ("题数", len(cases)),
            ("Trace 数", len(run.traces)),
            ("Prediction 数", len(predictions)),
            ("过程门", audit.process_gate),
            ("质量评分状态", audit.quality_scoring_gate),
        )
    )
    args.project_audit_html.write_text(
        "<!doctype html><html lang='zh-CN'><meta charset='utf-8'>"
        "<title>V5 Holdout 过程监督</title>"
        "<style>body{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;"
        "max-width:900px;margin:32px auto;padding:0 20px;background:#f7f8fb;color:#18212b}"
        "table{border-collapse:collapse;width:100%;background:#fff}th,td{border:1px solid #dce3ec;"
        "padding:10px;text-align:left}th{width:240px;background:#eef2f6}.note{padding:12px;"
        "background:#fff7df;border-left:4px solid #cf8c00}</style>"
        "<h1>V5 独立 Holdout｜过程监督</h1>"
        "<p class='note'>本页只展示答案盲运行的过程事实，不包含题目、答案、"
        "逐题质量分数或私有路径。</p>"
        f"<table>{summary_rows}</table></html>",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "complete",
                "dataset_version": dataset_version,
                "case_count": len(cases),
                "prediction_count": len(predictions),
                "process_gate": audit.process_gate,
                "quality_scoring_gate": audit.quality_scoring_gate,
                "answer_key_read": False,
                "prediction_output": str(prediction_path),
                "trace_output": str(trace_path),
                "process_audit_output": str(audit_path),
                "project_process_audit": str(args.project_audit_html),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
