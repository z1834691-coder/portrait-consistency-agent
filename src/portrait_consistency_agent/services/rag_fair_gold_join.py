"""Join a sealed answerless RAG run with a private Gold key.

This module is the quality-scoring step after the independent process gate.
It deliberately keeps the answer key in memory and emits aggregate-only
results.  It also reports two separate tracks:

* compiler track: did the natural-language compiler propose the reviewed
  route (a provisional proxy until slot-level compiler Gold exists)?
* retrieval track: did the real retrieval result contain and rank the reviewed
  evidence, and did its relation labels agree?

The retrieval prediction is built from actual retrieved knowledge references,
never from projection aliases or evaluation labels.  The output contains no
questions, answer facts, private paths, or case IDs.
"""

# ruff: noqa: E501

from __future__ import annotations

import html
import json
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path

from portrait_consistency_agent.services.rag_gold_eval import (
    GoldAnnotation,
    GoldCase,
    GoldSetFormatError,
    Prediction,
    canonical_route,
    evaluate,
    load_annotations,
    load_holdout_runtime_cases,
    load_validation_cases,
)

FAIR_GOLD_JOIN_VERSION = "rag-fair-gold-join-v0.2"
_KNOWLEDGE_ID_ALIASES = {
    "tencent-beautify-pic-2019-12-13": "B",
    "tencent-compare-face-2018-03-01": "C",
    "tencent-image-moderation-2020-12-29": "I",
}
_METRIC_NAMES = (
    "route_accuracy",
    "evidence_exact_accuracy",
    "evidence_relation_accuracy",
    "precision_at_3",
    "precision_at_3_effective",
    "precision_at_3_returned",
    "recall_at_5",
    "hit_at_5",
    "mrr",
    "ndcg_at_5",
    "hard_safety_violation_count",
    "hard_safety_gate",
    "project_threshold_gate",
)
_RELATION_STRENGTH = {
    "reference_context": 1,
    "direct_evidence": 2,
    "conflict_evidence": 3,
}


def _sha256(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _knowledge_alias(ref: str) -> str | None:
    if ref in {"B", "C", "I", "P", "FX"}:
        return ref
    base = ref.split("#", 1)[0]
    if base.startswith("project-policy-"):
        if base.endswith("-lifecycle"):
            return "FX"
        if base.endswith("-guard"):
            return "P"
    return _KNOWLEDGE_ID_ALIASES.get(base)


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _merge_relation(relations: dict[str, str], alias: str, relation: str) -> None:
    """Collapse chunk-level relations without letting a later weak chunk win."""

    old = relations.get(alias)
    if old is None or _RELATION_STRENGTH.get(relation, 0) > _RELATION_STRENGTH.get(old, 0):
        relations[alias] = relation


def _load_runtime(path: Path, *, validation: bool) -> tuple[str, tuple[GoldCase, ...]]:
    if validation:
        return load_validation_cases(path)
    return load_holdout_runtime_cases(path)


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GoldSetFormatError(f"cannot read fair scoring artifact: {exc}") from exc


def _rows(payload: object, *, field: str, path: Path) -> list[Mapping[str, object]]:
    if not isinstance(payload, dict) or not isinstance(payload.get(field), list):
        raise GoldSetFormatError(f"{path}: expected {field}[]")
    values = payload[field]
    if not all(isinstance(item, dict) for item in values):
        raise GoldSetFormatError(f"{path}: {field} must contain objects")
    return values  # type: ignore[return-value]


def _validate_answerless_payload(payload: Mapping[str, object], *, path: Path) -> None:
    policy = payload.get("policy")
    if not isinstance(policy, dict):
        raise GoldSetFormatError(f"{path}: missing answerless policy")
    required_false = (
        "hidden_answer_key_read",
        "answer_key_read",
        "annotations_read",
        "quality_score_joined",
        "network_called",
        "llm_called",
        "provider_api_called",
        "external_provider_called",
        "photo_or_face_vector_read",
        "raw_prompt_persisted",
        "projection_injected_into_prediction",
    )
    bad = [key for key in required_false if policy.get(key) is not False]
    if bad:
        raise GoldSetFormatError(f"{path}: answerless policy is not clean: {sorted(bad)}")


def _load_fresh_artifacts(
    *,
    cases: tuple[GoldCase, ...],
    predictions_path: Path,
    trace_path: Path,
) -> tuple[dict[str, Mapping[str, object]], dict[str, Mapping[str, object]]]:
    prediction_payload = _read_json(predictions_path)
    trace_payload = _read_json(trace_path)
    if not isinstance(prediction_payload, dict) or not isinstance(trace_payload, dict):
        raise GoldSetFormatError("fair artifacts must be JSON objects")
    _validate_answerless_payload(prediction_payload, path=predictions_path)
    _validate_answerless_payload(trace_payload, path=trace_path)
    prediction_rows = _rows(prediction_payload, field="rows", path=predictions_path)
    trace_rows = _rows(trace_payload, field="traces", path=trace_path)
    expected_hashes = {_sha256(case.case_id) for case in cases}
    by_hash: dict[str, Mapping[str, object]] = {}
    for row in prediction_rows:
        case_hash = row.get("case_id_sha256")
        if not isinstance(case_hash, str) or case_hash not in expected_hashes:
            raise GoldSetFormatError("fair predictions have an unknown or non-redacted case hash")
        if "case_id" in row or "query" in row or any(str(k).startswith("gold_") for k in row):
            raise GoldSetFormatError("fair predictions contain a forbidden identifying field")
        if case_hash in by_hash:
            raise GoldSetFormatError("fair predictions contain duplicate case hashes")
        by_hash[case_hash] = row
    traces_by_ref: dict[str, Mapping[str, object]] = {}
    for row in trace_rows:
        case_hash = row.get("case_id_sha256")
        if not isinstance(case_hash, str) or case_hash not in expected_hashes:
            raise GoldSetFormatError("fair traces have an unknown or non-redacted case hash")
        if "case_id" in row or "query" in row or any(str(k).startswith("gold_") for k in row):
            raise GoldSetFormatError("fair traces contain a forbidden identifying field")
        prediction = row.get("prediction")
        if not isinstance(prediction, dict) or not isinstance(prediction.get("trace_ref"), str):
            raise GoldSetFormatError("fair trace has no prediction trace reference")
        trace_ref = str(prediction["trace_ref"])
        if trace_ref in traces_by_ref:
            raise GoldSetFormatError("fair traces contain duplicate trace references")
        traces_by_ref[trace_ref] = row
    if set(by_hash) != expected_hashes or len(traces_by_ref) != len(cases):
        raise GoldSetFormatError("fair artifacts do not cover exactly the runtime cases")
    return by_hash, traces_by_ref


def _metric_subset(report: object, *, retrieval_track: bool = False) -> dict[str, object]:
    metrics = dict(getattr(report, "metrics", {}) or {})
    subset = {name: metrics.get(name) for name in _METRIC_NAMES}
    if retrieval_track:
        # Route is decided downstream of retrieval.  The old v0.1 aggregate
        # exposed evaluate()'s route score here, which mixed two different
        # contracts and made the retrieval track look worse than it was.
        subset["route_accuracy"] = None
        subset["project_threshold_gate"] = "NOT_APPLICABLE_RETRIEVAL_TRACK"
    return subset


def _error_counts(
    *,
    cases: tuple[GoldCase, ...],
    annotations: Mapping[str, GoldAnnotation],
    predictions: Mapping[str, Prediction],
    include_route: bool = True,
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for case in cases:
        annotation = annotations[case.case_id]
        prediction = predictions[case.case_id]
        if include_route:
            expected_routes = {
                canonical_route(token.strip())
                for route in annotation.gold_routes
                for token in route.replace("→", "/").replace("+", "/").split("/")
                if token.strip()
            }
            if prediction.route is None or canonical_route(prediction.route) not in expected_routes:
                counts["route_mismatch"] += 1
        gold = set(annotation.gold_evidence)
        predicted = tuple(dict.fromkeys(prediction.evidence_refs))
        if gold and set(predicted) != gold:
            counts["evidence_set_mismatch"] += 1
        if annotation.gold_evidence_relations:
            if any(
                prediction.evidence_relations.get(ref) != relation
                for ref, relation in annotation.gold_evidence_relations.items()
            ):
                counts["evidence_relation_mismatch"] += 1
        if gold and not (gold & set(predicted[:5])):
            counts["retrieval_miss_at_5"] += 1
    return dict(sorted(counts.items()))


def _track_payload(
    *,
    name: str,
    report: object,
    errors: Mapping[str, int],
    note: str,
    retrieval_track: bool = False,
) -> dict[str, object]:
    return {
        "track": name,
        "status": getattr(report, "status", "unknown"),
        "counts": dict(getattr(report, "counts", {}) or {}),
        "metrics": _metric_subset(report, retrieval_track=retrieval_track),
        "route_metric_scope": (
            "not_scored_on_retrieval_track"
            if retrieval_track
            else "scored_on_compiler_or_end_to_end_track"
        ),
        "error_type_counts": dict(errors),
        "note": note,
    }


def _build_dataset_join(
    *,
    name: str,
    runtime_path: Path,
    predictions_path: Path,
    trace_path: Path,
    answer_key_path: Path,
    validation: bool,
) -> dict[str, object]:
    dataset_version, cases = _load_runtime(runtime_path, validation=validation)
    prediction_rows, trace_rows = _load_fresh_artifacts(
        cases=cases, predictions_path=predictions_path, trace_path=trace_path
    )
    annotations = load_annotations(
        answer_key_path, allowed_case_ids=[case.case_id for case in cases]
    )
    by_hash = {_sha256(case.case_id): case.case_id for case in cases}
    compiler_predictions: dict[str, Prediction] = {}
    retrieval_predictions: dict[str, Prediction] = {}
    compiler_unknown = 0
    unknown_ref_count = 0
    for case_hash, row in prediction_rows.items():
        case_id = by_hash[case_hash]
        trace_ref = row.get("trace_ref")
        trace = trace_rows.get(str(trace_ref))
        if trace is None:
            raise GoldSetFormatError("fair prediction is missing its trace")
        compiler = trace.get("compiler")
        retrieval = trace.get("retrieval")
        if not isinstance(compiler, dict) or not isinstance(retrieval, dict):
            raise GoldSetFormatError("fair trace is missing compiler or retrieval facts")
        compiler_status = str(compiler.get("status", "unknown"))
        compiler_unknown += int(compiler_status == "unknown_fallback")
        compiler_predictions[case_id] = Prediction(
            case_id=case_id,
            route=str(compiler.get("proposed_route")) if compiler.get("proposed_route") else None,
            observed_events=tuple(str(item) for item in row.get("observed_events", []) or []),
            trace_ref=str(trace_ref) if trace_ref else None,
        )
        ranked_refs: list[str] = []
        for raw_ref in retrieval.get("actual_evidence_refs", []) or []:
            alias = _knowledge_alias(str(raw_ref))
            if alias is None:
                unknown_ref_count += 1
                continue
            ranked_refs.append(alias)
        relations: dict[str, str] = {}
        for raw_ref, relation in (retrieval.get("evidence_relations", {}) or {}).items():
            alias = _knowledge_alias(str(raw_ref))
            if alias is not None:
                _merge_relation(relations, alias, str(relation))
        retrieval_predictions[case_id] = Prediction(
            case_id=case_id,
            route=str(retrieval.get("route")) if retrieval.get("route") else None,
            evidence_refs=_dedupe(ranked_refs),
            evidence_relations=relations,
            observed_events=tuple(str(item) for item in row.get("observed_events", []) or []),
            trace_ref=str(trace_ref) if trace_ref else None,
        )

    compiler_annotations = {
        case_id: GoldAnnotation(
            case_id=annotation.case_id,
            gold_routes=annotation.gold_routes,
            gold_evidence=(),
            gold_evidence_relations={},
            prohibited_events=annotation.prohibited_events,
            hard_safety=annotation.hard_safety,
        )
        for case_id, annotation in annotations.items()
    }
    compiler_report = evaluate(
        cases=cases,
        annotations=compiler_annotations,
        predictions=compiler_predictions,
        dataset_version=dataset_version,
    )
    retrieval_report = evaluate(
        cases=cases,
        annotations=annotations,
        predictions=retrieval_predictions,
        dataset_version=dataset_version,
    )
    return {
        "name": name,
        "dataset_version": dataset_version,
        "case_count": len(cases),
        "process_input_only": True,
        "gold_joined_in_memory": True,
        "compiler_unknown_fallback_cases": compiler_unknown,
        "unknown_retrieved_reference_count": unknown_ref_count,
        "compiler_track": _track_payload(
            name="natural_language_compiler",
            report=compiler_report,
            errors=_error_counts(
                cases=cases, annotations=compiler_annotations, predictions=compiler_predictions
            ),
            note="Provisional route proxy; slot-level compiler Gold is still a separate future contract.",
        ),
        "retrieval_track": _track_payload(
            name="real_retrieval",
            report=retrieval_report,
            errors=_error_counts(
                cases=cases,
                annotations=annotations,
                predictions=retrieval_predictions,
                include_route=False,
            ),
            note="Evidence ranking is built only from actual retrieved knowledge references.",
            retrieval_track=True,
        ),
    }


def build_fair_gold_join_report(
    *,
    process_report_path: Path,
    v3_runtime_path: Path,
    v3_predictions_path: Path,
    v3_trace_path: Path,
    v3_answer_key_path: Path,
    v4_runtime_path: Path,
    v4_predictions_path: Path,
    v4_trace_path: Path,
    v4_answer_key_path: Path,
) -> dict[str, object]:
    """Join both fresh answerless runs after a PASS process gate."""

    process_report = _read_json(process_report_path)
    if not isinstance(process_report, dict):
        raise GoldSetFormatError("process report must be an object")
    if process_report.get("fresh_replay_process_gate") != "PASS":
        raise GoldSetFormatError("cannot join Gold before fresh process gate PASS")
    datasets = (
        _build_dataset_join(
            name="V3 validation copy",
            runtime_path=v3_runtime_path,
            predictions_path=v3_predictions_path,
            trace_path=v3_trace_path,
            answer_key_path=v3_answer_key_path,
            validation=True,
        ),
        _build_dataset_join(
            name="V4 independent holdout",
            runtime_path=v4_runtime_path,
            predictions_path=v4_predictions_path,
            trace_path=v4_trace_path,
            answer_key_path=v4_answer_key_path,
            validation=False,
        ),
    )
    return {
        "report_version": FAIR_GOLD_JOIN_VERSION,
        "scope": "private_gold_join_aggregate_only",
        "quality_scoring_gate": "COMPLETE_AGGREGATE_ONLY",
        "project_promotion_gate": "LOCKED_UNTIL_NEW_HOLDOUT",
        "datasets": list(datasets),
        "policy": {
            "answer_key_read": True,
            "answer_key_path_emitted": False,
            "questions_emitted": False,
            "gold_facts_emitted": False,
            "case_ids_emitted": False,
            "case_level_results_emitted": False,
            "network_called": False,
            "llm_called": False,
            "provider_api_called": False,
            "photo_or_face_vector_read": False,
            "fresh_answerless_process_gate_required": True,
            "prediction_source": "retrieval_result_only_on_retrieval_track",
        },
        "interpretation": (
            "本报告把已封存运行包与负责人 Gold 在内存中一次性对齐，输出两条轨道的聚合事实。"
            "V3 是负责人解冻后的 validation，V4 才是独立泛化证据；任一失败都不能靠改分母或重复同一 Holdout 修复。"
        ),
        "next_step": "analyze_aggregate_failures_then_candidate_on_dev_only",
    }


def render_fair_gold_join_html(report: Mapping[str, object]) -> str:
    """Render aggregate-only HTML for the local RAG optimization dashboard."""

    datasets = report.get("datasets", [])
    sections: list[str] = []
    for dataset in datasets if isinstance(datasets, list) else []:
        if not isinstance(dataset, dict):
            continue
        name = html.escape(str(dataset.get("name", "dataset")))
        sections.append(f"<h2>{name}</h2>")
        sections.append(
            f"<p>题数：<strong>{html.escape(str(dataset.get('case_count', '—')))}</strong>；"
            f"未知理解兜底：<strong>{html.escape(str(dataset.get('compiler_unknown_fallback_cases', '—')))}</strong>；"
            f"Gold 只在内存中连接：<strong>是</strong></p>"
        )
        for key in ("compiler_track", "retrieval_track"):
            track = dataset.get(key, {})
            if not isinstance(track, dict):
                continue
            metrics = track.get("metrics", {})
            errors = track.get("error_type_counts", {})
            metrics = metrics if isinstance(metrics, dict) else {}
            errors = errors if isinstance(errors, dict) else {}
            rows = "".join(
                f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>"
                for k, v in metrics.items()
            )
            error_rows = (
                "".join(
                    f"<tr><td>{html.escape(str(k))}</td><td>{html.escape(str(v))}</td></tr>"
                    for k, v in errors.items()
                )
                or "<tr><td colspan='2'>无聚合错误记录</td></tr>"
            )
            sections.append(f"<h3>{html.escape(str(track.get('track', key)))}</h3>")
            sections.append(f"<table>{rows}</table>")
            sections.append(
                "<h4>失败类型计数</h4><table><tr><th>类型</th><th>数量</th></tr>"
                + error_rows
                + "</table>"
            )
    style = """
    body{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;max-width:1100px;margin:32px auto;padding:0 24px;color:#18212b;line-height:1.55;background:#f7f8fb}
    table{width:100%;border-collapse:collapse;background:#fff;margin:10px 0 22px}th,td{border:1px solid #dce3ec;padding:9px;text-align:left}th{width:330px;background:#eef2f6}.note{padding:14px 16px;background:#fff7df;border-left:4px solid #c88900;border-radius:5px}
    """
    return (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        f"<title>RAG 公平 Gold 连接聚合</title><style>{style}</style></head><body>"
        "<h1>RAG 公平评测｜Gold 连接聚合</h1>"
        "<div class='note'>这份报告只保留聚合指标和失败类型计数。答案键只在本地内存中使用，"
        "不写入报告；V3 是验证副本，V4 才承担独立泛化证据。</div>"
        + "".join(sections)
        + "<h2>边界与下一步</h2><p>过程门通过不等于内容质量通过。下一步只在开发/验证资料上做单变量候选，"
        "然后用全新、未参与诊断的 Holdout 验证；当前 RAG 仍 proposal-only。</p></body></html>"
    )


__all__ = ["FAIR_GOLD_JOIN_VERSION", "build_fair_gold_join_report", "render_fair_gold_join_html"]
