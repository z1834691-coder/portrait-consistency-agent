from __future__ import annotations

import json
from pathlib import Path

import pytest

from portrait_consistency_agent.services.rag_gold_eval import GoldSetFormatError
from portrait_consistency_agent.services.rag_v5_failure_analysis import (
    build_v5_failure_analysis,
    render_v5_failure_analysis_html,
)


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _fixture(tmp_path: Path) -> dict[str, Path]:
    runtime = tmp_path / "runtime.json"
    predictions = tmp_path / "predictions.json"
    trace = tmp_path / "trace.json"
    key = tmp_path / "answer-key.json"
    _write(
        runtime,
        {
            "dataset_version": "v5-fixture",
            "cases": [{"case_id": "V501", "query": "脱敏题"}],
        },
    )
    _write(
        key,
        {
            "annotations": [
                {
                    "case_id": "V501",
                    "gold_routes": ["DIRECT"],
                    "gold_evidence": ["B"],
                    "gold_evidence_relations": {"B": "direct_evidence"},
                    "prohibited_events": [],
                    "hard_safety": True,
                }
            ]
        },
    )
    _write(
        predictions,
        {
            "rows": [
                {
                    "case_id": "V501",
                    "route": "baseline_fallback",
                    "evidence_refs": ["P", "FX"],
                    "evidence_relations": {"P": "reference_context"},
                    "observed_events": [],
                    "trace_ref": "t1",
                    "machine_score_summary": {},
                }
            ]
        },
    )
    governance = {
        "hidden_answer_key_read": False,
        "annotations_read": False,
        "network_called": False,
        "llm_called": False,
        "provider_api_called": False,
        "external_provider_called": False,
        "photo_or_face_vector_read": False,
        "raw_prompt_persisted": False,
        "quality_score_joined": False,
    }
    _write(
        trace,
        {
            "traces": [
                {
                    "case_id": "V501",
                    "compiler": {"proposed_route": "DIRECT", "category_codes": ["x"]},
                    "retrieval": {},
                    "prediction": {},
                    "governance": governance,
                    "finalized": True,
                }
            ]
        },
    )
    return {"runtime": runtime, "predictions": predictions, "trace": trace, "key": key}


def test_requires_explicit_owner_approval(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    with pytest.raises(GoldSetFormatError, match="owner_approved"):
        build_v5_failure_analysis(
            runtime_path=paths["runtime"],
            predictions_path=paths["predictions"],
            trace_path=paths["trace"],
            answer_key_path=paths["key"],
        )


def test_returns_aggregate_only_and_finds_patterns(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    report = build_v5_failure_analysis(
        runtime_path=paths["runtime"],
        predictions_path=paths["predictions"],
        trace_path=paths["trace"],
        answer_key_path=paths["key"],
        owner_approved=True,
    )
    assert report["failure_counts"]["route_mismatch"] == 1
    assert report["failure_counts"]["evidence_overpacked_and_incomplete"] == 1
    assert report["policy"]["case_ids_in_output"] is False
    html = render_v5_failure_analysis_html(report)
    assert "V501" not in html
    assert "脱敏题" not in html


def test_rejects_key_inside_workspace(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    # The test fixture is outside the workspace; this checks the explicit
    # guard with a temporary path that resolves to the project only when
    # callers accidentally pass a project file.
    project_key = Path(__file__).resolve().parents[1] / "tests" / "_v5_key_should_not_exist.json"
    project_key.write_text("{}", encoding="utf-8")
    try:
        with pytest.raises(GoldSetFormatError, match="outside the project"):
            build_v5_failure_analysis(
                runtime_path=paths["runtime"],
                predictions_path=paths["predictions"],
                trace_path=paths["trace"],
                answer_key_path=project_key,
                owner_approved=True,
            )
    finally:
        project_key.unlink(missing_ok=True)
