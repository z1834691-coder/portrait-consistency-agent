from __future__ import annotations

import base64
from pathlib import Path

from portrait_consistency_agent.services.effect_web_e3_flow import (
    accept_and_verify_effect_web_result,
)
from portrait_consistency_agent.services.verification import ResultObservation
from tests.test_execution import TINY_PNG, _store, _web_bundle


def test_web_e3_flow_reuses_common_verifier_and_persists_only_redacted_facts(
    monkeypatch, tmp_path: Path
) -> None:
    store, session_id = _store(tmp_path)
    bundle = _web_bundle(session_id=session_id)

    monkeypatch.setattr(
        "portrait_consistency_agent.services.verification.observe_result_bytes",
        lambda result_image_bytes, photo_id: ResultObservation(
            photo_id=photo_id,
            photo_sha256="c" * 64,
            decode_ok=True,
            face_count=1,
            normalized_features=(),
            analysis_version="fixture-web-observer",
        ),
    )
    # The empty feature set intentionally routes to an honest unverifiable
    # result; this test is about the shared handoff, not visual performance.
    result = accept_and_verify_effect_web_result(
        confirmed_plan=bundle["confirmation"].confirmed_plan,
        execution_intent=bundle["confirmation"].execution_intent,
        target_image_bytes=bundle["target_bytes"],
        target_photo_id=bundle["target"].photo_id,
        profile=bundle["profile"],
        quality_result=bundle["quality"],
        prepared_request=bundle["request"].model_dump(mode="json"),
        browser_receipt=bundle["receipt"].model_dump(mode="json"),
        browser_result=bundle["result_payload"],
        store=store,
        now=bundle["now"],
        allow_candidate_trial=True,
    )

    assert result.execution.route == "succeeded"
    assert result.provider_run is not None
    assert result.verification is not None
    assert result.verification.verification_strategy.value == "manual_visual_review"
    assert any(item["step"] == "web_to_verification_handoff" for item in result.trace)
    text = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert "output_data_url" not in text
    assert base64.b64encode(TINY_PNG).decode("ascii") not in text


def test_web_e3_flow_does_not_verify_failed_or_invalid_browser_result() -> None:
    bundle = _web_bundle()
    failed_receipt = bundle["receipt"].model_copy(
        update={
            "status": "failed",
            "output_sha256": None,
            "output_width": None,
            "output_height": None,
            "error_code": "SDK_ERROR",
            "safe_error": "Web SDK failed",
        }
    )
    result = accept_and_verify_effect_web_result(
        confirmed_plan=bundle["confirmation"].confirmed_plan,
        execution_intent=bundle["confirmation"].execution_intent,
        target_image_bytes=bundle["target_bytes"],
        target_photo_id=bundle["target"].photo_id,
        profile=bundle["profile"],
        quality_result=bundle["quality"],
        prepared_request=bundle["request"].model_dump(mode="json"),
        browser_receipt=failed_receipt.model_dump(mode="json"),
        browser_result=None,
        allow_candidate_trial=True,
    )
    assert result.execution.route == "failed"
    assert result.verification is None
    assert result.trace[-1]["status"] == "skipped"
