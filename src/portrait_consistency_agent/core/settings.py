"""Non-secret runtime configuration loaded only from the local environment."""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr, field_validator, model_validator
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
    trace_path: Path = Path("logs/events.jsonl")
    photo_ttl_hours: int = 24

    tencent_secret_id: SecretStr | None = None
    tencent_secret_key: SecretStr | None = None
    tencent_region: str = "ap-guangzhou"
    tencent_beautify_endpoint: str = "fmu.tencentcloudapi.com"
    tencent_subject_endpoint: str = "iai.tencentcloudapi.com"
    tencent_moderation_endpoint: str = "ims.tencentcloudapi.com"
    tencent_moderation_biz_type: str = ""

    @field_validator("tencent_secret_id", "tencent_secret_key", mode="before")
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
