"""Non-secret runtime configuration loaded only from the local environment."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Settings with a deliberate local-only default deployment boundary."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8501
    app_log_level: str = "INFO"
    database_path: Path = Path("storage/demo.sqlite3")
    knowledge_database_path: Path = Path("storage/knowledge.sqlite3")
    rag_vector_database_path: Path = Path("storage/knowledge_vectors.sqlite3")
    rag_model_cache_path: Path = Path("storage/model_cache")
    rag_embedding_model: str = "BAAI/bge-small-zh-v1.5"
    rag_embedding_revision: str = "7999e1d3359715c523056ef9478215996d62a620"
    rag_reranker_model: str = "BAAI/bge-reranker-base"
    rag_reranker_revision: str = "2cfc18c9415c912f9d8155881c133215df768a70"
    rag_allow_model_download: bool = False
    trace_path: Path = Path("logs/events.jsonl")
    tencent_secret_id: SecretStr | None = None
    tencent_secret_key: SecretStr | None = None
    tencent_region: str = "ap-guangzhou"
    tencent_beautify_endpoint: str = "fmu.tencentcloudapi.com"
    tencent_subject_endpoint: str = "iai.tencentcloudapi.com"
    tencent_moderation_endpoint: str = "ims.tencentcloudapi.com"
    tencent_moderation_biz_type: str = ""

    # Tencent Effect Web SDK (browser-side static-image adapter).  The
    # License key identifies the exact bound domain; the token is only used
    # server-side to mint a short-lived signature and must never be sent to
    # the browser.  APP ID is account metadata required by Tencent's signing
    # formula, not a user-facing value.
    tencent_effect_app_id: str | None = None
    tencent_effect_license_key: SecretStr | None = None
    tencent_effect_license_token: SecretStr | None = None
    tencent_effect_sdk_url: str = (
        "https://webar-static.tencent-cloud.com/ar-sdk/resources/latest/webar-sdk.umd.js"
    )

    # Checkpoint 7 selection. The text-only adapter reads these values only
    # when the user explicitly opts in to one remote parse; keeping them here
    # makes the provider choice explicit and avoids hard-coding a key or model
    # name in prompts/UI.
    llm_provider: str = "deepseek"
    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    llm_timeout_seconds: int = Field(default=20, ge=1, le=60)
    llm_max_output_tokens: int = Field(default=900, ge=128, le=4096)
    llm_data_policy_version: str = "llm-text-only-v0"

    @field_validator(
        "tencent_secret_id",
        "tencent_secret_key",
        "tencent_effect_license_key",
        "tencent_effect_license_token",
        "deepseek_api_key",
        mode="before",
    )
    @classmethod
    def blank_secret_is_absent(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, SecretStr):
            value = value.get_secret_value()
        value = str(value).strip()
        return value or None

    @model_validator(mode="after")
    def validate_credential_pair(self) -> AppSettings:
        has_id = self.tencent_secret_id is not None
        has_key = self.tencent_secret_key is not None
        if has_id != has_key:
            raise ValueError("TENCENT_SECRET_ID and TENCENT_SECRET_KEY must be configured together")
        return self

    @property
    def has_tencent_credentials(self) -> bool:
        if self.tencent_secret_id is None or self.tencent_secret_key is None:
            return False
        return bool(
            self.tencent_secret_id.get_secret_value().strip()
            and self.tencent_secret_key.get_secret_value().strip()
        )

    @property
    def has_deepseek_credentials(self) -> bool:
        return bool(
            self.deepseek_api_key is not None and self.deepseek_api_key.get_secret_value().strip()
        )

    @property
    def has_tencent_effect_credentials(self) -> bool:
        """Return whether the Web SDK can receive a server-side signature."""

        return bool(
            self.tencent_effect_app_id
            and self.tencent_effect_app_id.strip()
            and self.tencent_effect_license_key is not None
            and self.tencent_effect_license_key.get_secret_value().strip()
            and self.tencent_effect_license_token is not None
            and self.tencent_effect_license_token.get_secret_value().strip()
        )
