import pytest
from pydantic import ValidationError

from portrait_consistency_agent.core.settings import AppSettings
from portrait_consistency_agent.services.provider_cards import load_tencent_compare_face_card
from portrait_consistency_agent.services.tencent_subject import (
    SubjectMatchCredentialsMissingError,
    SubjectMatchPolicy,
    TencentCompareFaceClient,
    TencentCompareFaceResponse,
    build_subject_match_decision,
)


def test_compare_face_provider_card_is_explicit_and_reviewed() -> None:
    card = load_tencent_compare_face_card()

    assert card["operation"] == "CompareFace"
    assert card["endpoint"] == "iai.tencentcloudapi.com"
    assert card["input"]["face_model_version"] == "3.0"
    assert card["routing_policy"]["user_visible_score"] is False


def test_compare_face_request_encodes_both_images_and_fixed_quality_settings() -> None:
    payload = TencentCompareFaceClient.build_base64_request(b"a", b"b")

    assert payload["ImageA"] == "YQ=="
    assert payload["ImageB"] == "Yg=="
    assert payload["FaceModelVersion"] == "3.0"
    assert payload["QualityControl"] == 0
    assert payload["NeedRotateDetection"] == 0


def test_compare_face_policy_has_match_uncertain_and_no_match_routes() -> None:
    policy = SubjectMatchPolicy.v0()

    assert policy.classify(70) == "match"
    assert policy.classify(50) == "uncertain"
    assert policy.classify(49.99) == "no_match"

    with pytest.raises(ValidationError, match="thresholds must be ordered"):
        SubjectMatchPolicy(uncertain_at_or_above=80, match_at_or_above=70)


def test_provider_score_stays_raw_and_never_becomes_probability() -> None:
    decision = build_subject_match_decision(
        TencentCompareFaceResponse(
            request_id="request_001",
            raw_score=73.2,
            face_model_version="3.0",
        ),
        receipt_ref="subject_receipt_001",
    )

    assert decision.status.value == "match"
    assert decision.evidence.raw_score == 73.2
    assert decision.evidence.calibrated is False
    assert decision.evidence.provider_request_id == "request_001"


def test_subject_client_refuses_network_without_credentials() -> None:
    client = TencentCompareFaceClient(AppSettings(_env_file=None))

    with pytest.raises(SubjectMatchCredentialsMissingError, match="credentials are absent"):
        client.compare_base64(b"a", b"b")
