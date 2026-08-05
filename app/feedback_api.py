from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.candidate_sessions import candidate_session_store
from app.feedback import feedback_store

router = APIRouter(prefix="/v1/candidate-sessions", tags=["candidate-feedback"])


class CandidateFeedbackRequest(BaseModel):
    candidate_id: str
    rating: int = Field(ge=1, le=5)
    accepted: bool
    reasons: list[str] = Field(default_factory=list, max_length=8)
    comment: str | None = Field(default=None, max_length=1000)


@router.post("/{session_id}/feedback", status_code=201)
def create_candidate_feedback(
    session_id: str,
    request: CandidateFeedbackRequest,
) -> dict[str, object]:
    try:
        session = candidate_session_store.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    normalized_candidate = request.candidate_id.strip().upper()
    available = {candidate.id for candidate in session.candidates}
    if normalized_candidate not in available:
        raise HTTPException(status_code=422, detail="Candidate is not available in this session.")
    if request.accepted and session.selected_candidate_id != normalized_candidate:
        raise HTTPException(
            status_code=409,
            detail="Only the currently selected candidate can be marked accepted.",
        )

    try:
        feedback = feedback_store.create(
            session_id=session.id,
            candidate_id=normalized_candidate,
            rating=request.rating,
            accepted=request.accepted,
            reasons=request.reasons,
            comment=request.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "feedback": feedback.to_dict(),
        "next_step": "final_render" if request.accepted else "refine_or_choose_another",
    }


@router.get("/{session_id}/feedback")
def list_candidate_feedback(session_id: str) -> dict[str, object]:
    try:
        candidate_session_store.get(session_id)
        feedback = feedback_store.list_for_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "session_id": session_id,
        "count": len(feedback),
        "feedback": [item.to_dict() for item in feedback],
    }
