from __future__ import annotations

import base64
import uuid
from dataclasses import asdict, dataclass
from threading import RLock

from app.comfyui import ComfyUIJobResult
from app.identity_score import IdentityFirstRanking


_CANDIDATE_LABELS = ("A", "B", "C", "D")


@dataclass(frozen=True)
class CandidatePreview:
    id: str
    source_index: int
    rank: int
    score: float
    status: str
    recommended: bool
    filename: str
    content_type: str
    image_base64: str
    reasons: tuple[str, ...]

    def to_dict(self, include_image: bool = True) -> dict[str, object]:
        data = asdict(self)
        data["reasons"] = list(self.reasons)
        if not include_image:
            data.pop("image_base64")
        return data


@dataclass
class CandidateSession:
    id: str
    prompt_id: str
    status: str
    candidates: tuple[CandidatePreview, ...]
    selected_candidate_id: str | None = None

    def to_dict(self, include_images: bool = True) -> dict[str, object]:
        return {
            "id": self.id,
            "prompt_id": self.prompt_id,
            "status": self.status,
            "selected_candidate_id": self.selected_candidate_id,
            "candidates": [item.to_dict(include_image=include_images) for item in self.candidates],
        }


class CandidateSessionStore:
    """Thread-safe in-memory store for the MVP candidate-selection workflow."""

    def __init__(self) -> None:
        self._items: dict[str, CandidateSession] = {}
        self._lock = RLock()

    def create(
        self,
        job: ComfyUIJobResult,
        ranking: IdentityFirstRanking,
    ) -> CandidateSession:
        if job.status != "completed":
            raise ValueError("Candidate sessions can only be created from completed generations.")
        if not job.images:
            raise ValueError("The completed generation did not return any images.")

        evaluations = {item.index: item for item in ranking.evaluations}
        eligible = [
            (index, image, evaluations.get(index))
            for index, image in enumerate(job.images)
            if evaluations.get(index) is not None and evaluations[index].status != "reject"
        ]
        eligible.sort(key=lambda item: (item[2].rank, item[0]))
        eligible = eligible[:4]
        if not eligible:
            raise ValueError("All generated candidates failed identity-safety checks.")

        previews: list[CandidatePreview] = []
        for label, (source_index, image, evaluation) in zip(
            _CANDIDATE_LABELS,
            eligible,
            strict=False,
        ):
            # Validate payload now so corrupt ComfyUI responses never reach the user.
            try:
                base64.b64decode(image.image_base64, validate=True)
            except ValueError as exc:
                raise ValueError(f"Candidate {source_index} contains invalid image data.") from exc
            previews.append(
                CandidatePreview(
                    id=label,
                    source_index=source_index,
                    rank=evaluation.rank,
                    score=evaluation.final_score,
                    status=evaluation.status,
                    recommended=source_index == ranking.recommended_index,
                    filename=image.filename,
                    content_type=image.content_type,
                    image_base64=image.image_base64,
                    reasons=evaluation.reasons,
                )
            )

        session = CandidateSession(
            id=uuid.uuid4().hex,
            prompt_id=job.prompt_id,
            status="awaiting_selection",
            candidates=tuple(previews),
        )
        with self._lock:
            self._items[session.id] = session
        return session

    def get(self, session_id: str) -> CandidateSession:
        with self._lock:
            session = self._items.get(session_id)
        if session is None:
            raise KeyError("Candidate session not found.")
        return session

    def select(self, session_id: str, candidate_id: str) -> CandidateSession:
        normalized = candidate_id.strip().upper()
        with self._lock:
            session = self._items.get(session_id)
            if session is None:
                raise KeyError("Candidate session not found.")
            if normalized not in {item.id for item in session.candidates}:
                raise ValueError("Unknown or unavailable candidate ID.")
            session.selected_candidate_id = normalized
            session.status = "selected"
            return session


candidate_session_store = CandidateSessionStore()
