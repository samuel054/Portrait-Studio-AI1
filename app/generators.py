from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

from app.planner import PortraitPlan


@dataclass(frozen=True)
class GeneratorCapabilities:
    id: str
    name: str
    open_source: bool
    local_execution: bool
    supports_image_reference: bool
    supports_negative_prompt: bool
    available: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class GenerationRequest:
    plan: PortraitPlan
    image_reference: str
    seed: int | None = None
    candidate_count: int = 4


@dataclass(frozen=True)
class GenerationResult:
    generator_id: str
    status: str
    candidate_count: int
    request_payload: dict[str, object]
    message: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class PortraitGenerator(Protocol):
    capabilities: GeneratorCapabilities

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate portrait candidates from an identity-preserving portrait plan."""


class DryRunGenerator:
    """Validate generation contracts without downloading model weights."""

    capabilities = GeneratorCapabilities(
        id="dry_run",
        name="Dry Run Generator",
        open_source=True,
        local_execution=True,
        supports_image_reference=True,
        supports_negative_prompt=True,
        available=True,
    )

    def generate(self, request: GenerationRequest) -> GenerationResult:
        payload = {
            "prompt": request.plan.prompt,
            "negative_prompt": " ".join(request.plan.negative_rules),
            "image_reference": request.image_reference,
            "seed": request.seed,
            "candidate_count": request.candidate_count,
            "style_id": request.plan.style_id,
            "crop": request.plan.crop,
            "background": request.plan.background,
            "output_type": request.plan.output_type,
        }
        return GenerationResult(
            generator_id=self.capabilities.id,
            status="validated",
            candidate_count=request.candidate_count,
            request_payload=payload,
            message="Generation request is valid. No model inference was executed.",
        )


def _build_registry() -> dict[str, PortraitGenerator]:
    from app.comfyui import ComfyUIGenerator

    generators: tuple[PortraitGenerator, ...] = (
        DryRunGenerator(),
        ComfyUIGenerator(),
    )
    return {generator.capabilities.id: generator for generator in generators}


_GENERATORS = _build_registry()


def list_generators() -> list[dict[str, object]]:
    return [generator.capabilities.to_dict() for generator in _GENERATORS.values()]


def get_generator(generator_id: str) -> PortraitGenerator | None:
    return _GENERATORS.get(generator_id.strip().lower())


def run_generation(generator_id: str, request: GenerationRequest) -> GenerationResult:
    generator = get_generator(generator_id)
    if generator is None:
        raise ValueError("Unknown generator ID.")
    if not generator.capabilities.available:
        raise RuntimeError(f"Generator '{generator_id}' is not currently available.")
    if request.candidate_count < 1 or request.candidate_count > 4:
        raise ValueError("candidate_count must be between 1 and 4.")
    if not request.image_reference.strip():
        raise ValueError("image_reference is required.")
    return generator.generate(request)
