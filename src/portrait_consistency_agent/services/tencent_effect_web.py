"""Tencent Effect Web SDK adapter and Streamlit Component v2 bridge.

The Tencent Effect Web SDK is a browser JavaScript/WebGL SDK, not a Python
REST API.  This module keeps the boundary explicit:

* Python validates product strengths, mints a short-lived signature, and
  creates a redacted request/receipt contract.
* The browser component receives only the License key, APP ID, signature and
  an ephemeral image input.  It invokes ``ArSdk`` and keeps the output image
  in the browser.
* The component sends back metadata (hash, dimensions, duration and safe
  error code), never the input/output image or the License token.

The adapter is intentionally independent of the existing BeautifyPic
execution service.  A live Web smoke receipt is required before its Card can
be promoted to an executable RAG provider.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from portrait_consistency_agent.core.contracts import (
    ArtifactLifecycle,
    ErrorCategory,
    ErrorPhase,
    ProviderErrorDetail,
    ProviderRun,
    ProviderRunStatus,
    TencentEffectWebParams,
    utc_now,
)
from portrait_consistency_agent.core.settings import AppSettings

EFFECT_WEB_CARD_ID = "tencent-effect-web"
EFFECT_WEB_CARD_VERSION = "web_candidate_2026-09-01"
EFFECT_WEB_OPERATION = "WebARImage"
EFFECT_WEB_PROVIDER = "tencent_effect_web"
EFFECT_WEB_SDK_DEFAULT_URL = (
    "https://webar-static.tencent-cloud.com/ar-sdk/resources/latest/webar-sdk.umd.js"
)
MAX_DATA_URL_BYTES = 8 * 1024 * 1024


class TencentEffectWebCredentialsMissingError(RuntimeError):
    """Raised before a component payload is created when Web credentials are absent."""


class TencentEffectWebConfigurationError(RuntimeError):
    """Raised when a Web SDK request is outside the reviewed adapter boundary."""


class EffectWebRequest(BaseModel):
    """Redacted request facts sent to the component; never contains image data."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    request_ref: str = Field(
        min_length=3,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
    )
    input_artifact_ref: str = Field(
        min_length=3,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
    )
    input_artifact_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    parameters: TencentEffectWebParams
    input_source: Literal["sample_url", "data_url"]
    card_id: Literal["tencent-effect-web"] = EFFECT_WEB_CARD_ID
    card_version: Literal["web_candidate_2026-09-01"] = EFFECT_WEB_CARD_VERSION


class EffectWebBrowserReceipt(BaseModel):
    """Safe metadata returned by the browser SDK bridge.

    ``output_sha256`` is computed over the browser's output bytes.  The image
    itself stays in the browser and is not part of this contract.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    status: Literal["succeeded", "failed"]
    receipt_id: str = Field(min_length=3, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    request_ref: str = Field(
        min_length=3,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
    )
    sdk_version: str = Field(min_length=1, max_length=96)
    input_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    output_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    input_width: int | None = Field(default=None, ge=1, le=20000)
    input_height: int | None = Field(default=None, ge=1, le=20000)
    output_width: int | None = Field(default=None, ge=1, le=20000)
    output_height: int | None = Field(default=None, ge=1, le=20000)
    elapsed_ms: int = Field(ge=0, le=900000)
    error_code: str | None = Field(default=None, min_length=2, max_length=96)
    safe_error: str | None = Field(default=None, min_length=2, max_length=256)
    result_retention: Literal["browser_session_only"] = "browser_session_only"
    created_at: str = Field(min_length=20, max_length=40)

    @model_validator(mode="after")
    def validate_success_payload(self) -> EffectWebBrowserReceipt:
        if self.status == "succeeded":
            required = (
                self.output_sha256,
                self.input_width,
                self.input_height,
                self.output_width,
                self.output_height,
            )
            if any(value is None for value in required):
                raise ValueError("a successful Web receipt requires output hash and dimensions")
            if self.error_code is not None or self.safe_error is not None:
                raise ValueError("a successful Web receipt cannot carry an error")
        elif self.error_code is None or self.safe_error is None:
            raise ValueError("a failed Web receipt requires a safe error code and message")
        return self


@dataclass(frozen=True)
class EffectWebComponentPayload:
    """Ephemeral data passed to the browser component; never persist this object."""

    data: dict[str, object]


class EffectWebAdmissionInput(BaseModel):
    """Non-secret evidence required to promote the Web card.

    A License being visible in a console is not enough for admission.  This
    contract forces the project to keep platform, privacy, budget, Adapter and
    live-receipt evidence separate.  It is evaluated before changing the JSON
    Card; it never changes the Card by itself.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    card_review_status: Literal["candidate", "verified"]
    license_active: bool = False
    exact_domain_bound: bool = False
    provider_permission_granted: bool = False
    outbound_data_policy_approved: bool = False
    region_approved: bool = False
    estimated_cost_known: bool = False
    adapter_ready: bool = False
    static_image_smoke_succeeded: bool = False
    smoke_receipt_ref: str | None = Field(default=None, max_length=128)
    product_owner_approved: bool = False


class EffectWebAdmissionDecision(BaseModel):
    """Readable result of the deterministic Web provider admission checklist."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    allowed: bool
    reason_codes: list[str] = Field(min_length=1, max_length=24)
    next_action: Literal["keep_candidate", "promote_after_review"]


def evaluate_effect_web_admission(
    evidence: EffectWebAdmissionInput,
) -> EffectWebAdmissionDecision:
    """Return whether the card may be manually promoted after a live smoke.

    The function is deliberately side-effect free.  A successful browser
    receipt is evidence, not an automatic permission grant; a human must still
    review the non-secret License/privacy/budget facts and then update the Card
    in a separate change.
    """

    reasons: list[str] = []
    checks = (
        (evidence.card_review_status == "candidate", "card_not_candidate_for_promotion"),
        (evidence.license_active, "license_not_active"),
        (evidence.exact_domain_bound, "exact_domain_not_bound"),
        (evidence.provider_permission_granted, "provider_permission_missing"),
        (evidence.outbound_data_policy_approved, "outbound_data_not_approved"),
        (evidence.region_approved, "region_not_approved"),
        (evidence.estimated_cost_known, "estimated_cost_unknown"),
        (evidence.adapter_ready, "adapter_not_ready"),
        (evidence.static_image_smoke_succeeded, "static_image_smoke_not_passed"),
        (bool(evidence.smoke_receipt_ref), "smoke_receipt_missing"),
        (evidence.product_owner_approved, "product_owner_approval_missing"),
    )
    reasons.extend(code for passed, code in checks if not passed)
    return EffectWebAdmissionDecision(
        allowed=not reasons,
        reason_codes=reasons or ["all_web_admission_evidence_present"],
        next_action="promote_after_review" if not reasons else "keep_candidate",
    )


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _data_url_bytes(value: str) -> int:
    # This is a conservative upper bound for the browser payload.  It is not
    # used to decode or store the image on the Python side.
    return len(value.encode("utf-8"))


def _normalize_strength(value: object, *, feature: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{feature} must be numeric, not boolean")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{feature} must be numeric") from exc
    if parsed < 0 or parsed > 100:
        raise ValueError(f"{feature} must stay inside the product 0..100 scale")
    return parsed / 100.0


class TencentEffectWebAdapter:
    """Prepare a Web SDK request, sign it server-side, and validate its receipt."""

    _FEATURE_TO_WEB_KEY = {
        "face_lifting": "lift",
        "face_narrow": "shave",
        "eye_enlarging": "eye",
        "chin": "chin",
        "whitening": "whiten",
        "smoothing": "dermabrasion",
    }

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    @classmethod
    def build_parameters(cls, values: Mapping[str, object]) -> TencentEffectWebParams:
        """Map product-level 0..100 strengths to the Web SDK's 0..1 values."""

        unknown = sorted(set(values) - set(cls._FEATURE_TO_WEB_KEY))
        if unknown:
            raise TencentEffectWebConfigurationError(
                "Web SDK static-image adapter does not expose feature(s): " + ", ".join(unknown)
            )
        normalized = {
            cls._FEATURE_TO_WEB_KEY[feature]: _normalize_strength(raw, feature=feature)
            for feature, raw in values.items()
        }
        # Explicit zeroes keep vendor defaults from silently enabling skin or
        # colour changes.  All six documented Web fields remain in the request.
        return TencentEffectWebParams(
            lift=normalized.get("lift", 0.0),
            shave=normalized.get("shave", 0.0),
            eye=normalized.get("eye", 0.0),
            chin=normalized.get("chin", 0.0),
            whiten=normalized.get("whiten", 0.0),
            dermabrasion=normalized.get("dermabrasion", 0.0),
        )

    def prepare_request(
        self,
        *,
        request_ref: str,
        input_artifact_ref: str,
        input_artifact_sha256: str,
        parameters: Mapping[str, object],
        input_source: Literal["sample_url", "data_url"],
    ) -> EffectWebRequest:
        if (
            len(input_artifact_sha256) != 64
            or input_artifact_sha256.lower() != input_artifact_sha256
        ):
            raise ValueError("input_artifact_sha256 must be a lowercase SHA-256")
        return EffectWebRequest(
            request_ref=request_ref,
            input_artifact_ref=input_artifact_ref,
            input_artifact_sha256=input_artifact_sha256,
            parameters=self.build_parameters(parameters),
            input_source=input_source,
        )

    def build_component_payload(
        self,
        request: EffectWebRequest,
        *,
        input_value: str,
        now_epoch_seconds: int | None = None,
        reset_token: str | None = None,
    ) -> EffectWebComponentPayload:
        """Build an ephemeral browser payload with a five-minute signature.

        ``reset_token`` identifies the current prepared request generation.  It
        deliberately does not default to the signature timestamp: Streamlit
        reruns after a component event, and changing only the timestamp must
        not make the browser throw away the still-pending result.  The page
        therefore keeps the request reference stable for one input/parameter
        generation while this method refreshes the short-lived signature.
        """

        if request.input_source == "sample_url":
            if not input_value.startswith("https://"):
                raise TencentEffectWebConfigurationError("sample input must be an HTTPS URL")
        else:
            if not input_value.startswith("data:image/"):
                raise TencentEffectWebConfigurationError("user input must be an image data URL")
            if _data_url_bytes(input_value) > MAX_DATA_URL_BYTES:
                raise TencentEffectWebConfigurationError(
                    "image data URL exceeds the 8MB bridge limit"
                )
        if not self.settings.has_tencent_effect_credentials:
            raise TencentEffectWebCredentialsMissingError(
                "Tencent Effect Web credentials are absent. Configure TENCENT_EFFECT_APP_ID, "
                "TENCENT_EFFECT_LICENSE_KEY and TENCENT_EFFECT_LICENSE_TOKEN in local .env "
                "or Streamlit Cloud Secrets."
            )
        timestamp = int(now_epoch_seconds if now_epoch_seconds is not None else time.time())
        token = self.settings.tencent_effect_license_token.get_secret_value()  # type: ignore[union-attr]
        app_id = self.settings.tencent_effect_app_id.strip()  # type: ignore[union-attr]
        if app_id.startswith(("http://", "https://")):
            raise TencentEffectWebConfigurationError(
                "TENCENT_EFFECT_APP_ID must be the Tencent account APPID, not the bound domain URL"
            )
        signature = _sha256_hex(f"{timestamp}{token}{app_id}{timestamp}").upper()
        license_key = self.settings.tencent_effect_license_key.get_secret_value()  # type: ignore[union-attr]
        sdk_url = self.settings.tencent_effect_sdk_url.strip() or EFFECT_WEB_SDK_DEFAULT_URL
        if not sdk_url.startswith("https://"):
            raise TencentEffectWebConfigurationError("SDK URL must use HTTPS")
        return EffectWebComponentPayload(
            data={
                "request_ref": request.request_ref,
                "card_id": request.card_id,
                "card_version": request.card_version,
                "sdk_url": sdk_url,
                "license_key": license_key,
                "app_id": app_id,
                "signature": signature,
                "timestamp": timestamp,
                "input": input_value,
                "input_sha256": request.input_artifact_sha256,
                "beautify": request.parameters.model_dump(mode="json", exclude_none=False),
                "reset_token": reset_token or request.request_ref,
            }
        )

    @staticmethod
    def validate_browser_receipt(
        receipt: Mapping[str, object],
        *,
        request: EffectWebRequest,
    ) -> EffectWebBrowserReceipt:
        validated = EffectWebBrowserReceipt.model_validate(receipt)
        if validated.request_ref != request.request_ref:
            raise ValueError("browser receipt request_ref does not match the prepared request")
        if validated.input_sha256 not in {None, request.input_artifact_sha256}:
            raise ValueError("browser receipt input hash does not match the prepared request")
        return validated

    @staticmethod
    def build_provider_run(
        *,
        request: EffectWebRequest,
        receipt: EffectWebBrowserReceipt,
        session_id: str,
        plan_id: str,
        photo_id: str,
        confirmation_ref: str,
        confirmation_scope_hash: str,
        attempt_number: int = 1,
    ) -> ProviderRun:
        """Turn a browser receipt into the common immutable ProviderRun contract."""

        now = utc_now()
        request_hash = _sha256_hex(
            json.dumps(
                {
                    "request_ref": request.request_ref,
                    "input_sha256": request.input_artifact_sha256,
                    "parameters": request.parameters.model_dump(mode="json"),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        idempotency_key = (
            "idem_"
            + _sha256_hex(
                f"{session_id}|{plan_id}|{request.request_ref}|{confirmation_scope_hash}"
            )[:40]
        )
        if receipt.status == "succeeded":
            assert receipt.output_sha256 is not None
            artifact_ref = f"browser_result_{receipt.output_sha256[:16]}"
            return ProviderRun(
                run_id=f"run_{receipt.receipt_id}",
                trace_id=f"trace_{receipt.receipt_id}",
                plan_id=plan_id,
                plan_revision=1,
                session_id=session_id,
                photo_id=photo_id,
                attempt_number=attempt_number,
                provider=EFFECT_WEB_PROVIDER,
                operation=EFFECT_WEB_OPERATION,
                provider_api_version=receipt.sdk_version,
                region="web_domain_bound",
                endpoint=EFFECT_WEB_SDK_DEFAULT_URL,
                provider_card_id=request.card_id,
                provider_card_version=request.card_version,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                request_params=request.parameters,
                input_artifact_ref=request.input_artifact_ref,
                input_artifact_sha256=request.input_artifact_sha256,
                confirmation_ref=confirmation_ref,
                confirmation_scope_hash=confirmation_scope_hash,
                consent_policy_version="effect_web_test_v0",
                status=ProviderRunStatus.SUCCEEDED,
                # WebAR is a client SDK and does not expose a Tencent API
                # RequestId; this is an auditable local browser receipt ID.
                provider_request_id=receipt.receipt_id,
                result_artifact_ref=artifact_ref,
                result_artifact_sha256=receipt.output_sha256,
                artifact_lifecycle=ArtifactLifecycle(expires_at=now + timedelta(minutes=10)),
                queued_at=now,
                started_at=now,
                completed_at=now + timedelta(milliseconds=receipt.elapsed_ms),
                queue_latency_ms=0,
                network_latency_ms=receipt.elapsed_ms,
                total_latency_ms=receipt.elapsed_ms,
                estimated_cost_cny=0.0,
            )
        return ProviderRun(
            run_id=f"run_{receipt.receipt_id}",
            trace_id=f"trace_{receipt.receipt_id}",
            plan_id=plan_id,
            plan_revision=1,
            session_id=session_id,
            photo_id=photo_id,
            attempt_number=attempt_number,
            provider=EFFECT_WEB_PROVIDER,
            operation=EFFECT_WEB_OPERATION,
            provider_api_version=receipt.sdk_version,
            region="web_domain_bound",
            endpoint=EFFECT_WEB_SDK_DEFAULT_URL,
            provider_card_id=request.card_id,
            provider_card_version=request.card_version,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            request_params=request.parameters,
            input_artifact_ref=request.input_artifact_ref,
            input_artifact_sha256=request.input_artifact_sha256,
            confirmation_ref=confirmation_ref,
            confirmation_scope_hash=confirmation_scope_hash,
            consent_policy_version="effect_web_test_v0",
            status=ProviderRunStatus.FAILED,
            provider_request_id=receipt.receipt_id,
            queued_at=now,
            started_at=now,
            completed_at=now + timedelta(milliseconds=receipt.elapsed_ms),
            total_latency_ms=receipt.elapsed_ms,
            error=ProviderErrorDetail(
                phase=ErrorPhase.PROVIDER,
                category=ErrorCategory.UNKNOWN,
                provider_code=receipt.error_code or "WEB_SDK_ERROR",
                safe_message=receipt.safe_error or "Tencent Effect Web SDK failed.",
                retryable=False,
            ),
        )


def effect_web_request_fingerprint(
    *,
    input_artifact_ref: str,
    input_artifact_sha256: str,
    parameters: Mapping[str, object],
    input_source: Literal["sample_url", "data_url"],
) -> str:
    """Return the stable identity of one browser request generation.

    The fingerprint contains only non-sensitive references, a hash and the
    requested product strengths.  It is used by the Streamlit page to avoid
    generating a new ``request_ref`` during the rerun that delivers a browser
    receipt.  Raw image bytes, credentials and provider output never enter it.
    """

    canonical = {
        "card_id": EFFECT_WEB_CARD_ID,
        "card_version": EFFECT_WEB_CARD_VERSION,
        "input_artifact_ref": input_artifact_ref,
        "input_artifact_sha256": input_artifact_sha256,
        "input_source": input_source,
        "parameters": {key: parameters[key] for key in sorted(parameters)},
    }
    return _sha256_hex(json.dumps(canonical, sort_keys=True, separators=(",", ":")))


def get_or_create_effect_web_request(
    session_state: MutableMapping[str, object],
    adapter: TencentEffectWebAdapter,
    *,
    input_artifact_ref: str,
    input_artifact_sha256: str,
    parameters: Mapping[str, object],
    input_source: Literal["sample_url", "data_url"],
) -> tuple[EffectWebRequest, bool]:
    """Keep one request reference stable across Streamlit component reruns.

    Returns ``(request, changed)``.  ``changed`` is true only when the input
    or requested parameters start a new generation; the caller can then clear
    a prior saved receipt.  The persisted value is a redacted request model,
    never the component payload or an image.
    """

    fingerprint = effect_web_request_fingerprint(
        input_artifact_ref=input_artifact_ref,
        input_artifact_sha256=input_artifact_sha256,
        parameters=parameters,
        input_source=input_source,
    )
    existing = session_state.get("effect_web_prepared_request")
    if isinstance(existing, dict) and existing.get("fingerprint") == fingerprint:
        try:
            return EffectWebRequest.model_validate(existing["request"]), False
        except (KeyError, TypeError, ValueError):
            # A malformed/stale session object is replaced below.  This is a
            # local UI recovery path, not a reason to accept an unverified
            # browser receipt.
            pass

    request = adapter.prepare_request(
        request_ref=f"effect_web_{uuid4().hex[:16]}",
        input_artifact_ref=input_artifact_ref,
        input_artifact_sha256=input_artifact_sha256,
        parameters=parameters,
        input_source=input_source,
    )
    session_state["effect_web_prepared_request"] = {
        "fingerprint": fingerprint,
        "request": request.model_dump(mode="json"),
    }
    session_state.pop("effect_web_saved_receipt", None)
    return request, True


# Streamlit Custom Components v2 bridge.  The import is intentionally local so
# the adapter can be unit-tested outside a Streamlit script context.
def render_tencent_effect_web(
    payload: EffectWebComponentPayload,
    *,
    key: str,
) -> object:
    """Mount the browser bridge and return its trigger object to Streamlit."""

    import streamlit as st

    component = st.components.v2.component(
        "tencent_effect_web_bridge",
        html="""
        <div class="effect-shell">
          <div class="effect-status" data-role="status">等待开始</div>
          <canvas data-role="canvas" style="display:none"></canvas>
          <img data-role="result" alt="腾讯特效处理结果" style="max-width:100%;display:none" />
          <a data-role="download" download="tencent-effect-result.png" style="display:none">
            下载处理结果
          </a>
          <button data-role="run" type="button">开始腾讯特效处理</button>
        </div>
        """,
        js="""
        export default function(component) {
          const { data, parentElement, setTriggerValue, setStateValue } = component;
          const status = parentElement.querySelector('[data-role="status"]');
          const canvas = parentElement.querySelector('[data-role="canvas"]');
          const result = parentElement.querySelector('[data-role="result"]');
          const download = parentElement.querySelector('[data-role="download"]');
          const runButton = parentElement.querySelector('[data-role="run"]');
          if (!status || !canvas || !result || !download || !runButton || !data) return;

          const state = parentElement.__tencentEffectState || {
            running: false,
            resetToken: null,
            sdk: null,
            scriptPromise: null,
            disposed: false,
          };
          parentElement.__tencentEffectState = state;

          const show = (text, tone) => {
            status.textContent = text;
            status.dataset.tone = tone || "info";
          };
          const errorCodeOf = (error, fallback) => {
            const candidate = error && (error.code ?? error.Code ?? error.errorCode);
            return candidate === undefined || candidate === null || candidate === ""
              ? fallback
              : String(candidate).slice(0, 96);
          };
          const safeError = (error, code) => {
            const known = {
              "100": "SDK 鉴权缺少必要参数，请检查账号 APPID、License Key 和签名",
              "101": "SDK 签名已超时，请重新生成签名",
              "102": "SDK 未找到对应账号，请检查账号 APPID",
              "103": "SDK 签名错误，请检查服务端签名公式和 Token",
              "104": "当前域名与 License 绑定不匹配",
              "20001001": "SDK 鉴权失败，请检查 License 和签名",
              "10000005": "SDK 无法解析输入图片",
              "10001103": "SDK 特效强度参数不正确",
              "10001104": "SDK 尚未启用，无法设置特效",
              "10001105": "SDK 收到无效特效 ID",
            };
            return known[code] || "浏览器 SDK 返回运行时错误，请检查 SDK 初始化、"
              + "License、域名和输入图片";
          };
          const emitFailure = (code, error, elapsed) => {
            const normalizedCode = errorCodeOf(error, code);
            const receipt = {
              status: "failed",
              receipt_id: `web_receipt_${data.request_ref}`,
              request_ref: data.request_ref,
              sdk_version: (globalThis.AR &&
                (globalThis.AR.version || globalThis.AR.VERSION)) || "unknown",
              input_sha256: data.input_sha256 || null,
              output_sha256: null,
              input_width: null,
              input_height: null,
              output_width: null,
              output_height: null,
              elapsed_ms: Math.max(0, Math.round(elapsed || 0)),
              error_code: normalizedCode,
              safe_error: safeError(error, normalizedCode),
              result_retention: "browser_session_only",
              created_at: new Date().toISOString(),
            };
            show(`处理失败：${code}`, "error");
            state.running = false;
            // A failed attempt must remain retryable.  The previous bridge
            // left the button disabled after an SDK error, forcing a full
            // Streamlit rerun and hiding whether a retry actually happened.
            runButton.disabled = false;
            setStateValue("status", "failed");
            setTriggerValue("completed", receipt);
          };
          const loadSdk = () => {
            if (globalThis.AR && globalThis.AR.ArSdk) return Promise.resolve(globalThis.AR);
            if (state.scriptPromise) return state.scriptPromise;
            state.scriptPromise = new Promise((resolve, reject) => {
              const script = document.createElement("script");
              script.src = data.sdk_url;
              script.async = true;
              script.onload = () => globalThis.AR && globalThis.AR.ArSdk
                ? resolve(globalThis.AR)
                : reject(new Error("SDK_GLOBAL_MISSING"));
              script.onerror = () => reject(new Error("SDK_SCRIPT_LOAD_FAILED"));
              document.head.appendChild(script);
            });
            return state.scriptPromise;
          };
          const loadImage = (src) => new Promise((resolve, reject) => {
            const image = new Image();
            image.crossOrigin = "anonymous";
            image.onload = () => resolve(image);
            image.onerror = () => reject(new Error("INPUT_IMAGE_LOAD_FAILED"));
            image.src = src;
          });
          const hashDataUrl = async (value) => {
            const encoded = String(value).split(",", 2)[1] || "";
            const binary = atob(encoded);
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
            const digest = await crypto.subtle.digest("SHA-256", bytes);
            return Array.from(new Uint8Array(digest))
              .map((byte) => byte.toString(16).padStart(2, "0"))
              .join("");
          };
          const run = async () => {
            if (state.running || state.disposed) return;
            state.running = true;
            const started = performance.now();
            runButton.disabled = true;
            show("正在加载腾讯特效 SDK…", "working");
            try {
              const arGlobal = await loadSdk();
              show("SDK 已加载，正在初始化…", "working");
              const inputImage = await loadImage(data.input);
              canvas.width = inputImage.naturalWidth || inputImage.width;
              canvas.height = inputImage.naturalHeight || inputImage.height;
              const sdk = new arGlobal.ArSdk({
                module: { beautify: true },
                auth: {
                  licenseKey: data.license_key,
                  appId: data.app_id,
                  authFunc: async () => ({ signature: data.signature, timestamp: data.timestamp }),
                },
                input: inputImage,
                output: canvas,
                beautify: data.beautify,
              });
              state.sdk = sdk;
              sdk.on("error", (event) => {
                if (state.running) {
                emitFailure("SDK_RUNTIME_ERROR", event, performance.now() - started);
                }
              });
              sdk.on("ready", async () => {
                if (!state.running) return;
                try {
                  // The static-image Web API returns ImageData from
                  // `takePhoto()`. The media-stream getter would not produce
                  // a verifiable still-image result here.
                  await sdk.setBeautify(data.beautify);
                  const imageData = await sdk.takePhoto();
                  if (!imageData || !imageData.data || !imageData.width || !imageData.height) {
                    throw new Error("STATIC_IMAGE_OUTPUT_MISSING");
                  }
                  // The SDK owns the output canvas after initialization.  Resizing
                  // that same canvas here triggers Chromium's
                  // "Cannot resize canvas after call to transfer..." error in
                  // some WebGL builds.  Keep the SDK canvas immutable and copy
                  // the returned ImageData into a fresh, browser-owned canvas.
                  const resultCanvas = document.createElement("canvas");
                  resultCanvas.width = imageData.width;
                  resultCanvas.height = imageData.height;
                  const context = resultCanvas.getContext("2d");
                  if (!context) throw new Error("CANVAS_CONTEXT_MISSING");
                  context.putImageData(imageData, 0, 0);
                  const outputUrl = resultCanvas.toDataURL("image/png");
                  const outputHash = await hashDataUrl(outputUrl);
                  result.src = outputUrl;
                  result.style.display = "block";
                  download.href = outputUrl;
                  download.style.display = "inline-block";
                  const elapsed = Math.round(performance.now() - started);
                  const receipt = {
                    status: "succeeded",
                    receipt_id: `web_receipt_${data.request_ref}`,
                    request_ref: data.request_ref,
                    sdk_version: (globalThis.AR &&
                      (globalThis.AR.version || globalThis.AR.VERSION)) || "unknown",
                    input_sha256: data.input_sha256 || null,
                    output_sha256: outputHash,
                    input_width: inputImage.naturalWidth || inputImage.width,
                    input_height: inputImage.naturalHeight || inputImage.height,
                    output_width: resultCanvas.width,
                    output_height: resultCanvas.height,
                    elapsed_ms: elapsed,
                    error_code: null,
                    safe_error: null,
                    result_retention: "browser_session_only",
                    created_at: new Date().toISOString(),
                  };
                  show("处理完成：结果只保留在当前浏览器", "success");
                  state.running = false;
                  runButton.disabled = false;
                  setStateValue("status", "succeeded");
                  setTriggerValue("completed", receipt);
                } catch (error) {
                  emitFailure("OUTPUT_CAPTURE_FAILED", error, performance.now() - started);
                }
              });
            } catch (error) {
              emitFailure(
                String(error && error.message || "SDK_INIT_FAILED").slice(0, 96),
                error,
                performance.now() - started,
              );
            } finally {
              if (!state.running) runButton.disabled = false;
            }
          };
          if (state.resetToken !== data.reset_token) {
            state.resetToken = data.reset_token;
            state.running = false;
            state.disposed = false;
            result.style.display = "none";
            download.style.display = "none";
            show("准备就绪：点击后才会发送图片到浏览器 SDK", "info");
          }
          runButton.onclick = run;
          return () => {
            state.disposed = true;
            try { if (state.sdk && state.sdk.stop) state.sdk.stop(); } catch (_) {}
          };
        }
        """,
        isolate_styles=True,
    )
    return component(
        data=payload.data,
        key=key,
        on_completed_change=lambda: None,
        on_status_change=lambda: None,
    )
