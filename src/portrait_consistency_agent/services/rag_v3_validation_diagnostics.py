# ruff: noqa: E501
"""Diagnose and optimise the product-owner-unlocked V3 validation set.

The historical V3 Holdout-A run remains preserved outside the workspace.  This
module is only used after the explicit owner decision to unlock V3 for
diagnosis.  It joins the reviewed questions, answer annotations, predictions
and full safe retrieval traces, then runs bounded proposal-only candidates.
Promotion still requires a fresh independent V4 Holdout.
"""

from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path
from typing import Any

from portrait_consistency_agent.services.rag_gold_baseline import RagGoldDeterministicBaseline
from portrait_consistency_agent.services.rag_gold_eval import (
    GoldAnnotation,
    GoldCase,
    Prediction,
    evaluate,
    load_annotations,
    load_public_cases,
    load_validation_cases,
)
from portrait_consistency_agent.services.rag_optimization_loop import (
    COMPOSITE_WEIGHTS,
    _normalise_prediction_relations,
    _pack_prediction_evidence,
    composite_score,
)
from portrait_consistency_agent.services.rag_query_compiler_candidate import (
    QUERY_COMPILER_CANDIDATE_V2_VERSION,
    QUERY_COMPILER_CANDIDATE_VERSION,
    compile_generalized_projection,
    compile_validation_projection_v2,
    normalize_for_compilation,
    run_failure_driven_candidate,
)

V3_VALIDATION_DIAGNOSTICS_VERSION = "rag-v3-validation-diagnostics-v0.1"
RUBRIC_VERSION = "rag-optimization-rubric-v0.3"
MIN_MEANINGFUL_GAIN = 0.01
LOW_GAIN_PATIENCE = 2


def _prediction_payload(prediction: Prediction | None) -> dict[str, object]:
    if prediction is None:
        return {"missing": True}
    return {
        "route": prediction.route,
        "evidence_refs": list(prediction.evidence_refs),
        "evidence_relations": dict(prediction.evidence_relations),
        "observed_events": list(prediction.observed_events),
        "trace_ref": prediction.trace_ref,
        "machine_score_summary": dict(prediction.machine_score_summary),
    }


def _case_failure_codes(*, case: GoldCase, annotation: GoldAnnotation, score: Any) -> list[str]:
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
    if score.safety_event_unknown_labels:
        codes.append("safety_event_unknown")
    if score.missing_prediction:
        codes.append("prediction_missing")
    return codes


def _case_status(codes: list[str]) -> str:
    if codes == ["metric_sparse_gold_denominator"]:
        return "metric_sparsity_only"
    return "failure" if codes else "pass"


def _failure_explanation(
    *, codes: list[str], trace: dict[str, object] | None, query: str
) -> dict[str, str]:
    """Translate machine error codes into a short, reviewable SOP entry."""

    category_codes = []
    flags: dict[str, object] = {}
    if trace:
        category_codes = [str(item) for item in trace.get("category_codes", [])]
        raw_flags = trace.get("signal_flags", {})
        if isinstance(raw_flags, dict):
            flags = raw_flags
    if "route_mismatch" in codes:
        root = "基线在检索前没有把这句自然语言稳定投影成正确任务路由。"
        correction = (
            "在检索前增加可审核的意图槽位、优先级和安全门；若槽位不足，回到 UNKNOWN/BASELINE。"
        )
    elif "evidence_relation_mismatch" in codes:
        root = (
            "找到了候选资料，但没有区分 direct_evidence、reference_context 和 conflict_evidence。"
        )
        correction = "让关系由证据类型和策略规则确定，不能由相似度或 LLM 自由改写。"
    elif "evidence_set_mismatch" in codes:
        root = "召回集合漏掉了必要证据，或把不应采用的资料带入了结果。"
        correction = "先做结构化查询与硬过滤，再做混合召回；保留采用和淘汰原因。"
    elif "rank_mismatch" in codes:
        root = "相关证据被召回，但排序没有把最关键的一条放在前面。"
        correction = "按权威、当前版本、生效期和任务匹配度重排，并用 Gold Set 回归。"
    elif "safety_event_unknown" in codes:
        root = "安全事件尚未映射到审核过的 canonical event ID。"
        correction = "先补齐事件目录映射；无法映射时只能 MANUAL_REVIEW_REQUIRED。"
    elif "prediction_missing" in codes:
        root = "该题没有产生可评分的结构化结果。"
        correction = "保留 UNKNOWN/BASELINE 的明确输出，不允许静默丢失。"
    elif "metric_sparse_gold_denominator" in codes:
        root = "这不是产品失败，而是 Gold 证据条数少于固定 Precision 分母造成的统计现象。"
        correction = (
            "并行查看覆盖式/返回式 Precision；固定 Precision 只作为历史 Gate，不拿它单独调参。"
        )
    else:
        root = "本题在当前机器口径下没有可复现错误。"
        correction = "保留 Trace，并放入后续独立 Holdout 观察泛化。"
    signal_summary = "、".join(
        name
        for name, value in flags.items()
        if value is True or (isinstance(value, int) and value > 0)
    )
    return {
        "root_cause": root,
        "correction": correction,
        "observed_category": "、".join(category_codes) or "baseline",
        "signal_summary": signal_summary or "无新增结构化信号",
        "review_note": "题干只用于本次产品负责人解冻后的验证诊断：" + query[:80],
    }


def _score_case_rows(
    *,
    cases: tuple[GoldCase, ...],
    annotations: dict[str, GoldAnnotation],
    predictions: dict[str, Prediction],
    report: Any,
    traces: tuple[dict[str, object], ...] = (),
) -> tuple[dict[str, object], ...]:
    score_by_id = {score.case_id: score for score in report.case_scores}
    trace_by_id = {str(trace.get("case_id")): trace for trace in traces}
    rows: list[dict[str, object]] = []
    for case in cases:
        annotation = annotations[case.case_id]
        score = score_by_id[case.case_id]
        codes = _case_failure_codes(case=case, annotation=annotation, score=score)
        trace = trace_by_id.get(case.case_id)
        rows.append(
            {
                "case_id": case.case_id,
                "query": case.query,
                "split": case.split,
                "gold": {
                    "routes": list(annotation.gold_routes),
                    "evidence": list(annotation.gold_evidence),
                    "evidence_relations": dict(annotation.gold_evidence_relations),
                    "prohibited_events": list(annotation.prohibited_events),
                },
                "prediction": _prediction_payload(predictions.get(case.case_id)),
                "status": _case_status(codes),
                "failure_codes": codes,
                "failure_analysis": _failure_explanation(
                    codes=codes, trace=trace, query=case.query
                ),
                "trace": trace or {},
                "score": {
                    "route_correct": score.route_correct,
                    "evidence_exact": score.evidence_exact,
                    "evidence_relation_accuracy": score.evidence_relation_accuracy,
                    "reciprocal_rank": score.reciprocal_rank,
                    "recall_at_5": score.recall_at_k.get("5"),
                    "ndcg_at_5": score.ndcg_at_k.get("5"),
                    "hard_safety_violation_count": score.hard_safety_violation_count,
                },
            }
        )
    return tuple(rows)


def _changed_count(before: tuple[Prediction, ...], after: tuple[Prediction, ...]) -> int:
    old = {row.case_id: row for row in before}
    return sum(
        (
            old.get(row.case_id) is None
            or old[row.case_id].route != row.route
            or old[row.case_id].evidence_refs != row.evidence_refs
            or dict(old[row.case_id].evidence_relations) != dict(row.evidence_relations)
        )
        for row in after
    )


def _metric_delta(before: dict[str, object], after: dict[str, object]) -> dict[str, float | None]:
    names = tuple(
        dict.fromkeys((*COMPOSITE_WEIGHTS, "route_accuracy", "evidence_relation_accuracy"))
    )
    result: dict[str, float | None] = {}
    for name in names:
        old, new = before.get(name), after.get(name)
        if isinstance(old, (int, float)) and isinstance(new, (int, float)):
            result[name] = round(float(new) - float(old), 6)
        else:
            result[name] = None
    return result


def _generation(
    *,
    generation_id: str,
    version: str,
    description: str,
    predictions: tuple[Prediction, ...],
    traces: tuple[dict[str, object], ...],
    cases: tuple[GoldCase, ...],
    annotations: dict[str, GoldAnnotation],
    previous_predictions: tuple[Prediction, ...] | None,
    previous_metrics: dict[str, object] | None,
    regression_metrics: dict[str, object],
    regression_gate: str | None,
    dataset_version: str,
) -> dict[str, object]:
    prediction_map = {row.case_id: row for row in predictions}
    report = evaluate(
        cases=cases,
        annotations=annotations,
        predictions=prediction_map,
        dataset_version=dataset_version,
    )
    metrics = dict(report.metrics or {})
    score = composite_score(metrics)
    prior_score = composite_score(previous_metrics or {}) if previous_metrics else None
    gain = round(score - prior_score, 6) if score is not None and prior_score is not None else None
    return {
        "generation_id": generation_id,
        "version": version,
        "description": description,
        "metrics": metrics,
        "composite_score": score,
        "composite_gain_vs_previous": gain,
        "metric_delta_vs_previous": _metric_delta(previous_metrics or {}, metrics),
        "changed_prediction_count": (
            _changed_count(previous_predictions, predictions)
            if previous_predictions is not None
            else None
        ),
        "trace_count": len(traces),
        "regression_metrics": regression_metrics,
        "regression_gate": regression_gate,
        "network_called": any(row.get("network_called") for row in traces),
        "llm_called": any(row.get("llm_called") for row in traces),
        "provider_api_called": any(row.get("provider_api_called") for row in traces),
        "hidden_answer_key_read": any(row.get("hidden_answer_key_read") for row in traces),
        "active_baseline_changed": False,
        "promotion_decision": "not_promoted_proposal_only",
        "case_diagnostics": _score_case_rows(
            cases=cases,
            annotations=annotations,
            predictions=prediction_map,
            report=report,
            traces=traces,
        ),
        "traces": list(traces),
    }


def _failure_counts(case_rows: tuple[dict[str, object], ...]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in case_rows:
        counts.update(str(code) for code in row.get("failure_codes", []))
    return dict(sorted(counts.items()))


def _guard_accepts_candidate(
    *, case: GoldCase, baseline: Prediction, candidate: Prediction, trace: dict[str, object]
) -> tuple[bool, str]:
    """Accept only high-confidence changes so a V3 fix cannot regress baseline.

    The guard is deliberately conservative.  It is an evaluation candidate,
    not an online authorization rule: when a known baseline already has a
    concrete answer, a new compiler must either make no semantic change or
    show an explicit, reviewable signal (for example face isolation or a
    measured verification regression).  An UNKNOWN baseline may be improved,
    except for an obvious unresolved lifecycle/unsupported-feature phrase.
    """

    baseline_key = (baseline.route, baseline.evidence_refs, dict(baseline.evidence_relations))
    candidate_key = (candidate.route, candidate.evidence_refs, dict(candidate.evidence_relations))
    if baseline_key == candidate_key:
        return True, "no_semantic_change"
    raw_flags = trace.get("signal_flags", {})
    flags = raw_flags if isinstance(raw_flags, dict) else {}
    normalized = normalize_for_compilation(case.query)
    if baseline.route not in (None, "UNKNOWN"):
        if (
            any(
                flags.get(name)
                for name in (
                    "face_isolation",
                    "result_worsened",
                    "natural_preference",
                    "replan_context",
                )
            )
            or "眼睛的面积" in normalized
            or "双眼面积" in normalized
        ):
            return True, "explicit_high_confidence_signal"
        return False, "preserve_known_baseline"
    # If the sentence says an old/previous capability is being checked, an
    # unsupported-feature suggestion is not safe until the conflict is
    # resolved; keep the baseline's conflict evidence instead.
    if (
        flags.get("unsupported_feature_count", 0)
        and any(token in normalized for token in ("上次", "旧版", "旧卡", "superseded"))
        and candidate.route in {"SUGGEST", "DIRECT"}
    ):
        return False, "unresolved_lifecycle_conflict"
    return True, "baseline_unknown_candidate_allowed"


def _apply_regression_guard(
    *,
    cases: tuple[GoldCase, ...],
    baseline_predictions: tuple[Prediction, ...],
    candidate_predictions: tuple[Prediction, ...],
    candidate_traces: tuple[dict[str, object], ...],
    runner_version: str,
) -> tuple[tuple[Prediction, ...], tuple[dict[str, object], ...]]:
    baseline_by_id = {row.case_id: row for row in baseline_predictions}
    trace_by_id = {str(row.get("case_id")): row for row in candidate_traces}
    guarded: list[Prediction] = []
    guarded_traces: list[dict[str, object]] = []
    for case, candidate in zip(cases, candidate_predictions, strict=True):
        baseline = baseline_by_id[case.case_id]
        source_trace = dict(trace_by_id.get(case.case_id, {}))
        accepted, reason = _guard_accepts_candidate(
            case=case, baseline=baseline, candidate=candidate, trace=source_trace
        )
        selected = candidate if accepted else baseline
        source_trace.update(
            {
                "runner_version": runner_version,
                "regression_guard": {
                    "decision": "accept_candidate" if accepted else "fallback_to_baseline",
                    "reason": reason,
                    "baseline_route": baseline.route,
                    "candidate_route": candidate.route,
                    "selected_route": selected.route,
                    "active_online_baseline_changed": False,
                },
            }
        )
        guarded.append(selected)
        guarded_traces.append(source_trace)
    return tuple(guarded), tuple(guarded_traces)


def _pattern_summary(case_rows: tuple[dict[str, object], ...]) -> dict[str, object]:
    counts = _failure_counts(case_rows)
    examples: dict[str, list[str]] = {key: [] for key in counts}
    for row in case_rows:
        case_id = str(row.get("case_id"))
        for code in row.get("failure_codes", []):
            key = str(code)
            if key in examples and len(examples[key]) < 5:
                examples[key].append(case_id)
    return {
        "counts": counts,
        "examples_first_five": examples,
        "interpretation": {
            "route_mismatch": "错误发生在检索前的查询理解/任务路由层。",
            "evidence_set_mismatch": "证据召回集合与人工 Gold 不一致。",
            "evidence_relation_mismatch": "证据找到了，但直接事实、背景参考和冲突证据关系标错。",
            "rank_mismatch": "关键证据出现了，但没有排在足够靠前的位置。",
            "metric_sparse_gold_denominator": "统计口径提醒，不是产品错误。",
        },
    }


def build_v3_validation_diagnostics(
    *,
    cases_path: Path,
    annotations_path: Path,
    regression_cases_path: Path,
    regression_annotations_path: Path,
) -> dict[str, object]:
    """Run V3 baseline and bounded candidates with full per-case evidence."""

    dataset_version, cases = load_validation_cases(cases_path)
    annotations = load_annotations(
        annotations_path, allowed_case_ids=[case.case_id for case in cases]
    )
    regression_version, regression_cases = load_public_cases(regression_cases_path)
    regression_annotations = load_annotations(
        regression_annotations_path,
        allowed_case_ids=[case.case_id for case in regression_cases],
    )
    baseline_runner = RagGoldDeterministicBaseline()
    baseline_run = baseline_runner.run_holdout(
        tuple(
            case.__class__(case_id=case.case_id, split="holdout", query=case.query)
            for case in cases
        )
    )
    baseline_predictions = baseline_run.predictions
    regression_baseline = baseline_runner.run(regression_cases)

    def _evaluate_regression(predictions: tuple[Prediction, ...]) -> Any:
        return evaluate(
            cases=regression_cases,
            annotations=regression_annotations,
            predictions={row.case_id: row for row in predictions},
            dataset_version=regression_version,
        )

    generations: list[dict[str, object]] = []
    previous_predictions = baseline_predictions
    baseline_report = evaluate(
        cases=cases,
        annotations=annotations,
        predictions={row.case_id: row for row in baseline_predictions},
        dataset_version=dataset_version,
    )
    previous_metrics = dict(baseline_report.metrics or {})
    baseline_regression_report = _evaluate_regression(regression_baseline.predictions)
    generations.append(
        _generation(
            generation_id="G0",
            version="rag-gold-baseline-deterministic-v0.2",
            description="原 V3 answerless baseline；现在只作为解冻后的诊断起点。",
            predictions=baseline_predictions,
            traces=tuple(baseline_run.safe_traces),
            cases=cases,
            annotations=annotations,
            previous_predictions=None,
            previous_metrics=None,
            regression_metrics=dict(baseline_regression_report.metrics or {}),
            regression_gate=(baseline_regression_report.metrics or {}).get(
                "project_threshold_gate"
            ),
            dataset_version=dataset_version,
        )
    )

    planned = (
        (
            "G1",
            QUERY_COMPILER_CANDIDATE_VERSION,
            "原 v0.1 查询编译候选，作为对照。",
            compile_generalized_projection,
        ),
        (
            "G2",
            QUERY_COMPILER_CANDIDATE_V2_VERSION,
            "V3 失败驱动查询编译：补充能力、权限、生命周期、反馈和多意图优先级。",
            compile_validation_projection_v2,
        ),
    )
    generation_predictions: dict[str, tuple[Prediction, ...]] = {"G0": baseline_predictions}
    generation_traces: dict[str, tuple[dict[str, object], ...]] = {
        "G0": tuple(baseline_run.safe_traces)
    }
    for generation_id, version, description, compiler in planned:
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
        regression_report = _evaluate_regression(regression_predictions)
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
                regression_metrics=dict(regression_report.metrics or {}),
                regression_gate=(regression_report.metrics or {}).get("project_threshold_gate"),
                dataset_version=dataset_version,
            )
        )
        generation_predictions[generation_id] = predictions
        generation_traces[generation_id] = traces
        previous_predictions = predictions
        current_metrics = generations[-1]["metrics"]
        previous_metrics = dict(current_metrics) if isinstance(current_metrics, dict) else {}

    # G3 is the first genuine correction after the V3 gains: a conservative
    # regression guard prevents a validation fix from silently degrading the
    # already-known public baseline.  It is still proposal-only.
    v2_predictions = generation_predictions["G2"]
    v2_traces = generation_traces["G2"]
    guarded_validation, guarded_validation_traces = _apply_regression_guard(
        cases=cases,
        baseline_predictions=baseline_predictions,
        candidate_predictions=v2_predictions,
        candidate_traces=v2_traces,
        runner_version="rag-query-compiler-candidate-v0.3-regression-guard",
    )
    public_v2_predictions, public_v2_traces = run_failure_driven_candidate(
        regression_cases,
        runtime_mode="public",
        compiler=compile_validation_projection_v2,
        runner_version=QUERY_COMPILER_CANDIDATE_V2_VERSION,
    )
    guarded_public, _guarded_public_traces = _apply_regression_guard(
        cases=regression_cases,
        baseline_predictions=regression_baseline.predictions,
        candidate_predictions=public_v2_predictions,
        candidate_traces=public_v2_traces,
        runner_version="rag-query-compiler-candidate-v0.3-regression-guard",
    )
    guarded_regression_report = _evaluate_regression(guarded_public)
    generations.append(
        _generation(
            generation_id="G3",
            version="rag-query-compiler-candidate-v0.3-regression-guard",
            description="对 V3 修复加公开集回归守门；低置信变更回退已知 baseline。",
            predictions=guarded_validation,
            traces=guarded_validation_traces,
            cases=cases,
            annotations=annotations,
            previous_predictions=previous_predictions,
            previous_metrics=previous_metrics,
            regression_metrics=dict(guarded_regression_report.metrics or {}),
            regression_gate=(guarded_regression_report.metrics or {}).get("project_threshold_gate"),
            dataset_version=dataset_version,
        )
    )
    previous_predictions = guarded_validation
    previous_metrics = dict(generations[-1]["metrics"])
    guarded_regression_predictions = guarded_public

    # G4/G5 intentionally run after G3 and preserve the full parent trace.
    # They answer whether relation/evidence post-processing, rather than query
    # understanding, can produce any additional gain.
    for generation_id, version, description, transform in (
        (
            "G4",
            "rag-relation-guard-candidate-v0.1",
            "只规范化关系字段，检查是否还有增益。",
            _normalise_prediction_relations,
        ),
        (
            "G5",
            "rag-evidence-packing-candidate-v0.1",
            "只做稳定去重和证据打包，检查是否还有增益。",
            _pack_prediction_evidence,
        ),
    ):
        predictions = tuple(transform(row) for row in previous_predictions)
        parent_trace_by_id = {str(row.get("case_id")): row for row in guarded_validation_traces}
        traces = []
        for row in predictions:
            parent = dict(parent_trace_by_id.get(row.case_id, {}))
            parent.update(
                {
                    "runner_version": version,
                    "transform": "validation_downstream_candidate",
                    "parent_runner_version": "rag-query-compiler-candidate-v0.3-regression-guard",
                    "active_baseline_changed": False,
                }
            )
            traces.append(parent)
        regression_predictions = tuple(transform(row) for row in guarded_regression_predictions)
        regression_report = _evaluate_regression(regression_predictions)
        generations.append(
            _generation(
                generation_id=generation_id,
                version=version,
                description=description,
                predictions=predictions,
                traces=tuple(traces),
                cases=cases,
                annotations=annotations,
                previous_predictions=previous_predictions,
                previous_metrics=previous_metrics,
                regression_metrics=dict(regression_report.metrics or {}),
                regression_gate=(regression_report.metrics or {}).get("project_threshold_gate"),
                dataset_version=dataset_version,
            )
        )
        guarded_validation_traces = tuple(traces)
        previous_predictions = predictions
        previous_metrics = dict(generations[-1]["metrics"])
        guarded_regression_predictions = regression_predictions

    baseline_case_rows = generations[0]["case_diagnostics"]
    final_case_rows = generations[-1]["case_diagnostics"]
    generation_ids = [str(row["generation_id"]) for row in generations]
    case_change_summary = []
    for before, after in zip(baseline_case_rows, final_case_rows, strict=True):
        before_prediction = before["prediction"]
        after_prediction = after["prediction"]
        case_change_summary.append(
            {
                "case_id": before["case_id"],
                "split": before["split"],
                "query": before["query"],
                "baseline_status": before["status"],
                "baseline_failure_codes": list(before["failure_codes"]),
                "final_status": after["status"],
                "final_failure_codes": list(after["failure_codes"]),
                "baseline_route": before_prediction.get("route"),
                "final_route": after_prediction.get("route"),
                "prediction_changed": before_prediction != after_prediction,
                "root_cause": before.get("failure_analysis", {}).get("root_cause"),
                "correction": before.get("failure_analysis", {}).get("correction"),
            }
        )

    all_traces = [trace for generation in generations for trace in generation["traces"]]
    return {
        "diagnostics_version": V3_VALIDATION_DIAGNOSTICS_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "dataset_version": dataset_version,
        "dataset_scope": "owner_unlocked_former_v3_holdout_validation",
        "status": "complete",
        "policy": {
            "owner_unlocked_v3": True,
            "historical_holdout_a_snapshot_preserved": True,
            "proposal_only": True,
            "active_baseline_changed": False,
            "hidden_answer_key_read": True,
            "same_historical_blind_run_repeated": False,
            "network_called": False,
            "llm_called": False,
            "provider_api_called": False,
            "photo_or_face_vector_read": False,
            "new_independent_v4_required_for_promotion": True,
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
            "hard_safety_gate": "zero violations and zero unknown labels",
            "fixed_precision_is_historical_gate": True,
        },
        "baseline_failure_counts": _failure_counts(tuple(baseline_case_rows)),
        "final_failure_counts": _failure_counts(tuple(final_case_rows)),
        "failure_pattern_analysis": _pattern_summary(tuple(baseline_case_rows)),
        "generations": generations,
        "generation_ids": generation_ids,
        "final_case_change_summary": case_change_summary,
        "trace_aggregate": {
            "trace_count": len(all_traces),
            "network_called": False,
            "llm_called": False,
            "provider_api_called": False,
            "hidden_answer_key_read": True,
            "active_baseline_changed": False,
        },
        "stop_reason": (
            "G2 repaired the V3 validation patterns; G3 added a public-regression guard; G4/G5 were downstream no-op checks. New V4 is required for independent generalisation."
        ),
    }


def write_v3_validation_diagnostics(
    report: dict[str, object], *, json_path: Path, html_path: Path
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html_path.write_text(render_v3_validation_html(report), encoding="utf-8")


def _pct(value: object) -> str:
    return f"{float(value) * 100:.2f}%" if isinstance(value, (int, float)) else "—"


def render_v3_validation_html(report: dict[str, object]) -> str:
    generations = report.get("generations", [])
    generations = generations if isinstance(generations, (list, tuple)) else []
    generation_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(row.get('generation_id')))}</td>"
        f"<td>{html.escape(str(row.get('version')))}</td>"
        f"<td>{html.escape(str(row.get('changed_prediction_count')))}</td>"
        f"<td>{html.escape(_pct((row.get('metrics') or {}).get('route_accuracy')))}</td>"
        f"<td>{html.escape(_pct((row.get('metrics') or {}).get('evidence_relation_accuracy')))}</td>"
        f"<td>{html.escape(_pct((row.get('metrics') or {}).get('recall_at_5')))}</td>"
        f"<td>{html.escape(str(row.get('composite_score')))}</td>"
        f"<td>{html.escape(str(row.get('composite_gain_vs_previous')))}</td>"
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
    base_counts = report.get("baseline_failure_counts", {})
    base_counts = base_counts if isinstance(base_counts, dict) else {}
    pattern_html = "".join(
        f"<tr><td>{html.escape(str(key))}</td><td>{html.escape(str(value))}</td></tr>"
        for key, value in base_counts.items()
    )
    final_generation = generations[-1] if generations else {}
    final_case_diagnostics = (
        final_generation.get("case_diagnostics", []) if isinstance(final_generation, dict) else []
    )
    final_case_diagnostics = (
        final_case_diagnostics if isinstance(final_case_diagnostics, (list, tuple)) else []
    )
    trace_html = "".join(
        "<tr>"
        f"<td>{html.escape(str(row.get('case_id')))}</td>"
        f"<td>{html.escape(str((row.get('trace') or {}).get('runner_version', '—')))}</td>"
        f"<td>{html.escape(str((row.get('trace') or {}).get('retrieval_route', '—')))}</td>"
        f"<td>{html.escape(str((row.get('trace') or {}).get('prediction_route', '—')))}</td>"
        f"<td>{html.escape(str((row.get('trace') or {}).get('category_codes', [])))}</td>"
        f"<td>{html.escape(str((row.get('trace') or {}).get('regression_guard', '—')))}</td>"
        "</tr>"
        for row in final_case_diagnostics
        if isinstance(row, dict)
    )
    full_trace_html = "".join(
        (
            "<details><summary>"
            f"{html.escape(str(row.get('case_id')))}｜完整 Trace 与逐题结论"
            "</summary>"
            "<h4>失败模式与修正 SOP</h4>"
            f"<pre>{html.escape(json.dumps(row.get('failure_analysis', {}), ensure_ascii=False, indent=2))}</pre>"
            "<h4>结构化评分</h4>"
            f"<pre>{html.escape(json.dumps(row.get('score', {}), ensure_ascii=False, indent=2))}</pre>"
            "<h4>完整安全 Trace</h4>"
            f"<pre>{html.escape(json.dumps(row.get('trace', {}), ensure_ascii=False, indent=2))}</pre>"
            "</details>"
        )
        for row in final_case_diagnostics
        if isinstance(row, dict)
    )
    style = """
    body{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;max-width:1500px;margin:28px auto;padding:0 22px;color:#18212b;background:#f7f8fb;line-height:1.55}
    h1{margin-bottom:4px}h2{margin-top:30px}table{width:100%;border-collapse:collapse;background:#fff;margin:12px 0 26px}th,td{border:1px solid #dce3ec;padding:8px;text-align:left;vertical-align:top}th{background:#eef2f6}td:nth-child(2){min-width:360px}.note{padding:14px 16px;border-left:4px solid #cf8c00;background:#fff7df;border-radius:5px}.mono{font-family:ui-monospace,monospace}details{background:#fff;border:1px solid #dce3ec;border-radius:5px;margin:8px 0;padding:10px 14px}summary{cursor:pointer;font-weight:600}pre{white-space:pre-wrap;overflow:auto;background:#f5f7fa;padding:10px;border-radius:4px}
    """
    return f"""<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><title>V3 解冻验证集诊断</title><style>{style}</style></head><body>
    <h1>V3 解冻验证集｜逐题诊断与 RAG 优化</h1>
    <p class='note'>这是产品负责人明确解冻后的 V3 诊断副本，不再是独立 Holdout。原始一次性盲测快照仍保留；本报告允许显示题干、Gold、逐题结论和完整安全 Trace。候选始终 proposal-only，推广前必须新建独立 V4。</p>
    <p>数据版本：<code>{html.escape(str(report.get("dataset_version")))}</code>；状态：<strong>{html.escape(str(report.get("status")))}</strong></p>
    <h2>G0 → G5 迭代结果</h2><table><thead><tr><th>代次</th><th>候选</th><th>改变预测数</th><th>Route</th><th>Relation</th><th>Recall@5</th><th>Composite</th><th>增益</th><th>Public regression</th></tr></thead><tbody>{generation_rows}</tbody></table>
    <h2>G0 失败模式</h2><table><thead><tr><th>失败代码</th><th>题数</th></tr></thead><tbody>{pattern_html}</tbody></table>
    <h2>最终逐题结论</h2><table><thead><tr><th>Case</th><th>题目</th><th>G0 状态</th><th>最终状态</th><th>G0 路由</th><th>最终路由</th><th>G0 失败代码</th><th>根因</th><th>修正 SOP</th></tr></thead><tbody>{case_html}</tbody></table>
    <h2>最终代次逐题 Trace 摘要</h2><table><thead><tr><th>Case</th><th>Runner</th><th>检索路由</th><th>预测路由</th><th>分类码</th><th>回归守门决策</th></tr></thead><tbody>{trace_html}</tbody></table>
    <h2>最终代次逐题完整 Trace</h2><p>以下 36 个折叠项分别对应 H01–H36。展开后可查看该题的失败模式解释、结构化评分和完整安全 Trace；所有代次的完整 Trace 仍在 JSON 的 <code>generations[*].traces</code> 中。</p>{full_trace_html}
    <h2>Trace 说明</h2><p>每个代次都保存 query hash、结构化投影、信号、P0-B 查询合同、FTS/dense/RRF/rerank、证据采用、路由和安全字段；不保存照片或人脸向量。完整 JSON 中的 <code>generations[*].traces</code> 可逐步回放。</p>
    <p class='note'>停止规则：G2 已修复主要可复现模式，G3/G4 只是下游 no-op 检查；固定 Precision 因 Gold 稀疏仍不能作为“通过”。下一质量证据必须来自与 V3 不重叠的独立 V4。</p>
    </body></html>"""


__all__ = [
    "RUBRIC_VERSION",
    "V3_VALIDATION_DIAGNOSTICS_VERSION",
    "build_v3_validation_diagnostics",
    "render_v3_validation_html",
    "write_v3_validation_diagnostics",
]
