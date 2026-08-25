"""Tencent BeautifyPic adapter with explicit parameters and no embedded secrets."""

from __future__ import annotations

import json
from dataclasses import dataclass

from portrait_consistency_agent.core.contracts import TencentBeautifyParams
from portrait_consistency_agent.core.settings import AppSettings


class TencentCredentialsMissingError(RuntimeError):
    """Raised before any network call when the local credential pair is absent."""


class TencentBeautifyApiError(RuntimeError):
    """A redacted external-provider failure suitable for a ProviderRun error field."""

    def __init__(self, error_code: str, message: str, request_id: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.request_id = request_id


@dataclass(frozen=True)
class TencentBeautifyResponse:
    request_id: str
    result_image_base64: str | None
    result_url: str | None


class TencentBeautifyClient:
    """The only V0 code path allowed to call Tencent BeautifyPic."""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    @staticmethod
    def build_base64_request(
        image_base64: str,
        params: TencentBeautifyParams,
    ) -> dict[str, object]:
        """Build a request that overrides all provider defaults explicitly."""

        if not image_base64.strip():
            raise ValueError("image_base64 must not be empty")
        return {
            "Image": image_base64,
            "FaceLifting": params.face_lifting,
            "EyeEnlarging": params.eye_enlarging,
            "Whitening": params.whitening,
            "Smoothing": params.smoothing,
            "RspImgType": "base64",
        }

    def beautify_base64(
        self,
        image_base64: str,
        params: TencentBeautifyParams,
    ) -> TencentBeautifyResponse:
        """Call Tencent only after local configuration is complete.

        The caller, rather than this client, is responsible for user confirmation,
        idempotency, result persistence, and ProviderRun trace construction.
        """

        if not self.settings.has_tencent_credentials:
            raise TencentCredentialsMissingError(
                "Tencent credentials are absent. Configure both values in local .env "
                "before a live call."
            )

        try:
            from tencentcloud.common import credential
            from tencentcloud.common.exception.tencent_cloud_sdk_exception import (
                TencentCloudSDKException,
            )
            from tencentcloud.common.profile.client_profile import ClientProfile
            from tencentcloud.common.profile.http_profile import HttpProfile
            from tencentcloud.fmu.v20191213 import fmu_client, models
        except ImportError as exc:  # pragma: no cover - dependency test covers normal path
            raise TencentBeautifyApiError(
                "SDK_MISSING",
                "Tencent FMU SDK is not installed in the current environment.",
            ) from exc

        try:
            credentials = credential.Credential(
                self.settings.tencent_secret_id.get_secret_value(),  # type: ignore[union-attr]
                self.settings.tencent_secret_key.get_secret_value(),  # type: ignore[union-attr]
            )
            http_profile = HttpProfile()
            http_profile.endpoint = self.settings.tencent_beautify_endpoint
            client_profile = ClientProfile()
            client_profile.httpProfile = http_profile
            client = fmu_client.FmuClient(
                credentials,
                self.settings.tencent_region,
                client_profile,
            )
            request = models.BeautifyPicRequest()
            request.from_json_string(json.dumps(self.build_base64_request(image_base64, params)))
            response = client.BeautifyPic(request)
        except TencentCloudSDKException as exc:
            error_code = getattr(exc, "get_error_code", lambda: "TENCENT_SDK_ERROR")()
            request_id = getattr(exc, "get_request_id", lambda: None)()
            raise TencentBeautifyApiError(
                error_code or "TENCENT_SDK_ERROR",
                "Tencent BeautifyPic request failed. "
                "See ProviderRun request_id/error_code for diagnosis.",
                request_id=request_id,
            ) from exc

        request_id = getattr(response, "RequestId", None)
        result_image_base64 = getattr(response, "ResultImage", None) or None
        result_url = getattr(response, "ResultUrl", None) or None
        if not request_id:
            raise TencentBeautifyApiError(
                "MISSING_REQUEST_ID",
                "Tencent returned no RequestId; the result cannot be audited.",
            )
        if not result_image_base64 and not result_url:
            raise TencentBeautifyApiError(
                "MISSING_RESULT",
                "Tencent returned no usable image result.",
                request_id=request_id,
            )
        return TencentBeautifyResponse(
            request_id=request_id,
            result_image_base64=result_image_base64,
            result_url=result_url,
        )
