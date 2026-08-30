from dataclasses import replace
from datetime import datetime, timezone

from portrait_consistency_agent.core.contracts import (
    ComparisonTrend,
    FeatureDifference,
    MeasurementStatus,
    MeasurementUnit,
    NormalizedFeature,
    StopReason,
    VerificationDecision,
    VerificationStrategy,
)
from portrait_consistency_agent.core.policies import build_v0_verification_policy
from portrait_consistency_agent.services import verification
from portrait_consistency_agent.services.verification import (
    ResultObservation,
    propose_verification_strategy,
    verify_result,
)
from portrait_consistency_agent.storage.local_store import LocalTraceStore
from tests.test_contracts import make_plan, make_profile, make_provider_run

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


def _observation(value: float, *, comparable: bool = True) -> ResultObservation:
    features = (
        (
            NormalizedFeature(
                feature_code="face_width_height_ratio",
                value=value,
                unit=MeasurementUnit.NORMALIZED_RATIO,
                status=MeasurementStatus.MEASURED,
                confidence=0.92,
            ),
        )
        if comparable
        else ()
    )
    return ResultObservation(
        photo_id="photo_001",
        photo_sha256="c" * 64,
        decode_ok=comparable,
        face_count=1 if comparable else 0,
        normalized_features=features,
        analysis_version="fixture-observer-v0",
    )


def _plan() -> object:
    return make_plan(
        baseline_feature_differences=[
            FeatureDifference(
                feature_code="face_width_height_ratio",
                reference_value=0.72,
                observed_value=0.8064,
                normalized_gap=0.12,
                measurement_confidence=0.92,
                editable=True,
                reason_codes=["mapped_feature"],
            )
        ]
    )


def test_verification_improvement_routes_to_replan_and_exposes_trace(monkeypatch) -> None:
    monkeypatch.setattr(
        verification,
        "observe_result_bytes",
        lambda result_image_bytes, photo_id: _observation(0.756),
    )

    result = verify_result(
        profile=make_profile(),
        plan=_plan(),
        provider_run=make_provider_run(),
        result_image_bytes=b"result-bytes",
        plan_family_id="family_001",
        verification_id="verification_improved",
    )

    assert result.verification.overall_trend == ComparisonTrend.IMPROVED
    assert result.verification.decision == VerificationDecision.REPLAN
    assert result.verification.cumulative_improvement is True
    assert result.verification.target_evidence_sufficient is False
    assert result.strategy_proposal.selected_strategy == VerificationStrategy.LOCAL_GEOMETRY
    assert [item["step"] for item in result.trace] == [
        "observe_result",
        "verification_strategy_select",
        "compare_features",
        "route",
        "persist_verification",
    ]


def test_verification_target_evidence_is_structured_not_a_probability(monkeypatch) -> None:
    monkeypatch.setattr(
        verification,
        "observe_result_bytes",
        lambda result_image_bytes, photo_id: _observation(0.7416),
    )

    result = verify_result(
        profile=make_profile(),
        plan=_plan(),
        provider_run=make_provider_run(),
        result_image_bytes=b"result-bytes",
        verification_id="verification_goal",
    )

    assert result.verification.overall_trend == ComparisonTrend.IMPROVED
    assert result.verification.target_evidence_sufficient is True
    assert result.verification.decision == VerificationDecision.CLOSE
    assert result.verification.stop_reason == StopReason.GOAL_MET
    assert result.verification.calibrated_acceptance is None


def test_worsened_result_requires_rollback_evidence(monkeypatch) -> None:
    monkeypatch.setattr(
        verification,
        "observe_result_bytes",
        lambda result_image_bytes, photo_id: _observation(0.864),
    )

    without_fallback = verify_result(
        profile=make_profile(),
        plan=_plan(),
        provider_run=make_provider_run(),
        result_image_bytes=b"result-bytes",
        verification_id="verification_worse_review",
    )
    assert without_fallback.verification.overall_trend == ComparisonTrend.WORSENED
    assert without_fallback.verification.decision == VerificationDecision.MANUAL_REVIEW
    assert without_fallback.verification.manual_review is not None

    with_fallback = verify_result(
        profile=make_profile(),
        plan=_plan(),
        provider_run=make_provider_run(run_id="run_worse_002"),
        result_image_bytes=b"result-bytes",
        last_known_good_artifact_ref="session_memory_previous",
        verification_id="verification_worse_stop",
    )
    assert with_fallback.verification.decision == VerificationDecision.STOP
    assert with_fallback.verification.stop_reason == StopReason.RESULT_WORSENED


def test_uncomparable_result_routes_to_reshoot_without_claiming_success(monkeypatch) -> None:
    monkeypatch.setattr(
        verification,
        "observe_result_bytes",
        lambda result_image_bytes, photo_id: _observation(0.0, comparable=False),
    )

    result = verify_result(
        profile=make_profile(),
        plan=_plan(),
        provider_run=make_provider_run(run_id="run_uncomparable"),
        result_image_bytes=b"broken-result",
        verification_id="verification_reshoot",
    )

    assert result.verification.decision == VerificationDecision.RESHOOT
    assert result.verification.stop_reason == StopReason.INPUT_NOT_COMPARABLE
    assert result.verification.target_evidence_sufficient is False
    assert result.verification.result_artifact_available is False


def test_strategy_selector_requires_permission_for_external_route() -> None:
    observation = _observation(0.72, comparable=False)
    proposal = propose_verification_strategy(
        observation,
        policy=replace(
            build_v0_verification_policy(),
            allowed_strategies=(
                VerificationStrategy.EXTERNAL_SUBJECT_MATCH,
                VerificationStrategy.MANUAL_VISUAL_REVIEW,
            ),
        ),
        available_strategies=[
            VerificationStrategy.EXTERNAL_SUBJECT_MATCH,
            VerificationStrategy.MANUAL_VISUAL_REVIEW,
        ],
        data_outbound_allowed=True,
        proposal_id="strategy_external",
    )

    assert proposal.selected_strategy == VerificationStrategy.EXTERNAL_SUBJECT_MATCH
    assert proposal.data_outbound is True
    assert proposal.additional_consent_required is True


def test_verification_persists_redacted_result_and_trace(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        verification,
        "observe_result_bytes",
        lambda result_image_bytes, photo_id: _observation(0.7416),
    )
    store = LocalTraceStore(tmp_path / "demo.sqlite3", tmp_path / "events.jsonl")
    store.initialize()
    session = store.create_session()
    plan = _plan().model_copy(update={"session_id": session.session_id})
    provider_run = make_provider_run(
        session_id=session.session_id,
        plan_id=plan.plan_id,
        photo_id=plan.photo_id,
    )

    result = verify_result(
        profile=make_profile(),
        plan=plan,
        provider_run=provider_run,
        result_image_bytes=b"result-bytes",
        store=store,
        verification_id="verification_persisted",
    )

    assert result.verification.decision == VerificationDecision.CLOSE
    with store._connect() as connection:
        row = connection.execute(
            "SELECT verification_payload_redacted_json FROM verification_results "
            "WHERE verification_id = ?",
            ("verification_persisted",),
        ).fetchone()
    assert row is not None
    payload = row["verification_payload_redacted_json"]
    assert "result-bytes" not in payload
    assert "image_base64" not in payload
    assert "result_bytes_persisted" in store.trace_path.read_text(encoding="utf-8")
