import pytest

from portrait_consistency_agent.core.contracts import ContentSafetyStatus
from portrait_consistency_agent.core.settings import AppSettings
from portrait_consistency_agent.services.provider_cards import load_tencent_image_moderation_card
from portrait_consistency_agent.services.tencent_safety import (
    ContentSafetyCredentialsMissingError,
    ContentSafetyDecision,
    TencentImageModerationClient,
    TencentImageModerationResponse,
    build_content_safety_decision,
)


def test_image_moderation_card_is_reviewed_and_has_explicit_review_policy() -> None:
    card = load_tencent_image_moderation_card()

    assert card["operation"] == "ImageModeration"
    assert card["endpoint"] == "ims.tencentcloudapi.com"
    assert card["v0_policy"]["review"] == "BLOCKED until a human review policy exists"
    assert card["card_version"] == "reviewed_2026-08-28"
    assert card["latest_live_verification"]["status"] == "passed"
    assert card["latest_live_verification"]["request_id"] == "211483d5-4ee0-41e8-b5d5-156f81557a69"


def test_image_moderation_request_uses_file_content_and_optional_biz_type() -> None:
    assert TencentImageModerationClient.build_base64_request(b"a") == {
        "FileContent": "YQ==",
        "Type": "IMAGE",
    }
    assert TencentImageModerationClient.build_base64_request(b"a", biz_type="portrait_beta") == {
        "FileContent": "YQ==",
        "Type": "IMAGE",
        "BizType": "portrait_beta",
    }


@pytest.mark.parametrize(
    ("suggestion", "expected", "reason"),
    [
        ("Pass", ContentSafetyStatus.PASSED, "content_safety_provider_passed"),
        ("Review", ContentSafetyStatus.BLOCKED, "content_safety_review_required"),
        ("Block", ContentSafetyStatus.BLOCKED, "content_safety_provider_blocked"),
    ],
)
def test_safety_suggestion_is_mapped_to_a_conservative_decision(
    suggestion: str,
    expected: ContentSafetyStatus,
    reason: str,
) -> None:
    decision = build_content_safety_decision(
        TencentImageModerationResponse(
            request_id="request_001",
            suggestion=suggestion,
            label="Normal",
            sub_label=None,
            score=0.0,
        ),
        receipt_ref="safety_receipt_001",
    )

    assert isinstance(decision, ContentSafetyDecision)
    assert decision.status == expected
    assert decision.reason_code == reason
    assert decision.evidence.provider_request_id == "request_001"


def test_moderation_client_refuses_network_without_credentials() -> None:
    client = TencentImageModerationClient(AppSettings(_env_file=None))

    with pytest.raises(ContentSafetyCredentialsMissingError, match="credentials are absent"):
        client.moderate_base64(b"a")
