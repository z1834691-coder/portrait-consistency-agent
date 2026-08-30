"""Aggregate-only projection for product-owner private holdout scoring.

This module deliberately never accepts an answer-key path, a prompt, a photo,
or an individual ``GoldAnnotation``.  The caller may have used a locally held
private key to create an :class:`EvaluationReport`, but this projection strips
the case-level results before a report leaves the product owner's machine.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from html import escape

from portrait_consistency_agent.core.rag_safety_events import SAFETY_EVENT_CATALOG_VERSION
from portrait_consistency_agent.services.rag_gold_eval import (
    EvaluationReport,
    GoldAnnotation,
    GoldSetFormatError,
)

PRIVATE_SCORE_VERSION = "rag-gold-private-aggregate-v0.2"

_ROUTE_TOKENS = (
    "DIRECT",
    "REFERENCE",
    "SUGGEST",
    "CLARIFY",
    "BLOCK",
    "BASELINE",
    "UNKNOWN",
    "STOP",
)
_EVIDENCE_ALIASES = ("FX", "B", "C", "I", "P")


def parse_private_markdown_annotations(
    markdown: str, *, allowed_case_ids: Iterable[str]
) -> dict[str, GoldAnnotation]:
    """Parse the PM-only holdout table entirely in memory.

    The source stays in a product-owner-controlled Markdown file.  This parser
    accepts only the established five-column table shape: ``ID | prompt | Gold
    evidence / route | required facts | must-not``.  It never returns prompt,
    required-fact, or must-not text; only the normalized route/evidence fields
    required for aggregate scoring leave this function.

    The natural-language ``must-not`` column is deliberately *not* converted
    into invented event IDs.  Callers must mark hard-safety scoring as requiring
    manual review unless the key is later upgraded to a machine-normalized JSON
    annotation format.
    """

    allowed = set(allowed_case_ids)
    table_rows: list[list[str]] = []
    for line in markdown.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        header = " ".join(cells).casefold()
        if "gold" in header and ("route" in header or "路由" in header):
            table_rows = []
            continue
        if all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            continue
        if re.fullmatch(r"H\d{2}", cells[0].strip().upper()):
            table_rows.append(cells)

    annotations: dict[str, GoldAnnotation] = {}
    for cells in table_rows:
        case_id = cells[0].upper()
        if case_id not in allowed:
            raise GoldSetFormatError("private Markdown answer key contains an unexpected case ID")
        if case_id in annotations:
            raise GoldSetFormatError("private Markdown answer key contains a duplicate case ID")

        gold_cell = cells[2].upper()
        routes = tuple(
            token for token in _ROUTE_TOKENS if re.search(rf"(?<![A-Z]){token}(?![A-Z])", gold_cell)
        )
        evidence = tuple(
            token
            for token in _EVIDENCE_ALIASES
            if re.search(rf"(?<![A-Z]){token}(?![A-Z])", gold_cell)
        )
        if not routes:
            raise GoldSetFormatError("private Markdown answer key has an unparseable route")

        if "BLOCK" in routes and "FX" in evidence:
            relations = {token: "conflict_evidence" for token in evidence}
        elif "DIRECT" in routes and evidence:
            relations = {
                token: ("direct_evidence" if index == 0 else "reference_context")
                for index, token in enumerate(evidence)
            }
        else:
            relations = {token: "reference_context" for token in evidence}

        annotations[case_id] = GoldAnnotation(
            case_id=case_id,
            gold_routes=routes,
            gold_evidence=evidence,
            gold_evidence_relations=relations,
            prohibited_events=(),
            hard_safety=False,
        )

    if set(annotations) != allowed:
        raise GoldSetFormatError(
            "private Markdown answer key does not cover exactly the holdout IDs"
        )
    return annotations


def private_aggregate_payload(
    report: EvaluationReport, *, annotation_source: str = "machine_normalized_json"
) -> dict[str, object]:
    """Return metrics and error *counts*, never prompts, IDs, or Gold facts."""

    error_types: Counter[str] = Counter()
    for score in report.case_scores:
        if score.missing_prediction:
            error_types["missing_prediction"] += 1
            continue
        if score.route_correct is False:
            error_types["route_mismatch"] += 1
        if score.evidence_exact is False:
            error_types["evidence_set_mismatch"] += 1
        if score.evidence_relation_accuracy is not None and score.evidence_relation_accuracy < 1:
            error_types["evidence_relation_mismatch"] += 1
        if (score.hard_safety_violation_count or 0) > 0:
            error_types["hard_safety_violation"] += 1

    metrics = dict(report.metrics or {})
    manual_safety_review_required = (
        annotation_source == "markdown_table_v1"
        or metrics.get("safety_event_unknown_label_count", 0) > 0
    )
    if manual_safety_review_required:
        # A natural-language `must not` column must not be hallucinated into
        # machine event IDs.  Do not display a false `PASS` for that sub-gate.
        metrics["hard_safety_gate"] = "MANUAL_REVIEW_REQUIRED"

    return {
        "scorer_version": PRIVATE_SCORE_VERSION,
        "status": report.status,
        "scope": "private_holdout_aggregate_only",
        "counts": {
            "cases": report.counts.get("cases", 0),
            "predictions": report.counts.get("predictions", 0),
            "missing_predictions": report.counts.get("missing_predictions", 0),
            "error_case_count": sum(
                1
                for score in report.case_scores
                if score.missing_prediction
                or score.route_correct is False
                or score.evidence_exact is False
                or (
                    score.evidence_relation_accuracy is not None
                    and score.evidence_relation_accuracy < 1
                )
                or (score.hard_safety_violation_count or 0) > 0
            ),
        },
        "metrics": metrics,
        "error_type_counts": dict(sorted(error_types.items())),
        "evaluation_limitations": {
            "annotation_source": annotation_source,
            "hard_safety_manual_review_required": manual_safety_review_required,
            "safety_event_catalog_version": SAFETY_EVENT_CATALOG_VERSION,
            "precision_reporting_policy": "precision-dual-report-v0.1",
            "reason": (
                "The private Markdown key preserves must-not facts as natural language; "
                "it has not been converted into machine event IDs."
                if annotation_source == "markdown_table_v1"
                else "At least one safety label is not in the reviewed event dictionary."
                if manual_safety_review_required
                else None
            ),
        },
        "policy": {
            "case_ids_emitted": False,
            "questions_emitted": False,
            "answer_facts_emitted": False,
            "private_answer_key_path_emitted": False,
            "llm_called": False,
            "photo_or_face_vector_read": False,
            "external_provider_called": False,
            "network_called": False,
        },
    }


def render_private_aggregate_html(payload: dict[str, object]) -> str:
    """Render a visual aggregate report without case-level or Gold data."""

    metrics = payload.get("metrics", {})
    counts = payload.get("counts", {})
    errors = payload.get("error_type_counts", {})
    limitations = payload.get("evaluation_limitations", {})
    if not isinstance(metrics, dict) or not isinstance(counts, dict):
        raise ValueError("private aggregate payload is malformed")

    def value(name: str) -> str:
        item = metrics.get(name)
        if isinstance(item, float):
            return f"{item * 100:.2f}%"
        return escape(str(item if item is not None else "—"))

    rows = (
        "".join(
            f"<tr><td>{escape(str(name))}</td><td>{escape(str(count))}</td></tr>"
            for name, count in (errors.items() if isinstance(errors, dict) else ())
        )
        or "<tr><td colspan='2'>无聚合错误条目</td></tr>"
    )
    limitation = (
        escape(str(limitations.get("reason")))
        if isinstance(limitations, dict) and limitations.get("reason")
        else "无额外限制说明"
    )
    styles = """
body { font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif;
       max-width: 960px; margin: 42px auto; padding: 0 24px; color: #19212d; }
h1 { margin-bottom: 6px; }
.muted { color: #5f6c7b; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 12px; margin: 22px 0; }
.card { border: 1px solid #dce3ea; border-radius: 12px; padding: 16px; background: #fff; }
.k { font-size: 13px; color: #5f6c7b; }
.v { font-size: 25px; font-weight: 700; margin-top: 6px; }
.warn { background: #fff7ed; border-left: 4px solid #f59e0b; padding: 14px 16px;
        border-radius: 6px; }
table { border-collapse: collapse; width: 100%; margin-top: 12px; }
th, td { border: 1px solid #dce3ea; padding: 10px; text-align: left; }
th { background: #f6f8fa; }
""".strip()

    def card(label: str, display_value: str) -> str:
        return "\n".join(
            (
                "<div class='card'>",
                f"<div class='k'>{label}</div>",
                f"<div class='v'>{display_value}</div>",
                "</div>",
            )
        )

    cards = "\n".join(
        (
            card("覆盖题数", escape(str(counts.get("cases", "—")))),
            card("路由正确率", value("route_accuracy")),
            card("Recall@5", value("recall_at_5")),
            card("MRR", value("mrr")),
            card("nDCG@5", value("ndcg_at_5")),
            card("项目 Gate", value("project_threshold_gate")),
        )
    )
    return f"""<!doctype html>
<html lang='zh-CN'>
<head>
<meta charset='utf-8'>
<title>RAG Gold v2｜私有隐藏集汇总</title>
<style>{styles}</style>
</head>
<body><h1>RAG Gold Set v2｜私有隐藏集汇总</h1>
<p class='muted'>
仅显示聚合指标和错误类型；不含题目、案例编号、Gold 答案、答案键路径、原始文本、图片或外部调用数据。
</p>
<div class='grid'>
{cards}
</div>
<div class='warn'><strong>安全解释：</strong>{value("hard_safety_gate")}。{limitation}</div>
<h2>聚合错误类型</h2><table><thead><tr><th>错误类型</th><th>数量</th></tr></thead><tbody>{rows}</tbody></table>
</body></html>"""
