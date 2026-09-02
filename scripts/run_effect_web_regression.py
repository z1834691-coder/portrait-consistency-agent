"""Run the offline multi-sample/negative regression for the Web B handoff.

This script uses synthetic bytes and contract fixtures only.  It does not
load a browser, read a user photo, call Tencent, or read any credential.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

# ruff: noqa: E402 - direct script execution bootstraps the src layout above.
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
    *,
    case_id: str,
    category: str,
    expected: str,
    receipt_override: dict[str, object] | None = None,
    result_override: dict[str, object] | None = None,
) -> EffectWebRegressionSample:
    input_bytes = f"synthetic-input-{case_id}".encode()
    input_hash = hashlib.sha256(input_bytes).hexdigest()
    request = adapter.prepare_request(
        request_ref=f"effect_web_reg_{case_id}",
        input_artifact_ref=f"regression_input_{case_id}",
        input_artifact_sha256=input_hash,
        parameters={"face_lifting": 10, "eye_enlarging": 10},
        input_source="data_url",
    )
    output_hash = hashlib.sha256(TINY_PNG).hexdigest()
    receipt = EffectWebBrowserReceipt(
        status="succeeded",
        receipt_id=f"web_reg_receipt_{case_id}",
        request_ref=request.request_ref,
        sdk_version="fixture-web-sdk",
        input_sha256=input_hash,
        output_sha256=output_hash,
        input_width=1,
        input_height=1,
        output_width=1,
        output_height=1,
        elapsed_ms=12,
        created_at="2026-09-02T00:00:00+00:00",
    ).model_dump(mode="json")
    result = {
        "request_ref": request.request_ref,
        "input_sha256": input_hash,
        "output_sha256": output_hash,
        "output_data_url": "data:image/png;base64," + base64.b64encode(TINY_PNG).decode("ascii"),
        "output_width": 1,
        "output_height": 1,
        "result_retention": "python_memory_only",
        "created_at": "2026-09-02T00:00:00+00:00",
    }
    if receipt_override:
        receipt.update(receipt_override)
    if result_override:
        result.update(result_override)
    return EffectWebRegressionSample(
        case_id=case_id,
        category=category,
        request=request,
        receipt=receipt,
        result=result,
        expected=expected,  # type: ignore[arg-type]
    )


def _samples(adapter: TencentEffectWebAdapter) -> tuple[EffectWebRegressionSample, ...]:
    return (
        _sample(adapter, case_id="S01", category="success_png", expected="accepted_success"),
        _sample(
            adapter,
            case_id="S03",
            category="request_ref_mismatch",
            expected="rejected",
            receipt_override={"request_ref": "effect_web_other_request"},
        ),
        # Keep a valid sample immediately after a rejected one.  This makes
        # the batch-isolation assertion exercise the promised behavior rather
        # than merely counting that all cases were evaluated.
        _sample(
            adapter,
            case_id="S02",
            category="provider_failure_receipt",
            expected="accepted_failure",
            receipt_override={
                "status": "failed",
                "output_sha256": None,
                "input_width": None,
                "input_height": None,
                "output_width": None,
                "output_height": None,
                "error_code": "SDK_RUNTIME_ERROR",
                "safe_error": "fixture failure",
            },
            result_override=None,
        ),
        _sample(
            adapter,
            case_id="S04",
            category="output_hash_mismatch",
            expected="rejected",
            result_override={"output_sha256": "f" * 64},
        ),
        _sample(
            adapter,
            case_id="S05",
            category="unsupported_mime",
            expected="rejected",
            result_override={
                "output_data_url": "data:image/svg+xml;base64,"
                + base64.b64encode(TINY_PNG).decode("ascii")
            },
        ),
        _sample(
            adapter,
            case_id="S06",
            category="dimensions_mismatch",
            expected="rejected",
            result_override={"output_width": 2},
        ),
        _sample(
            adapter,
            case_id="S07",
            category="input_hash_mismatch",
            expected="rejected",
            result_override={"input_sha256": "f" * 64},
        ),
        _sample(
            adapter,
            case_id="S08",
            category="result_size_exceeded",
            expected="rejected",
            result_override={
                "output_data_url": "data:image/png;base64," + ("A" * (8 * 1024 * 1024)),
            },
        ),
    )


def _html_report(payload: dict[str, object]) -> str:
    rows = []
    for item in payload["items"]:  # type: ignore[index]
        row = item  # type: ignore[assignment]
        rows.append(
            "<tr>"
            + "".join(
                f"<td>{html.escape(str(row.get(key, '')))}</td>"
                for key in ("case_id", "category", "expected", "observed", "passed", "anomaly_code")
            )
            + "</tr>"
        )
    summary = (
        "<pre>"
        + html.escape(
            json.dumps(
                {key: payload[key] for key in payload if key != "items"},
                ensure_ascii=False,
                indent=2,
            )
        )
        + "</pre>"
    )
    return (
        "<!doctype html><html lang='zh-CN'><meta charset='utf-8'>"
        "<title>Tencent Effect Web E2 Regression</title>"
        "<style>body{font-family:system-ui;max-width:1100px;margin:32px auto}"
        "table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:8px}"
        ".ok{color:#087f23}.bad{color:#b42318}</style><body>"
        "<h1>Tencent Effect Web｜E2 多样本/异常/批量隔离回归</h1>"
        + summary
        + "<table><thead><tr><th>case</th><th>category</th><th>expected</th>"
        "<th>observed</th><th>passed</th><th>anomaly</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></body></html>"
    )


def main() -> int:
    adapter = TencentEffectWebAdapter(AppSettings(_env_file=None))
    report = run_effect_web_regression(adapter, _samples(adapter))
    payload = report.projection()
    output_json = PROJECT_ROOT / "reports/tencent_effect_web_regression_v1.json"
    output_html = PROJECT_ROOT / "reports/tencent_effect_web_regression_v1.html"
    output_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    output_html.write_text(_html_report(payload), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report.hard_safety_passed and report.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
