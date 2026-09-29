from __future__ import annotations

import base64
import json
import sqlite3
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.comfyui import ComfyUIJobResult
from app.identity_score import IdentityFirstRanking
from app.settings import get_settings


_CANDIDATE_LABELS = ("A", "B", "C", "D")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _default_database_path() -> Path:
    return get_settings().portrait_candidate_db


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
        connection.execute("PRAGMA secure_delete = ON")
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
            columns = {row[1] for row in connection.execute("PRAGMA table_info(candidate_sessions)")}
            if "source_image_base64" not in columns:
                connection.execute("ALTER TABLE candidate_sessions ADD COLUMN source_image_base64 TEXT")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_candidate_sessions_prompt_id "
                "ON candidate_sessions(prompt_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_candidate_sessions_status "
                "ON candidate_sessions(status)"
            )

    def create(
        self, job: ComfyUIJobResult, ranking: IdentityFirstRanking,
        source_image_bytes: bytes | None = None,
    ) -> CandidateSession:
        if job.status != "completed":
            raise ValueError("Candidate sessions can only be created from completed generations.")
        if not job.images:
            raise ValueError("The completed generation did not return any images.")

        evaluations = {item.index: item for item in ranking.evaluations}
        eligible = [
            (index, image, evaluations.get(index))
            for index, image in enumerate(job.images)
            if evaluations.get(index) is not None and evaluations[index].status == "pass"
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
                    created_at, updated_at, source_image_base64
                ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?)
                """,
                (session.id, session.prompt_id, session.status, serialized, timestamp, timestamp,
                 base64.b64encode(source_image_bytes).decode("ascii") if source_image_bytes else None),
            )
        return self.get(session.id)

    def get(self, session_id: str) -> CandidateSession:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM candidate_sessions WHERE id = ?", (session_id,)
            ).fetchone()
        if row is None:
            raise KeyError("Candidate session not found.")
        cutoff = datetime.now(UTC) - timedelta(minutes=get_settings().portrait_session_ttl_minutes)
        if datetime.fromisoformat(row["created_at"]) < cutoff:
            self.delete(session_id)
            raise KeyError("This portrait session has expired. Please upload the photo again.")
        return self._from_row(row)

    def source_bytes(self, session_id: str) -> bytes:
        self.get(session_id)  # Enforce expiry before accessing the private source.
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT source_image_base64 FROM candidate_sessions WHERE id = ?", (session_id,)
            ).fetchone()
        if row is None or not row[0]:
            raise ValueError("The original photo has expired. Upload it again to refine safely.")
        return base64.b64decode(row[0], validate=True)

    def delete(self, session_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM candidate_sessions WHERE id = ?", (session_id,))

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

    def delete_expired(self, ttl_minutes: int | None = None) -> int:
        ttl = ttl_minutes or get_settings().portrait_session_ttl_minutes
        cutoff = (datetime.now(UTC) - timedelta(minutes=ttl)).isoformat()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM candidate_sessions WHERE created_at < ?",
                (cutoff,),
            )
            return max(cursor.rowcount, 0)

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
