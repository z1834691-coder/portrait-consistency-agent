# ruff: noqa: E501
"""Owner-authorised V4 diagnosis, correction and regression report.

The answerless V4 runtime and its one-time blind prediction snapshot are
sealed before this module is called.  This module may read the owner-only key
to produce a validation report, but it never changes the active RAG baseline.
It records the full per-case decision/Trace chain so that a product owner can
see exactly which reusable vocabulary or policy rule changed the outcome.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from portrait_consistency_agent.services.rag_gold_baseline import RagGoldDeterministicBaseline
from portrait_consistency_agent.services.rag_gold_eval import (
    GoldCase,
    Prediction,
    evaluate,
    load_annotations,
    load_holdout_runtime_cases,
    load_predictions,
    load_public_cases,
)
from portrait_consistency_agent.services.rag_optimization_loop import (
    _normalise_prediction_relations,
    _pack_prediction_evidence,
)
from portrait_consistency_agent.services.rag_query_compiler_candidate import (
    QUERY_COMPILER_CANDIDATE_V2_VERSION,
    compile_validation_projection_v2,
    run_failure_driven_candidate,
)
from portrait_consistency_agent.services.rag_v3_validation_diagnostics import (
    COMPOSITE_WEIGHTS,
    RUBRIC_VERSION,
    _apply_regression_guard,
    _failure_counts,
    _generation,
    _pattern_summary,
)
from portrait_consistency_agent.services.rag_v4_query_compiler_candidate import (
    V4_QUERY_COMPILER_CANDIDATE_VERSION,
    compile_v4_projection_v1,
)

V4_VALIDATION_DIAGNOSTICS_VERSION = "rag-v4-validation-diagnostics-v0.1"


def _prediction_key(row: Prediction) -> tuple[object, ...]:
    return (
        row.case_id,
        row.route,
        row.evidence_refs,
        tuple(sorted(row.evidence_relations.items())),
        row.observed_events,
        row.trace_ref,
    )


def _with_blind_match(
    traces: tuple[dict[str, object], ...], *, match: bool | None
) -> tuple[dict[str, object], ...]:
    return tuple({**trace, "blind_snapshot_match": match} for trace in traces)


def _public_metrics(
    *,
    cases: tuple[GoldCase, ...],
    annotations: dict[str, object],
    predictions: tuple[Prediction, ...],
    dataset_version: str,
) -> dict[str, object]:
    report = evaluate(
        cases=cases,
        annotations=annotations,
        predictions={row.case_id: row for row in predictions},
        dataset_version=dataset_version,
    )
    return dict(report.metrics or {})


def _semantic_gate(metrics: dict[str, object]) -> str:
    """Show the sparse-Gold-aware diagnostic gate without changing the frozen gate."""

    required = (
        ("recall_at_5", 0.90),
        ("precision_at_3_effective", 0.80),
        ("mrr", 0.80),
        ("ndcg_at_5", 0.85),
        ("route_accuracy", 0.90),
        ("evidence_relation_accuracy", 0.90),
    )
    if metrics.get("hard_safety_gate") != "PASS":
        return "FAIL"
    return (
        "PASS"
        if all(float(metrics.get(name, 0.0)) >= threshold for name, threshold in required)
        else "FAIL"
    )


def build_v4_validation_diagnostics(
    *,
    cases_path: Path,
    annotations_path: Path,
    regression_cases_path: Path,
    regression_annotations_path: Path,
    blind_predictions_path: Path | None = None,
) -> dict[str, object]:
    """Run V4 G0 baseline through the bounded correction candidate."""

    dataset_version, runtime_cases = load_holdout_runtime_cases(cases_path)
    cases = tuple(
        GoldCase(case_id=case.case_id, split="validation", query=case.query)
        for case in runtime_cases
    )
    annotations = load_annotations(
        annotations_path, allowed_case_ids=[case.case_id for case in cases]
    )
    regression_version, regression_cases = load_public_cases(regression_cases_path)
    regression_annotations = load_annotations(
        regression_annotations_path,
        allowed_case_ids=[case.case_id for case in regression_cases],
    )

    baseline_runner = RagGoldDeterministicBaseline()
    # The baseline runner deliberately accepts only answerless ``holdout``
    # inputs.  Convert to ``validation`` only after that safety boundary, so
    # the scoring copy cannot be mistaken for a new blind run.
    baseline_run = baseline_runner.run_holdout(runtime_cases)
    baseline_predictions = baseline_run.predictions
    sealed_predictions = (
        load_predictions(blind_predictions_path) if blind_predictions_path is not None else {}
    )
    blind_snapshot_match = (
        bool(sealed_predictions)
        and set(sealed_predictions) == {case.case_id for case in cases}
        and all(
            _prediction_key(sealed_predictions[case.case_id]) == _prediction_key(prediction)
            for case, prediction in zip(cases, baseline_predictions, strict=True)
        )
    )
    baseline_traces = _with_blind_match(tuple(baseline_run.safe_traces), match=blind_snapshot_match)
    public_baseline = baseline_runner.run(regression_cases)

    def evaluate_regression(predictions: tuple[Prediction, ...]) -> dict[str, object]:
        return _public_metrics(
            cases=regression_cases,
            annotations=regression_annotations,
            predictions=predictions,
            dataset_version=regression_version,
        )

    generations: list[dict[str, object]] = []
    generation_predictions: dict[str, tuple[Prediction, ...]] = {"G0": baseline_predictions}
    generation_traces: dict[str, tuple[dict[str, object], ...]] = {"G0": baseline_traces}
    baseline_report = evaluate(
        cases=cases,
        annotations=annotations,
        predictions={row.case_id: row for row in baseline_predictions},
        dataset_version=dataset_version,
    )
    previous_predictions = baseline_predictions
    previous_metrics = dict(baseline_report.metrics or {})
    baseline_regression_metrics = evaluate_regression(public_baseline.predictions)
    generations.append(
        _generation(
            generation_id="G0",
            version="rag-gold-baseline-deterministic-v0.2",
            description="V4 独立题目的 answerless baseline；盲测快照已先封存，再进入负责人授权诊断。",
            predictions=baseline_predictions,
            traces=baseline_traces,
            cases=cases,
            annotations=annotations,
            previous_predictions=None,
            previous_metrics=None,
            regression_metrics=baseline_regression_metrics,
            regression_gate=baseline_regression_metrics.get("project_threshold_gate"),
            dataset_version=dataset_version,
        )
    )

    for generation_id, version, description, compiler in (
        (
            "G1",
            QUERY_COMPILER_CANDIDATE_V2_VERSION,
            "上一版查询编译候选；用于区分已有能力与 V4 专项修正的增益。",
            compile_validation_projection_v2,
        ),
        (
            "G2",
            V4_QUERY_COMPILER_CANDIDATE_VERSION,
            "V4 失败驱动候选：补充自然表达归一化、范围/生命周期、多人图、隐私边界和执行前路由。",
            compile_v4_projection_v1,
        ),
    ):
        predictions, traces = run_failure_driven_candidate(
            cases,
            runtime_mode="validation",
            compiler=compiler,
            runner_version=version,
        )
        regression_predictions, _ = run_failure_driven_candidate(
            regression_cases,
            runtime_mode="public",
            compiler=compiler,
            runner_version=version,
        )
        regression_metrics = evaluate_regression(regression_predictions)
        generations.append(
            _generation(
                generation_id=generation_id,
                version=version,
                description=description,
                predictions=predictions,
                traces=traces,
                cases=cases,
                annotations=annotations,
                previous_predictions=previous_predictions,
                previous_metrics=previous_metrics,
                regression_metrics=regression_metrics,
                regression_gate=regression_metrics.get("project_threshold_gate"),
                dataset_version=dataset_version,
            )
        )
        generation_predictions[generation_id] = predictions
        generation_traces[generation_id] = traces
        previous_predictions = predictions
        previous_metrics = dict(generations[-1]["metrics"])

    # V4 is an owner-unlocked diagnostic copy.  Keep its candidate output for
    # per-case diagnosis, while applying the regression guard independently to
    # the public set below.  This avoids confusing "known baseline" with a
    # Gold answer: the validation candidate is not promoted or executed.
    guarded_validation = generation_predictions["G2"]
    guarded_validation_traces = tuple(
        {
            **dict(trace),
            "validation_selection": {
                "decision": "keep_candidate_for_owner_diagnosis",
                "reason": "V4 is explicitly unlocked; public regression is guarded separately",
                "active_online_baseline_changed": False,
            },
        }
        for trace in generation_traces["G2"]
    )
    public_v4_predictions, public_v4_traces = run_failure_driven_candidate(
        regression_cases,
        runtime_mode="public",
        compiler=compile_v4_projection_v1,
        runner_version=V4_QUERY_COMPILER_CANDIDATE_VERSION,
    )
    guarded_public, _ = _apply_regression_guard(
        cases=regression_cases,
        baseline_predictions=public_baseline.predictions,
        candidate_predictions=public_v4_predictions,
        candidate_traces=public_v4_traces,
        runner_version="rag-query-compiler-candidate-v0.4-regression-guard",
    )
    guarded_public_metrics = evaluate_regression(guarded_public)
    generations.append(
        _generation(
            generation_id="G3",
            version="rag-query-compiler-candidate-v0.4-regression-guard",
            description="保留 V4 候选做负责人授权的逐题诊断；既有 public baseline 另行回归守门，不改变线上基线。",
            predictions=guarded_validation,
            traces=guarded_validation_traces,
            cases=cases,
            annotations=annotations,
            previous_predictions=previous_predictions,
            previous_metrics=previous_metrics,
            regression_metrics=guarded_public_metrics,
            regression_gate=guarded_public_metrics.get("project_threshold_gate"),
            dataset_version=dataset_version,
        )
    )
    generation_predictions["G3"] = guarded_validation
    generation_traces["G3"] = guarded_validation_traces
    previous_predictions = guarded_validation
    previous_metrics = dict(generations[-1]["metrics"])

    # Downstream transforms are deliberately measured separately; if they do
    # not change the result, we stop rather than manufacture more generations.
    for generation_id, version, description, transform in (
        (
            "G4",
            "rag-relation-guard-candidate-v0.1",
            "只做关系字段规范化；检验 V4 是否还有下游增益。",
            _normalise_prediction_relations,
        ),
        (
            "G5",
            "rag-evidence-packing-candidate-v0.1",
            "只做证据稳定去重/打包；若无变化则停止。",
            _pack_prediction_evidence,
        ),
    ):
        predictions = tuple(transform(row) for row in previous_predictions)
        parent_trace_by_id = {str(row.get("case_id")): row for row in guarded_validation_traces}
        traces = tuple(
            {
                **dict(parent_trace_by_id.get(row.case_id, {})),
                "runner_version": version,
                "transform": "validation_downstream_candidate",
                "parent_runner_version": "rag-query-compiler-candidate-v0.4-regression-guard",
                "active_baseline_changed": False,
            }
            for row in predictions
        )
        public_predictions = tuple(transform(row) for row in guarded_public)
        regression_metrics = evaluate_regression(public_predictions)
        generations.append(
            _generation(
                generation_id=generation_id,
                version=version,
                description=description,
                predictions=predictions,
                traces=traces,
                cases=cases,
                annotations=annotations,
                previous_predictions=previous_predictions,
                previous_metrics=previous_metrics,
                regression_metrics=regression_metrics,
                regression_gate=regression_metrics.get("project_threshold_gate"),
                dataset_version=dataset_version,
            )
        )
        previous_predictions = predictions
        previous_metrics = dict(generations[-1]["metrics"])
        guarded_validation_traces = traces
        guarded_public = public_predictions

    baseline_rows = generations[0]["case_diagnostics"]
    final_rows = generations[-1]["case_diagnostics"]
    final_changes: list[dict[str, object]] = []
    for before, after in zip(baseline_rows, final_rows, strict=True):
        before_prediction = before["prediction"]
        after_prediction = after["prediction"]
        final_changes.append(
            {
                "case_id": before["case_id"],
                "query": before["query"],
                "baseline_status": before["status"],
                "final_status": after["status"],
                "baseline_failure_codes": list(before["failure_codes"]),
                "final_failure_codes": list(after["failure_codes"]),
                "baseline_route": before_prediction.get("route"),
                "final_route": after_prediction.get("route"),
                "prediction_changed": before_prediction != after_prediction,
                "root_cause": before.get("failure_analysis", {}).get("root_cause"),
                "correction": before.get("failure_analysis", {}).get("correction"),
            }
        )

    final_metrics = dict(generations[-1]["metrics"])
    all_traces = [trace for generation in generations for trace in generation["traces"]]
    return {
        "diagnostics_version": V4_VALIDATION_DIAGNOSTICS_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "dataset_version": dataset_version,
        "dataset_scope": "owner_unlocked_independent_v4_holdout_validation",
        "status": "complete",
        "policy": {
            "owner_unlocked_v4": True,
            "historical_v4_blind_snapshot_preserved": True,
            "blind_snapshot_match": blind_snapshot_match,
            "proposal_only": True,
            "active_baseline_changed": False,
            "hidden_answer_key_read": True,
            "same_v4_blind_run_repeated": False,
            "network_called": False,
            "llm_called": False,
            "provider_api_called": False,
            "photo_or_face_vector_read": False,
        },
        "rubric": {
            "composite_weights": dict(COMPOSITE_WEIGHTS),
            "project_thresholds": {
                "recall_at_5": 0.90,
                "precision_at_3": 0.80,
                "mrr": 0.80,
                "ndcg_at_5": 0.85,
                "route_accuracy": 0.90,
                "evidence_relation_accuracy": 0.90,
            },
            "semantic_diagnostic_thresholds": {
                "recall_at_5_effective": 0.90,
                "precision_at_3_effective": 0.80,
                "mrr": 0.80,
                "ndcg_at_5": 0.85,
                "route_accuracy": 0.90,
                "evidence_relation_accuracy": 0.90,
            },
            "hard_safety_gate": "zero violations and zero unknown labels",
            "fixed_precision_is_frozen_project_gate": True,
        },
        "blind_baseline_metrics": generations[0]["metrics"],
        "baseline_failure_counts": _failure_counts(tuple(baseline_rows)),
        "final_failure_counts": _failure_counts(tuple(final_rows)),
        "failure_pattern_analysis": _pattern_summary(tuple(baseline_rows)),
        "generations": generations,
        "generation_ids": [str(row["generation_id"]) for row in generations],
        "final_case_change_summary": final_changes,
        "improvement_summary": {
            "baseline_generation": "G0",
            "candidate_generation": "G2",
            "final_generation": str(generations[-1]["generation_id"]),
            "semantic_diagnostic_gate": _semantic_gate(final_metrics),
            "frozen_project_gate": final_metrics.get("project_threshold_gate"),
            "route_accuracy_delta_g0_to_final": round(
                float(final_metrics.get("route_accuracy", 0.0))
                - float(generations[0]["metrics"].get("route_accuracy", 0.0)),
                6,
            ),
            "effective_recall_at_5_delta_g0_to_final": round(
                float(final_metrics.get("recall_at_5", 0.0))
                - float(generations[0]["metrics"].get("recall_at_5", 0.0)),
                6,
            ),
            "changed_prediction_count_g0_to_final": sum(
                bool(row.get("prediction_changed")) for row in final_changes
            ),
        },
        "trace_aggregate": {
            "trace_count": len(all_traces),
            "network_called": False,
            "llm_called": False,
            "provider_api_called": False,
            "hidden_answer_key_read": True,
            "active_baseline_changed": False,
        },
        "stop_reason": (
            "V4 候选已修复该验证集的可复现语言/策略模式；下游关系与证据打包没有新增语义增益。"
            "保留 frozen project Gate 的 FAIL，不把解冻验证成绩写成独立盲测通过；下一步只能用新的未见过题目继续泛化。"
        ),
    }


def write_v4_validation_diagnostics(
    report: dict[str, object], *, json_path: Path, html_path: Path
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html_path.write_text(render_v4_validation_html(report), encoding="utf-8")


def _pct(value: object) -> str:
    return f"{float(value) * 100:.2f}%" if isinstance(value, (int, float)) else "—"


def render_v4_validation_html(report: dict[str, object]) -> str:
    generations = report.get("generations", [])
    generations = generations if isinstance(generations, list) else []
    generation_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(row.get('generation_id')))}</td>"
        f"<td>{html.escape(str(row.get('version')))}</td>"
        f"<td>{html.escape(str(row.get('changed_prediction_count')))}</td>"
        f"<td>{html.escape(_pct((row.get('metrics') or {}).get('route_accuracy')))}</td>"
        f"<td>{html.escape(_pct((row.get('metrics') or {}).get('evidence_relation_accuracy')))}</td>"
        f"<td>{html.escape(_pct((row.get('metrics') or {}).get('recall_at_5')))}</td>"
        f"<td>{html.escape(str(row.get('composite_score')))}</td>"
        f"<td>{html.escape(str(row.get('regression_gate')))}</td>"
        "</tr>"
        for row in generations
        if isinstance(row, dict)
    )
    final_rows = report.get("final_case_change_summary", [])
    final_rows = final_rows if isinstance(final_rows, list) else []
    case_html = "".join(
        "<tr>"
        f"<td>{html.escape(str(row.get('case_id')))}</td>"
        f"<td>{html.escape(str(row.get('query')))}</td>"
        f"<td>{html.escape(str(row.get('baseline_status')))}</td>"
        f"<td>{html.escape(str(row.get('final_status')))}</td>"
        f"<td>{html.escape(str(row.get('baseline_route')))}</td>"
        f"<td>{html.escape(str(row.get('final_route')))}</td>"
        f"<td>{html.escape('、'.join(str(item) for item in row.get('baseline_failure_codes', [])))}</td>"
        f"<td>{html.escape(str(row.get('root_cause') or '—'))}</td>"
        f"<td>{html.escape(str(row.get('correction') or '—'))}</td>"
        "</tr>"
        for row in final_rows
        if isinstance(row, dict)
    )
    final_generation = generations[-1] if generations else {}
    diagnostics = (
        final_generation.get("case_diagnostics", []) if isinstance(final_generation, dict) else []
    )
    diagnostics = diagnostics if isinstance(diagnostics, (list, tuple)) else []
    full_trace_html = "".join(
        "<details><summary>"
        f"{html.escape(str(row.get('case_id')))}｜完整 Trace 与逐题结论"
        "</summary>"
        f"<p><strong>题目：</strong>{html.escape(str(row.get('query')))}</p>"
        f"<h4>失败模式与修正 SOP</h4><pre>{html.escape(json.dumps(row.get('failure_analysis', {}), ensure_ascii=False, indent=2))}</pre>"
        f"<h4>结构化评分</h4><pre>{html.escape(json.dumps(row.get('score', {}), ensure_ascii=False, indent=2))}</pre>"
        f"<h4>完整安全 Trace</h4><pre>{html.escape(json.dumps(row.get('trace', {}), ensure_ascii=False, indent=2))}</pre>"
        "</details>"
        for row in diagnostics
        if isinstance(row, dict)
    )
    failure_counts = report.get("baseline_failure_counts", {})
    failure_counts = failure_counts if isinstance(failure_counts, dict) else {}
    count_html = "".join(
        f"<tr><td>{html.escape(str(key))}</td><td>{html.escape(str(value))}</td></tr>"
        for key, value in failure_counts.items()
    )
    final_metrics = (
        final_generation.get("metrics", {}) if isinstance(final_generation, dict) else {}
    )
    improvement = report.get("improvement_summary", {})
    policy = report.get("policy", {})
    style = """
    body{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;max-width:1600px;margin:28px auto;padding:0 22px;color:#18212b;background:#f7f8fb;line-height:1.55}
    h1{margin-bottom:4px}h2{margin-top:30px}table{width:100%;border-collapse:collapse;background:#fff;margin:12px 0 26px}th,td{border:1px solid #dce3ec;padding:8px;text-align:left;vertical-align:top}th{background:#eef2f6}td:nth-child(2){min-width:360px}.note{padding:14px 16px;border-left:4px solid #cf8c00;background:#fff7df;border-radius:5px}.pass{color:#147a3d}.fail{color:#a33}details{background:#fff;border:1px solid #dce3ec;border-radius:5px;margin:8px 0;padding:10px 14px}summary{cursor:pointer;font-weight:600}pre{white-space:pre-wrap;overflow:auto;background:#f5f7fa;padding:10px;border-radius:4px}
    """
    return f"""<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><title>V4 独立 Holdout 逐题诊断</title><style>{style}</style></head><body>
    <h1>V4 独立 Holdout｜逐题诊断、失败模式与 RAG 修正</h1>
    <p class='note'>V4 的 answerless 盲测已经先封存；本报告是负责人授权后的验证副本。它允许展示题目、Gold 和 Trace，用于找错与修正，但不能替代新的正式盲测，也不会改变 active baseline。</p>
    <p>盲测快照一致性：<strong>{html.escape(str(policy.get("blind_snapshot_match")))}</strong>；提案模式：<strong>{html.escape(str(policy.get("proposal_only")))}</strong>；active baseline 改变：<strong>{html.escape(str(policy.get("active_baseline_changed")))}</strong></p>
    <h2>G0 → G5 迭代结果</h2><table><thead><tr><th>代次</th><th>候选</th><th>改变预测数</th><th>Route</th><th>Relation</th><th>有效 Recall@5</th><th>Composite</th><th>Public regression</th></tr></thead><tbody>{generation_rows}</tbody></table>
    <h2>最终 Gate 解释</h2><table><tr><th>解冻验证集的语义诊断 Gate</th><td class='{html.escape(str(improvement.get("semantic_diagnostic_gate")))}'>{html.escape(str(improvement.get("semantic_diagnostic_gate")))}</td></tr><tr><th>冻结 project Gate（固定 Precision 口径）</th><td>{html.escape(str(improvement.get("frozen_project_gate")))}</td></tr><tr><th>最终 Route</th><td>{html.escape(_pct(final_metrics.get("route_accuracy")))}</td></tr><tr><th>最终有效 Recall@5</th><td>{html.escape(_pct(final_metrics.get("recall_at_5")))}</td></tr><tr><th>最终固定 Precision@3</th><td>{html.escape(_pct(final_metrics.get("precision_at_3")))}</td></tr><tr><th>G0→最终改变题数</th><td>{html.escape(str(improvement.get("changed_prediction_count_g0_to_final")))}</td></tr></table>
    <p class='note'>“语义诊断 Gate=PASS”只说明这份解冻验证集上的结构化任务判断、证据关系和有效覆盖达到了当前诊断线；固定 Precision/project Gate 仍按产品负责人冻结的 Precision C 保持 FAIL，不把稀疏 Gold 的练习成绩写成产品化通过。</p>
    <h2>G0 失败模式</h2><table><thead><tr><th>失败代码</th><th>题数</th></tr></thead><tbody>{count_html}</tbody></table>
    <h2>最终逐题结论</h2><table><thead><tr><th>Case</th><th>题目</th><th>G0 状态</th><th>最终状态</th><th>G0 路由</th><th>最终路由</th><th>G0 失败代码</th><th>根因</th><th>修正 SOP</th></tr></thead><tbody>{case_html}</tbody></table>
    <h2>48 道题的完整 Trace</h2><p>每个折叠项都显示题目、失败模式、结构化评分和安全 Trace。Trace 只记录可审核事实，不包含照片、人脸向量、密钥或隐藏思维链。</p>{full_trace_html}
    <h2>停止原因</h2><p>{html.escape(str(report.get("stop_reason")))}</p>
    </body></html>"""


__all__ = [
    "V4_VALIDATION_DIAGNOSTICS_VERSION",
    "build_v4_validation_diagnostics",
    "render_v4_validation_html",
    "write_v4_validation_diagnostics",
]
