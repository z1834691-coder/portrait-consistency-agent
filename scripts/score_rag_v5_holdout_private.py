#!/usr/bin/env python3
"""Owner-authorised aggregate scorer for the independent V5 Holdout.

The command refuses to read a private answer key unless the caller explicitly
passes ``--owner-approved``.  It emits aggregate metrics only; no question,
case-level score, Gold label or answer-key path is written to the report.
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
DEFAULT_ROOT = Path(
    "/Users/fengzihan/Documents/Codex/portrait-consistency-agent-v5-holdout-owner-review-2026-09-02"
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--holdout-runtime",
        type=Path,
        default=DEFAULT_ROOT / "v5_holdout_runtime_answerless.json",
    )
    parser.add_argument(
        "--predictions", type=Path, default=DEFAULT_ROOT / "v5_blind_predictions.json"
    )
    parser.add_argument(
        "--private-answer-key",
        type=Path,
        default=DEFAULT_ROOT / "v5_holdout_answer_key_owner_only.json",
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_ROOT / "v5_holdout_private_aggregate.json"
    )
    parser.add_argument(
        "--html-output",
        type=Path,
        default=DEFAULT_ROOT / "v5_holdout_private_aggregate.html",
    )
    parser.add_argument(
        "--owner-approved",
        action="store_true",
        help="explicitly confirm that the owner reviewed and froze the answer key",
    )
    return parser


def _ensure_private_key(path: Path) -> None:
    resolved = path.resolve()
    project = PROJECT_ROOT.resolve()
    if resolved == project or project in resolved.parents:
        raise SystemExit("private answer key must remain outside the project workspace")


def _safe_payload(
    *, dataset_version: str, case_count: int, prediction_count: int, report: object
) -> dict[str, object]:
    metrics = dict(getattr(report, "metrics", {}) or {})
    return {
        "report_version": "rag-v5-holdout-private-aggregate-v0.1",
        "dataset_version": dataset_version,
        "dataset_scope": "v5_independent_holdout_aggregate_only",
        "case_count": case_count,
        "prediction_count": prediction_count,
        "owner_approved": True,
        "hidden_answer_key_read": True,
        "questions_or_case_rows_in_output": False,
        "blind_snapshot_is_sealed_before_scoring": True,
        "network_called": False,
        "llm_called": False,
        "photo_or_face_vector_read": False,
        "external_provider_called": False,
        "metrics": metrics,
    }


def _render_html(payload: dict[str, object]) -> str:
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
    return (
        "<!doctype html><html lang='zh-CN'><meta charset='utf-8'>"
        "<title>V5 Holdout 聚合评分</title>"
        "<style>body{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;"
        "max-width:1050px;margin:32px auto;padding:0 22px;background:#f7f8fb;color:#18212b;"
        "line-height:1.55}table{border-collapse:collapse;width:100%;background:#fff}"
        "th,td{border:1px solid #dce3ec;padding:9px;text-align:left}th{width:360px;"
        "background:#eef2f6}.note{padding:13px;background:#fff7df;border-left:4px solid #cf8c00}"
        "</style><h1>V5 独立 Holdout｜聚合评分</h1>"
        "<p class='note'>仅在负责人审核并显式授权后生成；不含题目、案例编号、"
        "Gold 或答案键路径。</p>"
        f"<table><tr><th>数据版本</th><td>{html.escape(str(payload.get('dataset_version')))}</td></tr>"
        f"<tr><th>题目数</th><td>{html.escape(str(payload.get('case_count')))}</td></tr>"
        f"<tr><th>项目 Gate</th><td><strong>"
        f"{html.escape(str(metrics.get('project_threshold_gate')))}</strong></td></tr>"
        f"<tr><th>安全 Gate</th><td><strong>"
        f"{html.escape(str(metrics.get('hard_safety_gate')))}</strong></td></tr></table>"
        f"<h2>指标</h2><table>{rows}</table><h2>按 Gold 证据数量分层</h2>{strata_html}</html>"
    )


def main() -> int:
    args = _parser().parse_args()
    if not args.owner_approved:
        raise SystemExit(
            "refusing to read V5 answer key: review it first, then pass --owner-approved"
        )
    _ensure_private_key(args.private_answer_key)
    dataset_version, cases = load_holdout_runtime_cases(args.holdout_runtime)
    predictions = load_predictions(args.predictions)
    if set(predictions) != {case.case_id for case in cases}:
        raise SystemExit("predictions do not exactly cover the V5 runtime cases")
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
    args.html_output.write_text(_render_html(payload), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
