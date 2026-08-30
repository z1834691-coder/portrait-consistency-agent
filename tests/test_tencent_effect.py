import math

import pytest
from pydantic import ValidationError

from portrait_consistency_agent.services.provider_cards import load_tencent_effect_card
from portrait_consistency_agent.services.tencent_effect import (
    EFFECT_CARD_ID,
    EFFECT_CARD_VERSION,
    EffectGateInput,
    EffectLicenseStatus,
    EffectPlatform,
    TencentEffectAdapter,
    TencentEffectNotReadyError,
    load_typed_tencent_effect_card,
)


def test_candidate_card_is_typed_and_keeps_unverified_features_explicit() -> None:
    raw = load_tencent_effect_card()
    card = load_typed_tencent_effect_card()

    assert raw["review_status"] == "candidate"
    assert card.card_id == EFFECT_CARD_ID
    assert card.card_version == EFFECT_CARD_VERSION
    assert set(card.platforms) == set(EffectPlatform)
    by_feature = {item.feature_code: item for item in card.parameters}
    assert by_feature["lips_thickness"].provider_parameter == "BeautyConstant.BEAUTY_MOUTH_HEIGHT"
    assert by_feature["eyebrow"].provider_parameter is None
    assert (
        by_feature["eyebrow"].documentation_status.value == "documented_feature_no_static_mapping"
    )
    assert (
        card.platforms[EffectPlatform.WEB].static_image_status.value
        == "documented_not_live_verified"
    )
    assert card.endpoint is None
    assert card.batch.status.value == "not_documented_in_reviewed_sources"
    assert card.evidence_review["privacy_region_latency_findings"]["latency"].startswith(
        "No official"
    )


def test_candidate_card_loader_rejects_a_promoted_card(monkeypatch: pytest.MonkeyPatch) -> None:
    import portrait_consistency_agent.services.provider_cards as provider_cards

    original = provider_cards.TENCENT_EFFECT_CARD_PATH

    class FakePath:
        def read_text(self, *, encoding: str) -> str:
            import json

            payload = json.loads(original.read_text(encoding=encoding))
            payload["review_status"] = "verified"
            return json.dumps(payload)

    monkeypatch.setattr(provider_cards, "TENCENT_EFFECT_CARD_PATH", FakePath())
    with pytest.raises(Exception, match="must remain candidate"):
        load_tencent_effect_card()


def test_prepare_request_contains_only_opaque_artifact_and_parameters() -> None:
    adapter = TencentEffectAdapter()

    request = adapter.prepare_request(
        request_ref="effect_request_001",
        input_artifact_ref="photo_artifact_001",
        platform=EffectPlatform.WEB,
        parameters={"lips_thickness": 8, "face_shape": 12},
        batch_size=2,
    )

    payload = request.model_dump(mode="json")
    assert payload["request_mode"] == "candidate_shell"
    assert payload["parameters"] == {"lips_thickness": 8.0, "face_shape": 12.0}
    assert "image" not in payload
    assert "base64" not in payload
    assert "secret" not in payload


def test_prepare_request_rejects_unknown_or_unverified_parameters() -> None:
    adapter = TencentEffectAdapter()

    with pytest.raises(ValueError, match="does not list feature"):
        adapter.prepare_request(
            request_ref="effect_request_002",
            input_artifact_ref="photo_artifact_001",
            platform=EffectPlatform.PC,
            parameters={"unknown_feature": 2},
        )
    with pytest.raises(ValueError, match="not range-verified"):
        adapter.prepare_request(
            request_ref="effect_request_003",
            input_artifact_ref="photo_artifact_001",
            platform=EffectPlatform.PC,
            parameters={"eyebrow": 2},
        )
    with pytest.raises(ValueError, match="outside its documented range"):
        adapter.prepare_request(
            request_ref="effect_request_004",
            input_artifact_ref="photo_artifact_001",
            platform=EffectPlatform.PC,
            parameters={"face_shape": -1},
        )


def test_prepare_request_rejects_path_like_artifact_refs_and_non_finite_values() -> None:
    adapter = TencentEffectAdapter()

    with pytest.raises(ValidationError):
        adapter.prepare_request(
            request_ref="effect_request_005",
            input_artifact_ref="/tmp/photo.jpg",
            platform=EffectPlatform.WEB,
            parameters={"lips_thickness": 2},
        )
    with pytest.raises(ValueError, match="finite"):
        adapter.prepare_request(
            request_ref="effect_request_006",
            input_artifact_ref="photo_artifact_001",
            platform=EffectPlatform.WEB,
            parameters={"lips_thickness": math.nan},
        )


def test_default_gate_is_fail_closed_and_reports_all_missing_prerequisites() -> None:
    decision = __import__(
        "portrait_consistency_agent.services.tencent_effect",
        fromlist=["evaluate_effect_gate"],
    ).evaluate_effect_gate(EffectGateInput(platform=EffectPlatform.MOBILE))

    assert decision.allowed is False
    assert "card_candidate_not_admitted" in decision.reason_codes
    assert "allow_live_not_explicit" in decision.reason_codes
    assert "license_not_active" not in decision.reason_codes
    assert "request_license_not_active" in decision.reason_codes
    assert "user_image_consent_missing" in decision.reason_codes
    assert "estimated_cost_unknown" in decision.reason_codes


def test_gate_still_blocks_candidate_even_if_request_evidence_is_filled() -> None:
    from portrait_consistency_agent.services.tencent_effect import evaluate_effect_gate

    decision = evaluate_effect_gate(
        EffectGateInput(
            allow_live=True,
            platform=EffectPlatform.WEB,
            license_status=EffectLicenseStatus.TEST_ACTIVE,
            provider_permission_granted=True,
            user_image_consent=True,
            outbound_data_approved=True,
            region_approved=True,
            adapter_ready=True,
            static_image_smoke_passed=True,
            estimated_cost_cny=0.1,
            plan_budget_cny=1.0,
        )
    )

    assert decision.allowed is False
    assert "card_candidate_not_admitted" in decision.reason_codes
    assert "platform_license_not_active" in decision.reason_codes


def test_dry_run_and_execute_have_a_trace_but_never_make_a_network_call() -> None:
    adapter = TencentEffectAdapter()
    request = adapter.prepare_request(
        request_ref="effect_request_007",
        input_artifact_ref="photo_artifact_001",
        platform=EffectPlatform.WEB,
        parameters={"lips_thickness": 8},
    )

    result = adapter.dry_run(request)
    assert result.status == "blocked"
    assert result.trace[-1]["status"] == "not_attempted"
    assert result.gate.allowed is False
    with pytest.raises(TencentEffectNotReadyError, match="candidate is not live-ready") as exc_info:
        adapter.execute(request)
    assert "network_call" not in str(exc_info.value)
