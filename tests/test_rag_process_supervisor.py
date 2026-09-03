from __future__ import annotations

from portrait_consistency_agent.services.rag_gold_eval import GoldCase
from portrait_consistency_agent.services.rag_process_supervisor import (
    RagFairEvaluationRunner,
    RagProcessSupervisor,
    audit_fair_run,
    fair_run_payload,
    fair_trace_payload,
)
from portrait_consistency_agent.services.rag_query_compiler_candidate import (
    compile_generalized_projection_v3,
)
from portrait_consistency_agent.services.rag_route_handoff_candidate import (
    select_validated_route,
)


def test_fair_runner_retrieves_every_case_without_projection_injection() -> None:
    cases = (
        GoldCase(case_id="H401", split="holdout", query="请说明一个没有固定关键词的复杂目标"),
        GoldCase(case_id="H402", split="holdout", query="我想让脸宽更接近母版，但不要改变妆面"),
    )
    run = RagFairEvaluationRunner().run(
        cases,
        dataset_version="test-v1",
        runtime_mode="holdout_process_replay",
    )
    report = audit_fair_run(run, run_id="test-fair-run")

    assert report.process_gate == "PASS"
    assert report.quality_scoring_gate == "READY_AFTER_SEPARATE_GOLD_JOIN"
    assert report.counts["retrieval_complete"] == 2
    assert report.counts["compiler_unknown_fallback"] == 1
    assert all(
        row["route_source"] == "retrieval_result" and row["evidence_source"] == "retrieval_result"
        for row in run.predictions
    )
    assert all("projection" not in trace for trace in run.traces)
    assert all(trace["governance"]["hidden_answer_key_read"] is False for trace in run.traces)

    persisted_prediction = fair_run_payload(run)
    persisted_trace = fair_trace_payload(run)
    assert len(persisted_prediction["rows"]) == 2
    assert len(persisted_trace["traces"]) == 2
    for payload in (persisted_prediction, persisted_trace):
        serialized = str(payload)
        assert "原始题干不应出现在 Trace" not in serialized
        assert '"question"' not in serialized
        assert '"gold_route"' not in serialized
    assert "case_id" not in persisted_trace["traces"][0]["prediction"]
    assert "case_id" not in persisted_trace["traces"][0]


def test_fair_runner_records_validated_route_handoff_lineage() -> None:
    cases = (GoldCase(case_id="H403", split="holdout", query="请把脸宽调整得更接近母版"),)
    run = RagFairEvaluationRunner().run(
        cases,
        dataset_version="test-v1",
        runtime_mode="holdout_process_replay",
        projection_compiler=compile_generalized_projection_v3,
        compiler_version="route-handoff-fixture-v1",
        route_handoff=select_validated_route,
    )
    report = audit_fair_run(run, run_id="test-handoff")
    assert report.process_gate == "PASS"
    assert run.predictions[0]["route_source"] == "validated_route_handoff"
    assert run.traces[0]["route_handoff"]["proposal_only"] is True
    assert run.traces[0]["route_handoff"]["execution_authorized"] is False


def test_supervisor_rejects_legacy_projection_and_incomplete_trace() -> None:
    report = RagProcessSupervisor().audit(
        dataset_version="legacy-v0",
        runtime_mode="historical_v4_snapshot",
        run_id="legacy",
        case_ids=["H401"],
        traces=[
            {
                "case_id": "H401",
                "projection": {"route": "UNKNOWN", "evidence_aliases": ["P"]},
                "prediction_route": "UNKNOWN",
                "query": "原始题干不应出现在 Trace",
            }
        ],
        predictions=[
            {
                "case_id": "H401",
                "route": "UNKNOWN",
                "evidence_refs": ["P"],
                "gold_route": "UNKNOWN",
            }
        ],
        policy={
            "hidden_answer_key_read": False,
            "annotations_read": False,
            "network_called": False,
            "llm_called": False,
            "provider_api_called": False,
            "external_provider_called": False,
            "photo_or_face_vector_read": False,
            "raw_prompt_persisted": False,
        },
    )

    assert report.process_gate == "FAIL"
    assert report.violations_by_code["PROJECTION_INJECTED_INTO_EVALUATION"] >= 1
    assert report.violations_by_code["ANSWER_OR_GOLD_FIELD_PRESENT"] >= 1
    assert report.violations_by_code["RAW_QUESTION_FIELD_PRESENT"] >= 1
    assert report.quality_scoring_gate == "LOCKED_PROCESS_AUDIT"


def test_supervisor_does_not_unlock_quality_when_a_case_is_missing() -> None:
    report = RagProcessSupervisor().audit(
        dataset_version="test-v1",
        runtime_mode="holdout_process_replay",
        run_id="missing",
        case_ids=["H401", "H402"],
        traces=[],
        predictions=[],
        policy={
            "hidden_answer_key_read": False,
            "annotations_read": False,
            "network_called": False,
            "llm_called": False,
            "provider_api_called": False,
            "external_provider_called": False,
            "photo_or_face_vector_read": False,
            "raw_prompt_persisted": False,
        },
    )

    assert report.process_gate == "FAIL"
    assert report.quality_scoring_gate == "LOCKED_PROCESS_AUDIT"
    assert report.excluded_count == 2
    assert report.violations_by_code["MISSING_CASE_TRACE"] == 1
    assert report.violations_by_code["MISSING_CASE_PREDICTION"] == 1
