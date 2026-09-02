from __future__ import annotations

import json
from pathlib import Path

import pytest

from portrait_consistency_agent.services.rag_gold_eval import (
    GoldCase,
    load_holdout_runtime_cases,
    load_predictions,
)
from portrait_consistency_agent.services.rag_query_compiler_candidate import (
    run_failure_driven_candidate,
)
from portrait_consistency_agent.services.rag_report_registry import available_rag_reports
from portrait_consistency_agent.services.rag_v4_query_compiler_candidate import (
    V4_QUERY_COMPILER_CANDIDATE_VERSION,
    compile_v4_projection_v1,
    normalize_v4_for_compilation,
)
from portrait_consistency_agent.services.rag_v4_validation_diagnostics import (
    build_v4_validation_diagnostics,
    render_v4_validation_html,
    write_v4_validation_diagnostics,
)

PROJECT_ROOT = Path(__file__).parents[1]
V4_RUNTIME = PROJECT_ROOT / "data/evaluation/rag_v4_holdout_runtime.json"
V3_VALIDATION = PROJECT_ROOT / "data/evaluation/rag_v3_validation_cases_v1.json"
V4_KEY = Path(
    "/Users/fengzihan/Documents/Codex/portrait-consistency-agent-v4-holdout-owner-only-2026-09-02/v4_holdout_answer_key_owner_only.json"
)
V4_BLIND = PROJECT_ROOT / "reports/rag_v4_holdout_blind_predictions.json"
PUBLIC_CASES = PROJECT_ROOT / "data/evaluation/rag_gold_v2_public.json"
PUBLIC_ANNOTATIONS = PROJECT_ROOT / "data/evaluation/rag_gold_v2_annotations.json"


@pytest.fixture(scope="module")
def report() -> dict[str, object]:
    return build_v4_validation_diagnostics(
        cases_path=V4_RUNTIME,
        annotations_path=V4_KEY,
        regression_cases_path=PUBLIC_CASES,
        regression_annotations_path=PUBLIC_ANNOTATIONS,
        blind_predictions_path=V4_BLIND,
    )


def test_v4_runtime_is_answerless_and_independent_shape() -> None:
    version, cases = load_holdout_runtime_cases(V4_RUNTIME)
    assert version == "rag-v4-holdout-runtime-2026-09-02"
    assert len(cases) == 48
    assert all(case.case_id.startswith("H4") and case.split == "holdout" for case in cases)
    encoded = json.dumps([case.__dict__ for case in cases], ensure_ascii=False)
    assert "gold_routes" not in encoded
    assert "prohibited_events" not in encoded


def test_v4_queries_do_not_overlap_v3_validation() -> None:
    v4 = json.loads(V4_RUNTIME.read_text(encoding="utf-8"))["cases"]
    v3 = json.loads(V3_VALIDATION.read_text(encoding="utf-8"))["cases"]
    v4_queries = {row["query"] for row in v4}
    v3_queries = {row["query"] for row in v3}
    assert v4_queries.isdisjoint(v3_queries)
    assert {row["case_id"] for row in v4}.isdisjoint({row["case_id"] for row in v3})


def test_v4_compiler_uses_reviewed_paraphrase_not_case_id() -> None:
    assert "脸宽" in normalize_v4_for_compilation("下颌线太外扩")
    assert "眼距" in normalize_v4_for_compilation("两眼之间的空隙太大")
    cases = (
        GoldCase("H999", "validation", "下颌线太外扩，能把脸廓往内收吗？"),
        GoldCase("H998", "validation", "脸颊两侧收窄，眼神更大一些。"),
    )
    predictions, traces = run_failure_driven_candidate(
        cases,
        runtime_mode="validation",
        compiler=compile_v4_projection_v1,
        runner_version=V4_QUERY_COMPILER_CANDIDATE_VERSION,
    )
    assert [row.route for row in predictions] == ["DIRECT", "DIRECT"]
    assert all(row.trace_ref.startswith(V4_QUERY_COMPILER_CANDIDATE_VERSION) for row in predictions)
    assert all(
        trace["network_called"] is False
        and trace["llm_called"] is False
        and trace["provider_api_called"] is False
        for trace in traces
    )


def test_v4_diagnostics_shows_real_gain_and_preserves_boundaries(
    report: dict[str, object],
) -> None:
    assert report["status"] == "complete"
    assert report["generation_ids"] == ["G0", "G1", "G2", "G3", "G4", "G5"]
    generations = report["generations"]
    assert isinstance(generations, list)
    assert generations[0]["metrics"]["route_accuracy"] == pytest.approx(0.125)
    assert generations[2]["metrics"]["route_accuracy"] == 1.0
    assert generations[2]["metrics"]["evidence_relation_accuracy"] == 1.0
    assert generations[2]["metrics"]["recall_at_5"] == 1.0
    assert generations[-1]["metrics"]["hard_safety_gate"] == "PASS"
    assert generations[-1]["metrics"]["project_threshold_gate"] == "FAIL"
    assert report["improvement_summary"]["semantic_diagnostic_gate"] == "PASS"
    assert report["policy"]["blind_snapshot_match"] is True
    assert report["policy"]["proposal_only"] is True
    assert report["policy"]["active_baseline_changed"] is False


def test_v4_report_contains_all_traces_and_only_sparse_metric_warning(
    report: dict[str, object],
) -> None:
    generations = report["generations"]
    assert isinstance(generations, list)
    assert all(len(row["case_diagnostics"]) == 48 for row in generations)
    assert all(len(row["traces"]) == 48 for row in generations)
    assert report["final_failure_counts"] == {"metric_sparse_gold_denominator": 47}
    assert all(
        trace["network_called"] is False
        and trace["llm_called"] is False
        and trace["provider_api_called"] is False
        for generation in generations
        for trace in generation["traces"]
    )


def test_v4_html_and_files_are_reviewable(tmp_path: Path, report: dict[str, object]) -> None:
    rendered = render_v4_validation_html(report)
    assert "V4 独立 Holdout｜逐题诊断、失败模式与 RAG 修正" in rendered
    assert "语义诊断 Gate" in rendered
    assert rendered.count("<details>") == 48
    assert "H448｜完整 Trace 与逐题结论" in rendered
    json_path = tmp_path / "v4.json"
    html_path = tmp_path / "v4.html"
    write_v4_validation_diagnostics(report, json_path=json_path, html_path=html_path)
    assert json.loads(json_path.read_text(encoding="utf-8"))["status"] == "complete"
    assert html_path.read_text(encoding="utf-8") == rendered


def test_v4_report_artifacts_are_allowlisted() -> None:
    keys = {artifact.key for artifact, _path in available_rag_reports(PROJECT_ROOT)}
    assert "v4_holdout_blind_aggregate" in keys
    assert "v4_validation_diagnostics" in keys


def test_blind_prediction_loader_sees_only_redacted_rows() -> None:
    predictions = load_predictions(V4_BLIND)
    assert len(predictions) == 48
    encoded = json.dumps([row.__dict__ for row in predictions.values()], ensure_ascii=False)
    assert "gold_" not in encoded
    assert "query" not in encoded
