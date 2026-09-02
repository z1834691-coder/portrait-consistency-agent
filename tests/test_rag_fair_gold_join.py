from __future__ import annotations

# ruff: noqa: E501
import json
from pathlib import Path

import pytest

from portrait_consistency_agent.services.rag_fair_gold_join import (
    build_fair_gold_join_report,
    render_fair_gold_join_html,
)
from portrait_consistency_agent.services.rag_gold_eval import GoldSetFormatError


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _fixtures(tmp_path: Path, *, gate: str = "PASS") -> dict[str, Path]:
    v3_runtime = tmp_path / "v3.json"
    v4_runtime = tmp_path / "v4.json"
    _write(
        v3_runtime,
        {
            "dataset_version": "v3-fixture",
            "cases": [{"case_id": "H01", "split": "validation", "query": "测试"}],
        },
    )
    _write(
        v4_runtime,
        {"dataset_version": "v4-fixture", "cases": [{"case_id": "H401", "query": "测试"}]},
    )
    v3_key = tmp_path / "v3-key.json"
    v4_key = tmp_path / "v4-key.json"

    def key(case_id: str) -> dict[str, object]:
        return {
            "annotations": [
                {
                    "case_id": case_id,
                    "gold_routes": ["DIRECT"],
                    "gold_evidence": ["B"],
                    "gold_evidence_relations": {"B": "direct_evidence"},
                    "prohibited_events": [],
                    "hard_safety": True,
                }
            ]
        }

    _write(v3_key, key("H01"))
    _write(v4_key, key("H401"))

    def artifacts(case_id: str, *, route: str = "evidence_found") -> tuple[dict, dict]:
        import hashlib

        case_hash = hashlib.sha256(case_id.encode()).hexdigest()
        trace_ref = f"trace-{case_id}"
        prediction = {
            "route": route,
            "evidence_refs": [],
            "evidence_relations": {},
            "route_source": "retrieval_result",
            "evidence_source": "retrieval_result",
            "trace_ref": trace_ref,
            "case_id_sha256": case_hash,
        }
        trace = {
            "runner_version": "fixture",
            "compiler": {
                "status": "structured",
                "proposed_route": "DIRECT",
                "input_sha256": "input",
                "query_id": "q",
                "query_created": True,
            },
            "retrieval": {
                "route": route,
                "actual_evidence_refs": ["tencent-beautify-pic-2019-12-13#x"],
                "adopted_evidence_refs": [],
                "evidence_relations": {"tencent-beautify-pic-2019-12-13#x": "direct_evidence"},
            },
            "prediction": {"trace_ref": trace_ref},
            "governance": {
                "hidden_answer_key_read": False,
                "annotations_read": False,
                "quality_score_joined": False,
                "network_called": False,
                "llm_called": False,
                "provider_api_called": False,
                "external_provider_called": False,
                "photo_or_face_vector_read": False,
                "raw_prompt_persisted": False,
                "projection_injected_into_prediction": False,
            },
            "finalized": True,
            "case_id_sha256": case_hash,
        }
        return prediction, trace

    v3_prediction, v3_trace = artifacts("H01")
    v4_prediction, v4_trace = artifacts("H401")
    v3_predictions = tmp_path / "v3-predictions.json"
    v4_predictions = tmp_path / "v4-predictions.json"
    v3_traces = tmp_path / "v3-traces.json"
    v4_traces = tmp_path / "v4-traces.json"
    policy = {
        "hidden_answer_key_read": False,
        "answer_key_read": False,
        "annotations_read": False,
        "quality_score_joined": False,
        "network_called": False,
        "llm_called": False,
        "provider_api_called": False,
        "external_provider_called": False,
        "photo_or_face_vector_read": False,
        "raw_prompt_persisted": False,
        "projection_injected_into_prediction": False,
    }
    _write(v3_predictions, {"policy": policy, "rows": [v3_prediction]})
    _write(v4_predictions, {"policy": policy, "rows": [v4_prediction]})
    _write(v3_traces, {"policy": policy, "traces": [v3_trace]})
    _write(v4_traces, {"policy": policy, "traces": [v4_trace]})
    process = tmp_path / "process.json"
    _write(process, {"fresh_replay_process_gate": gate})
    return {
        "process": process,
        "v3_runtime": v3_runtime,
        "v3_predictions": v3_predictions,
        "v3_trace": v3_traces,
        "v3_key": v3_key,
        "v4_runtime": v4_runtime,
        "v4_predictions": v4_predictions,
        "v4_trace": v4_traces,
        "v4_key": v4_key,
    }


def _build(paths: dict[str, Path]) -> dict[str, object]:
    return build_fair_gold_join_report(
        process_report_path=paths["process"],
        v3_runtime_path=paths["v3_runtime"],
        v3_predictions_path=paths["v3_predictions"],
        v3_trace_path=paths["v3_trace"],
        v3_answer_key_path=paths["v3_key"],
        v4_runtime_path=paths["v4_runtime"],
        v4_predictions_path=paths["v4_predictions"],
        v4_trace_path=paths["v4_trace"],
        v4_answer_key_path=paths["v4_key"],
    )


def test_gold_join_requires_fresh_process_gate(tmp_path: Path) -> None:
    paths = _fixtures(tmp_path, gate="FAIL")
    with pytest.raises(GoldSetFormatError, match="process gate"):
        _build(paths)


def test_gold_join_separates_compiler_and_retrieval(tmp_path: Path) -> None:
    report = _build(_fixtures(tmp_path))
    assert report["quality_scoring_gate"] == "COMPLETE_AGGREGATE_ONLY"
    assert report["project_promotion_gate"] == "LOCKED_UNTIL_NEW_HOLDOUT"
    v4 = report["datasets"][1]
    assert v4["compiler_track"]["metrics"]["route_accuracy"] == 1.0
    assert v4["retrieval_track"]["metrics"]["recall_at_5"] == 1.0
    assert report["policy"]["gold_facts_emitted"] is False


def test_gold_join_html_is_aggregate_only(tmp_path: Path) -> None:
    report = _build(_fixtures(tmp_path))
    html = render_fair_gold_join_html(report)
    assert "Gold 只在内存中连接" in html
    assert "测试" not in html
    assert "gold_evidence" not in html
    assert "H401" not in html
