from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass
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


@dataclass(frozen=True)
class ComfyUIUploadResult:
    name: str
    subfolder: str
    image_type: str

    @property
    def image_reference(self) -> str:
        return f"{self.subfolder}/{self.name}" if self.subfolder else self.name

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "subfolder": self.subfolder,
            "type": self.image_type,
            "image_reference": self.image_reference,
        }


@dataclass(frozen=True)
class ComfyUIImage:
    filename: str
    subfolder: str
    image_type: str
    content_type: str
    image_base64: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class ComfyUIJobResult:
    prompt_id: str
    status: str
    images: tuple[ComfyUIImage, ...]
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "prompt_id": self.prompt_id,
            "status": self.status,
            "images": [image.to_dict() for image in self.images],
            "error": self.error,
        }


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

    def _request_json(self, path: str) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(
                f"{self.config.base_url}{path}",
                timeout=self.config.timeout_seconds,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"ComfyUI is unavailable at '{self.config.base_url}'."
            ) from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("ComfyUI returned an invalid JSON response.") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("ComfyUI returned an unexpected response.")
        return payload

    def upload_image(
        self,
        image_bytes: bytes,
        filename: str,
        content_type: str,
        subfolder: str = "portrait-studio-ai",
        overwrite: bool = False,
    ) -> ComfyUIUploadResult:
        if not image_bytes:
            raise ValueError("Image data is required.")
        safe_name = os.path.basename(filename.strip())
        if not safe_name:
            raise ValueError("A valid filename is required.")

        boundary = f"portrait-{uuid.uuid4().hex}"
        parts = [
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{safe_name}\"\r\nContent-Type: {content_type}\r\n\r\n".encode(),
            image_bytes,
            f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"subfolder\"\r\n\r\n{subfolder}\r\n".encode(),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\n{str(overwrite).lower()}\r\n".encode(),
            f"--{boundary}--\r\n".encode(),
        ]
        request = urllib.request.Request(
            f"{self.config.base_url}/upload/image",
            data=b"".join(parts),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"ComfyUI is unavailable at '{self.config.base_url}'."
            ) from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("ComfyUI returned an invalid upload response.") from exc

        if not isinstance(payload, dict) or not payload.get("name"):
            raise RuntimeError("ComfyUI did not confirm the uploaded image.")
        return ComfyUIUploadResult(
            name=str(payload["name"]),
            subfolder=str(payload.get("subfolder", "")),
            image_type=str(payload.get("type", "input")),
        )

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

    def _download_image(self, metadata: dict[str, Any]) -> ComfyUIImage:
        filename = str(metadata.get("filename", ""))
        if not filename:
            raise RuntimeError("ComfyUI image output is missing a filename.")
        subfolder = str(metadata.get("subfolder", ""))
        image_type = str(metadata.get("type", "output"))
        query = urllib.parse.urlencode(
            {"filename": filename, "subfolder": subfolder, "type": image_type}
        )
        try:
            with urllib.request.urlopen(
                f"{self.config.base_url}/view?{query}",
                timeout=self.config.timeout_seconds,
            ) as response:
                image_bytes = response.read()
                content_type = response.headers.get_content_type()
        except urllib.error.URLError as exc:
            raise RuntimeError("ComfyUI generated an image but it could not be downloaded.") from exc

        return ComfyUIImage(
            filename=filename,
            subfolder=subfolder,
            image_type=image_type,
            content_type=content_type,
            image_base64=base64.b64encode(image_bytes).decode("ascii"),
        )

    def get_job(self, prompt_id: str, include_images: bool = True) -> ComfyUIJobResult:
        normalized = prompt_id.strip()
        if not normalized:
            raise ValueError("prompt_id is required.")

        history = self._request_json(f"/history/{urllib.parse.quote(normalized)}")
        job = history.get(normalized)
        if job is None:
            return ComfyUIJobResult(prompt_id=normalized, status="queued", images=())
        if not isinstance(job, dict):
            raise RuntimeError("ComfyUI returned malformed job history.")

        status_payload = job.get("status", {})
        status_text = "completed"
        error: str | None = None
        if isinstance(status_payload, dict):
            completed = status_payload.get("completed")
            status_text = str(status_payload.get("status_str", "completed"))
            if completed is False and status_text == "error":
                error = "ComfyUI reported a generation error."

        images: list[ComfyUIImage] = []
        outputs = job.get("outputs", {})
        if include_images and isinstance(outputs, dict):
            for node_output in outputs.values():
                if not isinstance(node_output, dict):
                    continue
                for metadata in node_output.get("images", []):
                    if isinstance(metadata, dict):
                        images.append(self._download_image(metadata))

        if error:
            final_status = "failed"
        elif images:
            final_status = "completed"
        elif status_text in {"running", "executing"}:
            final_status = "running"
        else:
            final_status = "processing"

        return ComfyUIJobResult(
            prompt_id=normalized,
            status=final_status,
            images=tuple(images),
            error=error,
        )
