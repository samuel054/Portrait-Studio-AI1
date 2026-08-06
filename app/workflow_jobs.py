from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
VALID_STATUSES = {
    "queued",
    "analyzing",
    "enhancing",
    "generating",
    "evaluating",
    "awaiting_selection",
    "refining",
    "rendering",
    "completed",
    "failed",
    "cancelled",
}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _default_database_path() -> Path:
    return Path(os.getenv("PORTRAIT_WORKFLOW_DB", "portrait_workflows.db"))


@dataclass(frozen=True)
class PortraitWorkflowJob:
    id: str
    status: str
    stage: str
    progress: int
    prompt_id: str | None
    candidate_session_id: str | None
    filename: str | None
    style_id: str
    error_code: str | None
    error_message: str | None
    payload: dict[str, Any]
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "stage": self.stage,
            "progress": self.progress,
            "prompt_id": self.prompt_id,
            "candidate_session_id": self.candidate_session_id,
            "filename": self.filename,
            "style_id": self.style_id,
            "error": (
                {"code": self.error_code, "message": self.error_message}
                if self.error_code or self.error_message
                else None
            ),
            "payload": self.payload,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class PortraitWorkflowStore:
    """Small persistent workflow store for the local MVP.

    SQLite is intentionally hidden behind this repository-style class so the
    implementation can later move to PostgreSQL without changing API routes.
    """

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
                CREATE TABLE IF NOT EXISTS portrait_workflow_jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    progress INTEGER NOT NULL,
                    prompt_id TEXT,
                    candidate_session_id TEXT,
                    filename TEXT,
                    style_id TEXT NOT NULL,
                    error_code TEXT,
                    error_message TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_workflow_prompt_id "
                "ON portrait_workflow_jobs(prompt_id)"
            )

    def create(
        self,
        *,
        filename: str | None,
        style_id: str,
        prompt_id: str | None,
        payload: dict[str, Any],
        status: str = "generating",
        stage: str = "generation_queued",
        progress: int = 45,
    ) -> PortraitWorkflowJob:
        self._validate_status(status)
        self._validate_progress(progress)
        job_id = str(uuid.uuid4())
        timestamp = _utc_now()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO portrait_workflow_jobs (
                    id, status, stage, progress, prompt_id, candidate_session_id,
                    filename, style_id, error_code, error_message, payload_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, NULL, NULL, ?, ?, ?)
                """,
                (
                    job_id,
                    status,
                    stage,
                    progress,
                    prompt_id,
                    filename,
                    style_id,
                    json.dumps(payload, separators=(",", ":"), sort_keys=True),
                    timestamp,
                    timestamp,
                ),
            )
        return self.get(job_id)

    def get(self, job_id: str) -> PortraitWorkflowJob:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM portrait_workflow_jobs WHERE id = ?", (job_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Portrait workflow job '{job_id}' was not found.")
        return self._from_row(row)

    def update(
        self,
        job_id: str,
        *,
        status: str | None = None,
        stage: str | None = None,
        progress: int | None = None,
        candidate_session_id: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        payload_patch: dict[str, Any] | None = None,
    ) -> PortraitWorkflowJob:
        current = self.get(job_id)
        next_status = status or current.status
        next_stage = stage or current.stage
        next_progress = current.progress if progress is None else progress
        self._validate_status(next_status)
        self._validate_progress(next_progress)
        if current.status in TERMINAL_STATUSES and next_status != current.status:
            raise ValueError("A terminal portrait workflow cannot transition to another status.")

        payload = dict(current.payload)
        if payload_patch:
            payload.update(payload_patch)

        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE portrait_workflow_jobs
                SET status = ?, stage = ?, progress = ?, candidate_session_id = ?,
                    error_code = ?, error_message = ?, payload_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    next_status,
                    next_stage,
                    next_progress,
                    candidate_session_id or current.candidate_session_id,
                    error_code,
                    error_message,
                    json.dumps(payload, separators=(",", ":"), sort_keys=True),
                    _utc_now(),
                    job_id,
                ),
            )
        return self.get(job_id)

    @staticmethod
    def _validate_status(status: str) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"Unsupported portrait workflow status: {status}")

    @staticmethod
    def _validate_progress(progress: int) -> None:
        if not 0 <= progress <= 100:
            raise ValueError("Workflow progress must be between 0 and 100.")

    @staticmethod
    def _from_row(row: sqlite3.Row) -> PortraitWorkflowJob:
        return PortraitWorkflowJob(
            id=row["id"],
            status=row["status"],
            stage=row["stage"],
            progress=row["progress"],
            prompt_id=row["prompt_id"],
            candidate_session_id=row["candidate_session_id"],
            filename=row["filename"],
            style_id=row["style_id"],
            error_code=row["error_code"],
            error_message=row["error_message"],
            payload=json.loads(row["payload_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


portrait_workflow_store = PortraitWorkflowStore()
