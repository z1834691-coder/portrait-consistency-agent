"""Run a fair, answerless compiler candidate on public development data.

This module is deliberately kept away from V3/V4 holdout paths.  It compares
the active phrase projector with a reviewed query-compiler candidate while
keeping the retrieval prediction restricted to actual P0-B evidence.  Gold
annotations are read only for the public development report and are never
passed into the runner.
"""

from __future__ import annotations

import html
import json
from collections.abc import Mapping
from pathlib import Path

from portrait_consistency_agent.services.rag_gold_eval import (
    GoldCase,
    GoldSetFormatError,
    Prediction,
    evaluate,
    load_annotations,
    load_public_cases,
)
from portrait_consistency_agent.services.rag_process_supervisor import (
    FairEvaluationRun,
    RagFairEvaluationRunner,
    audit_fair_run,
    fair_trace_payload,
)
from portrait_consistency_agent.services.rag_query_compiler_candidate import (
    compile_generalized_projection,
)

FAIR_DEV_CANDIDATE_VERSION = "rag-fair-dev-compiler-candidate-v0.1"
_KNOWLEDGE_ALIASES = {
    "tencent-beautify-pic-2019-12-13": "B",
    "tencent-compare-face-2018-03-01": "C",
    "tencent-image-moderation-2020-12-29": "I",
}
_RELATION_STRENGTH = {
    "reference_context": 1,
    "direct_evidence": 2,
    "conflict_evidence": 3,
}


def _alias(ref: str) -> str | None:
    base = ref.split("#", 1)[0]
    if base.startswith("project-policy-"):
        if base.endswith("-lifecycle"):
            return "FX"
        if base.endswith("-guard"):
            return "P"
    return _KNOWLEDGE_ALIASES.get(base)


def _merge_relation(relations: dict[str, str], alias: str, relation: str) -> None:
    """Keep the strongest relation when several chunks share one source alias."""

    old = relations.get(alias)
    if old is None or _RELATION_STRENGTH.get(relation, 0) > _RELATION_STRENGTH.get(old, 0):
        relations[alias] = relation


def _compiler_predictions(run: FairEvaluationRun) -> tuple[Prediction, ...]:
    traces = run.traces
    rows: list[Prediction] = []
    for trace in traces:
        compiler = trace.get("compiler", {})
        prediction = trace.get("prediction", {})
        if not isinstance(compiler, Mapping) or not isinstance(prediction, Mapping):
            raise GoldSetFormatError("fair candidate trace is missing compiler/prediction")
        case_id = str(trace.get("case_id", ""))
        rows.append(
            Prediction(
                case_id=case_id,
                route=str(compiler.get("proposed_route"))
                if compiler.get("proposed_route")
                else None,
                trace_ref=str(prediction.get("trace_ref")) if prediction.get("trace_ref") else None,
            )
        )
    return tuple(rows)


def _retrieval_predictions(run: FairEvaluationRun) -> tuple[Prediction, ...]:
    traces = run.traces
    rows: list[Prediction] = []
    for trace in traces:
        retrieval = trace.get("retrieval", {})
        prediction = trace.get("prediction", {})
        if not isinstance(retrieval, Mapping) or not isinstance(prediction, Mapping):
            raise GoldSetFormatError("fair candidate trace is missing retrieval/prediction")
        # Retrieval quality is scored on the ranked candidates the retriever
        # actually returned.  ``adopted_evidence_refs`` is a downstream
        # policy subset and would silently mix retrieval with evidence
        # adoption.  The fair Gold join uses the same boundary.
        actual_refs = retrieval.get("actual_evidence_refs", [])
        relation_map = retrieval.get("evidence_relations", {})
        if not isinstance(actual_refs, list) or not isinstance(relation_map, Mapping):
            raise GoldSetFormatError("fair candidate retrieval lineage is malformed")
        refs: list[str] = []
        relations: dict[str, str] = {}
        for raw_ref in actual_refs:
            alias = _alias(str(raw_ref))
            if alias is None or alias in refs:
                continue
            refs.append(alias)
            _merge_relation(
                relations,
                alias,
                str(relation_map.get(str(raw_ref), "reference_context")),
            )
        rows.append(
            Prediction(
                case_id=str(trace.get("case_id", "")),
                route=str(retrieval.get("route")) if retrieval.get("route") else None,
                evidence_refs=tuple(refs),
                evidence_relations=relations,
                trace_ref=str(prediction.get("trace_ref")) if prediction.get("trace_ref") else None,
            )
        )
    return tuple(rows)


def _adopted_predictions(run: FairEvaluationRun) -> tuple[Prediction, ...]:
    """Build a second, explicitly downstream adoption track.

    The ranked retrieval list is allowed to contain more than the three facts
    that the advisory layer adopts.  Scoring that ranked list with exact-set
    accuracy would therefore mark a healthy Top-10 retrieval as wrong.  This
    helper keeps the adopted subset separate so exact-set/route-adjacent
    diagnostics remain available without mixing them into ranking metrics.
    """

    rows: list[Prediction] = []
    for trace in run.traces:
        retrieval = trace.get("retrieval", {})
        prediction = trace.get("prediction", {})
        if not isinstance(retrieval, Mapping) or not isinstance(prediction, Mapping):
            raise GoldSetFormatError("fair candidate trace is missing retrieval/prediction")
        adopted_refs = retrieval.get("adopted_evidence_refs", [])
        relation_map = retrieval.get("evidence_relations", {})
        if not isinstance(adopted_refs, list) or not isinstance(relation_map, Mapping):
            raise GoldSetFormatError("fair candidate adoption lineage is malformed")
        refs: list[str] = []
        relations: dict[str, str] = {}
        for raw_ref in adopted_refs:
            alias = _alias(str(raw_ref))
            if alias is None or alias in refs:
                continue
            refs.append(alias)
            _merge_relation(
                relations,
                alias,
                str(relation_map.get(str(raw_ref), "reference_context")),
            )
        rows.append(
            Prediction(
                case_id=str(trace.get("case_id", "")),
                route=str(retrieval.get("route")) if retrieval.get("route") else None,
                evidence_refs=tuple(refs),
                evidence_relations=relations,
                trace_ref=str(prediction.get("trace_ref")) if prediction.get("trace_ref") else None,
            )
        )
    return tuple(rows)


def _route_only_metrics(
    cases: tuple[GoldCase, ...],
    annotations: Mapping[str, object],
    predictions: tuple[Prediction, ...],
) -> dict[str, object]:
    prediction_by_id = {row.case_id: row for row in predictions}
    correct = 0
    for case in cases:
        annotation = annotations[case.case_id]
        routes = getattr(annotation, "gold_routes", ())
        route = prediction_by_id.get(case.case_id)
        if route is not None:
            expected = {
                token.strip().upper()
                for value in routes
                for token in value.replace("→", "/").replace("+", "/").split("/")
                if token.strip()
            }
            if str(route.route).upper() in expected:
                correct += 1
    return {
        "cases": len(cases),
        "predictions": len(predictions),
        "route_correct": correct,
        "route_accuracy": round(correct / len(cases), 6) if cases else None,
        "unknown_or_missing_route": len(cases) - correct,
    }


def _changed_count(before: tuple[Prediction, ...], after: tuple[Prediction, ...]) -> int:
    old = {row.case_id: row for row in before}
    return sum(
        old.get(row.case_id) is None
        or old[row.case_id].route != row.route
        or old[row.case_id].evidence_refs != row.evidence_refs
        or dict(old[row.case_id].evidence_relations) != dict(row.evidence_relations)
        for row in after
    )


def _retrieval_metric_report(
    *,
    cases: tuple[GoldCase, ...],
    annotations: Mapping[str, object],
    predictions: tuple[Prediction, ...],
    dataset_version: str,
) -> dict[str, object]:
    """Score ranked evidence without importing the downstream route contract."""

    metrics = dict(
        evaluate(
            cases=cases,
            annotations=annotations,
            predictions={row.case_id: row for row in predictions},
            dataset_version=dataset_version,
        ).metrics
        or {}
    )
    # A ranked candidate list is deliberately longer than the adopted
    # evidence set.  Exact-set accuracy is consequently an adoption metric,
    # not a retrieval-ranking metric.  Keep the historical value out of this
    # track instead of letting it create a false failure signal.
    metrics["evidence_exact_accuracy"] = None
    metrics["evidence_exact_scope"] = "not_scored_on_ranked_candidate_list"
    metrics["cases"] = len(cases)
    metrics["predictions"] = len(predictions)
    metrics["route_accuracy"] = None
    metrics["project_threshold_gate"] = "NOT_APPLICABLE_RETRIEVAL_TRACK"
    metrics["route_metric_scope"] = "not_scored_on_retrieval_track"
    return metrics


def _adoption_metric_report(
    *,
    cases: tuple[GoldCase, ...],
    annotations: Mapping[str, object],
    predictions: tuple[Prediction, ...],
    dataset_version: str,
) -> dict[str, object]:
    """Score the evidence subset actually adopted by the advisory layer."""

    metrics = dict(
        evaluate(
            cases=cases,
            annotations=annotations,
            predictions={row.case_id: row for row in predictions},
            dataset_version=dataset_version,
        ).metrics
        or {}
    )
    metrics["evidence_exact_scope"] = "scored_on_adopted_evidence_subset"
    metrics["cases"] = len(cases)
    metrics["predictions"] = len(predictions)
    metrics["route_accuracy"] = None
    metrics["route_metric_scope"] = "not_scored_on_adoption_track"
    metrics["project_threshold_gate"] = "NOT_APPLICABLE_ADOPTION_TRACK"
    return metrics


def _run_one(
    cases: tuple[GoldCase, ...],
    *,
    compiler: object | None,
    compiler_version: str,
) -> tuple[FairEvaluationRun, dict[str, object]]:
    runner = RagFairEvaluationRunner()
    run = runner.run(
        cases,
        dataset_version="public-dev",
        runtime_mode="public_dev_candidate",
        projection_compiler=compiler,  # type: ignore[arg-type]
        compiler_version=compiler_version,
    )
    audit = audit_fair_run(run, run_id=f"{compiler_version}-process")
    return run, audit.to_dict(redact_case_ids=True)


def build_fair_dev_candidate_report(
    *,
    cases_path: Path,
    annotations_path: Path,
    regression_cases_path: Path,
    regression_annotations_path: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    """Compare baseline and one compiler candidate on public dev/regression."""

    dataset_version, cases = load_public_cases(cases_path)
    annotations = load_annotations(
        annotations_path, allowed_case_ids=[case.case_id for case in cases]
    )
    regression_version, regression_cases = load_public_cases(regression_cases_path)
    regression_annotations = load_annotations(
        regression_annotations_path,
        allowed_case_ids=[case.case_id for case in regression_cases],
    )
    baseline, baseline_process = _run_one(
        cases, compiler=None, compiler_version="project-runtime-prompt-v0.2"
    )
    candidate, candidate_process = _run_one(
        cases,
        compiler=compile_generalized_projection,
        compiler_version=FAIR_DEV_CANDIDATE_VERSION,
    )
    regression_baseline, _ = _run_one(
        regression_cases, compiler=None, compiler_version="project-runtime-prompt-v0.2"
    )
    regression_candidate, regression_candidate_process = _run_one(
        regression_cases,
        compiler=compile_generalized_projection,
        compiler_version=FAIR_DEV_CANDIDATE_VERSION,
    )
    baseline_compiler = _compiler_predictions(baseline)
    candidate_compiler = _compiler_predictions(candidate)
    baseline_retrieval = _retrieval_predictions(baseline)
    candidate_retrieval = _retrieval_predictions(candidate)
    regression_baseline_retrieval = _retrieval_predictions(regression_baseline)
    regression_candidate_retrieval = _retrieval_predictions(regression_candidate)
    report = {
        "report_version": FAIR_DEV_CANDIDATE_VERSION,
        "scope": "public_dev_candidate_only",
        "dataset": {
            "version": dataset_version,
            "cases": len(cases),
            "annotations_read": True,
            "holdout_answers_read": False,
        },
        "candidate": {
            "compiler_version": FAIR_DEV_CANDIDATE_VERSION,
            "description": (
                "把经过审核的同义词、动作/能力和安全优先级接到真实 RAG 查询入口；"
                "不修改 Provider 或权限。"
            ),
            "proposal_only": True,
            "active_baseline_changed": False,
        },
        "tracks": {
            "compiler_baseline": _route_only_metrics(cases, annotations, baseline_compiler),
            "compiler_candidate": _route_only_metrics(cases, annotations, candidate_compiler),
            "retrieval_baseline": _retrieval_metric_report(
                cases=cases,
                annotations=annotations,
                predictions=baseline_retrieval,
                dataset_version=dataset_version,
            ),
            "retrieval_candidate": _retrieval_metric_report(
                cases=cases,
                annotations=annotations,
                predictions=candidate_retrieval,
                dataset_version=dataset_version,
            ),
            "regression_baseline": _retrieval_metric_report(
                cases=regression_cases,
                annotations=regression_annotations,
                predictions=regression_baseline_retrieval,
                dataset_version=regression_version,
            ),
            "regression_candidate": _retrieval_metric_report(
                cases=regression_cases,
                annotations=regression_annotations,
                predictions=regression_candidate_retrieval,
                dataset_version=regression_version,
            ),
        },
        "changed_prediction_count": _changed_count(baseline_retrieval, candidate_retrieval),
        "process": {
            "baseline": baseline_process,
            "candidate": candidate_process,
            "regression_candidate": regression_candidate_process,
        },
        "policy": {
            "network_called": False,
            "llm_called": False,
            "provider_api_called": False,
            "hidden_answer_key_read": False,
            "prediction_source": "actual_retrieved_evidence_only",
            "promotion_decision": "not_promoted_proposal_only",
        },
        "interpretation": (
            "本实验只验证候选是否触达真实查询入口；开发集提升不能替代独立 Holdout，"
            "回归退化时必须回滚。"
        ),
        "next_step": "if_no_holdout_gain_then_add_reviewed_policy_cards_or_create_v5",
    }
    traces = {
        "report_version": FAIR_DEV_CANDIDATE_VERSION,
        "baseline": fair_trace_payload(baseline),
        "candidate": fair_trace_payload(candidate),
    }
    return report, traces


def render_fair_dev_candidate_html(report: Mapping[str, object]) -> str:
    tracks = report.get("tracks", {})
    tracks = tracks if isinstance(tracks, Mapping) else {}
    rows: list[str] = []
    for name in (
        "compiler_baseline",
        "compiler_candidate",
        "retrieval_baseline",
        "retrieval_candidate",
        "regression_baseline",
        "regression_candidate",
    ):
        metrics = tracks.get(name, {})
        metrics = metrics if isinstance(metrics, Mapping) else {}
        rows.append(
            "<tr><th>"
            + html.escape(name)
            + "</th>"
            + "".join(
                f"<td>{html.escape(str(metrics.get(key, '—')))}</td>"
                for key in (
                    "cases",
                    "route_accuracy",
                    "evidence_relation_accuracy",
                    "recall_at_5",
                    "mrr",
                )
            )
            + "</tr>"
        )
    style = (
        "body{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;"
        "max-width:1100px;margin:30px auto;padding:0 22px;background:#f7f8fb;"
        "color:#18212b;line-height:1.55}"
        "table{width:100%;border-collapse:collapse;background:#fff}"
        "th,td{border:1px solid #dce3ec;padding:9px;text-align:left}"
        "th{background:#eef2f6}.note{padding:14px 16px;background:#fff7df;"
        "border-left:4px solid #c88900;margin:14px 0}"
    )
    return (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<title>RAG 公平开发候选</title>"
        f"<style>{style}</style></head><body><h1>RAG 公平开发候选｜查询入口实验</h1>"
        "<div class='note'>这是公开开发/回归实验，不是 V3/V4 Holdout，"
        "也不代表 RAG 已产品化。检索指标只使用实际召回证据。</div>"
        "<table><thead><tr><th>轨道/代次</th><th>题数</th><th>路由准确率</th><th>证据关系</th><th>Recall@5</th><th>MRR</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table><p>真实改变的检索 Prediction 数：<strong>"
        + html.escape(str(report.get("changed_prediction_count", "—")))
        + "</strong>；过程门和副作用事实见 JSON。</p></body></html>"
    )


def write_fair_dev_candidate_report(
    report: Mapping[str, object],
    traces: Mapping[str, object],
    *,
    json_path: Path,
    html_path: Path,
    trace_path: Path,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html_path.write_text(render_fair_dev_candidate_html(report), encoding="utf-8")
    trace_path.write_text(json.dumps(traces, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


__all__ = [
    "FAIR_DEV_CANDIDATE_VERSION",
    "build_fair_dev_candidate_report",
    "render_fair_dev_candidate_html",
    "write_fair_dev_candidate_report",
]
