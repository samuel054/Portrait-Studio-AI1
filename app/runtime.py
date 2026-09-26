"""Explicit local model readiness; no downloads or paid services in request handlers."""
from __future__ import annotations

from dataclasses import replace
import importlib.util

from app.comfyui import ComfyUIGenerator
from app.workflow_engine import workflow_engine
from app.composition import background_model_path


def runtime_status() -> dict[str, object]:
    generator = ComfyUIGenerator()
    generator.config = replace(generator.config, timeout_seconds=3.0)
    checks: list[dict[str, object]] = []
    try:
        generator._request_json("/system_stats")
        checks.append({"id": "comfyui", "ready": True, "message": "Local image engine connected."})
        workflow = generator._load_workflow()
        info = generator._request_json("/object_info")
        missing = sorted({node.get("class_type") for node in workflow.values()
                          if isinstance(node, dict) and node.get("class_type") not in info})
        if missing:
            raise RuntimeError("Install missing workflow nodes: " + ", ".join(map(str, missing)))
        names = info.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
        if generator.config.checkpoint not in names:
            raise RuntimeError("Install the configured portrait checkpoint in ComfyUI models/checkpoints.")
        checks.append({"id": "workflow", "ready": True, "message": "Portrait workflow and checkpoint found."})
    except (RuntimeError, KeyError, TypeError, IndexError) as exc:
        checks.append({"id": "workflow", "ready": False, "message": str(exc)})
    try:
        workflow_engine.likeness_adapter
        checks.append({"id": "identity", "ready": True, "message": "Local likeness model loaded."})
    except (RuntimeError, ImportError, OSError, ValueError, AssertionError):
        checks.append({"id": "identity", "ready": False,
                       "message": "Install the likeness dependencies and model using the setup guide."})
    return {"ready": all(item["ready"] for item in checks), "checks": checks,
            "background_removal": bool(importlib.util.find_spec("rembg") and background_model_path().is_file())}


def require_identity_runtime() -> None:
    # Check before spending GPU time; embeddings are computed only during this workflow.
    try:
        workflow_engine.likeness_adapter
    except (ImportError, OSError, ValueError, AssertionError) as exc:
        raise RuntimeError("The local likeness model could not load. Check model setup.") from exc
