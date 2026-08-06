from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    app_name: str = Field(default="Portrait Studio AI", validation_alias="PORTRAIT_APP_NAME")
    app_version: str = Field(default="0.19.0", validation_alias="PORTRAIT_APP_VERSION")
    environment: str = Field(default="development", validation_alias="PORTRAIT_ENVIRONMENT")
    log_level: str = Field(default="INFO", validation_alias="PORTRAIT_LOG_LEVEL")

    max_upload_mb: int = Field(
        default=20,
        ge=1,
        le=100,
        validation_alias="PORTRAIT_MAX_UPLOAD_MB",
    )
    max_image_pixels: int = Field(
        default=40_000_000,
        ge=1_000_000,
        le=200_000_000,
        validation_alias="PORTRAIT_MAX_IMAGE_PIXELS",
    )

    comfyui_base_url: str = Field(
        default="http://127.0.0.1:8188",
        validation_alias="COMFYUI_BASE_URL",
    )
    comfyui_workflow_path: Path = Field(
        default=Path("workflows/portrait_api.json"),
        validation_alias="COMFYUI_WORKFLOW_PATH",
    )
    comfyui_timeout_seconds: float = Field(
        default=15.0,
        ge=1.0,
        le=600.0,
        validation_alias="COMFYUI_TIMEOUT_SECONDS",
    )

    portrait_workflow_db: Path = Field(
        default=Path("portrait_workflows.db"),
        validation_alias="PORTRAIT_WORKFLOW_DB",
    )
    portrait_feedback_db: Path = Field(
        default=Path("portrait_feedback.db"),
        validation_alias="PORTRAIT_FEEDBACK_DB",
    )
    portrait_session_ttl_minutes: int = Field(
        default=60,
        ge=5,
        le=10_080,
        validation_alias="PORTRAIT_SESSION_TTL_MINUTES",
    )
    portrait_likeness_threshold: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        validation_alias="PORTRAIT_LIKENESS_THRESHOLD",
    )

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"development", "test", "staging", "production"}
        if normalized not in allowed:
            raise ValueError(f"environment must be one of: {', '.join(sorted(allowed))}")
        return normalized

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in allowed:
            raise ValueError(f"log_level must be one of: {', '.join(sorted(allowed))}")
        return normalized

    @field_validator("comfyui_base_url")
    @classmethod
    def normalize_comfyui_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("comfyui_base_url must use http:// or https://")
        return normalized

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
