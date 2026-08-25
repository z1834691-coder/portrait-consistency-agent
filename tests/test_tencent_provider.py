import pytest
from pydantic import ValidationError

from portrait_consistency_agent.core.contracts import TencentBeautifyParams
from portrait_consistency_agent.core.settings import AppSettings
from portrait_consistency_agent.services.provider_cards import load_tencent_beautify_card
from portrait_consistency_agent.services.tencent_beautify import (
    TencentBeautifyClient,
    TencentCredentialsMissingError,
)


def test_provider_card_contains_reviewed_v0_constraints() -> None:
    card = load_tencent_beautify_card()

    assert card["operation"] == "BeautifyPic"
    assert card["api_version"] == "2019-12-13"
    assert card["parameters"]["FaceLifting"]["default"] == 70
    assert card["parameters"]["EyeEnlarging"]["default"] == 70
    assert card["review_status"] == "verified"


def test_settings_reject_partial_credential_pair() -> None:
    with pytest.raises(ValidationError, match="must be configured together"):
        AppSettings(
            _env_file=None,
            tencent_secret_id="example-id",
            tencent_secret_key=None,
        )


def test_payload_explicitly_overrides_all_tencent_defaults() -> None:
    payload = TencentBeautifyClient.build_base64_request(
        "aGVsbG8=",
        TencentBeautifyParams(face_lifting=8, eye_enlarging=15, whitening=0, smoothing=0),
    )

    assert payload == {
        "Image": "aGVsbG8=",
        "FaceLifting": 8,
        "EyeEnlarging": 15,
        "Whitening": 0,
        "Smoothing": 0,
        "RspImgType": "base64",
    }


def test_client_refuses_to_call_without_credentials() -> None:
    client = TencentBeautifyClient(AppSettings(_env_file=None))

    with pytest.raises(TencentCredentialsMissingError, match="credentials are absent"):
        client.beautify_base64("aGVsbG8=", TencentBeautifyParams())
