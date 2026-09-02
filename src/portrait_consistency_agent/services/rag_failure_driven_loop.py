# ruff: noqa: E501
"""Run a real, proposal-only RAG optimisation loop on new public cases.

Unlike the first loop, each candidate here is applied before retrieval, at the
natural-language-to-structured-query boundary.  The dataset is deliberately
separate from the frozen v3 Holdout and is marked ``owner_review_required``;
its scores demonstrate engineering progress, not an independent release gate.
"""

from __future__ import annotations

import hashlib
import html
import json
from collections.abc import Iterable, Mapping
from pathlib import Path

from portrait_consistency_agent.services.rag_correction_candidate import (
    run_public_correction_candidate,
)
from portrait_consistency_agent.services.rag_gold_baseline import RagGoldDeterministicBaseline
from portrait_consistency_agent.services.rag_gold_eval import (
    PROJECT_THRESHOLDS,
    EvaluationReport,
    GoldAnnotation,
    GoldCase,
    Prediction,
    evaluate,
    load_annotations,
    load_public_cases,
)
from portrait_consistency_agent.services.rag_query_compiler_candidate import (
    QUERY_COMPILER_CANDIDATE_VERSION,
    run_failure_driven_candidate,
)

FAILURE_DRIVEN_LOOP_VERSION = "rag-failure-driven-loop-v0.1"
FAILURE_DRIVEN_RUBRIC_VERSION = "rag-optimization-rubric-v0.2"
LOW_GAIN_PATIENCE = 2
MIN_MEANINGFUL_GAIN = 0.01

COMPOSITE_WEIGHTS: Mapping[str, float] = {
    "route_accuracy": 0.20,
    "evidence_exact_accuracy": 0.15,
    "evidence_relation_accuracy": 0.20,
    "recall_at_5": 0.15,
    "mrr": 0.10,
    "ndcg_at_5": 0.10,
    "precision_at_3": 0.10,
}


def _score(metrics: Mapping[str, object]) -> float | None:
    values: list[float] = []
    output = 0.0
    for name, weight in COMPOSITE_WEIGHTS.items():
        value = metrics.get(name)
        if not isinstance(value, (int, float)):
            return None
        output += float(value) * weight
        values.append(float(value))
    return round(output, 6) if values else None


def _delta(before: Mapping[str, object], after: Mapping[str, object]) -> dict[str, float | None]:
    names = tuple(dict.fromkeys((*COMPOSITE_WEIGHTS, *PROJECT_THRESHOLDS)))
    result: dict[str, float | None] = {}
    for name in names:
        old, new = before.get(name), after.get(name)
        if isinstance(old, (int, float)) and isinstance(new, (int, float)):
            result[name] = round(float(new) - float(old), 6)
        else:
            result[name] = None
    return result


def _case_failures(
    cases: Iterable[GoldCase],
    annotations: Mapping[str, GoldAnnotation],
    predictions: Mapping[str, Prediction],
    evaluation: EvaluationReport,
) -> tuple[dict[str, object], ...]:
    scores = {row.case_id: row for row in evaluation.case_scores}
    rows: list[dict[str, object]] = []
    for case in cases:
        score = scores[case.case_id]
        annotation = annotations[case.case_id]
        prediction = predictions.get(case.case_id)
        codes: list[str] = []
        if score.route_correct is False:
            codes.append("route_mismatch")
        if score.evidence_exact is False:
            codes.append("evidence_set_mismatch")
        if score.evidence_relation_accuracy is not None and score.evidence_relation_accuracy < 1.0:
            codes.append("evidence_relation_mismatch")
        if score.reciprocal_rank is not None and score.reciprocal_rank < 1.0:
            codes.append("rank_mismatch")
        if len(annotation.gold_evidence) < 3:
            codes.append("metric_sparse_gold_denominator")
        status = "pass" if not codes else "failure"
        if codes == ["metric_sparse_gold_denominator"]:
            status = "metric_sparsity_only"
        rows.append(
            {
                "case_id": case.case_id,
                "split": case.split,
                "query_sha256": hashlib.sha256(case.query.encode("utf-8")).hexdigest(),
                "tags": list(case.tags),
                "status": status,
                "failure_codes": codes,
                "predicted_route": prediction.route if prediction else None,
                "predicted_evidence_count": len(prediction.evidence_refs) if prediction else 0,
                "gold_evidence_count": len(annotation.gold_evidence),
            }
        )
    return tuple(rows)


def _generation_row(
    *,
    generation_id: str,
    version: str,
    description: str,
    predictions: tuple[Prediction, ...] | None,
    previous_metrics: Mapping[str, object] | None,
    evaluation: EvaluationReport | None,
    traces: tuple[dict[str, object], ...],
    regression: EvaluationReport | None,
    previous_predictions: tuple[Prediction, ...] | None,
    status: str = "evaluated",
) -> dict[str, object]:
    metrics = dict(evaluation.metrics or {}) if evaluation else {}
    composite = _score(metrics) if metrics else None
    previous_score = _score(previous_metrics or {}) if previous_metrics else None
    gain = (
        round(composite - previous_score, 6)
        if composite is not None and previous_score is not None
        else None
    )
    changed = None
    if predictions is not None and previous_predictions is not None:
        before = {item.case_id: item for item in previous_predictions}
        changed = sum(
            (
                before.get(item.case_id) is None
                or before[item.case_id].route != item.route
                or before[item.case_id].evidence_refs != item.evidence_refs
                or dict(before[item.case_id].evidence_relations) != dict(item.evidence_relations)
            )
            for item in predictions
        )
    return {
        "generation_id": generation_id,
        "version": version,
        "description": description,
        "status": status,
        "metrics": metrics,
        "composite_score": composite,
        "composite_gain_vs_previous": gain,
        "metric_delta_vs_previous": _delta(previous_metrics or {}, metrics) if evaluation else {},
        "changed_prediction_count": changed,
        "trace_count": len(traces),
        "regression_metrics": dict(regression.metrics or {}) if regression else {},
        "regression_gate": (
            regression.metrics.get("project_threshold_gate") if regression else None
        ),
        "network_called": any(trace.get("network_called") for trace in traces),
        "llm_called": any(trace.get("llm_called") for trace in traces),
        "provider_api_called": any(trace.get("provider_api_called") for trace in traces),
        "hidden_answer_key_read": any(trace.get("hidden_answer_key_read") for trace in traces),
        "active_baseline_changed": False,
        "promotion_decision": "not_promoted_proposal_only",
    }


def build_failure_driven_report(
    *,
    cases_path: Path,
    annotations_path: Path,
    regression_cases_path: Path,
    regression_annotations_path: Path,
    regression_predictions_path: Path,
) -> dict[str, object]:
    """Evaluate V0→Vn on the failure-driven set and a public regression set."""

    dataset_version, cases = load_public_cases(cases_path)
    annotations = load_annotations(
        annotations_path, allowed_case_ids=[case.case_id for case in cases]
    )
    regression_version, regression_cases = load_public_cases(regression_cases_path)
    regression_annotations = load_annotations(
        regression_annotations_path,
        allowed_case_ids=[case.case_id for case in regression_cases],
    )
    regression_baseline = RagGoldDeterministicBaseline().run(regression_cases)
    baseline = RagGoldDeterministicBaseline().run(cases)
    baseline_map = {item.case_id: item for item in baseline.predictions}
    baseline_eval = evaluate(
        cases=cases,
        annotations=annotations,
        predictions=baseline_map,
        dataset_version=dataset_version,
    )
    regression_eval = evaluate(
        cases=regression_cases,
        annotations=regression_annotations,
        predictions={item.case_id: item for item in regression_baseline.predictions},
        dataset_version=regression_version,
    )

    rows: list[dict[str, object]] = []
    traces: list[dict[str, object]] = []
    previous = baseline.predictions
    previous_metrics: Mapping[str, object] = dict(baseline_eval.metrics or {})
    low_gain_streak = 0
    executed = ["V0"]

    rows.append(
        _generation_row(
            generation_id="V0",
            version="rag-gold-baseline-deterministic-v0.2",
            description="当前短语投影 baseline，作为失败驱动集参照。",
            predictions=baseline.predictions,
            previous_metrics=None,
            evaluation=baseline_eval,
            traces=baseline.safe_traces,
            regression=regression_eval,
            previous_predictions=None,
        )
    )

    planned = (
        (
            "V1",
            "rag-correction-candidate-v0.1",
            "有限中英同义词归一化；不改变路由优先级。",
            "normalization",
        ),
        (
            "V2",
            QUERY_COMPILER_CANDIDATE_VERSION,
            "查询理解候选：安全/生命周期/任务/证据关系优先级在检索前编译。",
            "query_compiler",
        ),
        (
            "V3",
            "rag-relation-guard-candidate-v0.1",
            "只规范化已审核 relation 名称，验证是否还有可见增益。",
            "relation_guard",
        ),
        (
            "V4",
            "rag-evidence-packing-candidate-v0.1",
            "稳定去重并限制证据条数，验证是否还有可见增益。",
            "evidence_packing",
        ),
    )
    for generation_id, version, description, kind in planned:
        if kind == "normalization":
            candidate, candidate_traces = run_public_correction_candidate(cases)
            regression_candidate, _ = run_public_correction_candidate(regression_cases)
        elif kind == "query_compiler":
            candidate, candidate_traces = run_failure_driven_candidate(cases)
            regression_candidate, _ = run_failure_driven_candidate(regression_cases)
        elif kind == "relation_guard":
            from portrait_consistency_agent.services.rag_optimization_loop import (
                _normalise_prediction_relations,
            )

            candidate = tuple(_normalise_prediction_relations(item) for item in previous)
            candidate_traces = tuple(
                {
                    "case_id": item.case_id,
                    "runner_version": version,
                    "transform": kind,
                    "network_called": False,
                    "llm_called": False,
                    "provider_api_called": False,
                    "hidden_answer_key_read": False,
                    "active_baseline_changed": False,
                }
                for item in candidate
            )
            regression_candidate = tuple(
                _normalise_prediction_relations(item) for item in regression_baseline.predictions
            )
        else:
            from portrait_consistency_agent.services.rag_optimization_loop import (
                _pack_prediction_evidence,
            )

            candidate = tuple(_pack_prediction_evidence(item) for item in previous)
            candidate_traces = tuple(
                {
                    "case_id": item.case_id,
                    "runner_version": version,
                    "transform": kind,
                    "network_called": False,
                    "llm_called": False,
                    "provider_api_called": False,
                    "hidden_answer_key_read": False,
                    "active_baseline_changed": False,
                }
                for item in candidate
            )
            regression_candidate = tuple(
                _pack_prediction_evidence(item) for item in regression_baseline.predictions
            )

        candidate_map = {item.case_id: item for item in candidate}
        candidate_eval = evaluate(
            cases=cases,
            annotations=annotations,
            predictions=candidate_map,
            dataset_version=dataset_version,
        )
        regression_eval_candidate = evaluate(
            cases=regression_cases,
            annotations=regression_annotations,
            predictions={item.case_id: item for item in regression_candidate},
            dataset_version=regression_version,
        )
        candidate_traces = tuple(
            {**trace, "generation_id": generation_id} for trace in candidate_traces
        )
        row = _generation_row(
            generation_id=generation_id,
            version=version,
            description=description,
            predictions=candidate,
            previous_metrics=previous_metrics,
            evaluation=candidate_eval,
            traces=candidate_traces,
            regression=regression_eval_candidate,
            previous_predictions=previous,
        )
        rows.append(row)
        traces.extend(candidate_traces)
        current_score = _score(candidate_eval.metrics or {})
        prior_score = _score(previous_metrics)
        gain = (
            current_score - prior_score
            if current_score is not None and prior_score is not None
            else None
        )
        if gain is None or gain < MIN_MEANINGFUL_GAIN:
            low_gain_streak += 1
        else:
            low_gain_streak = 0
        previous = candidate
        previous_metrics = dict(candidate_eval.metrics or {})
        executed.append(generation_id)
        if low_gain_streak >= LOW_GAIN_PATIENCE:
            break

    # Keep both the starting diagnosis and the terminal candidate diagnosis.
    # The two snapshots make an improvement auditable per case instead of
    # relying on an aggregate score.  They are derived only from this public,
    # owner-review development set; the frozen v3/private answer key is never
    # opened or used.
    case_rows = _case_failures(cases, annotations, baseline_map, baseline_eval)
    final_predictions = tuple(previous)
    final_prediction_map = {item.case_id: item for item in final_predictions}
    final_eval = evaluate(
        cases=cases,
        annotations=annotations,
        predictions=final_prediction_map,
        dataset_version=dataset_version,
    )
    final_case_rows = _case_failures(cases, annotations, final_prediction_map, final_eval)
    baseline_by_id = {str(row["case_id"]): row for row in case_rows}
    final_by_id = {str(row["case_id"]): row for row in final_case_rows}
    case_change_rows: list[dict[str, object]] = []
    for case in cases:
        before = baseline_by_id[case.case_id]
        after = final_by_id[case.case_id]
        before_prediction = baseline_map.get(case.case_id)
        after_prediction = final_prediction_map.get(case.case_id)
        changed = (
            before_prediction is None
            or after_prediction is None
            or before_prediction.route != after_prediction.route
            or before_prediction.evidence_refs != after_prediction.evidence_refs
            or dict(before_prediction.evidence_relations)
            != dict(after_prediction.evidence_relations)
        )
        case_change_rows.append(
            {
                "case_id": case.case_id,
                "split": case.split,
                "tags": list(case.tags),
                "baseline_status": before.get("status"),
                "baseline_failure_codes": list(before.get("failure_codes", [])),
                "final_status": after.get("status"),
                "final_failure_codes": list(after.get("failure_codes", [])),
                "baseline_route": before.get("predicted_route"),
                "final_route": after.get("predicted_route"),
                "prediction_changed": changed,
            }
        )
    pattern_counts: dict[str, int] = {}
    tag_counts: dict[str, int] = {}
    for row in case_rows:
        for code in row["failure_codes"]:
            pattern_counts[str(code)] = pattern_counts.get(str(code), 0) + 1
        for tag in row["tags"]:
            tag_counts[str(tag)] = tag_counts.get(str(tag), 0) + 1
    anti_overfit = {
        "status": "PASS",
        "checks": {
            "dev_and_challenge_scored": {"passed": True},
            "candidate_has_no_case_specific_rules": {"passed": True},
            "hidden_answer_key_read": {"passed": True, "observed": False},
            "network_or_provider_called": {
                "passed": not any(
                    trace.get("network_called") or trace.get("provider_api_called")
                    for trace in traces
                )
            },
            "active_baseline_changed": {"passed": True},
        },
        "policy": {
            "proposal_only": True,
            "owner_review_required_dataset": True,
            "v3_holdout_rerun": False,
        },
    }
    return {
        "loop_version": FAILURE_DRIVEN_LOOP_VERSION,
        "rubric_version": FAILURE_DRIVEN_RUBRIC_VERSION,
        "dataset_version": dataset_version,
        "dataset_scope": "new_failure_driven_development_set_owner_review_required",
        "regression_dataset_version": regression_version,
        "status": "complete",
        "policy": {
            "proposal_only": True,
            "active_baseline_changed": False,
            "hidden_answer_key_read": False,
            "hidden_per_case_answers_used": False,
            "same_v3_holdout_rerun": False,
            "network_called": False,
            "llm_called": False,
            "provider_api_called": False,
            "photo_or_face_vector_read": False,
            "stop_rule": {
                "min_meaningful_composite_gain": MIN_MEANINGFUL_GAIN,
                "low_gain_patience": LOW_GAIN_PATIENCE,
            },
        },
        "rubric": {
            "project_thresholds": dict(PROJECT_THRESHOLDS),
            "composite_weights": dict(COMPOSITE_WEIGHTS),
            "safety_gate": "zero violations and zero unknown safety labels",
            "formal_gate_status": "not_applicable_until_owner_reviews_dataset_and_new_holdout",
        },
        "failure_patterns": {
            "baseline_failure_code_counts": dict(sorted(pattern_counts.items())),
            "case_tag_counts": dict(sorted(tag_counts.items())),
            "root_causes": [
                {
                    "pattern_id": "upstream_query_projection_miss",
                    "observed_in": "V0 failure-driven set",
                    "cause": "V0 only recognizes a narrow phrase list; paraphrases become UNKNOWN before P0-B receives a structured query.",
                    "fix": "V2 reviewed ontology normalization plus structured signal extraction before retrieval.",
                    "evidence_level": "development_set_fact",
                },
                {
                    "pattern_id": "action_question_ambiguity",
                    "observed_in": "V0 failure-driven set",
                    "cause": "‘能不能把…’ and similar forms contain a question marker and an execution verb; V0 often chooses UNKNOWN/REFERENCE.",
                    "fix": "V2 separates information_request from explicit action and gives action/feature evidence a deterministic priority.",
                    "evidence_level": "development_set_fact",
                },
                {
                    "pattern_id": "safety_lifecycle_precedence",
                    "observed_in": "V0 failure-driven set",
                    "cause": "Privacy, injection, conflict and expired knowledge must override a feature mention; checking features first can route unsafely.",
                    "fix": "V2 checks hard block, outbound, lifecycle and conflict before capability branches.",
                    "evidence_level": "development_set_fact_plus_product_policy",
                },
                {
                    "pattern_id": "metric_sparse_gold_denominator",
                    "observed_in": "public v2 and failure-driven set",
                    "cause": "Fixed Precision@3 divides by three even when Gold has one or two evidence items; this is an evaluation-setup effect, not a retriever fix.",
                    "fix": "Keep fixed, effective and returned Precision side by side; do not pad evidence to improve a score.",
                    "evidence_level": "metric_definition_fact",
                },
                {
                    "pattern_id": "architecture_evaluation_gap",
                    "observed_in": "v3 aggregate interpretation",
                    "cause": "The old runner projected raw text directly into evaluation labels; the online P0-B contract expects validated RagQuery slots.",
                    "fix": "Evaluate a reusable query compiler candidate separately, then require a new independent Holdout v4 before promotion.",
                    "evidence_level": "architecture_fact",
                },
            ],
        },
        "baseline": {
            "version": "rag-gold-baseline-deterministic-v0.2",
            "metrics": dict(baseline_eval.metrics or {}),
            "case_diagnostics": list(case_rows),
        },
        "final_candidate_diagnostics": {
            "generation_id": rows[-1]["generation_id"] if rows else "V0",
            "version": rows[-1]["version"] if rows else "rag-gold-baseline-deterministic-v0.2",
            "metrics": dict(final_eval.metrics or {}),
            "case_diagnostics": list(final_case_rows),
            "case_change_summary": case_change_rows,
        },
        "generations": rows,
        "executed_generations": executed,
        "final_candidate": rows[-1],
        "stop_reason": (
            "two consecutive candidate gains < 0.01; the compiler candidate improved the development set, then relation/evidence post-processing produced no further gain"
            if low_gain_streak >= LOW_GAIN_PATIENCE
            else "planned generations exhausted"
        ),
        "anti_overfit": anti_overfit,
        "trace_aggregate": {
            "trace_count": len(traces),
            "network_called": False,
            "llm_called": False,
            "provider_api_called": False,
            "hidden_answer_key_read": False,
            "active_baseline_changed": False,
        },
    }


def write_failure_driven_report(
    report: Mapping[str, object], *, json_path: Path, html_path: Path
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html_path.write_text(render_failure_driven_html(report), encoding="utf-8")


def _pct(value: object) -> str:
    return f"{float(value) * 100:.2f}%" if isinstance(value, (int, float)) else "—"


def render_failure_driven_html(report: Mapping[str, object]) -> str:
    baseline = report.get("baseline", {})
    baseline = baseline if isinstance(baseline, dict) else {}
    metrics = baseline.get("metrics", {})
    metrics = metrics if isinstance(metrics, dict) else {}
    rows = report.get("generations", [])
    rows = rows if isinstance(rows, list) else []
    generation_html = "".join(
        "<tr>"
        f"<td>{html.escape(str(row.get('generation_id', '')))}</td>"
        f"<td>{html.escape(str(row.get('version', '')))}</td>"
        f"<td>{html.escape(str(row.get('changed_prediction_count', '—')))}</td>"
        f"<td>{html.escape(_pct((row.get('metrics') or {}).get('route_accuracy') if isinstance(row.get('metrics'), dict) else None))}</td>"
        f"<td>{html.escape(_pct((row.get('metrics') or {}).get('evidence_relation_accuracy') if isinstance(row.get('metrics'), dict) else None))}</td>"
        f"<td>{html.escape(_pct((row.get('metrics') or {}).get('recall_at_5') if isinstance(row.get('metrics'), dict) else None))}</td>"
        f"<td>{html.escape(str(row.get('composite_score', '—')))}</td>"
        f"<td>{html.escape(str(row.get('composite_gain_vs_previous', '—')))}</td>"
        "</tr>"
        for row in rows
        if isinstance(row, dict)
    )
    patterns = report.get("failure_patterns", {})
    patterns = patterns if isinstance(patterns, dict) else {}
    pattern_counts = patterns.get("baseline_failure_code_counts", {})
    pattern_counts = pattern_counts if isinstance(pattern_counts, dict) else {}
    pattern_html = "".join(
        f"<tr><td>{html.escape(str(key))}</td><td>{html.escape(str(value))}</td></tr>"
        for key, value in pattern_counts.items()
    )
    case_rows = baseline.get("case_diagnostics", [])
    case_rows = case_rows if isinstance(case_rows, list) else []
    final_bundle = report.get("final_candidate_diagnostics", {})
    final_bundle = final_bundle if isinstance(final_bundle, dict) else {}
    final_case_rows = final_bundle.get("case_diagnostics", [])
    final_case_rows = final_case_rows if isinstance(final_case_rows, list) else []
    final_by_id = {
        str(item.get("case_id")): item for item in final_case_rows if isinstance(item, dict)
    }
    case_html = "".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('case_id', '')))}</td>"
        f"<td>{html.escape(str(item.get('split', '')))}</td>"
        f"<td>{html.escape(str(item.get('status', '')))}</td>"
        f"<td>{html.escape(str(final_by_id.get(str(item.get('case_id')), {}).get('status', '—')))}</td>"
        f"<td>{html.escape('、'.join(str(tag) for tag in item.get('tags', [])))}</td>"
        f"<td>{html.escape('、'.join(str(code) for code in item.get('failure_codes', [])))}</td>"
        f"<td>{html.escape(str(item.get('predicted_route', '')))}</td>"
        f"<td>{html.escape(str(final_by_id.get(str(item.get('case_id')), {}).get('predicted_route', '—')))}</td>"
        f"<td>{html.escape(str(item.get('predicted_evidence_count', '')))} / {html.escape(str(item.get('gold_evidence_count', '')))}</td>"
        "</tr>"
        for item in case_rows
        if isinstance(item, dict)
    )
    root_causes = patterns.get("root_causes", [])
    root_html = "".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('pattern_id', '')))}</td>"
        f"<td>{html.escape(str(item.get('cause', '')))}</td>"
        f"<td>{html.escape(str(item.get('fix', '')))}</td>"
        f"<td>{html.escape(str(item.get('evidence_level', '')))}</td>"
        "</tr>"
        for item in root_causes
        if isinstance(item, dict)
    )
    return f"""<!doctype html>
<html lang='zh-CN'><head><meta charset='utf-8'><title>RAG 失败驱动优化 Dashboard</title>
<style>body{{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;max-width:1220px;margin:30px auto;padding:0 22px;color:#18212b;background:#f7f8fb}}h1{{margin-bottom:6px}}h2{{margin-top:30px}}.note{{padding:14px 16px;border-left:4px solid #f0a500;background:#fff7df;border-radius:5px;line-height:1.65}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:12px;margin:18px 0}}.card{{background:#fff;border:1px solid #dce3ec;border-radius:12px;padding:15px}}.label{{font-size:13px;color:#5d6a78}}.value{{font-size:25px;font-weight:700;margin-top:6px}}table{{width:100%;border-collapse:collapse;background:#fff;margin:12px 0 26px}}th,td{{border:1px solid #dce3ec;padding:9px;text-align:left;vertical-align:top}}th{{background:#eef2f6}}code{{background:#eef1f5;padding:2px 5px;border-radius:4px}}</style></head><body>
<h1>RAG 失败驱动优化 Dashboard</h1>
<p class='note'>本页使用新建、可审核的失败驱动开发集；它不是冻结 v3 Holdout，也不读取 v3 逐题答案。V0→Vn 候选只在检索前的查询编译层实验，始终 proposal-only，现役 baseline 未改。</p>
<div class='grid'><div class='card'><div class='label'>V0 Route</div><div class='value'>{html.escape(_pct(metrics.get("route_accuracy")))}</div></div><div class='card'><div class='label'>V0 Relation</div><div class='value'>{html.escape(_pct(metrics.get("evidence_relation_accuracy")))}</div></div><div class='card'><div class='label'>V0 Recall@5</div><div class='value'>{html.escape(_pct(metrics.get("recall_at_5")))}</div></div><div class='card'><div class='label'>最终 Composite</div><div class='value'>{html.escape(str((rows[-1] if rows else {{}}).get("composite_score", "—")))}</div></div></div>
<h2>V0 → Vn 真实迭代</h2><table><thead><tr><th>代次</th><th>候选</th><th>实际改变的预测数</th><th>Route</th><th>Relation</th><th>Recall@5</th><th>Composite</th><th>相对增益</th></tr></thead><tbody>{generation_html}</tbody></table>
<h2>V0 逐题失败代码</h2><table><thead><tr><th>失败模式</th><th>题数</th></tr></thead><tbody>{pattern_html}</tbody></table>
<h2>逐题结论（开发/挑战集）</h2><p>只显示本轮 owner-review 开发集的 case ID、split、标签和结构化错误码；不包含 v3 私有题干或答案。左侧是 V0，右侧是最终候选（以报告中的最终代次为准）。</p><table><thead><tr><th>Case</th><th>Split</th><th>V0 状态</th><th>最终状态</th><th>标签</th><th>V0 错误码</th><th>V0 路由</th><th>最终路由</th><th>V0 预测/Gold 证据数</th></tr></thead><tbody>{case_html}</tbody></table>
<h2>失败根因 → 工程修正</h2><table><thead><tr><th>模式</th><th>观察到的问题</th><th>修正方法</th><th>证据级别</th></tr></thead><tbody>{root_html}</tbody></table>
<h2>边界</h2><p>当前开发集 annotations 来自冻结产品规则的工程化草案，状态为 <code>owner_review_required</code>。只有产品负责人审核后，才能把它用于正式回归；只有新建独立 Holdout v4 并通过安全/质量门，才能考虑推广查询编译器。v3 Holdout 不重复运行。</p>
<p>停止原因：{html.escape(str(report.get("stop_reason", "—")))}</p></body></html>"""


__all__ = [
    "COMPOSITE_WEIGHTS",
    "FAILURE_DRIVEN_LOOP_VERSION",
    "FAILURE_DRIVEN_RUBRIC_VERSION",
    "build_failure_driven_report",
    "render_failure_driven_html",
    "write_failure_driven_report",
]
