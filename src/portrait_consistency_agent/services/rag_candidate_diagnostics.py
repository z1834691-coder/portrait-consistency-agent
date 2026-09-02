"""Per-case diagnostics for the public RAG candidate experiments.

This module turns the public development/regression traces into an auditable
failure table.  It never reads a Holdout answer key and never changes the
active RAG baseline.  The purpose is to answer *where* a candidate changed a
result (query scope, retrieval rank, or evidence relation), not to optimise a
score by editing labels after the fact.
"""

from __future__ import annotations

import html
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from portrait_consistency_agent.services.rag_gold_eval import GoldCase, GoldSetFormatError

DIAGNOSTICS_VERSION = "rag-candidate-diagnostics-v0.2-operation-coverage"

_ALIASES = {
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
    return _ALIASES.get(base)


def _trace_rows(
    payload: object,
    *,
    cases: Sequence[GoldCase],
) -> dict[str, dict[str, object]]:
    """Reattach public case IDs by stable input order after redaction."""

    if not isinstance(payload, list) or len(payload) != len(cases):
        raise GoldSetFormatError("diagnostic trace list must cover cases exactly once")
    output: dict[str, dict[str, object]] = {}
    for case, row in zip(cases, payload, strict=True):
        if not isinstance(row, dict):
            raise GoldSetFormatError("diagnostic trace row must be an object")
        if case.case_id in output:
            raise GoldSetFormatError(f"duplicate diagnostic case {case.case_id}")
        output[case.case_id] = row
    return output


def _prediction_from_trace(case_id: str, trace: Mapping[str, object]) -> dict[str, object]:
    retrieval = trace.get("retrieval", {})
    if not isinstance(retrieval, Mapping):
        raise GoldSetFormatError("diagnostic trace has no retrieval object")
    raw_refs = retrieval.get("actual_evidence_refs", [])
    raw_relations = retrieval.get("evidence_relations", {})
    if not isinstance(raw_refs, list) or not isinstance(raw_relations, Mapping):
        raise GoldSetFormatError("diagnostic retrieval lineage is malformed")
    refs: list[str] = []
    relations: dict[str, str] = {}
    for raw_ref in raw_refs:
        alias = _alias(str(raw_ref))
        if alias is None:
            continue
        if alias not in refs:
            refs.append(alias)
        relation = str(raw_relations.get(str(raw_ref), "reference_context"))
        old = relations.get(alias)
        if old is None or _RELATION_STRENGTH.get(relation, 0) > _RELATION_STRENGTH.get(old, 0):
            relations[alias] = relation
    return {
        "case_id": case_id,
        "route": retrieval.get("route"),
        "evidence_refs": refs,
        "evidence_relations": relations,
        "compiler_status": (trace.get("compiler", {}) or {}).get("status"),
        "compiler_route": (trace.get("compiler", {}) or {}).get("proposed_route"),
        "trace_stage_count": len(retrieval.get("trace", []) or []),
    }


def _first_relevant_rank(gold: set[str], refs: Sequence[str]) -> int | None:
    for index, ref in enumerate(refs, start=1):
        if ref in gold:
            return index
    return None


def _case_row(
    case: GoldCase,
    annotation: Mapping[str, object],
    baseline: Mapping[str, object],
    candidate: Mapping[str, object],
) -> dict[str, object]:
    gold = {str(item) for item in annotation.get("gold_evidence", []) or []}
    gold_relations = {
        str(key): str(value)
        for key, value in (annotation.get("gold_evidence_relations", {}) or {}).items()
    }
    base_refs = [str(item) for item in baseline.get("evidence_refs", [])]
    cand_refs = [str(item) for item in candidate.get("evidence_refs", [])]
    base_rel = dict(baseline.get("evidence_relations", {}) or {})
    cand_rel = dict(candidate.get("evidence_relations", {}) or {})
    base_rank = _first_relevant_rank(gold, base_refs)
    cand_rank = _first_relevant_rank(gold, cand_refs)
    base_relation_ok = all(base_rel.get(key) == value for key, value in gold_relations.items())
    cand_relation_ok = all(cand_rel.get(key) == value for key, value in gold_relations.items())
    base_hit = base_rank is not None and base_rank <= 5
    cand_hit = cand_rank is not None and cand_rank <= 5
    changed = (
        base_refs != cand_refs
        or base_rel != cand_rel
        or baseline.get("route") != candidate.get("route")
    )
    if not cand_hit:
        root_cause = "retrieval_miss_at_5"
        sop = "先检查查询槽位与 Provider/operation 过滤；检索不到时返回不知道并记录 miss。"
    elif not cand_relation_ok:
        root_cause = "evidence_relation_mismatch"
        sop = "保留直接/参考/冲突三种关系，检查关系解析器是否被弱关系覆盖。"
    elif not changed:
        root_cause = "no_candidate_change"
        sop = "该题没有被本轮变量触达，不能把分数变化归因给候选。"
    elif not base_hit or (not base_relation_ok and cand_relation_ok):
        root_cause = "candidate_improved"
        sop = "保留该改动，仍需公开回归与独立 Holdout 复核。"
    else:
        root_cause = "candidate_neutral_or_regressed"
        sop = "保留 Trace，比较回退前后证据；不得为抬分放宽安全或补无关证据。"
    return {
        "case_id": case.case_id,
        "split": case.split,
        "query": case.query,
        "gold_evidence": sorted(gold),
        "gold_evidence_relations": gold_relations,
        "baseline": dict(baseline),
        "candidate": dict(candidate),
        "baseline_hit_at_5": base_hit,
        "candidate_hit_at_5": cand_hit,
        "baseline_first_relevant_rank": base_rank,
        "candidate_first_relevant_rank": cand_rank,
        "baseline_relation_correct": base_relation_ok,
        "candidate_relation_correct": cand_relation_ok,
        "changed_prediction": changed,
        "root_cause": root_cause,
        "sop": sop,
    }


def _diagnose_dataset(
    *,
    cases_payload: object,
    annotations_payload: object,
    baseline_traces: object,
    candidate_traces: object,
    dataset_name: str,
) -> dict[str, object]:
    if not isinstance(cases_payload, list) or not all(
        isinstance(row, dict) for row in cases_payload
    ):
        raise GoldSetFormatError("diagnostic cases payload must be a list")
    cases = tuple(
        GoldCase(
            case_id=str(row["case_id"]),
            split=str(row.get("split", "dev")),
            query=str(row["query"]),
            tags=tuple(str(item) for item in row.get("tags", []) or []),
        )
        for row in cases_payload
    )
    if not isinstance(annotations_payload, list):
        raise GoldSetFormatError("diagnostic annotations payload must be a list")
    annotations = {str(row["case_id"]): row for row in annotations_payload if isinstance(row, dict)}
    base_rows = _trace_rows(baseline_traces, cases=cases)
    candidate_rows = _trace_rows(candidate_traces, cases=cases)
    rows: list[dict[str, object]] = []
    for case in cases:
        if case.case_id not in annotations:
            raise GoldSetFormatError(f"diagnostic annotation missing {case.case_id}")
        baseline = _prediction_from_trace(case.case_id, base_rows[case.case_id])
        candidate = _prediction_from_trace(case.case_id, candidate_rows[case.case_id])
        rows.append(_case_row(case, annotations[case.case_id], baseline, candidate))
    counts = Counter(str(row["root_cause"]) for row in rows)
    return {
        "name": dataset_name,
        "cases": len(rows),
        "changed_prediction_count": sum(bool(row["changed_prediction"]) for row in rows),
        "candidate_hit_at_5": sum(bool(row["candidate_hit_at_5"]) for row in rows),
        "candidate_relation_correct": sum(bool(row["candidate_relation_correct"]) for row in rows),
        "root_cause_counts": dict(sorted(counts.items())),
        "sop": [
            {
                "root_cause": key,
                "count": value,
                "recommended_action": next(
                    str(row["sop"]) for row in rows if row["root_cause"] == key
                ),
            }
            for key, value in sorted(counts.items())
        ],
        "cases_detail": rows,
    }


def build_candidate_diagnostics(
    *,
    report: Mapping[str, object],
    traces: Mapping[str, object],
    development_cases: list[dict[str, object]],
    development_annotations: list[dict[str, object]],
    regression_cases: list[dict[str, object]],
    regression_annotations: list[dict[str, object]],
    development_baseline_track: str = "multi_operation_candidate",
    development_candidate_track: str = "operation_coverage_candidate",
    regression_baseline_track: str = "regression_multi_operation_candidate",
    regression_candidate_track: str = "regression_operation_coverage_candidate",
) -> dict[str, object]:
    """Build public per-case diagnostics from one candidate report."""

    def trace_list(name: str) -> list[object] | None:
        value = traces.get(name) if isinstance(traces, Mapping) else None
        if isinstance(value, Mapping):
            value = value.get("traces")
        return value if isinstance(value, list) else None

    development_traces = trace_list(development_candidate_track)
    development_baseline = trace_list(development_baseline_track)
    regression_traces = trace_list(regression_candidate_track)
    regression_baseline = trace_list(regression_baseline_track)
    for value in (development_traces, development_baseline, regression_traces, regression_baseline):
        if not isinstance(value, list):
            raise GoldSetFormatError("candidate diagnostics require baseline and candidate traces")
    datasets = [
        _diagnose_dataset(
            cases_payload=development_cases,
            annotations_payload=development_annotations,
            baseline_traces=development_baseline,
            candidate_traces=development_traces,
            dataset_name="development",
        ),
        _diagnose_dataset(
            cases_payload=regression_cases,
            annotations_payload=regression_annotations,
            baseline_traces=regression_baseline,
            candidate_traces=regression_traces,
            dataset_name="public_regression",
        ),
    ]
    total_counts: Counter[str] = Counter()
    for dataset in datasets:
        total_counts.update(dataset.get("root_cause_counts", {}))
    return {
        "diagnostics_version": DIAGNOSTICS_VERSION,
        "source_report_version": report.get("report_version"),
        "scope": "public_development_and_public_regression_only",
        "baseline_track": {
            "development": development_baseline_track,
            "public_regression": regression_baseline_track,
        },
        "candidate_track": {
            "development": development_candidate_track,
            "public_regression": regression_candidate_track,
        },
        "holdout_answers_read": False,
        "active_baseline_changed": False,
        "promotion_decision": "not_promoted_proposal_only",
        "datasets": datasets,
        "aggregate_root_cause_counts": dict(sorted(total_counts.items())),
        "interpretation": (
            "逐题表只用于定位查询覆盖、排序和证据关系问题；它不修改标签、不重算 Holdout，"
            "也不能把公开集提升解释成产品化通过。"
        ),
    }


def render_candidate_diagnostics_html(report: Mapping[str, object]) -> str:
    datasets = report.get("datasets", [])
    sections: list[str] = []
    for dataset in datasets if isinstance(datasets, list) else []:
        if not isinstance(dataset, Mapping):
            continue
        name = html.escape(str(dataset.get("name", "dataset")))
        counts = dataset.get("root_cause_counts", {})
        count_rows = "".join(
            f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(str(value))}</td></tr>"
            for key, value in (counts.items() if isinstance(counts, Mapping) else [])
        )
        detail_payload = dataset.get("cases_detail", [])
        detail_rows: list[str] = []
        for row in detail_payload if isinstance(detail_payload, list) else []:
            if not isinstance(row, Mapping):
                continue
            detail_rows.append(
                "<tr>"
                + "".join(
                    f"<td>{html.escape(str(row.get(key, '—')))}</td>"
                    for key in (
                        "case_id",
                        "root_cause",
                        "baseline_hit_at_5",
                        "candidate_hit_at_5",
                        "baseline_relation_correct",
                        "candidate_relation_correct",
                        "changed_prediction",
                    )
                )
                + "</tr>"
            )
        sections.append(
            f"<h2>{name}</h2>"
            f"<p>题数：<strong>{html.escape(str(dataset.get('cases', '—')))}</strong>；"
            f"候选改变：<strong>"
            f"{html.escape(str(dataset.get('changed_prediction_count', '—')))}</strong>；"
            f"前五条命中：<strong>"
            f"{html.escape(str(dataset.get('candidate_hit_at_5', '—')))}</strong>；"
            f"关系正确：<strong>"
            f"{html.escape(str(dataset.get('candidate_relation_correct', '—')))}</strong></p>"
            f"<h3>根因计数</h3><table>{count_rows}</table>"
            "<h3>逐题检查（公开数据）</h3><table><tr>"
            "<th>题号</th><th>根因</th><th>基线命中</th><th>候选命中</th>"
            "<th>基线关系</th><th>候选关系</th><th>候选改变</th></tr>"
            + "".join(detail_rows)
            + "</table>"
        )
    style = (
        "body{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;"
        "max-width:1250px;margin:30px auto;padding:0 22px;background:#f7f8fb;"
        "color:#18212b;line-height:1.55}"
        "table{width:100%;border-collapse:collapse;background:#fff;margin:10px 0 22px}"
        "th,td{border:1px solid #dce3ec;padding:8px;text-align:left}th{background:#eef2f6}"
        ".note{padding:14px 16px;background:#fff7df;border-left:4px solid #c88900;margin:14px 0}"
    )
    return (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        f"<title>RAG 逐题候选诊断</title><style>{style}</style></head><body>"
        "<h1>RAG｜逐题失败模式与候选诊断</h1>"
        "<div class='note'>只读公开开发/回归题；不读取 Holdout 答案，不修改 active baseline。"
        "逐题诊断用于发现下一条 SOP，不代表 RAG 已产品化。</div>"
        + "".join(sections)
        + "<h2>总根因计数</h2><pre>"
        + html.escape(
            json.dumps(
                report.get("aggregate_root_cause_counts", {}),
                ensure_ascii=False,
                indent=2,
            )
        )
        + "</pre></body></html>"
    )


def write_candidate_diagnostics(
    report: Mapping[str, object], *, json_path: Path, html_path: Path
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html_path.write_text(render_candidate_diagnostics_html(report), encoding="utf-8")


__all__ = [
    "DIAGNOSTICS_VERSION",
    "build_candidate_diagnostics",
    "render_candidate_diagnostics_html",
    "write_candidate_diagnostics",
]
