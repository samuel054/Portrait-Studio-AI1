from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.candidate_sessions import candidate_session_store
from app.comfyui import ComfyUIGenerator
from app.generators import GenerationRequest, run_generation
from app.refinement import build_refinement_plan
from app.workflow_jobs import portrait_workflow_store
from app.composition import background_session

router = APIRouter(tags=["portrait-refinement"])


class RefinementRequest(BaseModel):
    style_id: str
    operation: str
    instruction: str = Field(min_length=1, max_length=500)
    crop: str = "original"
    background: str = "keep"
    output_type: str = "social"
    preserve_pose: bool = True
    preserve_clothing: bool = True
    strength: float = Field(default=0.25, ge=0.05, le=0.50)
    seed: int | None = None
    candidate_count: int = Field(default=2, ge=1, le=4)


@router.post("/{session_id}/refine", status_code=202)
def refine_selected_candidate(
    session_id: str,
    request: RefinementRequest,
) -> dict[str, object]:
    try:
        session = candidate_session_store.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if session.selected_candidate_id is None:
        raise HTTPException(
            status_code=409,
            detail="Select a candidate before requesting a refinement.",
        )
    selected = next(
        item for item in session.candidates if item.id == session.selected_candidate_id
    )

    try:
        original_bytes = candidate_session_store.source_bytes(session_id)
        if request.background in {"transparent", "blur"}:
            background_session()
        image_bytes = base64.b64decode(selected.image_base64, validate=True)
        plan = build_refinement_plan(
            style_id=request.style_id,
            operation=request.operation,
            instruction=request.instruction,
            crop=request.crop,
            background=request.background,
            output_type=request.output_type,
            preserve_pose=request.preserve_pose,
            preserve_clothing=request.preserve_clothing,
            strength=request.strength,
        )
        comfyui = ComfyUIGenerator()
        upload = comfyui.upload_image(
            image_bytes=image_bytes,
            filename=f"refine-{session.id}-{selected.id}.png",
            content_type=selected.content_type,
            subfolder="portrait-studio-ai/refinements",
            overwrite=False,
        )
        generation = run_generation(
            "comfyui",
            GenerationRequest(
                plan=plan,
                image_reference=upload.image_reference,
                seed=request.seed,
                candidate_count=request.candidate_count,
            ),
        )
        payload = generation.to_dict()
        prompt_id = payload.get("request_payload", {}).get("prompt_id")
        if not prompt_id:
            raise RuntimeError("The refinement provider did not return a job ID.")
        workflow = portrait_workflow_store.create(
            filename="refinement.png", style_id=request.style_id, prompt_id=prompt_id,
            stage="refinement_queued",
            payload={
                "plan": plan.to_dict(), "generation": payload,
                "parent_session_id": session.id,
                "_source_image_base64": base64.b64encode(original_bytes).decode("ascii"),
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "session_id": session.id,
        "source_candidate_id": selected.id,
        "refinement_plan": plan.to_dict(),
        "generation": generation.to_dict(),
        "job": workflow.to_dict(),
        "next_step": "poll_portrait_job",
    }
