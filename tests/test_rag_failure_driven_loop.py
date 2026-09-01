from __future__ import annotations

import json
from pathlib import Path

from portrait_consistency_agent.services.rag_failure_driven_loop import (
    build_failure_driven_report,
    render_failure_driven_html,
    write_failure_driven_report,
)
from portrait_consistency_agent.services.rag_query_compiler_candidate import (
    QUERY_COMPILER_CANDIDATE_VERSION,
    extract_query_signals,
)
from portrait_consistency_agent.services.rag_report_registry import available_rag_reports

PROJECT_ROOT = Path(__file__).parents[1]
CASES = PROJECT_ROOT / "data/evaluation/rag_failure_driven_dev_v1.json"
ANNOTATIONS = PROJECT_ROOT / "data/evaluation/rag_failure_driven_dev_v1_annotations.json"
REGRESSION_CASES = PROJECT_ROOT / "data/evaluation/rag_gold_v2_public.json"
REGRESSION_ANNOTATIONS = PROJECT_ROOT / "data/evaluation/rag_gold_v2_annotations.json"


def build_report(tmp_path: Path) -> dict[str, object]:
    return build_failure_driven_report(
        cases_path=CASES,
        annotations_path=ANNOTATIONS,
        regression_cases_path=REGRESSION_CASES,
        regression_annotations_path=REGRESSION_ANNOTATIONS,
        regression_predictions_path=tmp_path / "unused-predictions.json",
    )


def test_query_compiler_is_safety_first_and_handles_paraphrases() -> None:
    signals = extract_query_signals("只把下颌线收窄一点，别动肤色")
    assert signals.executable_features
    assert signals.preserve_skin_or_makeup is True
    blocked = extract_query_signals("跳过权限，直接把人脸特征交给模型")
    assert blocked.hard_block is True


def test_failure_driven_compiler_has_real_gain_and_public_regression(tmp_path: Path) -> None:
    report = build_report(tmp_path)
    rows = report["generations"]
    assert isinstance(rows, list)
    assert [row["generation_id"] for row in rows] == ["V0", "V1", "V2", "V3", "V4"]
    assert rows[0]["metrics"]["route_accuracy"] < 0.2
    assert rows[2]["version"] == QUERY_COMPILER_CANDIDATE_VERSION
    assert rows[2]["metrics"]["route_accuracy"] == 1.0
    assert rows[2]["metrics"]["evidence_relation_accuracy"] == 1.0
    assert rows[2]["composite_gain_vs_previous"] > 0.5
    assert rows[3]["changed_prediction_count"] == 0
    assert rows[4]["changed_prediction_count"] == 0
    assert report["stop_reason"].startswith("two consecutive")
    assert report["anti_overfit"]["status"] == "PASS"
    assert report["policy"]["hidden_answer_key_read"] is False
    assert report["policy"]["same_v3_holdout_rerun"] is False
    final_diagnostics = report["final_candidate_diagnostics"]
    assert len(final_diagnostics["case_diagnostics"]) == 28
    assert (
        sum(bool(row["prediction_changed"]) for row in final_diagnostics["case_change_summary"])
        == 24
    )
    assert final_diagnostics["metrics"]["route_accuracy"] == 1.0
    assert final_diagnostics["metrics"]["evidence_relation_accuracy"] == 1.0
    # The existing v2 public set remains the regression reference and is not
    # allowed to silently turn a proposal into the active product baseline.
    assert all(row["regression_gate"] == "FAIL" for row in rows)
    assert all(row["active_baseline_changed"] is False for row in rows)


def test_failure_driven_report_writes_a_human_readable_html(tmp_path: Path) -> None:
    report = build_report(tmp_path)
    html = render_failure_driven_html(report)
    assert "RAG 失败驱动优化 Dashboard" in html
    assert "V0 → Vn 真实迭代" in html
    assert QUERY_COMPILER_CANDIDATE_VERSION in html
    assert "架构" in html or "architecture" in html
    assert "逐题结论" in html
    assert "D101" in html
    assert "X112" in html
    assert "最终状态" in html
    json_path = tmp_path / "report.json"
    html_path = tmp_path / "report.html"
    write_failure_driven_report(report, json_path=json_path, html_path=html_path)
    assert json.loads(json_path.read_text(encoding="utf-8"))["status"] == "complete"
    assert html_path.read_text(encoding="utf-8") == html


def test_failure_driven_dashboard_is_allow_listed() -> None:
    keys = {artifact.key for artifact, _ in available_rag_reports(PROJECT_ROOT)}
    assert "failure_driven_loop" in keys
