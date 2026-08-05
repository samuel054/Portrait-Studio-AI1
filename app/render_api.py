from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.candidate_sessions import candidate_session_store
from app.final_render import render_selected_candidate

router = APIRouter(prefix="/v1/candidate-sessions", tags=["final-render"])


class FinalRenderRequest(BaseModel):
    output_format: str = "png"
    max_dimension: int | None = Field(default=None, ge=256, le=8192)
    quality: int = Field(default=95, ge=1, le=100)
    allow_upscale: bool = False


@router.post("/{session_id}/render")
def render_candidate(session_id: str, request: FinalRenderRequest) -> dict[str, object]:
    try:
        session = candidate_session_store.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if session.selected_candidate_id is None:
        raise HTTPException(
            status_code=409,
            detail="Select a candidate before requesting the final render.",
        )

    selected = next(
        item for item in session.candidates if item.id == session.selected_candidate_id
    )
    try:
        result = render_selected_candidate(
            candidate_id=selected.id,
            source_filename=selected.filename,
            image_base64=selected.image_base64,
            output_format=request.output_format,
            max_dimension=request.max_dimension,
            quality=request.quality,
            allow_upscale=request.allow_upscale,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "render": result.to_dict(),
        "session_id": session.id,
        "next_step": "download_or_refine",
    }
