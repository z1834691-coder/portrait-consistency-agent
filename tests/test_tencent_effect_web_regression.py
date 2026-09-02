from __future__ import annotations

import base64
import hashlib

from portrait_consistency_agent.core.settings import AppSettings
from portrait_consistency_agent.services.tencent_effect_web import (
    EffectWebBrowserReceipt,
    TencentEffectWebAdapter,
)
from portrait_consistency_agent.services.tencent_effect_web_regression import (
    EffectWebRegressionSample,
    run_effect_web_regression,
)

TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/"
    "aK8VYQAAAABJRU5ErkJggg=="
)


def _sample(
    adapter: TencentEffectWebAdapter,
    case_id: str,
    *,
    expected: str,
    receipt_update: dict[str, object] | None = None,
    result_update: dict[str, object] | None = None,
) -> EffectWebRegressionSample:
    input_hash = hashlib.sha256(f"input-{case_id}".encode()).hexdigest()
    request = adapter.prepare_request(
        request_ref=f"regression_{case_id}",
        input_artifact_ref=f"input_{case_id}",
        input_artifact_sha256=input_hash,
        parameters={"face_lifting": 10},
        input_source="data_url",
    )
    output_hash = hashlib.sha256(TINY_PNG).hexdigest()
    receipt = EffectWebBrowserReceipt(
        status="succeeded",
        receipt_id=f"receipt_{case_id}",
        request_ref=request.request_ref,
        sdk_version="fixture",
        input_sha256=input_hash,
        output_sha256=output_hash,
        input_width=1,
        input_height=1,
        output_width=1,
        output_height=1,
        elapsed_ms=10,
        created_at="2026-09-02T00:00:00+00:00",
    ).model_dump(mode="json")
    result = {
        "request_ref": request.request_ref,
        "input_sha256": input_hash,
        "output_sha256": output_hash,
        "output_data_url": "data:image/png;base64," + base64.b64encode(TINY_PNG).decode(),
        "output_width": 1,
        "output_height": 1,
        "result_retention": "python_memory_only",
        "created_at": "2026-09-02T00:00:00+00:00",
    }
    receipt.update(receipt_update or {})
    result.update(result_update or {})
    return EffectWebRegressionSample(
        case_id=case_id,
        category="fixture",
        request=request,
        receipt=receipt,
        result=result,
        expected=expected,  # type: ignore[arg-type]
    )


def test_regression_accepts_success_and_failure_and_rejects_tampering() -> None:
    adapter = TencentEffectWebAdapter(AppSettings(_env_file=None))
    samples = (
        _sample(adapter, "ok", expected="accepted_success"),
        _sample(
            adapter,
            "provider_error",
            expected="accepted_failure",
            receipt_update={
                "status": "failed",
                "output_sha256": None,
                "input_width": None,
                "input_height": None,
                "output_width": None,
                "output_height": None,
                "error_code": "SDK_ERROR",
                "safe_error": "fixture failure",
            },
        ),
        _sample(
            adapter,
            "tampered",
            expected="rejected",
            result_update={"output_sha256": "0" * 64},
        ),
    )

    report = run_effect_web_regression(adapter, samples)

    assert report.total == 3
    assert report.passed == 3
    assert report.hard_safety_passed is True
    assert report.items[2].anomaly_code == "output_hash_mismatch"
    assert all(item.projection()["result_payload_persisted"] is False for item in report.items)


def test_regression_continues_after_bad_sample_and_reports_isolation() -> None:
    adapter = TencentEffectWebAdapter(AppSettings(_env_file=None))
    samples = (
        _sample(
            adapter,
            "bad_first",
            expected="rejected",
            receipt_update={"request_ref": "wrong_request"},
        ),
        _sample(adapter, "good_after_bad", expected="accepted_success"),
    )

    report = run_effect_web_regression(adapter, samples)

    assert report.failed == 0
    assert report.batch_failure_isolation_passed is True
    assert [item.observed for item in report.items] == ["rejected", "accepted_success"]


def test_regression_classifies_input_hash_and_size_anomalies() -> None:
    adapter = TencentEffectWebAdapter(AppSettings(_env_file=None))
    input_hash = hashlib.sha256(b"input-size").hexdigest()
    request = adapter.prepare_request(
        request_ref="regression_size",
        input_artifact_ref="input_size",
        input_artifact_sha256=input_hash,
        parameters={"face_lifting": 10},
        input_source="data_url",
    )
    output_hash = hashlib.sha256(TINY_PNG).hexdigest()
    receipt = EffectWebBrowserReceipt(
        status="succeeded",
        receipt_id="receipt_size",
        request_ref=request.request_ref,
        sdk_version="fixture",
        input_sha256=input_hash,
        output_sha256=output_hash,
        input_width=1,
        input_height=1,
        output_width=1,
        output_height=1,
        elapsed_ms=10,
        created_at="2026-09-02T00:00:00+00:00",
    ).model_dump(mode="json")
    valid_result = {
        "request_ref": request.request_ref,
        "input_sha256": input_hash,
        "output_sha256": output_hash,
        "output_data_url": "data:image/png;base64," + base64.b64encode(TINY_PNG).decode(),
        "output_width": 1,
        "output_height": 1,
        "result_retention": "python_memory_only",
        "created_at": "2026-09-02T00:00:00+00:00",
    }
    samples = (
        EffectWebRegressionSample(
            case_id="input_hash",
            category="input_hash_mismatch",
            request=request,
            receipt=receipt,
            result={**valid_result, "input_sha256": "f" * 64},
            expected="rejected",
        ),
        EffectWebRegressionSample(
            case_id="size_limit",
            category="result_size_exceeded",
            request=request,
            receipt=receipt,
            result={
                **valid_result,
                "output_data_url": "data:image/png;base64," + ("A" * (8 * 1024 * 1024)),
            },
            expected="rejected",
        ),
    )

    report = run_effect_web_regression(adapter, samples)

    assert report.failed == 0
    assert [item.anomaly_code for item in report.items] == [
        "input_hash_mismatch",
        "result_size_exceeded",
    ]
    assert report.hard_safety_passed is True
