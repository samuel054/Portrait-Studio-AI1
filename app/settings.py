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
    )

    app_name: str = "Portrait Studio AI"
    app_version: str = "0.19.0"
    environment: str = "development"
    log_level: str = "INFO"

    max_upload_mb: int = Field(default=20, ge=1, le=100)
    max_image_pixels: int = Field(default=40_000_000, ge=1_000_000, le=200_000_000)

    comfyui_base_url: str = "http://127.0.0.1:8188"
    comfyui_workflow_path: Path = Path("workflows/portrait_api.json")
    comfyui_timeout_seconds: float = Field(default=15.0, ge=1.0, le=600.0)

    portrait_workflow_db: Path = Path("portrait_workflows.db")
    portrait_feedback_db: Path = Path("portrait_feedback.db")
    portrait_session_ttl_minutes: int = Field(default=60, ge=5, le=10_080)
    portrait_likeness_threshold: float = Field(default=0.35, ge=0.0, le=1.0)

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
