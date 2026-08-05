from __future__ import annotations

import json
from pathlib import Path

from app.comfyui import ComfyUIConfig, ComfyUIGenerator
from app.generators import GenerationRequest
from app.planner import build_portrait_plan


class FakeHeaders:
    def get_content_type(self) -> str:
        return "image/png"


class FakeResponse:
    def __init__(self, body: bytes, content_type: bool = False) -> None:
        self.body = body
        self.headers = FakeHeaders() if content_type else FakeHeaders()

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def test_comfyui_payload_replaces_workflow_tokens(tmp_path: Path) -> None:
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(
        json.dumps(
            {
                "prompt": "{{PROMPT}}",
                "negative": "{{NEGATIVE_PROMPT}}",
                "image": "{{IMAGE_REFERENCE}}",
                "seed": "{{SEED}}",
                "count": "{{CANDIDATE_COUNT}}",
            }
        ),
        encoding="utf-8",
    )
    generator = ComfyUIGenerator(
        ComfyUIConfig(
            base_url="http://127.0.0.1:8188",
            workflow_path=str(workflow_path),
        )
    )
    request = GenerationRequest(
        plan=build_portrait_plan("soft_lifestyle_illustration"),
        image_reference="portrait.png",
        seed=42,
        candidate_count=2,
    )

    payload = generator.build_payload(request)
    workflow = payload["prompt"]

    assert workflow["image"] == "portrait.png"
    assert workflow["seed"] == 42
    assert workflow["count"] == 2
    assert "same person" in workflow["prompt"]
    assert "different face" in workflow["negative"]


def test_comfyui_missing_workflow_is_reported(tmp_path: Path) -> None:
    generator = ComfyUIGenerator(
        ComfyUIConfig(workflow_path=str(tmp_path / "missing.json"))
    )
    request = GenerationRequest(
        plan=build_portrait_plan("soft_lifestyle_illustration"),
        image_reference="portrait.png",
    )

    try:
        generator.build_payload(request)
    except RuntimeError as exc:
        assert "workflow not found" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")


def test_comfyui_upload_returns_reference(monkeypatch) -> None:
    response = {"name": "portrait.png", "subfolder": "portrait-studio-ai", "type": "input"}

    def fake_urlopen(request, **_kwargs):
        assert request.full_url.endswith("/upload/image")
        assert b"portrait.png" in request.data
        assert b"image/png" in request.data
        return FakeResponse(json.dumps(response).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    result = ComfyUIGenerator().upload_image(b"png-bytes", "portrait.png", "image/png")

    assert result.image_reference == "portrait-studio-ai/portrait.png"
    assert result.image_type == "input"


def test_comfyui_unknown_job_is_queued(monkeypatch) -> None:
    generator = ComfyUIGenerator()
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: FakeResponse(b"{}"),
    )

    result = generator.get_job("prompt-1")

    assert result.status == "queued"
    assert result.images == ()


def test_comfyui_completed_job_returns_base64_images(monkeypatch) -> None:
    history = {
        "prompt-1": {
            "status": {"completed": True, "status_str": "success"},
            "outputs": {
                "9": {
                    "images": [
                        {"filename": "portrait.png", "subfolder": "", "type": "output"}
                    ]
                }
            },
        }
    }

    def fake_urlopen(request, **_kwargs):
        url = request if isinstance(request, str) else request.full_url
        if "/history/" in url:
            return FakeResponse(json.dumps(history).encode("utf-8"))
        if "/view?" in url:
            return FakeResponse(b"png-bytes", content_type=True)
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    result = ComfyUIGenerator().get_job("prompt-1")

    assert result.status == "completed"
    assert len(result.images) == 1
    assert result.images[0].filename == "portrait.png"
    assert result.images[0].image_base64 == "cG5nLWJ5dGVz"
