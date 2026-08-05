from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from app.generators import (
    GenerationRequest,
    GenerationResult,
    GeneratorCapabilities,
)


@dataclass(frozen=True)
class ComfyUIConfig:
    base_url: str = "http://127.0.0.1:8188"
    workflow_path: str = "workflows/portrait_api.json"
    timeout_seconds: float = 15.0

    @classmethod
    def from_environment(cls) -> "ComfyUIConfig":
        return cls(
            base_url=os.getenv("COMFYUI_BASE_URL", cls.base_url).rstrip("/"),
            workflow_path=os.getenv("COMFYUI_WORKFLOW_PATH", cls.workflow_path),
            timeout_seconds=float(os.getenv("COMFYUI_TIMEOUT_SECONDS", cls.timeout_seconds)),
        )


class ComfyUIGenerator:
    """Submit identity-first portrait jobs to a local ComfyUI server."""

    capabilities = GeneratorCapabilities(
        id="comfyui",
        name="ComfyUI Local Generator",
        open_source=True,
        local_execution=True,
        supports_image_reference=True,
        supports_negative_prompt=True,
        available=True,
    )

    def __init__(self, config: ComfyUIConfig | None = None) -> None:
        self.config = config or ComfyUIConfig.from_environment()

    def _load_workflow(self) -> dict[str, Any]:
        try:
            with open(self.config.workflow_path, encoding="utf-8") as workflow_file:
                workflow = json.load(workflow_file)
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"ComfyUI workflow not found at '{self.config.workflow_path}'."
            ) from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("ComfyUI workflow is not valid JSON.") from exc

        if not isinstance(workflow, dict):
            raise RuntimeError("ComfyUI workflow must be a JSON object.")
        return workflow

    @staticmethod
    def _replace_tokens(value: Any, tokens: dict[str, Any]) -> Any:
        if isinstance(value, dict):
            return {key: ComfyUIGenerator._replace_tokens(item, tokens) for key, item in value.items()}
        if isinstance(value, list):
            return [ComfyUIGenerator._replace_tokens(item, tokens) for item in value]
        if isinstance(value, str) and value in tokens:
            return tokens[value]
        return value

    def build_payload(self, request: GenerationRequest) -> dict[str, object]:
        workflow = self._load_workflow()
        tokens: dict[str, Any] = {
            "{{PROMPT}}": request.plan.prompt,
            "{{NEGATIVE_PROMPT}}": " ".join(request.plan.negative_rules),
            "{{IMAGE_REFERENCE}}": request.image_reference,
            "{{SEED}}": request.seed if request.seed is not None else 0,
            "{{CANDIDATE_COUNT}}": request.candidate_count,
        }
        return {
            "prompt": self._replace_tokens(workflow, tokens),
            "client_id": "portrait-studio-ai",
        }

    def generate(self, request: GenerationRequest) -> GenerationResult:
        payload = self.build_payload(request)
        encoded = json.dumps(payload).encode("utf-8")
        http_request = urllib.request.Request(
            f"{self.config.base_url}/prompt",
            data=encoded,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                http_request,
                timeout=self.config.timeout_seconds,
            ) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"ComfyUI is unavailable at '{self.config.base_url}'."
            ) from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("ComfyUI returned an invalid JSON response.") from exc

        prompt_id = response_payload.get("prompt_id")
        if not prompt_id:
            raise RuntimeError("ComfyUI did not return a prompt_id.")

        return GenerationResult(
            generator_id=self.capabilities.id,
            status="queued",
            candidate_count=request.candidate_count,
            request_payload={
                "prompt_id": prompt_id,
                "server": self.config.base_url,
                "style_id": request.plan.style_id,
                "seed": request.seed,
            },
            message="Portrait generation was queued in ComfyUI.",
        )
