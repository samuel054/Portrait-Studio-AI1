from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.settings import Settings


def test_settings_load_documented_environment_variables(monkeypatch, tmp_path: Path) -> None:
    workflow_db = tmp_path / "workflows.db"
    monkeypatch.setenv("PORTRAIT_ENVIRONMENT", "test")
    monkeypatch.setenv("PORTRAIT_LOG_LEVEL", "debug")
    monkeypatch.setenv("PORTRAIT_MAX_UPLOAD_MB", "24")
    monkeypatch.setenv("PORTRAIT_WORKFLOW_DB", str(workflow_db))
    monkeypatch.setenv("COMFYUI_BASE_URL", "http://localhost:8188/")
    monkeypatch.setenv("COMFYUI_TIMEOUT_SECONDS", "90")

    settings = Settings(_env_file=None)

    assert settings.environment == "test"
    assert settings.log_level == "DEBUG"
    assert settings.max_upload_mb == 24
    assert settings.max_upload_bytes == 24 * 1024 * 1024
    assert settings.portrait_workflow_db == workflow_db
    assert settings.comfyui_base_url == "http://localhost:8188"
    assert settings.comfyui_timeout_seconds == 90


def test_settings_reject_invalid_environment() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="unknown", _env_file=None)


def test_settings_reject_unbounded_upload_size() -> None:
    with pytest.raises(ValidationError):
        Settings(max_upload_mb=500, _env_file=None)
