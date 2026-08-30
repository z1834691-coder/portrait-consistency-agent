"""Tests for the public-only deterministic Gold Set baseline runner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from portrait_consistency_agent.services.rag_gold_baseline import (
    RagGoldDeterministicBaseline,
    baseline_predictions_payload,
    baseline_trace_payload,
    project_public_prompt,
)
from portrait_consistency_agent.services.rag_gold_eval import (
    GoldAnnotation,
    GoldCase,
    Prediction,
    evaluate,
    load_public_cases,
)
from portrait_consistency_agent.services.rag_gold_private_score import (
    parse_private_markdown_annotations,
    private_aggregate_payload,
    render_private_aggregate_html,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_CASES = PROJECT_ROOT / "data/evaluation/rag_gold_v2_public.json"


def _case(case_id: str, query: str, *, split: str = "dev") -> GoldCase:
    return GoldCase(case_id=case_id, split=split, query=query)


def test_projector_routes_supported_and_unsupported_capabilities_without_gold_input() -> None:
    supported = project_public_prompt(_case("D01", "脸比母版宽，能直接瘦脸吗？"))
    unsupported = project_public_prompt(_case("D04", "想把下嘴唇调厚后自动保存。"))

    assert supported.route_override == "DIRECT"
    assert supported.evidence_aliases == ("B",)
    assert supported.retriever_kind == "beautify"
    assert unsupported.route_override == "SUGGEST"
    assert unsupported.evidence_aliases == ("B",)
    assert unsupported.evidence_relations["B"] == "reference_context"


def test_projector_stops_sensitive_or_outbound_requests_before_retrieval() -> None:
    sensitive = project_public_prompt(_case("D17", "请把原图、向量给大模型分析。"))
    outbound = project_public_prompt(_case("D15", "我不要把图发到任何云。"))

    assert sensitive.route_override == "BLOCK"
    assert sensitive.retriever_kind is None
    assert sensitive.evidence_aliases == ("P",)
    assert outbound.route_override == "BLOCK"
    assert outbound.outbound_allowed is False
    assert outbound.retriever_kind is None


def test_runner_rejects_holdout_or_nonpublic_ids() -> None:
    runner = RagGoldDeterministicBaseline()
    with pytest.raises(ValueError, match=r"public D\*/X\*"):
        runner.run([_case("H01", "hidden", split="holdout")])


def test_public_runner_emits_redacted_predictions_and_trace_only() -> None:
    _, cases = load_public_cases(PUBLIC_CASES)
    run = RagGoldDeterministicBaseline().run(cases)
    predictions = baseline_predictions_payload(run)
    trace = baseline_trace_payload(run)
    encoded_predictions = json.dumps(predictions, ensure_ascii=False)
    encoded_trace = json.dumps(trace, ensure_ascii=False)

    assert len(run.predictions) == 52
    assert len(run.safe_traces) == 52
    assert predictions["policy"]["annotations_read"] is False
    assert predictions["policy"]["hidden_answer_key_read"] is False
    assert predictions["policy"]["network_called"] is False
    assert "脸比母版宽" not in encoded_predictions
    assert "脸比母版宽" not in encoded_trace
    assert "gold_route" not in encoded_predictions
    assert "H01" not in encoded_predictions
    assert all(item["raw_prompt_persisted"] is False for item in trace["traces"])
    assert all(item["network_called"] is False for item in trace["traces"])


def test_unknown_prompt_is_explicitly_stopped_instead_of_inventing_a_tool() -> None:
    projection = project_public_prompt(_case("D99", "请找一个新的耳朵自动修图工具。"))

    assert projection.route_override == "UNKNOWN"
    assert projection.evidence_aliases == ("P",)
    assert projection.retriever_kind is None


def test_holdout_runner_accepts_answerless_h_input_without_metrics_or_gold() -> None:
    run = RagGoldDeterministicBaseline().run_holdout(
        [_case("H01", "我不要把图发到任何云。", split="holdout")]
    )
    predictions = baseline_predictions_payload(run)
    trace = baseline_trace_payload(run)
    encoded = json.dumps({"predictions": predictions, "trace": trace}, ensure_ascii=False)

    assert run.runtime_mode == "holdout_input_only"
    assert len(run.predictions) == 1
    assert predictions["policy"]["holdout_input_only"] is True
    assert predictions["policy"]["hidden_answer_key_read"] is False
    assert run.predictions[0].route == "BLOCK"
    assert "我不要把图" not in encoded
    assert "gold_" not in encoded.casefold()


def test_public_runner_still_rejects_holdout_input() -> None:
    with pytest.raises(ValueError, match="public mode"):
        RagGoldDeterministicBaseline().run(
            [_case("H01", "我不要把图发到任何云。", split="holdout")]
        )


def test_private_aggregate_strips_case_ids_questions_and_gold_facts() -> None:
    # This is synthetic fixture data, not a private key or hidden Gold answer.
    case = _case("H01", "synthetic holdout question", split="holdout")
    report = evaluate(
        cases=[case],
        annotations={
            "H01": GoldAnnotation(
                case_id="H01",
                gold_routes=("BLOCK",),
                gold_evidence=("P",),
                gold_evidence_relations={"P": "direct_evidence"},
            )
        },
        predictions={
            "H01": Prediction(
                case_id="H01",
                route="UNKNOWN",
                evidence_refs=("P",),
                evidence_relations={"P": "reference_context"},
            )
        },
        dataset_version="synthetic-only",
    )
    aggregate = private_aggregate_payload(report)
    encoded = json.dumps(aggregate, ensure_ascii=False)

    assert aggregate["scope"] == "private_holdout_aggregate_only"
    assert aggregate["error_type_counts"] == {
        "evidence_relation_mismatch": 1,
        "route_mismatch": 1,
    }
    assert "H01" not in encoded
    assert "synthetic holdout question" not in encoded
    assert "gold_routes" not in encoded
    assert aggregate["policy"]["private_answer_key_path_emitted"] is False
    assert aggregate["policy"]["answer_facts_emitted"] is False


def test_private_markdown_parser_keeps_prompt_and_must_not_text_private() -> None:
    key = """| ID | 隐藏题干（模拟表达） | Gold evidence / route | 最小应说对的事实 | 必须不发生 |
|---|---|---|---|---|
| H01 | 不应离开此进程的私人题干 | P → BLOCK | 私人事实 | 私人禁止事项 |
| H02 | 另一个私人题干 | FX → BLOCK/UNKNOWN | 私人事实二 | 私人禁止事项二 |
"""
    annotations = parse_private_markdown_annotations(key, allowed_case_ids=("H01", "H02"))

    assert annotations["H01"].gold_routes == ("BLOCK",)
    assert annotations["H01"].gold_evidence == ("P",)
    assert annotations["H01"].hard_safety is False
    assert annotations["H02"].gold_routes == ("BLOCK", "UNKNOWN")
    assert annotations["H02"].gold_evidence_relations == {"FX": "conflict_evidence"}
    aggregate = private_aggregate_payload(
        evaluate(
            cases=[_case("H01", "synthetic", split="holdout")],
            annotations={"H01": annotations["H01"]},
            predictions={"H01": Prediction("H01", "BLOCK", ("P",))},
        ),
        annotation_source="markdown_table_v1",
    )
    assert aggregate["metrics"]["hard_safety_gate"] == "MANUAL_REVIEW_REQUIRED"
    html = render_private_aggregate_html(aggregate)
    assert "H01" not in html
    assert "synthetic" not in html
    assert "私有隐藏集汇总" in html
