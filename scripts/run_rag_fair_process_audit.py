#!/usr/bin/env python3
# ruff: noqa: E501
"""Run the answerless RAG fairness/process-supervisor gate.

The command deliberately uses existing V3/V4 runtime questions only.  It
does not read annotations or hidden answers and it does not produce quality
metrics.  It writes a redacted process report so a later scorer can be
unlocked only after every case has a complete compiler/retrieval Trace.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

from portrait_consistency_agent.services.rag_gold_eval import (
    GoldCase,
    load_holdout_runtime_cases,
    load_validation_cases,
)
from portrait_consistency_agent.services.rag_process_supervisor import (
    RagFairEvaluationRunner,
    audit_fair_run,
    audit_trace_payload,
    fair_run_payload,
    fair_trace_payload,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_V3_CASES = PROJECT_ROOT / "data/evaluation/rag_v3_validation_cases_v1.json"
DEFAULT_V4_CASES = PROJECT_ROOT / "data/evaluation/rag_v4_holdout_runtime.json"
DEFAULT_V4_HISTORICAL_TRACE = PROJECT_ROOT / "reports/rag_v4_holdout_blind_trace.json"
DEFAULT_V4_HISTORICAL_PREDICTIONS = PROJECT_ROOT / "reports/rag_v4_holdout_blind_predictions.json"
DEFAULT_JSON = PROJECT_ROOT / "reports/rag_fair_process_audit_v1.json"
DEFAULT_HTML = PROJECT_ROOT / "reports/rag_fair_process_audit_v1.html"
DEFAULT_V3_PREDICTIONS = PROJECT_ROOT / "reports/rag_fair_v3_answerless_predictions_v1.json"
DEFAULT_V3_TRACE = PROJECT_ROOT / "reports/rag_fair_v3_answerless_trace_v1.json"
DEFAULT_V4_PREDICTIONS = PROJECT_ROOT / "reports/rag_fair_v4_answerless_predictions_v1.json"
DEFAULT_V4_TRACE = PROJECT_ROOT / "reports/rag_fair_v4_answerless_trace_v1.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v3-cases", type=Path, default=DEFAULT_V3_CASES)
    parser.add_argument("--v4-cases", type=Path, default=DEFAULT_V4_CASES)
    parser.add_argument("--historical-v4-trace", type=Path, default=DEFAULT_V4_HISTORICAL_TRACE)
    parser.add_argument(
        "--historical-v4-predictions", type=Path, default=DEFAULT_V4_HISTORICAL_PREDICTIONS
    )
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--html-out", type=Path, default=DEFAULT_HTML)
    parser.add_argument("--v3-predictions-out", type=Path, default=DEFAULT_V3_PREDICTIONS)
    parser.add_argument("--v3-trace-out", type=Path, default=DEFAULT_V3_TRACE)
    parser.add_argument("--v4-predictions-out", type=Path, default=DEFAULT_V4_PREDICTIONS)
    parser.add_argument("--v4-trace-out", type=Path, default=DEFAULT_V4_TRACE)
    return parser


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _rows_to_predictions(payload: dict[str, Any]) -> list[dict[str, object]]:
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _historical_v4_audit(*, trace_path: Path, prediction_path: Path) -> dict[str, object]:
    trace_payload = _read_json(trace_path)
    prediction_payload = _read_json(prediction_path)
    traces = trace_payload.get("traces", [])
    traces = traces if isinstance(traces, list) else []
    predictions = _rows_to_predictions(prediction_payload)
    case_ids = [
        str(row.get("case_id"))
        for row in predictions
        if isinstance(row.get("case_id"), str) and row.get("case_id")
    ]
    policy = trace_payload.get("policy", {})
    policy = policy if isinstance(policy, dict) else {}
    report = audit_trace_payload(
        dataset_version=str(trace_payload.get("dataset_version", "unknown")),
        runtime_mode="historical_v4_snapshot",
        run_id="historical-v4-snapshot",
        case_ids=case_ids,
        traces=[row for row in traces if isinstance(row, dict)],
        predictions=predictions,
        policy=policy,
    )
    return report.to_dict(redact_case_ids=True)


def _run_dataset(
    *,
    name: str,
    cases: tuple[GoldCase, ...],
    dataset_version: str,
    runtime_mode: str,
    predictions_out: Path,
    trace_out: Path,
) -> dict[str, object]:
    runner = RagFairEvaluationRunner()
    run = runner.run(cases, dataset_version=dataset_version, runtime_mode=runtime_mode)
    audit = audit_fair_run(run, run_id=f"{name}-{runtime_mode}-fair-replay")
    predictions_out.parent.mkdir(parents=True, exist_ok=True)
    trace_out.parent.mkdir(parents=True, exist_ok=True)
    predictions_out.write_text(
        json.dumps(fair_run_payload(run), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    trace_out.write_text(
        json.dumps(fair_trace_payload(run), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "name": name,
        "purpose": "answerless_process_replay_not_quality_score",
        "audit": audit.to_dict(redact_case_ids=True),
        "run_policy": dict(run.policy),
        "knowledge_snapshot": dict(run.knowledge_snapshot),
        "answerless_artifacts": {
            "predictions": str(predictions_out),
            "trace": str(trace_out),
            "trace_count": len(run.traces),
            "case_ids_redacted": True,
            "raw_questions_written": False,
            "answers_written": False,
        },
    }


def _summary_row(dataset: dict[str, object]) -> dict[str, object]:
    audit = dataset.get("audit", {})
    audit = audit if isinstance(audit, dict) else {}
    counts = audit.get("counts", {})
    counts = counts if isinstance(counts, dict) else {}
    return {
        "数据集": dataset.get("name", "—"),
        "题目数": audit.get("case_count", 0),
        "编译成功": counts.get("compiler_structured", 0),
        "未知但继续检索": counts.get("compiler_unknown_fallback", 0),
        "完整检索 Trace": counts.get("retrieval_complete", 0),
        "过程失败": counts.get("case_fail", 0),
        "过程门": audit.get("process_gate", "—"),
        "质量评分状态": audit.get("quality_scoring_gate", "—"),
    }


def render_html(payload: dict[str, object]) -> str:
    datasets = payload.get("datasets", [])
    datasets = datasets if isinstance(datasets, list) else []
    rows = "".join(
        "<tr>"
        + "".join(
            f"<td>{html.escape(str(row.get(key, '—')))}</td>"
            for key in (
                "数据集",
                "题目数",
                "编译成功",
                "未知但继续检索",
                "完整检索 Trace",
                "过程失败",
                "过程门",
                "质量评分状态",
            )
        )
        + "</tr>"
        for row in (_summary_row(item) for item in datasets if isinstance(item, dict))
    )
    historical = payload.get("historical_v4_snapshot", {})
    historical = historical if isinstance(historical, dict) else {}
    violations = historical.get("violations_by_code", {})
    violations = violations if isinstance(violations, dict) else {}
    violation_rows = (
        "".join(
            f"<tr><td>{html.escape(str(key))}</td><td>{html.escape(str(value))}</td></tr>"
            for key, value in sorted(violations.items())
        )
        or "<tr><td colspan='2'>无</td></tr>"
    )
    style = """
    body{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;max-width:1180px;margin:28px auto;padding:0 22px;color:#18212b;background:#f7f8fb;line-height:1.55}
    table{width:100%;border-collapse:collapse;background:#fff;margin:14px 0 24px}th,td{border:1px solid #dce3ec;padding:9px;text-align:left;vertical-align:top}th{background:#eef2f6}.note{padding:14px 16px;border-left:4px solid #6c5ce7;background:#f2efff;border-radius:5px}.bad{color:#a33;font-weight:700}.good{color:#167447;font-weight:700}code{background:#eef2f6;padding:2px 5px;border-radius:3px}
    """
    return f"""<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><title>RAG 公平评测过程监督</title><style>{style}</style></head><body>
    <h1>RAG 公平评测｜过程监督考官回执</h1>
    <div class='note'>这不是质量分数。它只回答一个问题：每道题是否真的经过了同一套“自然语言理解 → 结构化请求 → RAG 检索 → 结果回执”流程，而且没有把答案、路由标签或外部调用混进考试。</div>
    <h2>本轮结论</h2><table><tr><th>字段</th><th>值</th></tr>
    <tr><td>报告版本</td><td>{html.escape(str(payload.get("report_version")))}</td></tr>
    <tr><td>答案键是否读取</td><td class='good'>否</td></tr>
    <tr><td>质量分数是否提前合入</td><td class='good'>否</td></tr>
    <tr><td>新公平重放过程门</td><td class='{"good" if payload.get("fresh_replay_process_gate") == "PASS" else "bad"}'>{html.escape(str(payload.get("fresh_replay_process_gate")))}</td></tr>
    <tr><td>历史正式快照过程门</td><td class='{"good" if payload.get("historical_snapshot_process_gate") == "PASS" else "bad"}'>{html.escape(str(payload.get("historical_snapshot_process_gate")))}</td></tr>
    <tr><td>当前新运行过程门</td><td class='{"good" if payload.get("process_gate") == "PASS" else "bad"}'>{html.escape(str(payload.get("process_gate")))}</td></tr>
    <tr><td>新运行质量评分状态</td><td>{html.escape(str(payload.get("quality_scoring_gate")))}</td></tr>
    <tr><td>历史快照质量评分状态</td><td>{html.escape(str(payload.get("historical_quality_scoring_gate")))}</td></tr></table>
    <h2>同一批题目的过程重放</h2><table><thead><tr><th>数据集</th><th>题目数</th><th>编译成功</th><th>未知但继续检索</th><th>完整检索 Trace</th><th>过程失败</th><th>过程门</th><th>质量评分状态</th></tr></thead><tbody>{rows}</tbody></table>
    <h2>旧 V4 正式盲测快照的审计</h2><p>旧回执仍保留为历史证据；它没有被改写。下面只展示计数，不展示题干、答案或逐题内容。</p><table><tr><th>字段</th><th>值</th></tr>
    <tr><td>旧快照过程门</td><td class='{"good" if historical.get("process_gate") == "PASS" else "bad"}'>{html.escape(str(historical.get("process_gate")))}</td></tr>
    <tr><td>旧快照完整题数</td><td>{html.escape(str(historical.get("counts", {}).get("retrieval_complete", 0) if isinstance(historical.get("counts"), dict) else 0))}</td></tr>
    <tr><td>旧快照过程失败</td><td>{html.escape(str(historical.get("excluded_count", "—")))}</td></tr></table>
    <table><thead><tr><th>旧快照问题</th><th>数量</th></tr></thead><tbody>{violation_rows}</tbody></table>
    <h2>解释边界</h2><p>新重放的过程门通过，只表示新版评测器没有漏题、没有把上游投影当成检索答案，并且每题都有完整 Trace；它不表示 RAG 内容正确。旧 V4 正式快照本身不完整，历史质量分数永久保持锁定；这不会阻塞新重放按“两条轨道”单独连接 Gold 做验证。连接 Gold 仍是下一步独立动作，不能把验证成绩写成新的泛化盲测。</p>
    </body></html>"""


def main() -> int:
    args = _parser().parse_args()
    v3_version, v3_cases = load_validation_cases(args.v3_cases)
    v4_version, v4_cases = load_holdout_runtime_cases(args.v4_cases)
    v3 = _run_dataset(
        name="V3 validation copy",
        cases=v3_cases,
        dataset_version=v3_version,
        runtime_mode="validation_replay",
        predictions_out=args.v3_predictions_out,
        trace_out=args.v3_trace_out,
    )
    v4 = _run_dataset(
        name="V4 holdout input",
        cases=v4_cases,
        dataset_version=v4_version,
        runtime_mode="holdout_process_replay",
        predictions_out=args.v4_predictions_out,
        trace_out=args.v4_trace_out,
    )
    historical = _historical_v4_audit(
        trace_path=args.historical_v4_trace, prediction_path=args.historical_v4_predictions
    )
    all_audits = [v3["audit"], v4["audit"]]
    fresh_replay_pass = all(
        isinstance(item, dict) and item.get("process_gate") == "PASS" for item in all_audits
    )
    historical_pass = historical.get("process_gate") == "PASS"
    # The original V4 snapshot is a formal historical exam.  A corrected
    # replay can prove that the new runner is fair, but it cannot retroactively
    # repair the sealed old exam or turn its quality score into a valid one.
    # The old failure must not block a *new* complete answerless replay from
    # entering a separately joined validation run; historical quality remains
    # locked and is reported independently.
    fresh_quality_ready = fresh_replay_pass
    payload = {
        "report_version": "rag-fair-process-audit-v0.1",
        "scope": "answerless_process_integrity_only",
        "process_gate": "PASS" if fresh_replay_pass else "FAIL",
        "fresh_replay_process_gate": "PASS" if fresh_replay_pass else "FAIL",
        "historical_snapshot_process_gate": "PASS" if historical_pass else "FAIL",
        "quality_scoring_gate": (
            "READY_AFTER_SEPARATE_GOLD_JOIN"
            if fresh_quality_ready
            else "LOCKED_FRESH_PROCESS_AUDIT"
        ),
        "historical_quality_scoring_gate": (
            "READY_AFTER_SEPARATE_GOLD_JOIN"
            if historical_pass
            else "LOCKED_HISTORICAL_PROCESS_AUDIT"
        ),
        "policy": {
            "answer_key_read": False,
            "annotations_read": False,
            "quality_score_joined": False,
            "network_called": False,
            "llm_called": False,
            "provider_api_called": False,
            "photo_or_face_vector_read": False,
            "raw_prompt_persisted": False,
            "case_questions_written": False,
            "case_ids_in_report": False,
        },
        "datasets": [v3, v4],
        "historical_v4_snapshot": historical,
        "next_step": (
            "fresh_process_passed; join_gold_to_fresh_replay_only; historical_snapshot_remains_invalid"
            if fresh_quality_ready and not historical_pass
            else (
                "fresh_and_historical_process_passed; join_gold_is_still_a_separate_step"
                if fresh_quality_ready
                else "fresh_process_failed; do_not_join_gold"
            )
        ),
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.html_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.html_out.write_text(render_html(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "process_gate": payload["process_gate"],
                "quality_scoring_gate": payload["quality_scoring_gate"],
                "json_out": str(args.json_out),
                "html_out": str(args.html_out),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
