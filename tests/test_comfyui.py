from __future__ import annotations

import json
from pathlib import Path

from app.comfyui import ComfyUIConfig, ComfyUIGenerator
from app.generators import GenerationRequest
from app.planner import build_portrait_plan


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
