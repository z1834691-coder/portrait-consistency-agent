"""Data-driven RAG failure analysis and bounded self-correction proposals.

This module is deliberately an offline evaluator companion, not an online
permission engine.  It reads the answerless public runtime cases, the public
annotation file and a redacted prediction file.  An optional private
aggregate report may contribute only aggregate counts; it is never opened as
an answer key here.  The output contains no holdout question, case id or
answer fact and can therefore be shown in the local optimization dashboard.

The self-correction loop is proposal-only: it can identify one bounded change
to try and the regression checks that must pass, but it never mutates a
retriever, permission policy, Provider Card or hidden dataset automatically.
"""

from __future__ import annotations

import html
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from portrait_consistency_agent.services.rag_correction_candidate import (
    CORRECTION_CANDIDATE_VERSION,
    run_public_correction_candidate,
)
from portrait_consistency_agent.services.rag_gold_baseline import project_runtime_prompt
from portrait_consistency_agent.services.rag_gold_eval import (
    GoldCase,
    Prediction,
    evaluate,
    load_annotations,
    load_predictions,
    load_public_cases,
)

FAILURE_ANALYSIS_VERSION = "rag-failure-analysis-v0.1"


def _ratio(numerator: int | float, denominator: int | float) -> float | None:
    if denominator == 0:
        return None
    return round(float(numerator) / float(denominator), 6)


def _mean(values: list[float]) -> float | None:
    return round(mean(values), 6) if values else None


def _public_group_stats(
    cases: tuple[GoldCase, ...],
    annotations: dict[str, Any],
    predictions: dict[str, Prediction],
) -> dict[str, dict[str, object]]:
    """Aggregate public metrics by split and tag without retaining prompts."""

    grouped: dict[str, list[tuple[GoldCase, Any, Prediction]]] = defaultdict(list)
    for case in cases:
        annotation = annotations[case.case_id]
        prediction = predictions[case.case_id]
        grouped[f"split:{case.split}"].append((case, annotation, prediction))
        for tag in case.tags:
            grouped[f"tag:{tag}"].append((case, annotation, prediction))

    output: dict[str, dict[str, object]] = {}
    for group, rows in sorted(grouped.items()):
        route_correct = 0
        relation_correct = 0
        fixed_precision: list[float] = []
        effective_precision: list[float] = []
        returned_precision: list[float] = []
        gold_cardinality = Counter()
        projection_categories = Counter()
        for case, annotation, prediction in rows:
            route_correct += int(prediction.route in annotation.gold_routes)
            relation_correct += int(
                dict(prediction.evidence_relations) == dict(annotation.gold_evidence_relations)
            )
            gold = set(annotation.gold_evidence)
            predicted_ranked = list(dict.fromkeys(prediction.evidence_refs))
            top = predicted_ranked[:3]
            true_positive = len(gold & set(top))
            # This is a diagnostic secondary metric only.  It is not the
            # project's frozen Precision@3 Gate.
            returned_precision.append(_ratio(true_positive, len(top)) or 0.0)
            fixed_precision.append(_ratio(true_positive, 3) or 0.0)
            effective_precision.append(_ratio(true_positive, min(3, len(gold))) or 0.0)
            gold_cardinality[str(len(gold))] += 1
            projection_categories.update(project_runtime_prompt(case).category_codes)
        output[group] = {
            "cases": len(rows),
            "route_accuracy": _ratio(route_correct, len(rows)),
            "evidence_relation_accuracy": _ratio(relation_correct, len(rows)),
            "fixed_precision_at_3_mean": _mean(fixed_precision),
            "effective_precision_at_3_mean": _mean(effective_precision),
            "precision_at_returned_mean_diagnostic": _mean(returned_precision),
            "gold_evidence_cardinality": dict(sorted(gold_cardinality.items())),
            "projection_categories": dict(sorted(projection_categories.items())),
        }
    return output


def _public_sparsity(
    cases: tuple[GoldCase, ...],
    annotations: dict[str, Any],
    predictions: dict[str, Prediction],
) -> dict[str, object]:
    cardinality = Counter(len(annotations[case.case_id].gold_evidence) for case in cases)
    sparse_cases = sum(count for size, count in cardinality.items() if size < 3)
    fixed_values: list[float] = []
    effective_values: list[float] = []
    returned_values: list[float] = []
    for case in cases:
        gold = set(annotations[case.case_id].gold_evidence)
        predicted_ranked = list(dict.fromkeys(predictions[case.case_id].evidence_refs))
        predicted = set(predicted_ranked[:3])
        true_positive = len(gold & predicted)
        fixed_values.append(_ratio(true_positive, 3) or 0.0)
        effective_values.append(_ratio(true_positive, min(3, len(gold))) or 0.0)
        returned_values.append(_ratio(true_positive, len(predicted)) or 0.0)
    return {
        "cases": len(cases),
        "gold_evidence_cardinality": dict(sorted((str(k), v) for k, v in cardinality.items())),
        "gold_evidence_fewer_than_3_cases": sparse_cases,
        "gold_evidence_fewer_than_3_share": _ratio(sparse_cases, len(cases)),
        "fixed_precision_at_3_mean": _mean(fixed_values),
        "effective_precision_at_3_mean": _mean(effective_values),
        "precision_at_returned_mean_diagnostic": _mean(returned_values),
        "interpretation": (
            "固定 K=3 的分母会在 Gold 只有 1—2 条依据时产生结构性折损；"
            "这解释了公开集 Precision@3 偏低的一部分，但不改变当前项目 Gate。"
        ),
    }


def _patterns(
    *,
    public_sparsity: dict[str, object],
    public_metrics: dict[str, object],
    private_aggregate: dict[str, object] | None,
) -> list[dict[str, object]]:
    patterns: list[dict[str, object]] = [
        {
            "pattern_id": "P-METRIC-SPARSE-DENOMINATOR",
            "severity": "P0",
            "evidence": [
                f"public_gold_evidence_fewer_than_3={public_sparsity['gold_evidence_fewer_than_3_cases']}",
                f"fixed_precision_at_3_mean={public_sparsity['fixed_precision_at_3_mean']}",
                f"effective_precision_at_3_mean={public_sparsity['effective_precision_at_3_mean']}",
                f"diagnostic_precision_at_returned_mean={public_sparsity['precision_at_returned_mean_diagnostic']}",
            ],
            "diagnosis": "公开集的固定 K=3 分母与稀疏 Gold 依据数量存在测量口径张力。",
            "correction": (
                "同时报告固定分母 Precision@3、按返回条数的诊断值和按 Gold 数量分层值；"
                "不自动改 frozen project Gate。"
            ),
            "validation": "由产品负责人冻结口径后，重新运行 public 与独立 holdout。",
            "evidence_level": "observed_public",
        },
        {
            "pattern_id": "P-HOLDOUT-OUT-OF-DISTRIBUTION",
            "severity": "P0",
            "evidence": [
                "holdout_aggregate_error_case_count=17/20",
                "holdout_route_mismatch=15",
                "holdout_evidence_set_mismatch=14",
                "holdout_evidence_relation_mismatch=13",
            ],
            "diagnosis": (
                "隐藏集暴露了公开集未覆盖的表达组合或策略路由泛化问题；由于没有逐题答案，"
                "不能把某个具体原因写成事实。"
            ),
            "correction": (
                "先扩充公开 ontology/同义表达回归集，再逐次只改一个投影或检索策略；"
                "禁止读取隐藏答案反向补规则。"
            ),
            "validation": (
                "公开集 route/evidence/safety 不回退；之后只做一次无答案 holdout 聚合验证。"
            ),
            "evidence_level": "aggregate_observed_plus_inference",
        },
        {
            "pattern_id": "P-SAFETY-EVENT-NONCANONICAL",
            "severity": "P0",
            "evidence": ["private_hard_safety_gate=MANUAL_REVIEW_REQUIRED"],
            "diagnosis": "私有禁项仍是自然语言，评测器没有足够的机器事件 ID 来自动判定安全 Gate。",
            "correction": (
                "在产品负责人受限环境中把禁项映射为版本化 canonical event ID；"
                "映射表不进入被测运行包。"
            ),
            "validation": "先用合成事件做 parser/反向兼容测试，再重新进行私有聚合评分。",
            "evidence_level": "observed_private_aggregate",
        },
        {
            "pattern_id": "P-RAG-EXECUTION-BOUNDARY",
            "severity": "P0",
            "evidence": [
                f"public_hard_safety_gate={public_metrics.get('hard_safety_gate')}",
                "rag_execution_authorized=false",
                "candidate_provider_network_called=false",
            ],
            "diagnosis": "当前安全边界工作正常，不能为了提高召回而放宽 RAG 的执行权限。",
            "correction": (
                "只优化证据查询和表达归一化；权限、出站和 Provider 准入仍由确定性 Policy 独立裁决。"
            ),
            "validation": "每次候选优化必须通过注入、冲突、过期、出站拒绝和未就绪 Adapter 回归。",
            "evidence_level": "observed_public_and_runtime",
        },
    ]
    if private_aggregate is None:
        patterns.append(
            {
                "pattern_id": "P-HOLDOUT-AGGREGATE-MISSING",
                "severity": "P1",
                "evidence": ["private_aggregate_report_missing"],
                "diagnosis": "当前只具备公开集诊断，不能评估未见表达的泛化。",
                "correction": "先运行 answerless holdout，再只回流聚合结果。",
                "validation": "确认私有答案键不在项目工作区。",
                "evidence_level": "observed_runtime",
            }
        )
    return patterns


def _correction_sop() -> list[dict[str, object]]:
    return [
        {
            "step": 1,
            "name": "冻结事实快照",
            "action": (
                "保存代码版本、知识版本、public predictions、holdout aggregate 和 Trace 引用。"
            ),
            "must_not": "不读取隐藏答案，不把旧报告覆盖成新报告。",
        },
        {
            "step": 2,
            "name": "按错误层定位",
            "action": "先分开看指标口径、检索召回、证据关系、路由安全和 Provider 准入。",
            "must_not": "不把一个总分当成根因，也不让 LLM 自评替代事实。",
        },
        {
            "step": 3,
            "name": "提出单一受限修正",
            "action": "一次只改一个可解释变量，例如领域同义词归一化或 evidence packing。",
            "must_not": "不自动改权限、不自动放行新 Provider、不按 hidden 逐题答案写规则。",
        },
        {
            "step": 4,
            "name": "公开集回归",
            "action": (
                "重新跑 route/evidence/relation/排序指标和 hard-safety；任何安全回退都拒绝该修正。"
            ),
            "must_not": "不为了通过而降低阈值或删除失败题。",
        },
        {
            "step": 5,
            "name": "独立 holdout 验证",
            "action": (
                "只运行 answerless 输入并回流聚合指标；将结果作为泛化证据，不作为逐题监督信号。"
            ),
            "must_not": "不在同一 holdout 上反复试错。",
        },
        {
            "step": 6,
            "name": "人工批准与发布",
            "action": (
                "产品负责人查看失败模式、成本/延迟和风险后，决定是否把候选修正升级为现役规则。"
            ),
            "must_not": "没有批准就不改生产 Policy 或 Provider 状态。",
        },
    ]


def build_failure_analysis(
    *,
    public_cases_path: Path,
    public_annotations_path: Path,
    public_predictions_path: Path,
    private_aggregate_path: Path | None = None,
) -> dict[str, object]:
    """Build a redacted, reproducible failure-analysis snapshot."""

    dataset_version, cases = load_public_cases(public_cases_path)
    annotations = load_annotations(
        public_annotations_path,
        allowed_case_ids=[case.case_id for case in cases],
    )
    predictions = load_predictions(public_predictions_path)
    evaluation = evaluate(
        cases=cases,
        annotations=annotations,
        predictions=predictions,
        dataset_version=dataset_version,
    )
    metrics = dict(evaluation.metrics or {})
    candidate_predictions, candidate_traces = run_public_correction_candidate(cases)
    candidate_evaluation = evaluate(
        cases=cases,
        annotations=annotations,
        predictions={item.case_id: item for item in candidate_predictions},
        dataset_version=dataset_version,
    )
    candidate_metrics = dict(candidate_evaluation.metrics or {})
    comparable_metric_names = (
        "route_accuracy",
        "evidence_exact_accuracy",
        "evidence_relation_accuracy",
        "mrr",
        "recall_at_5",
        "ndcg_at_5",
        "precision_at_3",
        "precision_at_3_effective",
        "precision_at_3_returned",
    )
    metric_delta: dict[str, float | None] = {}
    for name in comparable_metric_names:
        before = metrics.get(name)
        after = candidate_metrics.get(name)
        if isinstance(before, (int, float)) and isinstance(after, (int, float)):
            metric_delta[name] = round(float(after) - float(before), 6)
        else:
            metric_delta[name] = None
    candidate_regression = {
        "version": CORRECTION_CANDIDATE_VERSION,
        "status": candidate_evaluation.status,
        "metrics": candidate_metrics,
        "delta_vs_active": metric_delta,
        "public_trace_count": len(candidate_traces),
        "trace_aggregate": {
            "normalization_applied_count": sum(
                int(trace.get("normalization_applied", False)) for trace in candidate_traces
            ),
            "route_counts": dict(
                Counter(str(trace.get("prediction_route")) for trace in candidate_traces)
            ),
            "network_called": any(trace.get("network_called", False) for trace in candidate_traces),
            "provider_api_called": any(
                trace.get("provider_api_called", False) for trace in candidate_traces
            ),
        },
        "active_baseline_changed": False,
        "promotion_decision": "not_promoted_proposal_only",
        "regression_gate": (
            "PASS"
            if all(
                candidate_metrics.get(name) == metrics.get(name)
                for name in (
                    "route_accuracy",
                    "evidence_exact_accuracy",
                    "evidence_relation_accuracy",
                    "mrr",
                    "recall_at_5",
                    "ndcg_at_5",
                    "hard_safety_gate",
                )
            )
            else "FAIL"
        ),
        "interpretation": (
            "候选只增加经审核的同义词/英文归一化；公开集结构化正确性与安全指标未回退，"
            "但它尚未改变现役 baseline，也不能据此推断隐藏集会提升。"
        ),
    }
    private_aggregate: dict[str, object] | None = None
    if private_aggregate_path is not None and private_aggregate_path.exists():
        payload = json.loads(private_aggregate_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and payload.get("scope") == "private_holdout_aggregate_only":
            private_aggregate = {
                "scope": payload.get("scope"),
                "counts": payload.get("counts", {}),
                "metrics": payload.get("metrics", {}),
                "error_type_counts": payload.get("error_type_counts", {}),
            }
    sparsity = _public_sparsity(cases, annotations, predictions)
    report: dict[str, object] = {
        "analysis_version": FAILURE_ANALYSIS_VERSION,
        "dataset_version": dataset_version,
        "scope": "public_aggregate_plus_private_aggregate_only",
        "policy": {
            "public_queries_read": True,
            "public_annotations_read": True,
            "public_predictions_read": True,
            "private_answer_key_read": False,
            "private_case_ids_emitted": False,
            "private_questions_emitted": False,
            "private_answer_facts_emitted": False,
            "llm_called": False,
            "network_called": False,
            "photo_or_face_vector_read": False,
            "provider_called": False,
            "self_correction_mode": "proposal_only",
            "precision_reporting_policy": "precision-dual-report-v0.1",
            "safety_event_id_policy": "versioned_dictionary_plus_owner_confirmation",
            "holdout_policy": "v2_historical_diagnostic_v3_independent_release_holdout",
        },
        "public": {
            "counts": dict(evaluation.counts),
            "metrics": metrics,
            "sparsity": sparsity,
            "groups": _public_group_stats(cases, annotations, predictions),
        },
        "correction_candidate": candidate_regression,
        "private_aggregate": private_aggregate,
        "patterns": _patterns(
            public_sparsity=sparsity,
            public_metrics=metrics,
            private_aggregate=private_aggregate,
        ),
        "self_correction": {
            "status": "proposal_only",
            "current_candidate": {
                "name": "rag-correction-candidate-v0.1",
                "changes": [
                    "增加领域同义词归一化，但不改变权限和 Provider 白名单",
                    "把固定 K=3 Precision 与稀疏诊断指标并列展示，不修改 project threshold gate",
                    "将所有新规则先写入公开 challenge 回归，不直接触碰 hidden key",
                ],
                "rollback": "保留现行 deterministic baseline v0.2；候选修正只以独立 profile 运行。",
            },
            "blocked_automatic_actions": [
                "按隐藏集逐题答案改规则",
                "自动降低安全或项目阈值",
                "自动把 candidate Provider 升级为 reviewed_active",
                "让 RAG 直接授予图片出站或工具调用权限",
            ],
        },
        "sop": _correction_sop(),
    }
    return report


def write_failure_analysis_report(
    report: dict[str, object], *, json_path: Path, html_path: Path
) -> None:
    """Write JSON and safe visual HTML artifacts."""

    json_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(render_failure_analysis_html(report), encoding="utf-8")


def _metric_card(label: str, value: object) -> str:
    return (
        "<div class='card'><div class='k'>"
        f"{html.escape(label)}"
        "</div><div class='v'>"
        f"{html.escape(str(value))}"
        "</div></div>"
    )


def render_failure_analysis_html(report: dict[str, object]) -> str:
    """Render an aggregate-only HTML report suitable for local review."""

    public = report.get("public", {})
    public = public if isinstance(public, dict) else {}
    metrics = public.get("metrics", {})
    metrics = metrics if isinstance(metrics, dict) else {}
    sparsity = public.get("sparsity", {})
    sparsity = sparsity if isinstance(sparsity, dict) else {}
    private = report.get("private_aggregate")
    private = private if isinstance(private, dict) else {}
    private_metrics = private.get("metrics", {})
    private_metrics = private_metrics if isinstance(private_metrics, dict) else {}
    patterns = report.get("patterns", [])
    patterns = patterns if isinstance(patterns, list) else []
    sop = report.get("sop", [])
    sop = sop if isinstance(sop, list) else []
    candidate_regression = report.get("correction_candidate", {})
    candidate_regression = candidate_regression if isinstance(candidate_regression, dict) else {}
    deltas = candidate_regression.get("delta_vs_active", {})
    deltas = deltas if isinstance(deltas, dict) else {}
    delta_rows = "".join(
        f"<tr><td>{html.escape(str(name))}</td><td>{html.escape(str(value))}</td></tr>"
        for name, value in deltas.items()
    )
    candidate_version = html.escape(str(candidate_regression.get("version", "")))
    candidate_gate = html.escape(str(candidate_regression.get("regression_gate", "")))
    candidate_decision = html.escape(
        str(candidate_regression.get("promotion_decision", "not_promoted_proposal_only"))
    )

    pattern_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('pattern_id', '')))}</td>"
        f"<td>{html.escape(str(item.get('severity', '')))}</td>"
        f"<td>{html.escape(str(item.get('diagnosis', '')))}</td>"
        f"<td>{html.escape(str(item.get('correction', '')))}</td>"
        "</tr>"
        for item in patterns
        if isinstance(item, dict)
    )
    sop_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('step', '')))}</td>"
        f"<td>{html.escape(str(item.get('name', '')))}</td>"
        f"<td>{html.escape(str(item.get('action', '')))}</td>"
        f"<td>{html.escape(str(item.get('must_not', '')))}</td>"
        "</tr>"
        for item in sop
        if isinstance(item, dict)
    )
    return f"""<!doctype html>
<html lang='zh-CN'><head><meta charset='utf-8'>
<title>RAG 优化与失败模式分析</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;
max-width:1180px;margin:30px auto;padding:0 22px;color:#17202a}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
gap:12px;margin:18px 0}}
.card{{border:1px solid #d9e2ec;border-radius:12px;padding:15px;background:#fff}}
.k{{font-size:13px;color:#5b6875}}.v{{font-size:25px;font-weight:700;margin-top:7px}}
.note{{background:#fff8e1;border-left:4px solid #f0ad00;padding:13px 16px;margin:18px 0}}
table{{border-collapse:collapse;width:100%;margin:12px 0 26px}}
th,td{{border:1px solid #d9e2ec;padding:9px;text-align:left;
vertical-align:top}}th{{background:#f5f7fa}}
code{{background:#f4f6f8;padding:2px 4px;border-radius:4px}}
</style></head><body>
<h1>RAG 优化与失败模式分析</h1>
<p class='note'>本报告只包含公开集聚合事实和私有隐藏集聚合指标；不含隐藏题干、
案例编号、Gold 答案、答案键路径、原始用户文本、图片或人脸向量。自校正模式为“只提出方案，
不自动改权限”。</p>
<div class='grid'>
{_metric_card("Public Route", metrics.get("route_accuracy"))}
{_metric_card("Public Precision@3（固定分母）", metrics.get("precision_at_3"))}
{_metric_card("Public Precision@3（覆盖式）", metrics.get("precision_at_3_effective"))}
{_metric_card("Public Precision@3（返回式）", metrics.get("precision_at_3_returned"))}
{_metric_card("Public Recall@5", metrics.get("recall_at_5"))}
{_metric_card("Public Project Gate", metrics.get("project_threshold_gate"))}
{_metric_card("Public Gold 依据少于3条", sparsity.get("gold_evidence_fewer_than_3_cases"))}
{_metric_card("Holdout Route（聚合）", private_metrics.get("route_accuracy", "未提供"))}
{_metric_card("Holdout Recall@5（聚合）", private_metrics.get("recall_at_5", "未提供"))}
{_metric_card("Holdout Project Gate", private_metrics.get("project_threshold_gate", "未提供"))}
</div>
<h2>主要失败模式</h2>
<table><thead><tr><th>模式</th><th>严重度</th><th>诊断</th><th>下一步修正</th></tr></thead><tbody>{pattern_rows}</tbody></table>
<h2>自校正 SOP</h2>
<table><thead><tr><th>步骤</th><th>名称</th><th>做什么</th><th>禁止什么</th></tr></thead><tbody>{sop_rows}</tbody></table>
<h2>本轮候选回归</h2>
<p>版本：{candidate_version}；公开回归：{candidate_gate}；推广决定：{candidate_decision}</p>
<table><thead><tr><th>指标</th><th>候选−现役 baseline</th></tr></thead>
<tbody>{delta_rows}</tbody></table>
<h2>边界</h2>
<p>公开集上的高分不能覆盖隐藏集的低泛化；隐藏集聚合只能定位方向，不能作为逐题调参标签。任何修正都必须先通过公开安全回归，再由产品负责人批准。</p>
</body></html>"""
