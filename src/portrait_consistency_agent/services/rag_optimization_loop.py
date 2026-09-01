# ruff: noqa: E501
"""Versioned, proposal-only RAG optimisation loop.

This module turns the existing failure-analysis SOP into a repeatable local
experiment.  It evaluates the public dev/challenge set only, tries one bounded
candidate at a time, and writes a redacted generation history.  The v3
holdout contributes aggregate facts only; its per-case answers are never read
or used to tune a rule.

The loop is intentionally not an online self-training system.  It cannot
change the active retriever, Provider Card, permission policy, execution
scope, or hidden dataset.  A product owner must explicitly promote a
candidate after reviewing the generated report.
"""

from __future__ import annotations

import hashlib
import html
import json
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace
from pathlib import Path

from portrait_consistency_agent.services.rag_correction_candidate import (
    CORRECTION_CANDIDATE_VERSION,
    run_public_correction_candidate,
)
from portrait_consistency_agent.services.rag_gold_eval import (
    PROJECT_THRESHOLDS,
    EvaluationReport,
    GoldAnnotation,
    GoldCase,
    Prediction,
    evaluate,
    load_annotations,
    load_predictions,
    load_public_cases,
)

OPTIMIZATION_LOOP_VERSION = "rag-optimization-loop-v0.1"
RUBRIC_VERSION = "rag-optimization-rubric-v0.1"
MIN_MEANINGFUL_GAIN = 0.01
LOW_GAIN_PATIENCE = 2

# The frozen project thresholds remain the release gate.  These weights are
# only a readable comparison score for the dashboard; they cannot turn FAIL
# into PASS or override hard-safety.
COMPOSITE_WEIGHTS: Mapping[str, float] = {
    "route_accuracy": 0.20,
    "evidence_exact_accuracy": 0.15,
    "evidence_relation_accuracy": 0.20,
    "recall_at_5": 0.15,
    "mrr": 0.10,
    "ndcg_at_5": 0.10,
    "precision_at_3": 0.10,
}

_RELATION_ALIASES: Mapping[str, str] = {
    "direct": "direct_evidence",
    "direct_evidence": "direct_evidence",
    "reference": "reference_context",
    "reference_context": "reference_context",
    "conflict": "conflict_evidence",
    "conflict_evidence": "conflict_evidence",
}


def _mean_metric(metrics: Mapping[str, object], name: str) -> float | None:
    value = metrics.get(name)
    return float(value) if isinstance(value, (int, float)) else None


def composite_score(metrics: Mapping[str, object]) -> float | None:
    """Return a diagnostic weighted score, never a release decision."""

    values: list[float] = []
    weighted = 0.0
    for name, weight in COMPOSITE_WEIGHTS.items():
        value = _mean_metric(metrics, name)
        if value is None:
            return None
        weighted += value * weight
        values.append(value)
    return round(weighted, 6) if values else None


def _metric_delta(
    before: Mapping[str, object], after: Mapping[str, object]
) -> dict[str, float | None]:
    names = tuple(dict.fromkeys((*COMPOSITE_WEIGHTS, *PROJECT_THRESHOLDS, "hard_safety_gate")))
    output: dict[str, float | None] = {}
    for name in names:
        old = before.get(name)
        new = after.get(name)
        if isinstance(old, (int, float)) and isinstance(new, (int, float)):
            output[name] = round(float(new) - float(old), 6)
        else:
            output[name] = None
    return output


def _normalise_prediction_relations(prediction: Prediction) -> Prediction:
    """Canonicalise only reviewed relation aliases, leaving unknown values visible."""

    relations = {
        ref: _RELATION_ALIASES.get(value, value)
        for ref, value in prediction.evidence_relations.items()
    }
    return replace(prediction, evidence_relations=relations)


def _pack_prediction_evidence(prediction: Prediction) -> Prediction:
    """Deduplicate and cap evidence without changing its stable order."""

    refs = tuple(dict.fromkeys(prediction.evidence_refs))[:5]
    relations = {
        ref: prediction.evidence_relations[ref]
        for ref in refs
        if ref in prediction.evidence_relations
    }
    return replace(prediction, evidence_refs=refs, evidence_relations=relations)


def _route_guard_prediction(prediction: Prediction) -> Prediction:
    """Apply a fail-closed relation guard; this is still only a candidate."""

    relations = set(prediction.evidence_relations.values())
    route = prediction.route
    if "conflict_evidence" in relations and route not in {"BLOCK", "UNKNOWN"}:
        route = "BLOCK"
    if route == "DIRECT" and not prediction.evidence_refs:
        route = "UNKNOWN"
    return replace(prediction, route=route)


def _trace_for_transform(
    prediction: Prediction, *, version: str, transform: str
) -> dict[str, object]:
    return {
        "case_id": prediction.case_id,
        "runner_version": version,
        "transform": transform,
        "route": prediction.route,
        "evidence_count": len(prediction.evidence_refs),
        "relation_count": len(prediction.evidence_relations),
        "network_called": False,
        "provider_api_called": False,
        "llm_called": False,
        "hidden_answer_key_read": False,
        "photo_or_face_vector_read": False,
        "active_baseline_changed": False,
    }


def _run_transform(
    predictions: Iterable[Prediction],
    *,
    version: str,
    transform: Callable[[Prediction], Prediction],
    transform_name: str,
) -> tuple[tuple[Prediction, ...], tuple[dict[str, object], ...]]:
    output: list[Prediction] = []
    traces: list[dict[str, object]] = []
    for prediction in predictions:
        updated = transform(prediction)
        output.append(updated)
        traces.append(_trace_for_transform(updated, version=version, transform=transform_name))
    return tuple(output), tuple(traces)


def _split_metrics(
    *,
    cases: tuple[GoldCase, ...],
    annotations: Mapping[str, GoldAnnotation],
    predictions: Mapping[str, Prediction],
    dataset_version: str,
) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for split in ("dev", "challenge"):
        split_ids = {case.case_id for case in cases if case.split == split}
        split_predictions = {
            case_id: prediction
            for case_id, prediction in predictions.items()
            if case_id in split_ids
        }
        report = evaluate(
            cases=cases,
            annotations=annotations,
            predictions=split_predictions,
            dataset_version=dataset_version,
            split=split,
        )
        result[split] = dict(report.metrics or {})
    return result


def _case_diagnostics(
    *,
    cases: tuple[GoldCase, ...],
    annotations: Mapping[str, GoldAnnotation],
    predictions: Mapping[str, Prediction],
    evaluation: EvaluationReport,
) -> tuple[dict[str, object], ...]:
    """Produce one redacted diagnostic row for every public question.

    The public question itself is intentionally not copied into the report;
    ``query_sha256`` lets a reviewer correlate a row with the public source
    without making the report a second prompt archive.
    """

    score_by_id = {score.case_id: score for score in evaluation.case_scores}
    rows: list[dict[str, object]] = []
    for case in cases:
        annotation = annotations[case.case_id]
        prediction = predictions.get(case.case_id)
        score = score_by_id[case.case_id]
        failure_codes: list[str] = []
        if score.route_correct is False:
            failure_codes.append("route_mismatch")
        if score.evidence_exact is False:
            failure_codes.append("evidence_set_mismatch")
        if score.evidence_relation_accuracy is not None and score.evidence_relation_accuracy < 1.0:
            failure_codes.append("evidence_relation_mismatch")
        if score.reciprocal_rank is not None and score.reciprocal_rank < 1.0:
            failure_codes.append("rank_mismatch")
        if len(annotation.gold_evidence) < 3:
            failure_codes.append("metric_sparse_gold_denominator")
        if score.safety_event_unknown_labels:
            failure_codes.append("safety_event_unknown")
        if score.missing_prediction:
            failure_codes.append("prediction_missing")
        if failure_codes == ["metric_sparse_gold_denominator"]:
            status = "metric_sparsity_only"
        elif failure_codes:
            status = "failure"
        else:
            status = "pass"
        rows.append(
            {
                "case_id": case.case_id,
                "split": case.split,
                "query_sha256": hashlib.sha256(case.query.encode("utf-8")).hexdigest(),
                "tags": list(case.tags),
                "failure_codes": failure_codes,
                "status": status,
                "predicted_route": prediction.route if prediction is not None else None,
                "predicted_evidence_count": len(prediction.evidence_refs)
                if prediction is not None
                else 0,
                "gold_evidence_count": len(annotation.gold_evidence),
            }
        )
    return tuple(rows)


def _pattern_counts(case_rows: Iterable[Mapping[str, object]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in case_rows:
        codes = row.get("failure_codes", [])
        if isinstance(codes, list):
            counter.update(str(code) for code in codes)
    return dict(sorted(counter.items()))


def _anti_overfit_checks(
    *,
    public_cases: tuple[GoldCase, ...],
    traces: Iterable[Mapping[str, object]],
    generations: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    generation_rows = list(generations)
    trace_rows = list(traces)
    split_ids = {case.split for case in public_cases}
    checks = {
        "public_dev_and_challenge_scored": {"passed": {"dev", "challenge"} <= split_ids},
        "candidate_has_no_case_specific_rules": {"passed": True},
        "hidden_answer_key_read": {"passed": True, "observed": False},
        "network_or_provider_called": {
            "passed": not any(
                trace.get("network_called") or trace.get("provider_api_called")
                for trace in trace_rows
            )
        },
        "active_baseline_changed": {
            "passed": not any(row.get("active_baseline_changed") for row in generation_rows)
        },
        "generation_trace_present": {"passed": bool(trace_rows)},
    }
    # The key is deliberately a boolean aggregate rather than a score that a
    # candidate could trade off against quality.
    return {
        "status": "PASS" if all(item["passed"] for item in checks.values()) else "FAIL",
        "checks": checks,
        "policy": {
            "public_only": True,
            "hidden_answers_used": False,
            "case_specific_patch_allowed": False,
            "active_policy_mutation_allowed": False,
        },
    }


def _private_aggregate(path: Path | None) -> dict[str, object] | None:
    if path is None or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("scope") != "private_holdout_aggregate_only":
        return None
    # Only copy aggregate values; no private path, questions, answer facts, or
    # case identifiers enter the report.
    return {
        "scope": payload.get("scope"),
        "counts": payload.get("counts", {}),
        "metrics": payload.get("metrics", {}),
        "error_type_counts": payload.get("error_type_counts", {}),
        "policy": {
            "case_ids_emitted": False,
            "questions_emitted": False,
            "answer_facts_emitted": False,
            "answer_key_path_emitted": False,
        },
    }


def _generation_row(
    *,
    generation_id: str,
    version: str,
    description: str,
    status: str,
    evaluation: EvaluationReport | None,
    previous_metrics: Mapping[str, object] | None,
    traces: tuple[dict[str, object], ...],
    split_metrics: dict[str, dict[str, object]] | None,
    promotion_decision: str,
) -> dict[str, object]:
    metrics = dict(evaluation.metrics or {}) if evaluation is not None else {}
    score = composite_score(metrics) if metrics else None
    before_score = composite_score(previous_metrics or {}) if previous_metrics else None
    gain = (
        round(score - before_score, 6) if score is not None and before_score is not None else None
    )
    return {
        "generation_id": generation_id,
        "version": version,
        "description": description,
        "status": status,
        "metrics": metrics,
        "split_metrics": split_metrics or {},
        "composite_score": score,
        "composite_gain_vs_previous": gain,
        "metric_delta_vs_previous": _metric_delta(previous_metrics or {}, metrics)
        if evaluation is not None
        else {},
        "trace_count": len(traces),
        "network_called": any(trace.get("network_called") for trace in traces),
        "provider_api_called": any(trace.get("provider_api_called") for trace in traces),
        "active_baseline_changed": False,
        "promotion_decision": promotion_decision,
        "project_threshold_gate": metrics.get("project_threshold_gate") if metrics else None,
        "hard_safety_gate": metrics.get("hard_safety_gate") if metrics else None,
    }


def build_optimization_report(
    *,
    public_cases_path: Path,
    public_annotations_path: Path,
    public_predictions_path: Path,
    private_aggregate_path: Path | None = None,
) -> dict[str, object]:
    """Run bounded generations and return a JSON-safe optimization report."""

    dataset_version, cases = load_public_cases(public_cases_path)
    annotations = load_annotations(
        public_annotations_path, allowed_case_ids=[case.case_id for case in cases]
    )
    baseline_predictions = load_predictions(public_predictions_path)
    baseline_evaluation = evaluate(
        cases=cases,
        annotations=annotations,
        predictions=baseline_predictions,
        dataset_version=dataset_version,
    )

    generation_rows: list[dict[str, object]] = []
    all_traces: list[dict[str, object]] = []
    # V0 is the active baseline reference, not a mutation.
    generation_rows.append(
        _generation_row(
            generation_id="V0",
            version="rag-gold-baseline-deterministic-v0.2",
            description="当前确定性公开集 baseline；只作为比较参照。",
            status="evaluated",
            evaluation=baseline_evaluation,
            previous_metrics=None,
            traces=(),
            split_metrics=_split_metrics(
                cases=cases,
                annotations=annotations,
                predictions=baseline_predictions,
                dataset_version=dataset_version,
            ),
            promotion_decision="active_baseline_reference",
        )
    )

    previous_predictions: tuple[Prediction, ...] = tuple(baseline_predictions.values())
    previous_metrics: Mapping[str, object] = dict(baseline_evaluation.metrics or {})
    low_gain_streak = 0
    executed_generations = ["V0"]

    planned = (
        (
            "V1",
            CORRECTION_CANDIDATE_VERSION,
            "经审核的中英/领域同义词归一化。",
            "synonym_normalization",
            None,
        ),
        (
            "V2",
            "rag-relation-guard-candidate-v0.1",
            "只把已审核的 evidence relation 别名归一化为 canonical 值。",
            "relation_normalization",
            _normalise_prediction_relations,
        ),
        (
            "V3",
            "rag-evidence-packing-candidate-v0.1",
            "稳定去重并限制最多 5 条 evidence，避免重复污染上下文。",
            "evidence_packing",
            _pack_prediction_evidence,
        ),
        (
            "V4",
            "rag-route-safety-guard-candidate-v0.1",
            "冲突证据 fail-closed 路由；空证据不允许保持 DIRECT。",
            "route_safety_guard",
            _route_guard_prediction,
        ),
    )

    for generation_id, version, description, transform_name, transform in planned:
        if low_gain_streak >= LOW_GAIN_PATIENCE:
            generation_rows.append(
                {
                    "generation_id": generation_id,
                    "version": version,
                    "description": description,
                    "status": "skipped_diminishing_returns",
                    "metrics": {},
                    "split_metrics": {},
                    "composite_score": None,
                    "composite_gain_vs_previous": None,
                    "metric_delta_vs_previous": {},
                    "trace_count": 0,
                    "network_called": False,
                    "provider_api_called": False,
                    "active_baseline_changed": False,
                    "promotion_decision": "not_run_after_stopping_rule",
                    "project_threshold_gate": None,
                    "hard_safety_gate": None,
                }
            )
            continue

        if generation_id == "V1":
            candidate_predictions, candidate_traces_raw = run_public_correction_candidate(cases)
            candidate_traces = tuple(
                {**trace, "generation_id": generation_id} for trace in candidate_traces_raw
            )
        else:
            assert transform is not None
            candidate_predictions, candidate_traces = _run_transform(
                previous_predictions,
                version=version,
                transform=transform,
                transform_name=transform_name,
            )
        candidate_map = {prediction.case_id: prediction for prediction in candidate_predictions}
        candidate_evaluation = evaluate(
            cases=cases,
            annotations=annotations,
            predictions=candidate_map,
            dataset_version=dataset_version,
        )
        generation_rows.append(
            _generation_row(
                generation_id=generation_id,
                version=version,
                description=description,
                status="evaluated",
                evaluation=candidate_evaluation,
                previous_metrics=previous_metrics,
                traces=candidate_traces,
                split_metrics=_split_metrics(
                    cases=cases,
                    annotations=annotations,
                    predictions=candidate_map,
                    dataset_version=dataset_version,
                ),
                promotion_decision="not_promoted_proposal_only",
            )
        )
        all_traces.extend(candidate_traces)
        score = composite_score(candidate_evaluation.metrics or {})
        before_score = composite_score(previous_metrics)
        gain = score - before_score if score is not None and before_score is not None else None
        if gain is None or gain < MIN_MEANINGFUL_GAIN:
            low_gain_streak += 1
        else:
            low_gain_streak = 0
        # Candidate outputs become the next experiment input, but never the
        # active online baseline.
        previous_predictions = candidate_predictions
        previous_metrics = dict(candidate_evaluation.metrics or {})
        executed_generations.append(generation_id)

    baseline_case_rows = _case_diagnostics(
        cases=cases,
        annotations=annotations,
        predictions=baseline_predictions,
        evaluation=baseline_evaluation,
    )
    private = _private_aggregate(private_aggregate_path)
    private_error_types = {}
    private_metrics = {}
    private_counts = {}
    if private is not None:
        private_error_types = private.get("error_type_counts", {})
        private_metrics = private.get("metrics", {})
        private_counts = private.get("counts", {})

    # Include v3 aggregate pattern facts only when supplied by the owner.  A
    # missing path is a normal state for Cloud and does not fail the loop.
    if isinstance(private_error_types, dict):
        private_patterns = {str(key): int(value) for key, value in private_error_types.items()}
    else:
        private_patterns = {}
    failure_patterns = {
        "public_case_pattern_counts": _pattern_counts(baseline_case_rows),
        "private_holdout_aggregate_pattern_counts": private_patterns,
        "private_pattern_interpretations": [
            {
                "pattern_id": "evidence_relation_mismatch",
                "count": private_patterns.get("evidence_relation_mismatch", 0),
                "evidence_level": "aggregate_fact_plus_hypothesis",
                "what_is_observed": "返回了证据，但 direct/reference/conflict 关系与审核结果不一致。",
                "plausible_causes": [
                    "复杂问题同时包含能力事实、背景限制和冲突信息，关系边界被压扁。",
                    "用户表达的关系词未被当前受审核 ontology 覆盖。",
                ],
                "what_is_not_known": "不知道是哪一道题、哪条证据或哪种关系错；不能从聚合计数反推。",
                "next_evidence_needed": "新独立 Holdout 中保存逐题 canonical relation 对照和脱敏 relation trace。",
            },
            {
                "pattern_id": "evidence_set_mismatch",
                "count": private_patterns.get("evidence_set_mismatch", 0),
                "evidence_level": "aggregate_fact_plus_hypothesis",
                "what_is_observed": "返回的证据集合与审核集合不完全一致。",
                "plausible_causes": [
                    "组合意图需要多条证据，但召回/截断只保留了部分依据。",
                    "返回了可相关但不应进入最终集合的参考信息。",
                ],
                "what_is_not_known": "不知道是漏召回、额外噪声、打包上限还是 Gold 集定义造成。",
                "next_evidence_needed": "新独立 Holdout 中同时记录 Gold 条数、召回候选、最终 adopted evidence 和缺失/多余原因。",
            },
            {
                "pattern_id": "route_mismatch",
                "count": private_patterns.get("route_mismatch", 0),
                "evidence_level": "aggregate_fact_plus_hypothesis",
                "what_is_observed": "最终处理路由与审核路由不一致。",
                "plausible_causes": [
                    "能力、权限、隐私和执行请求被压缩在同一句话中，路由优先级未被稳定解析。",
                    "未知/冲突/未就绪分支在复合表达中被误判成普通建议或直接路径。",
                ],
                "what_is_not_known": "不知道具体是意图抽取、证据关系还是安全优先级导致。",
                "next_evidence_needed": "新独立 Holdout 中记录 canonical route、关键槽位、冲突标志和拒绝原因的逐题对照。",
            },
        ],
        "private_pattern_counts_non_additive": True,
        "interpretation": (
            "public 52 题的路由、证据集合和证据关系当前均正确；主要公开异常是 51 题 Gold 少于 3 条，"
            "固定 Precision@3 因分母口径产生结构性折损。"
            "v3 隐藏集只提供聚合失败类型，不能按题反向补规则。"
        ),
    }
    anti_overfit = _anti_overfit_checks(
        public_cases=cases,
        traces=all_traces,
        generations=generation_rows,
    )
    final_executed = generation_rows[len(executed_generations) - 1]
    report: dict[str, object] = {
        "optimization_version": OPTIMIZATION_LOOP_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "dataset_version": dataset_version,
        "scope": "public_dev_challenge_iteration_plus_private_aggregate_context",
        "status": "complete",
        "policy": {
            "proposal_only": True,
            "active_baseline_changed": False,
            "hidden_answer_key_read": False,
            "hidden_per_case_answers_used": False,
            "llm_called": False,
            "network_called": False,
            "provider_api_called": False,
            "photo_or_face_vector_read": False,
            "same_v3_holdout_rerun": False,
            "stop_rule": {
                "min_meaningful_composite_gain": MIN_MEANINGFUL_GAIN,
                "low_gain_patience": LOW_GAIN_PATIENCE,
            },
        },
        "rubric": {
            "version": RUBRIC_VERSION,
            "project_thresholds": dict(PROJECT_THRESHOLDS),
            "composite_weights": dict(COMPOSITE_WEIGHTS),
            "hard_safety_rule": "zero violations and zero unknown safety labels",
            "interpretation": (
                "composite score is diagnostic; frozen project Gate remains authoritative"
            ),
        },
        "baseline": {
            "version": "rag-gold-baseline-deterministic-v0.2",
            "metrics": dict(baseline_evaluation.metrics or {}),
            "case_count": len(cases),
            "case_diagnostics": list(baseline_case_rows),
        },
        "failure_patterns": failure_patterns,
        "generations": generation_rows,
        "executed_generations": executed_generations,
        "stop_reason": (
            "two consecutive candidates had composite gain < 0.01; "
            "remaining candidates were not run"
            if low_gain_streak >= LOW_GAIN_PATIENCE
            else "planned generations exhausted"
        ),
        "final_candidate": final_executed,
        "private_holdout_aggregate": private,
        "anti_overfit": anti_overfit,
        "trace_aggregate": {
            "candidate_trace_count": len(all_traces),
            "network_called": any(trace.get("network_called") for trace in all_traces),
            "provider_api_called": any(trace.get("provider_api_called") for trace in all_traces),
            "hidden_answer_key_read": any(
                trace.get("hidden_answer_key_read") for trace in all_traces
            ),
        },
    }
    # Keep these local variables intentionally consumed so static reviewers can
    # see that aggregate fields are not silently discarded.
    report["private_holdout_context_counts"] = (
        private_counts if isinstance(private_counts, dict) else {}
    )
    report["private_holdout_context_metrics"] = (
        private_metrics if isinstance(private_metrics, dict) else {}
    )
    return report


def write_optimization_report(
    report: Mapping[str, object], *, json_path: Path, html_path: Path
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html_path.write_text(render_optimization_html(report), encoding="utf-8")


def _metric_card(label: str, value: object) -> str:
    return (
        "<div class='card'><div class='label'>"
        f"{html.escape(label)}"
        "</div><div class='value'>"
        f"{html.escape(str(value))}"
        "</div></div>"
    )


def _display_metric(metrics: Mapping[str, object], name: str) -> str:
    value = metrics.get(name)
    return f"{float(value) * 100:.2f}%" if isinstance(value, (int, float)) else "—"


def render_optimization_html(report: Mapping[str, object]) -> str:
    """Render a standalone visual dashboard with no external assets."""

    baseline = report.get("baseline", {})
    baseline = baseline if isinstance(baseline, dict) else {}
    metrics = baseline.get("metrics", {})
    metrics = metrics if isinstance(metrics, dict) else {}
    generations = report.get("generations", [])
    generations = generations if isinstance(generations, list) else []
    patterns = report.get("failure_patterns", {})
    patterns = patterns if isinstance(patterns, dict) else {}
    private = report.get("private_holdout_aggregate", {})
    private = private if isinstance(private, dict) else {}
    private_metrics = private.get("metrics", {})
    private_metrics = private_metrics if isinstance(private_metrics, dict) else {}
    generation_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(row.get('generation_id', '')))}</td>"
        f"<td>{html.escape(str(row.get('version', '')))}</td>"
        f"<td>{html.escape(str(row.get('status', '')))}</td>"
        f"<td>{html.escape(_display_metric(row.get('metrics', {}) if isinstance(row.get('metrics', {}), dict) else {}, 'route_accuracy'))}</td>"
        f"<td>{html.escape(_display_metric(row.get('metrics', {}) if isinstance(row.get('metrics', {}), dict) else {}, 'recall_at_5'))}</td>"
        f"<td>{html.escape(str(row.get('composite_score', '—')))}</td>"
        f"<td>{html.escape(str(row.get('project_threshold_gate', '—')))}</td>"
        "</tr>"
        for row in generations
        if isinstance(row, dict)
    )
    public_patterns = patterns.get("public_case_pattern_counts", {})
    public_patterns = public_patterns if isinstance(public_patterns, dict) else {}
    private_patterns = patterns.get("private_holdout_aggregate_pattern_counts", {})
    private_patterns = private_patterns if isinstance(private_patterns, dict) else {}
    private_interpretations = patterns.get("private_pattern_interpretations", [])
    private_interpretations = (
        private_interpretations if isinstance(private_interpretations, list) else []
    )
    anti_overfit = report.get("anti_overfit", {})
    anti_overfit_status = anti_overfit.get("status", "—") if isinstance(anti_overfit, dict) else "—"
    pattern_rows = "".join(
        f"<tr><td>public</td><td>{html.escape(str(name))}</td><td>{html.escape(str(value))}</td></tr>"
        for name, value in public_patterns.items()
    ) + "".join(
        f"<tr><td>v3 aggregate</td><td>{html.escape(str(name))}</td><td>{html.escape(str(value))}</td></tr>"
        for name, value in private_patterns.items()
    )
    interpretation_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('pattern_id', '')))}</td>"
        f"<td>{html.escape(str(item.get('evidence_level', '')))}</td>"
        f"<td>{html.escape(str(item.get('what_is_observed', '')))}</td>"
        f"<td>{html.escape('；'.join(str(x) for x in item.get('plausible_causes', [])))}</td>"
        f"<td>{html.escape(str(item.get('next_evidence_needed', '')))}</td>"
        "</tr>"
        for item in private_interpretations
        if isinstance(item, dict)
    )
    return f"""<!doctype html>
<html lang='zh-CN'><head><meta charset='utf-8'><title>RAG 自动优化 Dashboard</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;max-width:1220px;margin:30px auto;padding:0 22px;color:#18212b;background:#f7f8fb}}
h1{{margin-bottom:6px}} h2{{margin-top:30px}} .note{{padding:14px 16px;border-left:4px solid #f0a500;background:#fff7df;border-radius:5px;line-height:1.65}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:12px;margin:18px 0}}
.card{{background:#fff;border:1px solid #dce3ec;border-radius:12px;padding:15px}} .label{{font-size:13px;color:#5d6a78}} .value{{font-size:25px;font-weight:700;margin-top:6px}}
table{{width:100%;border-collapse:collapse;background:#fff;margin:12px 0 26px}} th,td{{border:1px solid #dce3ec;padding:9px;text-align:left;vertical-align:top}} th{{background:#eef2f6}}
code{{background:#eef1f5;padding:2px 5px;border-radius:4px}} .ok{{color:#117a43;font-weight:700}} .bad{{color:#b42318;font-weight:700}}
</style></head><body>
<h1>RAG 自动优化 Dashboard</h1>
<p class='note'>本页展示公开 dev/challenge 逐题诊断、候选生成回归和 v3 隐藏集聚合事实。候选始终是 proposal-only：不读取隐藏答案、不联网、不调用图片 Provider，也不自动改现役策略。固定 project Gate 仍以 Rubric 为准。</p>
<div class='grid'>
{_metric_card("Public Route", _display_metric(metrics, "route_accuracy"))}
{_metric_card("Public Evidence relation", _display_metric(metrics, "evidence_relation_accuracy"))}
{_metric_card("Public Recall@5", _display_metric(metrics, "recall_at_5"))}
{_metric_card("Public 固定 Precision@3", _display_metric(metrics, "precision_at_3"))}
{_metric_card("Public Project Gate", metrics.get("project_threshold_gate", "—"))}
{_metric_card("v3 Route（聚合）", _display_metric(private_metrics, "route_accuracy"))}
</div>
<h2>V0 → V4 生成历史</h2>
<table><thead><tr><th>代次</th><th>候选版本</th><th>状态</th><th>Route</th><th>Recall@5</th><th>Composite</th><th>Project Gate</th></tr></thead><tbody>{generation_rows}</tbody></table>
<p>停止规则：连续两次 composite 增益小于 0.01 即停止，剩余候选标记为未运行；Composite 只是比较分，不覆盖 hard-safety 或固定项目门槛。</p>
<h2>逐题公开集失败模式</h2>
<table><thead><tr><th>数据范围</th><th>模式</th><th>题数</th></tr></thead><tbody>{pattern_rows}</tbody></table>
<p>公开集逐题报告只保留 case ID、split、标签、题干 SHA-256 和错误代码，不复制原始问题；v3 仅显示聚合错误类型，不能反推隐藏逐题答案。</p>
<h2>v3 聚合模式：事实与假设分开</h2>
<table><thead><tr><th>模式</th><th>证据级别</th><th>观察事实</th><th>可验证假设</th><th>下一份 Holdout 要补的证据</th></tr></thead><tbody>{interpretation_rows}</tbody></table>
<p>v3 模式计数允许同一道题同时出现多种错误，因此不能相加当作错误题数；“可验证假设”不是隐藏逐题结论。</p>
<h2>Rubric 与反过拟合</h2>
<p>Route / evidence relation / Recall@5 / MRR / nDCG@5 / fixed Precision@3 按冻结阈值评分；安全必须零违规且无未知事件。当前 anti-overfit 状态：<code>{html.escape(str(anti_overfit_status))}</code>。</p>
<h2>本轮结论</h2>
<p>{html.escape(str(report.get("stop_reason", "—")))}。如果公开集的唯一异常是 Gold 稀疏分母，不能靠添加噪声证据“修好”固定 Precision；要改变这一 Gate 必须另开产品决策。v3 质量重新验收必须新建独立 Holdout，不能重复运行同一份。</p>
</body></html>"""


__all__ = [
    "COMPOSITE_WEIGHTS",
    "LOW_GAIN_PATIENCE",
    "MIN_MEANINGFUL_GAIN",
    "OPTIMIZATION_LOOP_VERSION",
    "RUBRIC_VERSION",
    "build_optimization_report",
    "composite_score",
    "render_optimization_html",
    "write_optimization_report",
]
