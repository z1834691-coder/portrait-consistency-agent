"""Public-only evaluation for the route-handoff and specificity candidates."""

from __future__ import annotations

import html
import json
from collections.abc import Mapping
from pathlib import Path

from portrait_consistency_agent.services.rag_evidence_selection_candidate import (
    EVIDENCE_SELECTION_CANDIDATE_VERSION,
    select_explanation_evidence,
)
from portrait_consistency_agent.services.rag_fair_dev_candidate import (
    _alias,
    _changed_count,
    _merge_relation,
    _retrieval_metric_report,
    _retrieval_predictions,
)
from portrait_consistency_agent.services.rag_gold_eval import (
    GoldCase,
    GoldSetFormatError,
    Prediction,
    evaluate,
    load_annotations,
    load_public_cases,
)
from portrait_consistency_agent.services.rag_policy_coverage_candidate import (
    policy_candidate_query_builder_multi_operation,
    policy_query_term_expander,
    policy_relation_resolver_v4,
    seed_reviewed_policy_knowledge_candidate,
)
from portrait_consistency_agent.services.rag_process_supervisor import (
    FairEvaluationRun,
    RagFairEvaluationRunner,
    audit_fair_run,
    fair_trace_payload,
)
from portrait_consistency_agent.services.rag_query_compiler_candidate import (
    compile_generalized_projection_v3,
)
from portrait_consistency_agent.services.rag_route_handoff_candidate import (
    ROUTE_HANDOFF_CANDIDATE_VERSION,
    select_validated_route,
)

SPECIFICITY_CANDIDATE_VERSION = "rag-specificity-candidate-v1.1"
EVALUATION_VERSION = "rag-route-handoff-evaluation-v0.1"


def _prediction_rows(run: FairEvaluationRun) -> tuple[Prediction, ...]:
    """Read final route/evidence and normalize refs to the Gold vocabulary.

    Provider chunks carry versioned source references, while the reviewed Gold
    annotations intentionally use stable abstract aliases (for example ``B``
    for BeautifyPic).  The old candidate evaluator compared these two
    vocabularies directly, so every final evidence score became zero even when
    the selected chunk was correct.  Normalization is deterministic and uses
    the same reviewed alias map as the ranked retrieval track; it does not add
    or invent evidence.
    """

    rows: list[Prediction] = []
    for trace in run.traces:
        prediction = trace.get("prediction")
        retrieval = trace.get("retrieval")
        if not isinstance(prediction, Mapping) or not isinstance(retrieval, Mapping):
            raise GoldSetFormatError("candidate trace missing prediction/retrieval")
        refs = prediction.get("evidence_refs", [])
        relations = prediction.get("evidence_relations", {})
        if not isinstance(refs, list) or not isinstance(relations, Mapping):
            raise GoldSetFormatError("candidate prediction lineage malformed")
        normalized_refs: list[str] = []
        normalized_relations: dict[str, str] = {}
        for raw_ref in refs:
            alias = _alias(str(raw_ref))
            if alias is None or alias in normalized_refs:
                continue
            normalized_refs.append(alias)
            _merge_relation(
                normalized_relations,
                alias,
                str(relations.get(str(raw_ref), "reference_context")),
            )
        rows.append(
            Prediction(
                case_id=str(trace.get("case_id", "")),
                route=str(prediction.get("route")) if prediction.get("route") else None,
                evidence_refs=tuple(normalized_refs),
                evidence_relations=normalized_relations,
                trace_ref=str(prediction.get("trace_ref")) if prediction.get("trace_ref") else None,
            )
        )
    return tuple(rows)


def _route_metrics(
    cases: tuple[GoldCase, ...],
    annotations: Mapping[str, object],
    predictions: tuple[Prediction, ...],
    dataset_version: str,
) -> dict[str, object]:
    metrics = dict(
        evaluate(
            cases=cases,
            annotations=annotations,
            predictions={row.case_id: row for row in predictions},
            dataset_version=dataset_version,
        ).metrics
        or {}
    )
    metrics["cases"] = len(cases)
    metrics["predictions"] = len(predictions)
    return metrics


def _run(
    cases: tuple[GoldCase, ...],
    *,
    compiler: bool,
    specificity: bool,
    explanation_selection: bool = False,
) -> tuple[FairEvaluationRun, dict[str, object]]:
    runner = RagFairEvaluationRunner()
    run = runner.run(
        cases,
        dataset_version="public-dev",
        runtime_mode="public_dev_candidate",
        projection_compiler=compile_generalized_projection_v3 if compiler else None,
        compiler_version=(
            EVIDENCE_SELECTION_CANDIDATE_VERSION
            if explanation_selection
            else SPECIFICITY_CANDIDATE_VERSION
            if specificity
            else ROUTE_HANDOFF_CANDIDATE_VERSION
            if compiler
            else "project-runtime-prompt-v0.2"
        ),
        knowledge_seeder=seed_reviewed_policy_knowledge_candidate if specificity else None,
        query_builder=policy_candidate_query_builder_multi_operation if specificity else None,
        relation_resolver=policy_relation_resolver_v4 if specificity else None,
        query_term_expander=policy_query_term_expander if specificity else None,
        operation_coverage=specificity,
        route_handoff=select_validated_route if compiler else None,
        evidence_selection=select_explanation_evidence if explanation_selection else None,
    )
    audit = audit_fair_run(run, run_id=f"{EVALUATION_VERSION}-{run.dataset_version}")
    return run, audit.to_dict(redact_case_ids=True)


def _one_dataset(
    *,
    cases: tuple[GoldCase, ...],
    annotations: Mapping[str, object],
    dataset_version: str,
) -> tuple[dict[str, object], dict[str, object]]:
    baseline, baseline_process = _run(cases, compiler=False, specificity=False)
    handoff, handoff_process = _run(cases, compiler=True, specificity=False)
    specificity, specificity_process = _run(cases, compiler=True, specificity=True)
    explanation, explanation_process = _run(
        cases,
        compiler=True,
        specificity=True,
        explanation_selection=True,
    )
    baseline_final = _prediction_rows(baseline)
    handoff_final = _prediction_rows(handoff)
    specificity_final = _prediction_rows(specificity)
    baseline_ranked = _retrieval_predictions(baseline)
    handoff_ranked = _retrieval_predictions(handoff)
    specificity_ranked = _retrieval_predictions(specificity)
    tracks: dict[str, object] = {
        "baseline_final": _route_metrics(cases, annotations, baseline_final, dataset_version),
        "route_handoff_final": _route_metrics(cases, annotations, handoff_final, dataset_version),
        "specificity_final": _route_metrics(cases, annotations, specificity_final, dataset_version),
        "explanation_selection_final": _route_metrics(
            cases, annotations, _prediction_rows(explanation), dataset_version
        ),
        "baseline_retrieval": _retrieval_metric_report(
            cases=cases,
            annotations=annotations,
            predictions=baseline_ranked,
            dataset_version=dataset_version,
        ),
        "route_handoff_retrieval": _retrieval_metric_report(
            cases=cases,
            annotations=annotations,
            predictions=handoff_ranked,
            dataset_version=dataset_version,
        ),
        "specificity_retrieval": _retrieval_metric_report(
            cases=cases,
            annotations=annotations,
            predictions=specificity_ranked,
            dataset_version=dataset_version,
        ),
        "explanation_selection_retrieval": _retrieval_metric_report(
            cases=cases,
            annotations=annotations,
            predictions=_retrieval_predictions(explanation),
            dataset_version=dataset_version,
        ),
    }
    payload = {
        "version": dataset_version,
        "cases": len(cases),
        "tracks": tracks,
        "changed_prediction_count_route_handoff": _changed_count(baseline_final, handoff_final),
        "changed_prediction_count_specificity": _changed_count(handoff_final, specificity_final),
        "changed_prediction_count_explanation_selection": _changed_count(
            specificity_final, _prediction_rows(explanation)
        ),
        "process": {
            "baseline": baseline_process,
            "route_handoff": handoff_process,
            "specificity": specificity_process,
            "explanation_selection": explanation_process,
        },
    }
    traces = {
        "evaluation_version": EVALUATION_VERSION,
        "dataset_version": dataset_version,
        "baseline": fair_trace_payload(baseline),
        "route_handoff": fair_trace_payload(handoff),
        "specificity": fair_trace_payload(specificity),
        "explanation_selection": fair_trace_payload(explanation),
    }
    return payload, traces


def build_route_handoff_evaluation_report(
    *,
    cases_path: Path,
    annotations_path: Path,
    regression_cases_path: Path,
    regression_annotations_path: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    dataset_version, cases = load_public_cases(cases_path)
    annotations = load_annotations(
        annotations_path, allowed_case_ids=[case.case_id for case in cases]
    )
    regression_version, regression_cases = load_public_cases(regression_cases_path)
    regression_annotations = load_annotations(
        regression_annotations_path,
        allowed_case_ids=[case.case_id for case in regression_cases],
    )
    development, development_traces = _one_dataset(
        cases=cases, annotations=annotations, dataset_version=dataset_version
    )
    regression, regression_traces = _one_dataset(
        cases=regression_cases,
        annotations=regression_annotations,
        dataset_version=regression_version,
    )
    return (
        {
            "report_version": EVALUATION_VERSION,
            "scope": "public_dev_and_regression_only",
            "candidate": {
                "route_handoff_version": ROUTE_HANDOFF_CANDIDATE_VERSION,
                "specificity_version": SPECIFICITY_CANDIDATE_VERSION,
                "evidence_selection_version": EVIDENCE_SELECTION_CANDIDATE_VERSION,
                "proposal_only": True,
                "active_baseline_changed": False,
                "external_calls": False,
                "description": (
                    "先修复结构化查询到最终路径的真实交接，再独立观察按功能部位区分证据关系；"
                    "最后再观察解释证据的最小按命名空间选取；三者均只消费真实检索结果。"
                ),
            },
            "datasets": {"development": development, "regression": regression},
            "policy": {
                "holdout_answers_read": False,
                "network_called": False,
                "llm_called": False,
                "provider_api_called": False,
                "photos_or_vectors_read": False,
                "promotion_decision": "not_promoted_proposal_only",
            },
            "next_step": "compare_candidate_deltas_then_decide_whether_new_holdout_is_needed",
        },
        {
            "development": development_traces,
            "regression": regression_traces,
        },
    )


def render_route_handoff_html(report: Mapping[str, object]) -> str:
    rows: list[str] = []
    datasets = report.get("datasets", {})
    for dataset_name, dataset in datasets.items() if isinstance(datasets, Mapping) else ():
        if not isinstance(dataset, Mapping):
            continue
        tracks = dataset.get("tracks", {})
        for track_name, metrics in tracks.items() if isinstance(tracks, Mapping) else ():
            if not isinstance(metrics, Mapping):
                continue
            rows.append(
                "<tr><td>"
                + html.escape(f"{dataset_name} / {track_name}")
                + "</td>"
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
        "max-width:1200px;margin:28px auto;padding:0 22px;background:#f6f8fb;"
        "color:#1f2933;line-height:1.55}"
        "table{width:100%;border-collapse:collapse;background:#fff}"
        "th,td{border:1px solid #d9e1ea;padding:8px;text-align:left}"
        "th{background:#edf2f7}.note{padding:12px;background:#fff7df;border-left:4px solid #c88719}"
    )
    development = datasets.get("development", {}) if isinstance(datasets, Mapping) else {}
    development = development if isinstance(development, Mapping) else {}
    handoff_count = development.get("changed_prediction_count_route_handoff", "—")
    specificity_count = development.get("changed_prediction_count_specificity", "—")
    explanation_count = development.get("changed_prediction_count_explanation_selection", "—")
    return (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<title>RAG 路径交接与证据特异性候选</title>"
        f"<style>{style}</style></head><body><h1>RAG 真实链路候选评测</h1>"
        "<div class='note'>公开开发/公开回归实验；V5 未读取，候选不改 "
        "active baseline，仍是 proposal-only。</div>"
        "<table><thead><tr><th>数据集/轨道</th><th>题数</th><th>Route</th><th>关系</th><th>Recall@5</th><th>MRR</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
        + "<p>路径交接真实改变数：<strong>"
        + html.escape(str(handoff_count))
        + "</strong>；特异性候选相对交接改变数：<strong>"
        + html.escape(str(specificity_count))
        + "</strong>；解释证据选取相对特异性候选改变数：<strong>"
        + html.escape(str(explanation_count))
        + "</strong>。</p></body></html>"
    )


def write_route_handoff_evaluation_report(
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
    html_path.write_text(render_route_handoff_html(report), encoding="utf-8")
    trace_path.write_text(json.dumps(traces, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


__all__ = [
    "EVALUATION_VERSION",
    "SPECIFICITY_CANDIDATE_VERSION",
    "build_route_handoff_evaluation_report",
    "render_route_handoff_html",
    "write_route_handoff_evaluation_report",
]
