from __future__ import annotations

import base64
import json
import os
import sqlite3
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.comfyui import ComfyUIJobResult
from app.identity_score import IdentityFirstRanking


_CANDIDATE_LABELS = ("A", "B", "C", "D")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _default_database_path() -> Path:
    return Path(os.getenv("PORTRAIT_CANDIDATE_DB", "portrait_candidates.db"))


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

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "CandidatePreview":
        return cls(
            id=str(data["id"]),
            source_index=int(data["source_index"]),
            rank=int(data["rank"]),
            score=float(data["score"]),
            status=str(data["status"]),
            recommended=bool(data["recommended"]),
            filename=str(data["filename"]),
            content_type=str(data["content_type"]),
            image_base64=str(data["image_base64"]),
            reasons=tuple(str(item) for item in data.get("reasons", [])),
        )


@dataclass(frozen=True)
class CandidateSession:
    id: str
    prompt_id: str
    status: str
    candidates: tuple[CandidatePreview, ...]
    selected_candidate_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self, include_images: bool = True) -> dict[str, object]:
        return {
            "id": self.id,
            "prompt_id": self.prompt_id,
            "status": self.status,
            "selected_candidate_id": self.selected_candidate_id,
            "candidates": [item.to_dict(include_image=include_images) for item in self.candidates],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class CandidateSessionStore:
    """Persistent SQLite repository for identity-safe candidate sessions."""

    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = Path(database_path) if database_path else _default_database_path()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS candidate_sessions (
                    id TEXT PRIMARY KEY,
                    prompt_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    selected_candidate_id TEXT,
                    candidates_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_candidate_sessions_prompt_id "
                "ON candidate_sessions(prompt_id)"
            )

    def create(self, job: ComfyUIJobResult, ranking: IdentityFirstRanking) -> CandidateSession:
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
        for label, (source_index, image, evaluation) in zip(_CANDIDATE_LABELS, eligible, strict=False):
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

        timestamp = _utc_now()
        session = CandidateSession(
            id=uuid.uuid4().hex,
            prompt_id=job.prompt_id,
            status="awaiting_selection",
            candidates=tuple(previews),
            created_at=timestamp,
            updated_at=timestamp,
        )
        serialized = json.dumps(
            [candidate.to_dict(include_image=True) for candidate in session.candidates],
            separators=(",", ":"),
            sort_keys=True,
        )
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO candidate_sessions (
                    id, prompt_id, status, selected_candidate_id, candidates_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, NULL, ?, ?, ?)
                """,
                (session.id, session.prompt_id, session.status, serialized, timestamp, timestamp),
            )
        return self.get(session.id)

    def get(self, session_id: str) -> CandidateSession:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM candidate_sessions WHERE id = ?", (session_id,)
            ).fetchone()
        if row is None:
            raise KeyError("Candidate session not found.")
        return self._from_row(row)

    def select(self, session_id: str, candidate_id: str) -> CandidateSession:
        normalized = candidate_id.strip().upper()
        session = self.get(session_id)
        if normalized not in {item.id for item in session.candidates}:
            raise ValueError("Unknown or unavailable candidate ID.")
        timestamp = _utc_now()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE candidate_sessions
                SET status = 'selected', selected_candidate_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (normalized, timestamp, session_id),
            )
        return self.get(session_id)

    @staticmethod
    def _from_row(row: sqlite3.Row) -> CandidateSession:
        raw_candidates = json.loads(row["candidates_json"])
        return CandidateSession(
            id=row["id"],
            prompt_id=row["prompt_id"],
            status=row["status"],
            selected_candidate_id=row["selected_candidate_id"],
            candidates=tuple(CandidatePreview.from_dict(item) for item in raw_candidates),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


candidate_session_store = CandidateSessionStore()
