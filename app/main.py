from __future__ import annotations

import base64
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.analyzer import analyze_image
from app.comfyui import ComfyUIGenerator
from app.enhancer import enhance_image
from app.generators import GenerationRequest, list_generators, run_generation
from app.identity import analyze_identity
from app.planner import build_portrait_plan
from app.styles import get_style, list_styles

app = FastAPI(title="Portrait Studio AI", version="0.8.0")

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 20 * 1024 * 1024
ImageUpload = Annotated[UploadFile, File()]


class PortraitPlanRequest(BaseModel):
    style_id: str
    crop: str = "original"
    background: str = "keep"
    output_type: str = "social"
    preserve_pose: bool = True
    preserve_clothing: bool = True


class GenerationApiRequest(PortraitPlanRequest):
    generator_id: str = "dry_run"
    image_reference: str
    seed: int | None = None
    candidate_count: int = Field(default=4, ge=1, le=4)


async def _read_upload(file: UploadFile) -> bytes:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Upload a JPG, PNG, or WEBP image.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="The image exceeds the 20 MB limit.")
    return data


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/styles")
def styles(category: str | None = Query(default=None)) -> dict[str, object]:
    items = list_styles(category)
    return {"count": len(items), "styles": items}


@app.get("/v1/styles/{style_id}")
def style_detail(style_id: str) -> dict[str, object]:
    style = get_style(style_id)
    if style is None:
        raise HTTPException(status_code=404, detail="Style not found.")
    return style.to_dict()


@app.get("/v1/generators")
def generators() -> dict[str, object]:
    items = list_generators()
    return {"count": len(items), "generators": items}


@app.get("/v1/generations/{prompt_id}")
def generation_status(
    prompt_id: str,
    include_images: bool = Query(default=True),
) -> dict[str, object]:
    try:
        result = ComfyUIGenerator().get_job(prompt_id, include_images=include_images)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    next_step = "select_candidate" if result.status == "completed" else "poll_generation"
    if result.status == "failed":
        next_step = "retry_generation"
    return {"generation": result.to_dict(), "next_step": next_step}


@app.post("/v1/plans")
def create_plan(request: PortraitPlanRequest) -> dict[str, object]:
    try:
        plan = build_portrait_plan(
            style_id=request.style_id,
            crop=request.crop,
            background=request.background,
            output_type=request.output_type,
            preserve_pose=request.preserve_pose,
            preserve_clothing=request.preserve_clothing,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"plan": plan.to_dict(), "next_step": "generation"}


@app.post("/v1/generate")
def generate(request: GenerationApiRequest) -> dict[str, object]:
    try:
        plan = build_portrait_plan(
            style_id=request.style_id,
            crop=request.crop,
            background=request.background,
            output_type=request.output_type,
            preserve_pose=request.preserve_pose,
            preserve_clothing=request.preserve_clothing,
        )
        result = run_generation(
            request.generator_id,
            GenerationRequest(
                plan=plan,
                image_reference=request.image_reference,
                seed=request.seed,
                candidate_count=request.candidate_count,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"generation": result.to_dict(), "next_step": "model_inference"}


@app.post("/v1/analyze")
async def analyze(file: ImageUpload) -> dict[str, object]:
    data = await _read_upload(file)

    try:
        image_report = analyze_image(data)
        identity_report = analyze_identity(data)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if image_report.needs_enhancement:
        next_step = "enhance"
    elif identity_report.identity_readiness in {"not_ready", "needs_better_photo"}:
        next_step = "request_better_photo"
    else:
        next_step = "style_selection"

    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "analysis": image_report.to_dict(),
        "identity": identity_report.to_dict(),
        "next_step": next_step,
    }


@app.post("/v1/enhance")
async def enhance(file: ImageUpload) -> dict[str, object]:
    data = await _read_upload(file)

    try:
        enhanced_bytes, report = enhance_image(data)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "filename": file.filename,
        "output_content_type": "image/png",
        "enhancement": report.to_dict(),
        "enhanced_image_base64": base64.b64encode(enhanced_bytes).decode("ascii"),
        "next_step": (
            "style_selection"
            if report.identity_after.identity_readiness not in {"not_ready", "needs_better_photo"}
            else "request_better_photo"
        ),
    }
