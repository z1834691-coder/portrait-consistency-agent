from __future__ import annotations

import json
from pathlib import Path

import pytest

from portrait_consistency_agent.core.rag_safety_events import (
    SAFETY_EVENT_CATALOG_VERSION,
    canonical_safety_event_id,
    normalize_safety_events,
)
from portrait_consistency_agent.services.rag_gold_eval import (
    GoldAnnotation,
    GoldCase,
    GoldSetFormatError,
    Prediction,
    build_blind_judge_input,
    build_holdout_input_report,
    evaluate,
    load_annotations,
    load_holdout_runtime_cases,
    load_predictions,
    load_public_cases,
    run_fake_judge,
    run_live_judge,
)


def _case(case_id: str = "D01", split: str = "dev") -> GoldCase:
    return GoldCase(case_id=case_id, split=split, query="测试问题")


def _annotation(case_id: str = "D01", *, prohibited: tuple[str, ...] = ()) -> GoldAnnotation:
    return GoldAnnotation(
        case_id=case_id,
        gold_routes=("DIRECT",),
        gold_evidence=("B", "P"),
        gold_evidence_relations={"B": "direct_evidence", "P": "reference_context"},
        prohibited_events=prohibited,
        hard_safety=True,
    )


def test_metrics_are_replayable_and_rank_aware() -> None:
    report = evaluate(
        cases=[_case()],
        annotations={"D01": _annotation()},
        predictions={
            "D01": Prediction(
                case_id="D01",
                route="evidence_found",
                evidence_refs=("P", "B"),
                evidence_relations={"B": "direct_evidence", "P": "reference_context"},
            )
        },
        dataset_version="fixture-v1",
    )

    assert report.status == "complete"
    assert report.metrics is not None
    assert report.metrics["route_accuracy"] == 1.0
    assert report.metrics["evidence_exact_accuracy"] == 1.0
    assert report.metrics["precision_at_3"] == pytest.approx(2 / 3)
    assert report.metrics["precision_at_3_effective"] == pytest.approx(1.0)
    assert report.metrics["precision_at_3_returned"] == pytest.approx(1.0)
    assert report.metrics["precision_by_gold_evidence_count"]["2"]["cases"] == 1
    assert report.metrics["precision_by_gold_evidence_count"]["2"][
        "precision_at_3"
    ] == pytest.approx(2 / 3)
    assert report.metrics["recall_at_5"] == 1.0
    assert report.metrics["mrr"] == 1.0 / 1.0
    assert report.metrics["hard_safety_gate"] == "PASS"
    assert report.metrics["project_threshold_gate"] == "FAIL"


def test_missing_and_empty_sets_are_pending_not_false_pass() -> None:
    empty = evaluate(cases=[], annotations={}, predictions={})
    assert empty.status == "pending"
    assert empty.metrics is not None
    assert empty.metrics["route_accuracy"] is None

    report = evaluate(
        cases=[_case()],
        annotations={"D01": _annotation()},
        predictions=None,
        dataset_version="fixture-v1",
    )

    assert report.status == "pending"
    assert report.counts["missing_predictions"] == 1
    assert report.case_scores[0].route_correct is None
    assert report.metrics is not None
    assert report.metrics["route_accuracy"] is None
    assert report.metrics["hard_safety_gate"] == "PENDING"
    assert report.metrics["project_threshold_gate"] == "PENDING"


def test_hard_safety_gate_counts_injection_or_conflict_violation() -> None:
    case = _case("X11", "challenge")
    annotation = _annotation("X11", prohibited=("ignore_hard_fact_conflict",))
    unsafe = evaluate(
        cases=[case],
        annotations={"X11": annotation},
        predictions={
            "X11": Prediction(
                case_id="X11",
                route="conflict_blocked",
                evidence_refs=("FX",),
                observed_events=("ignore_hard_fact_conflict",),
            )
        },
    )
    assert unsafe.metrics is not None
    assert unsafe.metrics["hard_safety_violation_count"] == 1
    assert unsafe.metrics["hard_safety_gate"] == "FAIL"

    safe = evaluate(
        cases=[case],
        annotations={"X11": annotation},
        predictions={
            "X11": Prediction(
                case_id="X11",
                route="conflict_blocked",
                evidence_refs=("FX",),
                observed_events=(),
            )
        },
    )
    assert safe.metrics is not None
    assert safe.metrics["hard_safety_violation_count"] == 0
    assert safe.metrics["hard_safety_gate"] == "PASS"


def test_safety_event_dictionary_is_exact_and_unknown_requires_review() -> None:
    known = canonical_safety_event_id("ignore hard fact conflict")
    assert known == "RAG_EVT_IGNORE_HARD_FACT_CONFLICT"
    assert canonical_safety_event_id("ignore_hard_fact_conflictt") is None
    normalized = normalize_safety_events(
        ("ignore_hard_fact_conflict", "RAG_EVT_IGNORE_HARD_FACT_CONFLICT", "new wording")
    )
    assert normalized.canonical_ids == ("RAG_EVT_IGNORE_HARD_FACT_CONFLICT",)
    assert normalized.unknown_labels == ("new wording",)
    assert normalized.manual_review_required is True

    case = _case("UNKNOWN_EVENT")
    annotation = _annotation("UNKNOWN_EVENT", prohibited=("new wording",))
    report = evaluate(
        cases=[case],
        annotations={case.case_id: annotation},
        predictions={case.case_id: Prediction(case.case_id, "direct", ("B", "P"))},
    )
    assert report.metrics is not None
    assert report.metrics["safety_event_catalog_version"] == SAFETY_EVENT_CATALOG_VERSION
    assert report.metrics["safety_event_unknown_label_count"] == 1
    assert report.metrics["hard_safety_gate"] == "MANUAL_REVIEW_REQUIRED"
    assert report.metrics["project_threshold_gate"] == "FAIL"


def test_unknown_conflict_injection_routes_are_scored_without_external_calls() -> None:
    cases = [_case("D25"), _case("X11", "challenge"), _case("X17", "challenge")]
    annotations = {
        "D25": GoldAnnotation(
            case_id="D25",
            gold_routes=("BLOCK",),
            gold_evidence=("FX",),
            gold_evidence_relations={"FX": "conflict_evidence"},
            prohibited_events=("follow_knowledge_prompt_injection",),
        ),
        "X11": GoldAnnotation(
            case_id="X11",
            gold_routes=("BLOCK",),
            gold_evidence=("FX",),
            gold_evidence_relations={"FX": "conflict_evidence"},
            prohibited_events=("ignore_hard_fact_conflict",),
        ),
        "X17": GoldAnnotation(
            case_id="X17",
            gold_routes=("UNKNOWN", "BASELINE"),
            gold_evidence=("P",),
            gold_evidence_relations={"P": "reference_context"},
            prohibited_events=("pretend_index_available",),
        ),
    }
    predictions = {
        "D25": Prediction("D25", "block", ("FX",), {"FX": "conflict_evidence"}),
        "X11": Prediction("X11", "conflict_blocked", ("FX",), {"FX": "conflict_evidence"}),
        "X17": Prediction("X17", "unknown_stopped", ("P",), {"P": "reference_context"}),
    }
    report = evaluate(cases=cases, annotations=annotations, predictions=predictions)
    assert report.metrics is not None
    assert report.metrics["route_accuracy"] == 1.0
    assert report.metrics["hard_safety_violation_count"] == 0
    assert report.policy["llm_called"] is False
    assert report.policy["external_provider_called"] is False


def test_public_case_file_has_no_answers_and_holdout_rejects_answer_fields(tmp_path) -> None:
    public = tmp_path / "public.json"
    public.write_text(
        json.dumps(
            {
                "dataset_version": "fixture",
                "cases": [{"case_id": "D01", "split": "dev", "query": "q"}],
            }
        ),
        encoding="utf-8",
    )
    version, cases = load_public_cases(public)
    assert version == "fixture"
    assert cases == (GoldCase(case_id="D01", split="dev", query="q"),)

    hidden = tmp_path / "hidden.json"
    hidden.write_text(json.dumps({"cases": [{"case_id": "H01", "query": "q"}]}), encoding="utf-8")
    _, hidden_cases = load_holdout_runtime_cases(hidden)
    report = build_holdout_input_report(dataset_version="fixture", cases=hidden_cases)
    assert report["metrics"] is None
    assert report["cases"] == [{"case_id": "H01", "query": "q"}]

    hidden.write_text(
        json.dumps({"cases": [{"case_id": "H01", "query": "q", "gold_route": "BLOCK"}]}),
        encoding="utf-8",
    )
    with pytest.raises(GoldSetFormatError):
        load_holdout_runtime_cases(hidden)


def test_independent_holdout_template_is_empty_and_answerless() -> None:
    template = (
        Path(__file__).parents[1] / "data/evaluation/rag_gold_v3_holdout_runtime.template.json"
    )
    version, cases = load_holdout_runtime_cases(template)
    assert version == "rag-v3-holdout-pending"
    assert cases == ()


def test_blind_judge_payload_excludes_gold_and_fake_judge_is_local() -> None:
    case = GoldCase(case_id="D01", split="dev", query="用户问题", tags=("secret_dev_label",))
    prediction = Prediction(
        case_id="D01",
        route="direct",
        evidence_refs=("B",),
        evidence_relations={"B": "direct_evidence"},
        trace_ref="trace_001",
        machine_score_summary={"retrieval_latency_ms": 12},
    )
    payload = build_blind_judge_input(case, prediction).to_dict()
    encoded = json.dumps(payload, ensure_ascii=False)
    assert "gold" not in encoded.casefold()
    assert "secret_dev_label" not in encoded
    assert "split" not in payload
    assert payload["machine_score_summary"]["retrieval_latency_ms"] == 12
    assert payload["machine_score_summary"]["evidence_count"] == 1
    result = run_fake_judge(build_blind_judge_input(case, prediction))
    assert result.verdict == "candidate_for_human_review"

    with pytest.raises(RuntimeError):
        run_live_judge(judge_input=build_blind_judge_input(case, prediction))


def test_annotation_loader_rejects_hidden_answer_id(tmp_path) -> None:
    path = tmp_path / "answers.json"
    path.write_text(
        json.dumps({"annotations": [{"case_id": "H01", "gold_routes": ["BLOCK"]}]}),
        encoding="utf-8",
    )
    with pytest.raises(GoldSetFormatError):
        load_annotations(path, allowed_case_ids={"D01"})


def test_load_predictions_rejects_raw_user_text_or_photo_fields(tmp_path) -> None:
    path = tmp_path / "predictions.json"
    path.write_text(
        json.dumps({"rows": [{"case_id": "D01", "raw_text": "secret"}]}), encoding="utf-8"
    )
    with pytest.raises(GoldSetFormatError):
        load_predictions(path)
