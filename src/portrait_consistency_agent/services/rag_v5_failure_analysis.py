"""Aggregate-only failure analysis for an owner-authorised V5 Gold join.

The V5 answer key is read only after an explicit owner approval and only in
memory.  This module intentionally emits aggregate counts and failure
patterns, never questions, case identifiers, Gold rows, or the private key
path.  It is a diagnosis artifact, not an automatic promotion mechanism.
"""

from __future__ import annotations

import html
import json
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path

from portrait_consistency_agent.services.rag_gold_eval import (
    GoldAnnotation,
    GoldSetFormatError,
    Prediction,
    canonical_route,
    evaluate,
    load_annotations,
    load_holdout_runtime_cases,
    load_predictions,
)

V5_FAILURE_ANALYSIS_VERSION = "rag-v5-failure-analysis-v0.1"
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _ensure_private_key(path: Path) -> None:
    """Refuse a key located in the project workspace."""

    resolved = path.resolve()
    project = PROJECT_ROOT.resolve()
    if resolved == project or project in resolved.parents:
        raise GoldSetFormatError("V5 answer key must remain outside the project workspace")


def _expected_routes(annotation: GoldAnnotation) -> set[str]:
    return {
        canonical_route(token.strip())
        for value in annotation.gold_routes
        for token in value.replace("→", "/").replace("+", "/").split("/")
        if token.strip()
    }


def _case_codes(
    *, annotation: GoldAnnotation, prediction: Prediction, score: object
) -> tuple[str, ...]:
    """Return machine-derived codes without retaining the case itself."""

    codes: list[str] = []
    route_correct = getattr(score, "route_correct", None)
    evidence_exact = getattr(score, "evidence_exact", None)
    relation_accuracy = getattr(score, "evidence_relation_accuracy", None)
    reciprocal_rank = getattr(score, "reciprocal_rank", None)
    if route_correct is False:
        codes.append("route_mismatch")
    if evidence_exact is False:
        codes.append("evidence_set_mismatch")
    if relation_accuracy is not None and relation_accuracy < 1.0:
        codes.append("evidence_relation_mismatch")
    if reciprocal_rank is not None and reciprocal_rank < 1.0:
        codes.append("rank_mismatch")
    if reciprocal_rank == 0.0:
        codes.append("retrieval_miss_at_5")
    gold = set(annotation.gold_evidence)
    predicted = set(prediction.evidence_refs)
    if gold and (predicted - gold) and (gold - predicted):
        codes.append("evidence_overpacked_and_incomplete")
    return tuple(codes)


def _trace_category(trace: Mapping[str, object]) -> str:
    compiler = trace.get("compiler", {})
    if not isinstance(compiler, Mapping):
        return "trace_compiler_missing"
    categories = compiler.get("category_codes", [])
    if not isinstance(categories, list) or not categories:
        return "none"
    # A category is a reviewed ontology label, not a question or an answer.
    return "|".join(sorted(str(item) for item in categories))


def build_v5_failure_analysis(
    *,
    runtime_path: Path,
    predictions_path: Path,
    trace_path: Path,
    answer_key_path: Path,
    owner_approved: bool = False,
) -> dict[str, object]:
    """Join V5 once and return a redacted aggregate diagnosis."""

    if not owner_approved:
        raise GoldSetFormatError(
            "refusing to read V5 answer key: pass owner_approved after owner review"
        )
    _ensure_private_key(answer_key_path)
    dataset_version, cases = load_holdout_runtime_cases(runtime_path)
    predictions = load_predictions(predictions_path)
    expected_ids = {case.case_id for case in cases}
    if set(predictions) != expected_ids:
        raise GoldSetFormatError("V5 predictions must cover exactly the runtime cases")
    annotations = load_annotations(answer_key_path, allowed_case_ids=expected_ids)
    report = evaluate(
        cases=cases,
        annotations=annotations,
        predictions=predictions,
        dataset_version=dataset_version,
    )

    try:
        trace_payload = json.loads(trace_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GoldSetFormatError(f"cannot read V5 trace: {exc}") from exc
    traces = trace_payload.get("traces") if isinstance(trace_payload, dict) else None
    if not isinstance(traces, list) or not all(isinstance(item, dict) for item in traces):
        raise GoldSetFormatError("V5 trace must contain traces[]")
    trace_by_id = {str(item.get("case_id")): item for item in traces}
    if set(trace_by_id) != expected_ids or len(trace_by_id) != len(traces):
        raise GoldSetFormatError("V5 trace must cover exactly the runtime cases")

    score_by_id = {score.case_id: score for score in report.case_scores}
    failure_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    category_failures: defaultdict[str, Counter[str]] = defaultdict(Counter)
    route_confusion: Counter[str] = Counter()
    evidence_extras: Counter[str] = Counter()
    evidence_missing: Counter[str] = Counter()
    relation_mismatches: Counter[str] = Counter()
    fallback_after_projection = 0
    compiler_unknown = 0
    trace_complete = 0
    governance_clean = 0

    for case in cases:
        annotation = annotations[case.case_id]
        prediction = predictions[case.case_id]
        score = score_by_id[case.case_id]
        trace = trace_by_id[case.case_id]
        codes = _case_codes(annotation=annotation, prediction=prediction, score=score)
        failure_counts.update(codes)
        category = _trace_category(trace)
        category_counts[category] += 1
        category_failures[category].update(codes)
        compiler = trace.get("compiler", {})
        compiler_route = (
            canonical_route(str(compiler.get("proposed_route")))
            if isinstance(compiler, Mapping) and compiler.get("proposed_route")
            else None
        )
        prediction_route = canonical_route(prediction.route)
        route_confusion[f"{compiler_route or 'NONE'}→{prediction_route or 'NONE'}"] += 1
        if compiler_route in {None, "UNKNOWN"}:
            compiler_unknown += 1
        if compiler_route not in {None, "UNKNOWN"} and prediction_route == "BASELINE":
            fallback_after_projection += 1
        if (
            isinstance(trace.get("finalized"), bool)
            and trace.get("finalized")
            and isinstance(trace.get("retrieval"), Mapping)
            and isinstance(trace.get("prediction"), Mapping)
        ):
            trace_complete += 1
        governance = trace.get("governance", {})
        if isinstance(governance, Mapping) and all(
            governance.get(field) is False
            for field in (
                "hidden_answer_key_read",
                "annotations_read",
                "network_called",
                "llm_called",
                "provider_api_called",
                "external_provider_called",
                "photo_or_face_vector_read",
                "raw_prompt_persisted",
                "quality_score_joined",
            )
        ):
            governance_clean += 1
        gold = set(annotation.gold_evidence)
        predicted = set(prediction.evidence_refs)
        evidence_extras.update(predicted - gold)
        evidence_missing.update(gold - predicted)
        for ref, expected_relation in annotation.gold_evidence_relations.items():
            actual = prediction.evidence_relations.get(ref, "MISSING")
            if actual != expected_relation:
                relation_mismatches[f"{expected_relation}→{actual}"] += 1

    metrics = dict(report.metrics or {})
    patterns = [
        {
            "pattern_id": "V5-P1-route-understanding-to-fallback",
            "severity": "P0",
            "count": failure_counts["route_mismatch"],
            "evidence": {
                "compiler_unknown_cases": compiler_unknown,
                "fallback_after_non_unknown_projection": fallback_after_projection,
                "route_confusion": dict(sorted(route_confusion.items())),
            },
            "diagnosis": (
                "很多题已经产生了结构化投影，但下游仍把它降级为 BASELINE；"
                "因此用户目标没有稳定传到最终路由。"
            ),
            "sop": (
                "把‘已识别意图’到‘允许的检索路由’做成显式映射；"
                "只在真正缺槽位或安全不确定时回退 UNKNOWN/BASELINE，"
                "并为每次回退保存原因。"
            ),
        },
        {
            "pattern_id": "V5-P2-evidence-overpacking",
            "severity": "P0",
            "count": failure_counts["evidence_overpacked_and_incomplete"],
            "evidence": {
                "exact_set_mismatch": failure_counts["evidence_set_mismatch"],
                "extra_refs": dict(sorted(evidence_extras.items())),
                "missing_refs": dict(sorted(evidence_missing.items())),
            },
            "diagnosis": (
                "候选池经常带入通用规则，同时漏掉题目真正需要的工具卡；"
                "这不是简单的 Top-K 不够，而是证据打包没有按任务操作覆盖。"
            ),
            "sop": (
                "先按请求中的每个操作分配证据槽位，再加入通用策略卡；"
                "记录采用、补充和淘汰原因，不能让一个操作占满全部名额。"
            ),
        },
        {
            "pattern_id": "V5-P3-relation-default-reference",
            "severity": "P0",
            "count": failure_counts["evidence_relation_mismatch"],
            "evidence": {"relation_mismatch_types": dict(sorted(relation_mismatches.items()))},
            "diagnosis": (
                "资料大多被标成‘参考’，即使 Gold 要求的是‘直接证据’；"
                "说明关系判断没有稳定使用来源类型、能力状态和生命周期。"
            ),
            "sop": (
                "关系标签只能由已审核的来源/能力/生命周期规则产生；"
                "相似度只能帮助排序，不能把参考资料升级为直接证据。"
            ),
        },
        {
            "pattern_id": "V5-P4-retrieval-recall-is-not-the-whole-task",
            "severity": "P1",
            "count": failure_counts["retrieval_miss_at_5"],
            "evidence": {
                "hit_at_5": metrics.get("hit_at_5"),
                "recall_at_5": metrics.get("recall_at_5"),
                "mrr": metrics.get("mrr"),
            },
            "diagnosis": (
                "大多数题在前五条中能碰到某条相关资料，但路由、证据集合和关系仍错；"
                "因此单看‘搜到了没有’会高估系统质量。"
            ),
            "sop": (
                "继续分开评估理解、召回、证据关系和最终路由；"
                "禁止用高 Hit@5 抵消 P0 路由或关系错误。"
            ),
        },
    ]
    return {
        "analysis_version": V5_FAILURE_ANALYSIS_VERSION,
        "dataset_version": dataset_version,
        "scope": "v5_owner_authorised_aggregate_only",
        "case_count": len(cases),
        "metrics": metrics,
        "failure_counts": dict(sorted(failure_counts.items())),
        "compiler_category_counts": dict(sorted(category_counts.items())),
        "compiler_category_failure_counts": {
            key: dict(sorted(value.items())) for key, value in sorted(category_failures.items())
        },
        "process_integrity": {
            "trace_count": len(traces),
            "complete_trace_count": trace_complete,
            "governance_clean_count": governance_clean,
            "trace_gate": "PASS"
            if trace_complete == len(cases) and governance_clean == len(cases)
            else "FAIL",
        },
        "patterns": patterns,
        "policy": {
            "owner_approved": True,
            "hidden_answer_key_read": True,
            "answer_key_in_output": False,
            "questions_in_output": False,
            "case_ids_in_output": False,
            "network_called": False,
            "llm_called": False,
            "provider_called": False,
            "photo_or_face_vector_read": False,
            "promotion_decision": "not_promoted_proposal_only",
            "v5_snapshot_reused_for_tuning": False,
        },
        "next_step": (
            "Use patterns to design one public/dev candidate; do not tune the sealed V5 snapshot. "
            "Run public safety/regression first, then create a fresh independent holdout if needed."
        ),
    }


def write_v5_failure_analysis_report(
    report: Mapping[str, object], *, json_path: Path, html_path: Path
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html_path.write_text(render_v5_failure_analysis_html(report), encoding="utf-8")


def render_v5_failure_analysis_html(report: Mapping[str, object]) -> str:
    metrics = report.get("metrics", {})
    metrics = metrics if isinstance(metrics, Mapping) else {}
    patterns = report.get("patterns", [])
    patterns = patterns if isinstance(patterns, list) else []
    failures = report.get("failure_counts", {})
    failures = failures if isinstance(failures, Mapping) else {}
    process = report.get("process_integrity", {})
    process = process if isinstance(process, Mapping) else {}
    metric_rows = "".join(
        f"<tr><th>{html.escape(str(name))}</th><td>{html.escape(str(value))}</td></tr>"
        for name, value in metrics.items()
        if name != "precision_by_gold_evidence_count"
    )
    pattern_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('pattern_id', '')))}</td>"
        f"<td>{html.escape(str(item.get('severity', '')))}</td>"
        f"<td>{html.escape(str(item.get('count', '')))}</td>"
        f"<td>{html.escape(str(item.get('diagnosis', '')))}</td>"
        f"<td>{html.escape(str(item.get('sop', '')))}</td>"
        "</tr>"
        for item in patterns
        if isinstance(item, Mapping)
    )
    return f"""<!doctype html>
<html lang='zh-CN'><head><meta charset='utf-8'>
<title>V5 失败模式聚合分析</title>
<style>body{{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;
max-width:1180px;margin:30px auto;padding:0 22px;color:#17202a;line-height:1.55}}
table{{border-collapse:collapse;width:100%;margin:12px 0 26px;background:#fff}}
th,td{{border:1px solid #d9e2ec;padding:9px;text-align:left;vertical-align:top}}
th{{background:#f5f7fa}}.note{{background:#fff8e1;border-left:4px solid #f0ad00;
padding:13px 16px;margin:18px 0}}</style></head><body>
<h1>V5 独立 Holdout｜失败模式聚合分析</h1>
<p class='note'>答案只在负责人授权后的内存连接中使用；本页不含题目、案例编号、Gold 答案或私有路径。
V5 快照已经封存，不用于逐题调参；本报告只用于提出下一轮公开候选。</p>
<h2>过程门</h2><table><tr><th>题数</th><td>{html.escape(str(report.get("case_count")))}</td></tr>
<tr><th>Trace 数</th><td>{html.escape(str(process.get("trace_count")))}</td></tr>
<tr><th>完整 Trace</th><td>{html.escape(str(process.get("complete_trace_count")))}</td></tr>
<tr><th>治理干净 Trace</th><td>{html.escape(str(process.get("governance_clean_count")))}</td></tr>
<tr><th>过程 Gate</th><td><strong>{html.escape(str(process.get("trace_gate")))}</strong></td></tr>
</table>
<h2>质量指标（聚合）</h2><table>{metric_rows}</table>
<h2>失败计数</h2><pre>{html.escape(json.dumps(failures, ensure_ascii=False, indent=2))}</pre>
<h2>主要模式与 SOP</h2><table><thead><tr><th>模式</th><th>严重度</th><th>数量</th>
<th>我们看到了什么</th><th>下一步怎么修</th></tr></thead><tbody>{pattern_rows}</tbody></table>
<p>推广决定：<strong>not_promoted_proposal_only</strong>。下一步先在公开开发/回归集验证候选，
再决定是否新建独立 Holdout。</p>
</body></html>"""
