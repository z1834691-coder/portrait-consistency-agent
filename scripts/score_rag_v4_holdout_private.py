#!/usr/bin/env python3
# ruff: noqa: E501
"""Score the sealed V4 blind predictions against the owner-only answer key.

The command is intentionally aggregate-only.  It may read the answer key only
after the blind prediction and Trace snapshots have been sealed outside the
workspace; the generated JSON/HTML contains no case IDs, questions, Gold
answers or private file paths.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from portrait_consistency_agent.services.rag_gold_eval import (
    evaluate,
    load_annotations,
    load_holdout_runtime_cases,
    load_predictions,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = PROJECT_ROOT / "data/evaluation/rag_v4_holdout_runtime.json"
DEFAULT_PREDICTIONS = PROJECT_ROOT / "reports/rag_v4_holdout_blind_predictions.json"
DEFAULT_KEY = Path(
    "/Users/fengzihan/Documents/Codex/portrait-consistency-agent-v4-holdout-owner-only-2026-09-02/v4_holdout_answer_key_owner_only.json"
)
DEFAULT_JSON = PROJECT_ROOT / "reports/rag_v4_holdout_blind_aggregate.json"
DEFAULT_HTML = PROJECT_ROOT / "reports/rag_v4_holdout_blind_aggregate.html"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--holdout-runtime", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--private-answer-key", type=Path, default=DEFAULT_KEY)
    parser.add_argument("--output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML)
    return parser


def _safe_payload(
    *, dataset_version: str, case_count: int, prediction_count: int, report: object
) -> dict[str, object]:
    metrics = dict(getattr(report, "metrics", {}) or {})
    return {
        "report_version": "rag-v4-holdout-private-aggregate-v0.1",
        "dataset_version": dataset_version,
        "dataset_scope": "v4_independent_holdout_blind_aggregate",
        "case_count": case_count,
        "prediction_count": prediction_count,
        "hidden_answer_key_read": True,
        "questions_or_case_rows_in_output": False,
        "blind_snapshot_is_sealed_before_scoring": True,
        "network_called": False,
        "llm_called": False,
        "photo_or_face_vector_read": False,
        "external_provider_called": False,
        "metrics": metrics,
    }


def render_html(payload: dict[str, object]) -> str:
    metrics = payload.get("metrics", {})
    metrics = metrics if isinstance(metrics, dict) else {}
    rows = "".join(
        f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(str(value))}</td></tr>"
        for key, value in metrics.items()
        if key != "precision_by_gold_evidence_count"
    )
    strata = metrics.get("precision_by_gold_evidence_count", {})
    strata_html = (
        f"<pre>{html.escape(json.dumps(strata, ensure_ascii=False, indent=2))}</pre>"
        if strata
        else "<p>—</p>"
    )
    style = """
    body{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;max-width:1100px;margin:30px auto;padding:0 22px;color:#18212b;background:#f7f8fb;line-height:1.55}
    table{width:100%;border-collapse:collapse;background:#fff;margin:14px 0 24px}th,td{border:1px solid #dce3ec;padding:9px;text-align:left;vertical-align:top}th{width:330px;background:#eef2f6}pre{white-space:pre-wrap;background:#fff;padding:14px;border:1px solid #dce3ec;border-radius:5px}.note{padding:14px 16px;border-left:4px solid #cf8c00;background:#fff7df;border-radius:5px}
    """
    return f"""<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><title>V4 Holdout 盲测聚合</title><style>{style}</style></head><body>
    <h1>V4 独立 Holdout｜盲测聚合结果</h1>
    <p class='note'>这份报告只展示聚合指标。盲测运行时没有读取答案键；答案键在盲测快照封存后才被用于本地评分。报告不含题目、案例编号、Gold 答案或答案键路径。</p>
    <table><tr><th>数据版本</th><td>{html.escape(str(payload.get("dataset_version")))}</td></tr><tr><th>题目数</th><td>{html.escape(str(payload.get("case_count")))}</td></tr><tr><th>预测数</th><td>{html.escape(str(payload.get("prediction_count")))}</td></tr><tr><th>project threshold gate</th><td><strong>{html.escape(str(metrics.get("project_threshold_gate")))}</strong></td></tr><tr><th>hard safety gate</th><td><strong>{html.escape(str(metrics.get("hard_safety_gate")))}</strong></td></tr></table>
    <h2>指标</h2><table>{rows}</table><h2>按 Gold 证据数量分层</h2>{strata_html}
    <h2>边界</h2><p>这是一次独立泛化验收的聚合事实，不是逐题调参输入。若要定位错误，必须另建负责人授权的验证副本；诊断结果不能改写本次盲测快照。</p>
    </body></html>"""


def main() -> int:
    args = _parser().parse_args()
    dataset_version, cases = load_holdout_runtime_cases(args.holdout_runtime)
    predictions = load_predictions(args.predictions)
    annotations = load_annotations(
        args.private_answer_key, allowed_case_ids=[case.case_id for case in cases]
    )
    report = evaluate(
        cases=cases,
        annotations=annotations,
        predictions=predictions,
        dataset_version=dataset_version,
    )
    payload = _safe_payload(
        dataset_version=dataset_version,
        case_count=len(cases),
        prediction_count=len(predictions),
        report=report,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.html_output.write_text(render_html(payload), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
