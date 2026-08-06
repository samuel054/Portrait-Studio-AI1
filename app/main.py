from __future__ import annotations

import asyncio
import base64
import logging
import urllib.error
import urllib.request
from contextlib import asynccontextmanager
from typing import Annotated, Any

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.analyzer import analyze_image
from app.candidate_api import router as candidate_router
from app.comfyui import ComfyUIGenerator
from app.enhancer import enhance_image
from app.generators import GenerationRequest, list_generators, run_generation
from app.http_middleware import ApiMiddleware
from app.identity import analyze_identity
from app.planner import build_portrait_plan
from app.settings import get_settings
from app.styles import get_style, list_styles
from app.workflow_engine import workflow_engine
from app.workflow_jobs import portrait_workflow_store

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    worker_task: asyncio.Task[None] | None = None
    if settings.enable_background_worker and settings.environment != "test":
        worker_task = asyncio.create_task(workflow_engine.run_forever())
    try:
        yield
    finally:
        if worker_task:
            workflow_engine.stop()
            await worker_task


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Identity-first, open-source portrait generation API.",
    lifespan=lifespan,
)
app.middleware("http")(ApiMiddleware(settings))
app.include_router(candidate_router)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
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
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"The image exceeds the {settings.max_upload_mb} MB limit.",
        )
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise HTTPException(status_code=400, detail="The uploaded image is corrupt or unreadable.")
    height, width = image.shape[:2]
    if width * height > settings.max_image_pixels:
        raise HTTPException(status_code=413, detail="The image pixel dimensions exceed the safe limit.")
    return data


def _find_prompt_id(payload: dict[str, Any]) -> str | None:
    direct = payload.get("prompt_id")
    if isinstance(direct, str) and direct:
        return direct
    request_payload = payload.get("request_payload")
    if isinstance(request_payload, dict):
        nested = request_payload.get("prompt_id")
        if isinstance(nested, str) and nested:
            return nested
    return None


def _next_step(status: str) -> str:
    return {
        "awaiting_selection": "select_candidate",
        "completed": "download",
        "failed": "retry_generation",
        "cancelled": "restart",
    }.get(status, "poll_portrait_job")


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": settings.app_version}


@app.get("/ready", tags=["operations"])
def ready() -> dict[str, object]:
    checks: dict[str, object] = {
        "workflow_database": portrait_workflow_store.database_path.exists(),
        "candidate_database": workflow_engine.candidates.database_path.exists(),
        "comfyui": False,
    }
    try:
        with urllib.request.urlopen(
            f"{settings.comfyui_base_url}/system_stats",
            timeout=min(settings.comfyui_timeout_seconds, 3.0),
        ) as response:
            checks["comfyui"] = 200 <= response.status < 500
    except (urllib.error.URLError, TimeoutError, OSError):
        checks["comfyui"] = False
    ready_state = bool(checks["workflow_database"] and checks["candidate_database"])
    return {"status": "ready" if ready_state else "not_ready", "checks": checks}


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


@app.post("/v1/portrait-jobs", status_code=202)
async def create_portrait_job(
    file: ImageUpload,
    style_id: Annotated[str, Form()],
    crop: Annotated[str, Form()] = "original",
    background: Annotated[str, Form()] = "keep",
    output_type: Annotated[str, Form()] = "social",
    preserve_pose: Annotated[bool, Form()] = True,
    preserve_clothing: Annotated[bool, Form()] = True,
    candidate_count: Annotated[int, Form(ge=1, le=4)] = 4,
    seed: Annotated[int | None, Form()] = None,
) -> dict[str, object]:
    data = await _read_upload(file)
    try:
        image_report = analyze_image(data)
        identity_report = analyze_identity(data)
        if identity_report.identity_readiness in {"not_ready", "needs_better_photo"}:
            raise ValueError("Upload a better photo with a clearly visible face before generation.")

        working_bytes = data
        enhancement_report = None
        if image_report.needs_enhancement:
            working_bytes, enhancement_report = enhance_image(data)
            if enhancement_report.identity_after.identity_readiness in {
                "not_ready",
                "needs_better_photo",
            }:
                raise ValueError("Enhancement could not produce a generation-ready identity image.")

        plan = build_portrait_plan(
            style_id=style_id,
            crop=crop,
            background=background,
            output_type=output_type,
            preserve_pose=preserve_pose,
            preserve_clothing=preserve_clothing,
        )
        comfyui = ComfyUIGenerator()
        upload = comfyui.upload_image(
            image_bytes=working_bytes,
            filename=file.filename or "portrait.png",
            content_type="image/png" if enhancement_report else (file.content_type or "image/png"),
            subfolder="portrait-studio-ai",
            overwrite=False,
        )
        generation = run_generation(
            "comfyui",
            GenerationRequest(
                plan=plan,
                image_reference=upload.image_reference,
                seed=seed,
                candidate_count=candidate_count,
            ),
        )
        generation_payload = generation.to_dict()
        workflow = portrait_workflow_store.create(
            filename=file.filename,
            style_id=style_id,
            prompt_id=_find_prompt_id(generation_payload),
            payload={
                "analysis": image_report.to_dict(),
                "identity": identity_report.to_dict(),
                "enhancement_applied": enhancement_report is not None,
                "enhancement": enhancement_report.to_dict() if enhancement_report else None,
                "plan": plan.to_dict(),
                "image_reference": upload.image_reference,
                "generation": generation_payload,
                "_source_image_base64": base64.b64encode(data).decode("ascii"),
                "_poll_retry_count": 0,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {"job": workflow.to_dict(), "next_step": "poll_portrait_job"}


@app.get("/v1/portrait-jobs/{job_id}")
def portrait_job_status(job_id: str, refresh: bool = Query(default=True)) -> dict[str, object]:
    try:
        workflow = workflow_engine.advance(job_id) if refresh else portrait_workflow_store.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"job": workflow.to_dict(), "next_step": _next_step(workflow.status)}


@app.post("/v1/portrait-jobs/{job_id}/retry")
def retry_portrait_job(job_id: str) -> dict[str, object]:
    try:
        workflow = portrait_workflow_store.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if workflow.status != "failed":
        raise HTTPException(status_code=409, detail="Only failed workflows can be retried.")
    raise HTTPException(
        status_code=409,
        detail="Create a new portrait job from the original upload; failed jobs remain immutable for auditability.",
    )


@app.post("/v1/comfyui/images")
async def upload_comfyui_image(
    file: ImageUpload,
    subfolder: Annotated[str, Form()] = "portrait-studio-ai",
    overwrite: Annotated[bool, Form()] = False,
) -> dict[str, object]:
    data = await _read_upload(file)
    try:
        result = ComfyUIGenerator().upload_image(
            image_bytes=data,
            filename=file.filename or "portrait.png",
            content_type=file.content_type or "application/octet-stream",
            subfolder=subfolder.strip().strip("/"),
            overwrite=overwrite,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"upload": result.to_dict(), "next_step": "generation"}


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
        plan = build_portrait_plan(**request.model_dump())
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
    if identity_report.identity_readiness in {"not_ready", "needs_better_photo"}:
        next_step = "request_better_photo"
    elif image_report.needs_enhancement:
        next_step = "enhance"
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
