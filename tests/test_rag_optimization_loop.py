from __future__ import annotations

import json
from pathlib import Path

from portrait_consistency_agent.services.rag_optimization_loop import (
    OPTIMIZATION_LOOP_VERSION,
    build_optimization_report,
    composite_score,
    write_optimization_report,
)
from portrait_consistency_agent.services.rag_report_registry import available_rag_reports

PROJECT_ROOT = Path(__file__).parents[1]
PUBLIC_CASES = PROJECT_ROOT / "data/evaluation/rag_gold_v2_public.json"
PUBLIC_ANNOTATIONS = PROJECT_ROOT / "data/evaluation/rag_gold_v2_annotations.json"
PUBLIC_PREDICTIONS = PROJECT_ROOT / "reports/rag_gold_v2_baseline_predictions.json"


def _build_report(tmp_path: Path) -> dict[str, object]:
    private = tmp_path / "private-aggregate.json"
    private.write_text(
        json.dumps(
            {
                "scope": "private_holdout_aggregate_only",
                "counts": {"cases": 36, "error_case_count": 32},
                "metrics": {"route_accuracy": 0.305556},
                "error_type_counts": {"route_mismatch": 25},
            }
        ),
        encoding="utf-8",
    )
    return build_optimization_report(
        public_cases_path=PUBLIC_CASES,
        public_annotations_path=PUBLIC_ANNOTATIONS,
        public_predictions_path=PUBLIC_PREDICTIONS,
        private_aggregate_path=private,
    )


def test_composite_score_is_diagnostic_and_weighted() -> None:
    assert (
        composite_score(
            {
                "route_accuracy": 1.0,
                "evidence_exact_accuracy": 1.0,
                "evidence_relation_accuracy": 1.0,
                "recall_at_5": 1.0,
                "mrr": 1.0,
                "ndcg_at_5": 1.0,
                "precision_at_3": 0.5,
            }
        )
        == 0.95
    )
    assert composite_score({"route_accuracy": 1.0}) is None


def test_loop_is_public_only_proposal_only_and_stops_on_diminishing_returns(tmp_path: Path) -> None:
    report = _build_report(tmp_path)
    assert report["optimization_version"] == OPTIMIZATION_LOOP_VERSION
    assert report["policy"]["proposal_only"] is True
    assert report["policy"]["hidden_answer_key_read"] is False
    assert report["policy"]["same_v3_holdout_rerun"] is False
    assert report["anti_overfit"]["status"] == "PASS"
    assert report["executed_generations"] == ["V0", "V1", "V2"]
    assert report["generations"][3]["status"] == "skipped_diminishing_returns"
    assert report["failure_patterns"]["private_holdout_aggregate_pattern_counts"] == {
        "route_mismatch": 25
    }
    interpretations = report["failure_patterns"]["private_pattern_interpretations"]
    assert {item["pattern_id"] for item in interpretations} == {
        "evidence_relation_mismatch",
        "evidence_set_mismatch",
        "route_mismatch",
    }
    assert report["failure_patterns"]["private_pattern_counts_non_additive"] is True
    assert len(report["baseline"]["case_diagnostics"]) == 52
    assert report["baseline"]["case_diagnostics"][0]["query_sha256"]


def test_report_is_serializable_and_visual_html_has_generation_history(tmp_path: Path) -> None:
    report = _build_report(tmp_path)
    output = tmp_path / "loop.json"
    html_path = tmp_path / "loop.html"
    write_optimization_report(report, json_path=output, html_path=html_path)
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "complete"
    html = html_path.read_text(encoding="utf-8")
    assert "RAG 自动优化 Dashboard" in html
    assert "V0 → V4 生成历史" in html
    assert "v3 aggregate" in html
    assert "隐藏答案" in html
    assert "事实与假设分开" in html


def test_registry_allow_lists_optimization_dashboard() -> None:
    report_keys = {artifact.key for artifact, _ in available_rag_reports(PROJECT_ROOT)}
    assert "optimization_loop" in report_keys


def test_optimization_page_mentions_loop_and_case_diagnostics() -> None:
    page = (PROJECT_ROOT / "pages/5_RAG优化看板.py").read_text(encoding="utf-8")
    assert "rag_optimization_loop_v1.json" in page
    assert "逐题诊断" in page
    assert "line_chart" in page
