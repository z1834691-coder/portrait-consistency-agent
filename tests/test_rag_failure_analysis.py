from __future__ import annotations

import json
from pathlib import Path

import pytest

from portrait_consistency_agent.services.rag_correction_candidate import (
    CORRECTION_CANDIDATE_VERSION,
    normalize_domain_prompt,
    run_public_correction_candidate,
)
from portrait_consistency_agent.services.rag_failure_analysis import (
    build_failure_analysis,
    render_failure_analysis_html,
)
from portrait_consistency_agent.services.rag_gold_eval import GoldCase
from portrait_consistency_agent.services.rag_report_registry import (
    RagReportArtifact,
    available_rag_reports,
)


def test_domain_candidate_normalizes_only_reviewed_synonyms() -> None:
    assert "瘦脸" in normalize_domain_prompt("Can you slim face?")
    assert "不外发照片" in normalize_domain_prompt("NO CLOUD TRANSFER")
    assert normalize_domain_prompt("unrecognized beauty phrase") == ("unrecognized beauty phrase")


def test_domain_candidate_handles_paraphrase_without_changing_policy() -> None:
    cases = (
        GoldCase("D90", "dev", "Can you slim face and enlarge eyes?"),
        GoldCase("X90", "challenge", "only adjust eye width, no cloud transfer"),
    )
    predictions, traces = run_public_correction_candidate(cases)
    assert len(predictions) == len(traces) == 2
    assert predictions[0].route == "DIRECT"
    assert predictions[0].evidence_refs == ("B", "P")
    assert predictions[1].route == "BLOCK"
    assert predictions[1].evidence_refs == ("P",)
    assert all(trace["network_called"] is False for trace in traces)
    assert all(trace["provider_api_called"] is False for trace in traces)
    assert all(trace["runner_version"] == CORRECTION_CANDIDATE_VERSION for trace in traces)


def test_domain_candidate_rejects_holdout_inputs() -> None:
    with pytest.raises(ValueError, match=r"public D\*/X\*"):
        run_public_correction_candidate((GoldCase("H90", "holdout", "瘦脸"),))


def test_failure_analysis_is_aggregate_only_and_proposes_not_mutates(tmp_path: Path) -> None:
    public_cases = tmp_path / "public.json"
    public_cases.write_text(
        json.dumps(
            {
                "dataset_version": "fixture-v1",
                "cases": [
                    {
                        "case_id": "D90",
                        "split": "dev",
                        "query": "脸比母版宽，能直接瘦脸吗？",
                        "tags": ["capability"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    annotations = tmp_path / "annotations.json"
    annotations.write_text(
        json.dumps(
            {
                "annotations": [
                    {
                        "case_id": "D90",
                        "gold_routes": ["DIRECT"],
                        "gold_evidence": ["B"],
                        "gold_evidence_relations": {"B": "direct_evidence"},
                        "prohibited_events": [],
                        "hard_safety": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    predictions = tmp_path / "predictions.json"
    predictions.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "case_id": "D90",
                        "route": "DIRECT",
                        "evidence_refs": ["B"],
                        "evidence_relations": {"B": "direct_evidence"},
                        "observed_events": [],
                        "trace_ref": "fixture-trace",
                        "machine_score_summary": {"candidate_count": 1},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    private_aggregate = tmp_path / "private-aggregate.json"
    private_aggregate.write_text(
        json.dumps(
            {
                "scope": "private_holdout_aggregate_only",
                "counts": {"cases": 0, "error_case_count": 0},
                "metrics": {"route_accuracy": 0.0},
                "error_type_counts": {"route_mismatch": 0},
            }
        ),
        encoding="utf-8",
    )

    report = build_failure_analysis(
        public_cases_path=public_cases,
        public_annotations_path=annotations,
        public_predictions_path=predictions,
        private_aggregate_path=private_aggregate,
    )
    assert report["policy"]["private_answer_key_read"] is False
    assert report["policy"]["self_correction_mode"] == "proposal_only"
    candidate = report["correction_candidate"]
    assert candidate["version"] == CORRECTION_CANDIDATE_VERSION
    assert candidate["active_baseline_changed"] is False
    assert candidate["regression_gate"] == "PASS"
    assert report["self_correction"]["current_candidate"]["name"] == CORRECTION_CANDIDATE_VERSION
    html = render_failure_analysis_html(report)
    assert "fixture-trace" not in html
    assert "D90" not in html
    assert "private_answer_key_read" not in html


def test_report_registry_is_allow_listed_and_ignores_other_files(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "rag_gold_v2_baseline_evaluation.html").write_text("<h1>ok</h1>", encoding="utf-8")
    (reports / "private-key.md").write_text("secret", encoding="utf-8")

    found = available_rag_reports(tmp_path)
    assert [artifact.key for artifact, _ in found] == ["public_evaluation"]
    with pytest.raises(ValueError):
        RagReportArtifact("bad", "bad", "../private-key.md", "bad", "bad").path(tmp_path)


def test_dashboards_reference_report_collection_and_failure_artifact() -> None:
    project_root = Path(__file__).parents[1]
    governance_page = (project_root / "pages/4_RAG治理看板.py").read_text(encoding="utf-8")
    optimization_page = (project_root / "pages/5_RAG优化看板.py").read_text(encoding="utf-8")
    assert "available_rag_reports" in governance_page
    assert "rag_gold_v2_baseline_evaluation.html" in (
        project_root / "src/portrait_consistency_agent/services/rag_report_registry.py"
    ).read_text(encoding="utf-8")
    assert "rag_failure_patterns_v1.json" in optimization_page
    assert "rag_v5_holdout_gold_aggregate.json" in optimization_page
    assert "rag_v5_failure_analysis_v1.json" in optimization_page
    assert "proposal_only" in optimization_page or "只提议" in optimization_page
    report_keys = {artifact.key for artifact, _ in available_rag_reports(project_root)}
    assert {
        "public_evaluation",
        "holdout_aggregate",
        "failure_analysis",
        "v5_holdout_gold_aggregate",
        "v5_failure_analysis",
    } <= report_keys
