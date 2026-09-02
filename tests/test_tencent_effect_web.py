from __future__ import annotations

import base64
import hashlib
import inspect
import re

import pytest
from pydantic import ValidationError

from portrait_consistency_agent.core.contracts import ProviderRunStatus, utc_now
from portrait_consistency_agent.core.settings import AppSettings
from portrait_consistency_agent.services.tencent_effect_web import (
    EffectWebAdmissionInput,
    EffectWebBrowserReceipt,
    TencentEffectWebAdapter,
    TencentEffectWebConfigurationError,
    TencentEffectWebCredentialsMissingError,
    effect_web_request_fingerprint,
    evaluate_effect_web_admission,
    get_or_create_effect_web_request,
    render_tencent_effect_web,
)


def _settings_with_effect_credentials() -> AppSettings:
    return AppSettings(
        _env_file=None,
        tencent_effect_app_id="app_123456",
        tencent_effect_license_key="license_public_key",
        tencent_effect_license_token="token_only_server_side_123",
    )


def _request(adapter: TencentEffectWebAdapter):
    input_bytes = b"approved-demo-image-bytes"
    input_hash = hashlib.sha256(input_bytes).hexdigest()
    return (
        adapter.prepare_request(
            request_ref="effect_web_req_001",
            input_artifact_ref="effect_web_input_001",
            input_artifact_sha256=input_hash,
            parameters={"face_lifting": 10, "eye_enlarging": 15},
            input_source="data_url",
        ),
        input_bytes,
        input_hash,
    )


def test_product_strengths_map_to_web_scale_and_zero_defaults_are_explicit() -> None:
    params = TencentEffectWebAdapter.build_parameters(
        {"face_lifting": 100, "eye_enlarging": 15, "face_narrow": 5}
    )

    assert params.lift == 1.0
    assert params.eye == 0.15
    assert params.shave == 0.05
    assert params.chin == 0.0
    assert params.whiten == 0.0
    assert params.dermabrasion == 0.0


def test_unknown_or_out_of_range_product_parameter_is_rejected() -> None:
    with pytest.raises(TencentEffectWebConfigurationError, match="does not expose"):
        TencentEffectWebAdapter.build_parameters({"lips_thickness": 8})
    with pytest.raises(ValueError, match="0..100"):
        TencentEffectWebAdapter.build_parameters({"face_lifting": 101})
    with pytest.raises(ValueError, match="not boolean"):
        TencentEffectWebAdapter.build_parameters({"face_lifting": True})


def test_prepare_request_rejects_bad_hash_and_data_url_policy() -> None:
    adapter = TencentEffectWebAdapter(_settings_with_effect_credentials())
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        adapter.prepare_request(
            request_ref="effect_web_req_002",
            input_artifact_ref="effect_web_input_001",
            input_artifact_sha256="A" * 64,
            parameters={"face_lifting": 1},
            input_source="data_url",
        )

    request, _, input_hash = _request(adapter)
    oversized = "data:image/png;base64," + ("A" * (8 * 1024 * 1024))
    with pytest.raises(TencentEffectWebConfigurationError, match="8MB"):
        adapter.build_component_payload(request, input_value=oversized)

    with pytest.raises(TencentEffectWebConfigurationError, match="data URL"):
        adapter.build_component_payload(request, input_value="https://example.com/image.jpg")
    assert request.input_artifact_sha256 == input_hash


def test_payload_mints_signature_without_exposing_license_token() -> None:
    adapter = TencentEffectWebAdapter(_settings_with_effect_credentials())
    request, input_bytes, input_hash = _request(adapter)
    encoded = base64.b64encode(input_bytes).decode("ascii")
    data_url = "data:image/png;base64," + encoded
    payload = adapter.build_component_payload(
        request,
        input_value=data_url,
        now_epoch_seconds=1_700_000_000,
    ).data

    assert payload["input"] == data_url
    assert payload["input_sha256"] == input_hash
    assert payload["app_id"] == "app_123456"
    assert payload["license_key"] == "license_public_key"
    assert "license_token" not in payload
    assert "token_only_server_side_123" not in payload.values()
    assert re.fullmatch(r"[0-9A-F]{64}", str(payload["signature"]))
    assert payload["beautify"] == {
        "contract_version": "0.4",
        "lift": 0.1,
        "shave": 0.0,
        "eye": 0.15,
        "chin": 0.0,
        "whiten": 0.0,
        "dermabrasion": 0.0,
    }


def test_effect_app_id_rejects_bound_domain_url() -> None:
    adapter = TencentEffectWebAdapter(
        AppSettings(
            _env_file=None,
            tencent_effect_app_id="https://portrait-consistency-agent.streamlit.app",
            tencent_effect_license_key="license_public_key",
            tencent_effect_license_token="token_only_server_side_123",
        )
    )
    request, _, _ = _request(adapter)
    with pytest.raises(TencentEffectWebConfigurationError, match="account APPID"):
        adapter.build_component_payload(request, input_value="data:image/png;base64,QUJD")


def test_request_generation_is_stable_across_streamlit_reruns() -> None:
    adapter = TencentEffectWebAdapter(_settings_with_effect_credentials())
    state: dict[str, object] = {}
    request_a, changed_a = get_or_create_effect_web_request(
        state,
        adapter,
        input_artifact_ref="effect_web_input_001",
        input_artifact_sha256="a" * 64,
        parameters={"face_lifting": 10, "eye_enlarging": 15},
        input_source="data_url",
    )
    state["effect_web_saved_receipt"] = "run_old"
    request_b, changed_b = get_or_create_effect_web_request(
        state,
        adapter,
        input_artifact_ref="effect_web_input_001",
        input_artifact_sha256="a" * 64,
        parameters={"eye_enlarging": 15, "face_lifting": 10},
        input_source="data_url",
    )

    assert changed_a is True
    assert changed_b is False
    assert request_b.request_ref == request_a.request_ref
    assert "effect_web_saved_receipt" in state
    assert state["effect_web_prepared_request"]["request"]["request_ref"] == request_a.request_ref  # type: ignore[index]

    request_c, changed_c = get_or_create_effect_web_request(
        state,
        adapter,
        input_artifact_ref="effect_web_input_001",
        input_artifact_sha256="a" * 64,
        parameters={"face_lifting": 11, "eye_enlarging": 15},
        input_source="data_url",
    )
    assert changed_c is True
    assert request_c.request_ref != request_a.request_ref
    assert "effect_web_saved_receipt" not in state


def test_signature_refresh_does_not_reset_same_browser_generation() -> None:
    adapter = TencentEffectWebAdapter(_settings_with_effect_credentials())
    request, _, _ = _request(adapter)
    encoded = base64.b64encode(b"approved-demo-image-bytes").decode("ascii")
    data_url = "data:image/png;base64," + encoded
    first = adapter.build_component_payload(
        request,
        input_value=data_url,
        now_epoch_seconds=1_700_000_000,
    ).data
    refreshed = adapter.build_component_payload(
        request,
        input_value=data_url,
        now_epoch_seconds=1_700_000_120,
    ).data

    assert first["reset_token"] == refreshed["reset_token"] == request.request_ref
    assert first["signature"] != refreshed["signature"]
    assert effect_web_request_fingerprint(
        input_artifact_ref=request.input_artifact_ref,
        input_artifact_sha256=request.input_artifact_sha256,
        parameters={"eye_enlarging": 15, "face_lifting": 10},
        input_source=request.input_source,
    ) == effect_web_request_fingerprint(
        input_artifact_ref=request.input_artifact_ref,
        input_artifact_sha256=request.input_artifact_sha256,
        parameters={"face_lifting": 10, "eye_enlarging": 15},
        input_source=request.input_source,
    )


def test_missing_effect_credentials_blocks_before_component_payload() -> None:
    adapter = TencentEffectWebAdapter(AppSettings(_env_file=None))
    request, _, _ = _request(adapter)
    with pytest.raises(TencentEffectWebCredentialsMissingError, match="TENCENT_EFFECT_APP_ID"):
        adapter.build_component_payload(
            request,
            input_value="data:image/png;base64,QUJD",
        )


def test_receipt_contract_requires_success_output_or_failure_error() -> None:
    now = utc_now().isoformat()
    with pytest.raises(ValidationError, match="successful Web receipt"):
        EffectWebBrowserReceipt(
            status="succeeded",
            receipt_id="web_receipt_bad",
            request_ref="effect_web_req_001",
            sdk_version="web-sdk",
            elapsed_ms=20,
            created_at=now,
        )

    failed = EffectWebBrowserReceipt(
        status="failed",
        receipt_id="web_receipt_failed",
        request_ref="effect_web_req_001",
        sdk_version="web-sdk",
        elapsed_ms=20,
        error_code="SDK_INIT_FAILED",
        safe_error="SDK could not initialise",
        created_at=now,
    )
    assert failed.status == "failed"


def test_receipt_hash_scope_and_provider_run_are_validated() -> None:
    adapter = TencentEffectWebAdapter(_settings_with_effect_credentials())
    request, _, input_hash = _request(adapter)
    output_hash = hashlib.sha256(b"web-output").hexdigest()
    receipt = EffectWebBrowserReceipt(
        status="succeeded",
        receipt_id="web_receipt_001",
        request_ref=request.request_ref,
        sdk_version="web-sdk-test",
        input_sha256=input_hash,
        output_sha256=output_hash,
        input_width=640,
        input_height=480,
        output_width=640,
        output_height=480,
        elapsed_ms=321,
        created_at=utc_now().isoformat(),
    )
    validated = adapter.validate_browser_receipt(receipt.model_dump(mode="json"), request=request)
    run = adapter.build_provider_run(
        request=request,
        receipt=validated,
        session_id="session_effect_001",
        plan_id="plan_effect_001",
        photo_id="photo_effect_001",
        confirmation_ref="confirm_effect_001",
        confirmation_scope_hash="a" * 64,
    )

    assert run.status == ProviderRunStatus.SUCCEEDED
    assert run.provider == "tencent_effect_web"
    assert run.operation == "WebARImage"
    assert run.provider_request_id == receipt.receipt_id
    assert run.result_artifact_sha256 == output_hash
    assert run.request_params.lift == 0.1

    with pytest.raises(ValueError, match="does not match"):
        adapter.validate_browser_receipt(
            receipt.model_copy(update={"request_ref": "other_request"}).model_dump(mode="json"),
            request=request,
        )


def test_web_admission_is_fail_closed_until_all_non_secret_evidence_is_present() -> None:
    blocked = evaluate_effect_web_admission(EffectWebAdmissionInput(card_review_status="candidate"))
    assert blocked.allowed is False
    assert blocked.next_action == "keep_candidate"
    assert "license_not_active" in blocked.reason_codes
    assert "static_image_smoke_not_passed" in blocked.reason_codes

    ready = evaluate_effect_web_admission(
        EffectWebAdmissionInput(
            card_review_status="candidate",
            license_active=True,
            exact_domain_bound=True,
            provider_permission_granted=True,
            outbound_data_policy_approved=True,
            region_approved=True,
            estimated_cost_known=True,
            adapter_ready=True,
            static_image_smoke_succeeded=True,
            smoke_receipt_ref="receipt_web_001",
            product_owner_approved=True,
        )
    )
    assert ready.allowed is True
    assert ready.reason_codes == ["all_web_admission_evidence_present"]
    assert ready.next_action == "promote_after_review"


def test_browser_bridge_uses_static_image_capture_api() -> None:
    source = inspect.getsource(render_tencent_effect_web)
    assert "takePhoto" in source
    assert "getOutput" not in source
    assert "errorCodeOf" in source
    assert "SDK 鉴权缺少必要参数" in source
    assert "runButton.disabled = false" in source
