from __future__ import annotations

import base64
from typing import Annotated

import cv2
import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app.candidate_sessions import candidate_session_store
from app.comfyui import ComfyUIGenerator
from app.feedback_api import router as feedback_router
from app.identity_score import rank_identity_first_candidates
from app.likeness import InsightFaceAdapter
from app.refinement_api import router as refinement_router
from app.render_api import router as render_router
from app.settings import get_settings
from app.workflow_jobs import portrait_workflow_store

router = APIRouter(prefix="/v1/candidate-sessions", tags=["candidate-selection"])

_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
OriginalUpload = Annotated[UploadFile, File()]


class CandidateSelectionRequest(BaseModel):
    candidate_id: str


async def _read_original(file: UploadFile) -> bytes:
    settings = get_settings()
    if file.content_type not in _ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Upload a JPG, PNG, or WEBP source image.")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The source image is empty.")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"The source image exceeds the {settings.max_upload_mb} MB limit.",
        )

    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise HTTPException(status_code=400, detail="The source image is corrupt or unreadable.")
    height, width = image.shape[:2]
    if width * height > settings.max_image_pixels:
        raise HTTPException(
            status_code=413,
            detail="The source image pixel dimensions exceed the safe limit.",
        )
    return data


@router.post("")
async def create_candidate_session(
    original: OriginalUpload,
    prompt_id: Annotated[str, Form()],
    likeness_threshold: Annotated[float, Form(ge=0.0, le=1.0)] = 0.35,
) -> dict[str, object]:
    original_bytes = await _read_original(original)
    try:
        job = ComfyUIGenerator().get_job(prompt_id, include_images=True)
        if job.status != "completed":
            return {
                "generation": job.to_dict(),
                "next_step": "poll_generation" if job.status != "failed" else "retry_generation",
            }

        candidate_bytes = [
            base64.b64decode(image.image_base64, validate=True) for image in job.images
        ]
        ranking = rank_identity_first_candidates(
            original_bytes=original_bytes,
            candidate_bytes=candidate_bytes,
            adapter=InsightFaceAdapter(),
            likeness_threshold=likeness_threshold,
        )
        session = candidate_session_store.create(job=job, ranking=ranking)
    except (ValueError, base64.binascii.Error) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "session": session.to_dict(include_images=True),
        "ranking": ranking.to_dict(),
        "question": "Which portrait do you prefer?",
        "next_step": "select_candidate",
    }


@router.get("/{session_id}")
def get_candidate_session(
    session_id: str,
    include_images: bool = Query(default=True),
) -> dict[str, object]:
    try:
        session = candidate_session_store.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"session": session.to_dict(include_images=include_images)}


@router.post("/{session_id}/selection")
def select_candidate(
    session_id: str,
    request: CandidateSelectionRequest,
) -> dict[str, object]:
    try:
        session = candidate_session_store.select(session_id, request.candidate_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    workflow = portrait_workflow_store.find_by_candidate_session(session_id)
    if workflow is not None and workflow.status == "awaiting_selection":
        portrait_workflow_store.update(
            workflow.id,
            status="rendering",
            stage="candidate_selected",
            progress=90,
            payload_patch={"selected_candidate_id": session.selected_candidate_id},
        )

    selected = next(item for item in session.candidates if item.id == session.selected_candidate_id)
    return {
        "session": session.to_dict(include_images=False),
        "selected_candidate": selected.to_dict(include_image=True),
        "next_step": "final_render",
    }


router.include_router(render_router)
router.include_router(feedback_router)
router.include_router(refinement_router)
