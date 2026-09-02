from __future__ import annotations

from pathlib import Path

import pytest

from scripts.audit_rag_low_success import (
    PROJECT_ROOT,
    build_audit,
    render_html,
)


def _paths() -> dict[str, Path]:
    reports = PROJECT_ROOT / "reports"
    return {
        "v4_aggregate_path": reports / "rag_v4_holdout_blind_aggregate.json",
        "v4_trace_path": reports / "rag_v4_holdout_blind_trace.json",
        "public_evaluation_path": reports / "rag_gold_v2_baseline_evaluation.json",
        "failure_loop_path": reports / "rag_failure_driven_loop_v1.json",
        "lifecycle_path": reports / "rag_lifecycle_audit.json",
    }


def test_public_audit_separates_query_boundary_from_retrieval() -> None:
    report = build_audit(**_paths())
    facts = report["facts"]
    v4_trace = facts["v4_trace_boundary"]
    v4_blind = facts["v4_blind"]

    assert report["status"] == "complete_no_promotion"
    assert report["scope"]["private_answer_key_read"] is False
    assert v4_blind["case_count"] == 48
    assert v4_trace["structured_query_created_count"] == 8
    assert v4_trace["structured_query_not_created_count"] == 40
    assert v4_trace["retrieval_trace_present_count"] == 8
    assert v4_blind["metrics"]["route_accuracy"] == 0.125
    assert v4_blind["metrics"]["evidence_relation_accuracy"] == 0.1875
    assert v4_blind["metrics"]["recall_at_5"] == 0.579861


def test_fixed_precision_bound_is_reported_without_changing_gate() -> None:
    report = build_audit(**_paths())
    v4 = report["facts"]["v4_blind"]
    public = report["facts"]["public_regression"]

    assert v4["max_reachable_fixed_precision_at_3"] == pytest.approx(0.5138888889)
    assert public["max_reachable_fixed_precision_at_3"] == pytest.approx(0.4743589744)
    assert v4["metrics"]["project_threshold_gate"] == "FAIL"


def test_html_is_explanatory_and_does_not_expose_case_questions() -> None:
    report = build_audit(**_paths())
    page = render_html(report)
    assert "RAG 低成功率反思审计" in page
    assert "大多数 V4 题没有真正进入检索" in page
    assert "下颌线太外扩" not in page
    assert "H401" not in page


def test_private_or_unknown_report_path_is_rejected() -> None:
    paths = _paths()
    paths["v4_trace_path"] = PROJECT_ROOT / "data/evaluation/rag_v4_holdout_runtime.json"
    with pytest.raises(ValueError, match="allow-listed"):
        build_audit(**paths)
