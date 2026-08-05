from __future__ import annotations

import os
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock

_ALLOWED_REASONS = {
    "best_likeness",
    "best_style",
    "best_expression",
    "best_composition",
    "wrong_face",
    "poor_quality",
    "artifacts",
    "other",
}


@dataclass(frozen=True)
class CandidateFeedback:
    id: str
    session_id: str
    candidate_id: str
    rating: int
    accepted: bool
    reasons: tuple[str, ...]
    comment: str | None
    created_at: str

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["reasons"] = list(self.reasons)
        return data


class FeedbackStore:
    """SQLite-backed preference store that never stores portrait image bytes."""

    def __init__(self, database_path: str | None = None) -> None:
        configured = database_path or os.getenv(
            "PORTRAIT_FEEDBACK_DB",
            "data/portrait_feedback.sqlite3",
        )
        self.database_path = configured
        self._lock = RLock()
        if configured != ":memory:":
            Path(configured).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS candidate_feedback (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
                    accepted INTEGER NOT NULL CHECK (accepted IN (0, 1)),
                    reasons TEXT NOT NULL,
                    comment TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_feedback_session ON candidate_feedback(session_id)"
            )

    @staticmethod
    def _normalize_reasons(reasons: list[str] | tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(dict.fromkeys(reason.strip().lower() for reason in reasons if reason.strip()))
        unknown = sorted(set(normalized) - _ALLOWED_REASONS)
        if unknown:
            raise ValueError(f"Unknown feedback reason: {', '.join(unknown)}.")
        return normalized

    def create(
        self,
        session_id: str,
        candidate_id: str,
        rating: int,
        accepted: bool,
        reasons: list[str] | tuple[str, ...] = (),
        comment: str | None = None,
    ) -> CandidateFeedback:
        normalized_session = session_id.strip()
        normalized_candidate = candidate_id.strip().upper()
        normalized_comment = comment.strip() if comment and comment.strip() else None
        normalized_reasons = self._normalize_reasons(reasons)

        if not normalized_session:
            raise ValueError("session_id is required.")
        if normalized_candidate not in {"A", "B", "C", "D"}:
            raise ValueError("candidate_id must be A, B, C, or D.")
        if rating < 1 or rating > 5:
            raise ValueError("rating must be between 1 and 5.")
        if normalized_comment and len(normalized_comment) > 1000:
            raise ValueError("comment must not exceed 1000 characters.")

        feedback = CandidateFeedback(
            id=uuid.uuid4().hex,
            session_id=normalized_session,
            candidate_id=normalized_candidate,
            rating=rating,
            accepted=accepted,
            reasons=normalized_reasons,
            comment=normalized_comment,
            created_at=datetime.now(UTC).isoformat(),
        )
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO candidate_feedback
                    (id, session_id, candidate_id, rating, accepted, reasons, comment, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feedback.id,
                    feedback.session_id,
                    feedback.candidate_id,
                    feedback.rating,
                    int(feedback.accepted),
                    ",".join(feedback.reasons),
                    feedback.comment,
                    feedback.created_at,
                ),
            )
        return feedback

    def list_for_session(self, session_id: str) -> tuple[CandidateFeedback, ...]:
        normalized = session_id.strip()
        if not normalized:
            raise ValueError("session_id is required.")
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, session_id, candidate_id, rating, accepted, reasons, comment, created_at
                FROM candidate_feedback
                WHERE session_id = ?
                ORDER BY created_at ASC
                """,
                (normalized,),
            ).fetchall()
        return tuple(
            CandidateFeedback(
                id=row["id"],
                session_id=row["session_id"],
                candidate_id=row["candidate_id"],
                rating=int(row["rating"]),
                accepted=bool(row["accepted"]),
                reasons=tuple(filter(None, str(row["reasons"]).split(","))),
                comment=row["comment"],
                created_at=row["created_at"],
            )
            for row in rows
        )


feedback_store = FeedbackStore()
