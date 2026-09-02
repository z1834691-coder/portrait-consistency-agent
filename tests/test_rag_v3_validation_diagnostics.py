from __future__ import annotations

import json
from pathlib import Path

import pytest

from portrait_consistency_agent.services.rag_gold_eval import (
    GoldSetFormatError,
    load_validation_cases,
)
from portrait_consistency_agent.services.rag_report_registry import available_rag_reports
from portrait_consistency_agent.services.rag_v3_validation_diagnostics import (
    build_v3_validation_diagnostics,
    render_v3_validation_html,
    write_v3_validation_diagnostics,
)

PROJECT_ROOT = Path(__file__).parents[1]
VALIDATION_CASES = PROJECT_ROOT / "data/evaluation/rag_v3_validation_cases_v1.json"
VALIDATION_ANNOTATIONS = PROJECT_ROOT / "data/evaluation/rag_v3_validation_annotations_v1.json"
REGRESSION_CASES = PROJECT_ROOT / "data/evaluation/rag_gold_v2_public.json"
REGRESSION_ANNOTATIONS = PROJECT_ROOT / "data/evaluation/rag_gold_v2_annotations.json"


@pytest.fixture(scope="module")
def report() -> dict[str, object]:
    return build_v3_validation_diagnostics(
        cases_path=VALIDATION_CASES,
        annotations_path=VALIDATION_ANNOTATIONS,
        regression_cases_path=REGRESSION_CASES,
        regression_annotations_path=REGRESSION_ANNOTATIONS,
    )


def test_unlocked_validation_loader_keeps_answerless_runtime_boundary() -> None:
    version, cases = load_validation_cases(VALIDATION_CASES)
    assert version == "rag-v3-validation-unlocked-2026-09-02"
    assert len(cases) == 36
    assert all(case.split == "validation" and case.case_id.startswith("H") for case in cases)

    answerful = VALIDATION_CASES.parent / "_test_validation_answerful.json"
    answerful.write_text(
        json.dumps(
            {
                "dataset_version": "fixture",
                "cases": [
                    {"case_id": "H01", "split": "validation", "query": "q", "gold_route": "BLOCK"}
                ],
            }
        ),
        encoding="utf-8",
    )
    try:
        with pytest.raises(GoldSetFormatError):
            load_validation_cases(answerful)
    finally:
        answerful.unlink(missing_ok=True)


def test_v3_diagnostics_shows_real_gain_and_public_regression_guard(
    report: dict[str, object],
) -> None:
    assert report["status"] == "complete"
    assert report["generation_ids"] == ["G0", "G1", "G2", "G3", "G4", "G5"]
    generations = report["generations"]
    assert isinstance(generations, list)
    assert generations[0]["metrics"]["route_accuracy"] == pytest.approx(0.305556)
    assert generations[2]["metrics"]["route_accuracy"] == 1.0
    assert generations[2]["metrics"]["evidence_relation_accuracy"] == 1.0
    assert generations[2]["composite_gain_vs_previous"] > 0.3
    assert generations[3]["regression_metrics"]["route_accuracy"] == 1.0
    assert generations[3]["regression_metrics"]["evidence_relation_accuracy"] == 1.0
    assert generations[-1]["metrics"]["evidence_relation_accuracy"] > 0.9
    assert generations[-1]["metrics"]["hard_safety_gate"] == "PASS"
    assert generations[-1]["metrics"]["project_threshold_gate"] == "FAIL"
    assert report["policy"]["owner_unlocked_v3"] is True
    assert report["policy"]["historical_holdout_a_snapshot_preserved"] is True
    assert report["policy"]["new_independent_v4_required_for_promotion"] is True
    assert report["policy"]["active_baseline_changed"] is False


def test_v3_report_contains_full_per_case_traces_and_failure_sop(
    report: dict[str, object],
) -> None:
    generations = report["generations"]
    assert isinstance(generations, list)
    assert all(len(row["case_diagnostics"]) == 36 for row in generations)
    assert all(len(row["traces"]) == 36 for row in generations)
    final_case = generations[-1]["case_diagnostics"][0]
    assert final_case["case_id"] == "H01"
    assert "failure_analysis" in final_case
    assert "trace" in final_case
    assert "retrieval_trace" in final_case["trace"]
    assert report["baseline_failure_counts"]["route_mismatch"] == 25
    assert report["baseline_failure_counts"]["evidence_relation_mismatch"] == 31
    assert report["failure_pattern_analysis"]["examples_first_five"]["route_mismatch"]
    assert all(
        trace["network_called"] is False
        and trace["llm_called"] is False
        and trace["provider_api_called"] is False
        for row in generations
        for trace in row["traces"]
    )


def test_v3_html_and_json_are_reviewable(tmp_path: Path, report: dict[str, object]) -> None:
    rendered = render_v3_validation_html(report)
    assert "V3 解冻验证集｜逐题诊断与 RAG 优化" in rendered
    assert "G0 → G5" in rendered
    assert "H01" in rendered
    assert "根因" in rendered and "修正 SOP" in rendered
    assert "最终代次逐题 Trace 摘要" in rendered
    assert rendered.count("<details>") == 36
    assert "H36｜完整 Trace 与逐题结论" in rendered
    json_path = tmp_path / "v3.json"
    html_path = tmp_path / "v3.html"
    write_v3_validation_diagnostics(report, json_path=json_path, html_path=html_path)
    assert json.loads(json_path.read_text(encoding="utf-8"))["status"] == "complete"
    assert html_path.read_text(encoding="utf-8") == rendered


def test_v3_report_is_allowlisted_for_the_read_only_dashboard() -> None:
    keys = {artifact.key for artifact, _path in available_rag_reports(PROJECT_ROOT)}
    assert "v3_validation_diagnostics" in keys
