from __future__ import annotations

import asyncio
import base64
import logging
from datetime import UTC, datetime

from app.candidate_sessions import CandidateSessionStore, candidate_session_store
from app.comfyui import ComfyUIGenerator
from app.identity_score import rank_identity_first_candidates
from app.likeness import InsightFaceAdapter
from app.settings import Settings, get_settings
from app.workflow_jobs import PortraitWorkflowJob, PortraitWorkflowStore, portrait_workflow_store

logger = logging.getLogger(__name__)


def _age_seconds(timestamp: str) -> float:
    return max((datetime.now(UTC) - datetime.fromisoformat(timestamp)).total_seconds(), 0.0)


class WorkflowEngine:
    """Advance persisted portrait jobs through generation and identity evaluation."""

    def __init__(
        self,
        *,
        workflows: PortraitWorkflowStore | None = None,
        candidates: CandidateSessionStore | None = None,
        generator: ComfyUIGenerator | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.workflows = workflows or portrait_workflow_store
        self.candidates = candidates or candidate_session_store
        self.generator = generator or ComfyUIGenerator()
        self.settings = settings or get_settings()
        self._stop_event = asyncio.Event()

    def advance(self, job_id: str) -> PortraitWorkflowJob:
        job = self.workflows.get(job_id)
        if job.status in {"completed", "failed", "cancelled", "awaiting_selection"}:
            return job
        if _age_seconds(job.created_at) > self.settings.workflow_timeout_seconds:
            return self.workflows.update(
                job_id,
                status="failed",
                stage="workflow_timed_out",
                progress=100,
                error_code="WORKFLOW_TIMEOUT",
                error_message="The portrait workflow exceeded its configured timeout.",
            )
        if not job.prompt_id:
            return self.workflows.update(
                job_id,
                status="failed",
                stage="missing_prompt_id",
                progress=100,
                error_code="MISSING_PROMPT_ID",
                error_message="The generation provider did not return a prompt ID.",
            )

        try:
            generation = self.generator.get_job(job.prompt_id, include_images=True)
        except RuntimeError as exc:
            retry_count = int(job.payload.get("_poll_retry_count", 0)) + 1
            if retry_count > self.settings.workflow_max_retries:
                return self.workflows.update(
                    job_id,
                    status="failed",
                    stage="generation_unavailable",
                    progress=100,
                    error_code="GENERATION_UNAVAILABLE",
                    error_message=str(exc),
                    payload_patch={"_poll_retry_count": retry_count},
                )
            return self.workflows.update(
                job_id,
                stage="generation_retry_scheduled",
                payload_patch={
                    "_poll_retry_count": retry_count,
                    "last_poll_error": str(exc),
                },
            )

        if generation.status == "failed":
            return self.workflows.update(
                job_id,
                status="failed",
                stage="generation_failed",
                progress=100,
                error_code="GENERATION_FAILED",
                error_message=generation.error or "ComfyUI reported a generation failure.",
                payload_patch={"generation_status": generation.to_dict()},
            )
        if generation.status != "completed":
            return self.workflows.update(
                job_id,
                status="generating",
                stage=generation.status,
                progress=max(job.progress, 50),
                payload_patch={
                    "generation_status": generation.to_dict(),
                    "_poll_retry_count": 0,
                },
            )

        source_base64 = job.payload.get("_source_image_base64")
        if not isinstance(source_base64, str) or not source_base64:
            return self.workflows.update(
                job_id,
                status="failed",
                stage="source_image_unavailable",
                progress=100,
                error_code="SOURCE_IMAGE_UNAVAILABLE",
                error_message="The source image required for identity evaluation is unavailable.",
            )

        try:
            original_bytes = base64.b64decode(source_base64, validate=True)
            candidate_bytes = [base64.b64decode(image.image_base64, validate=True) for image in generation.images]
            ranking = rank_identity_first_candidates(
                original_bytes=original_bytes,
                candidate_bytes=candidate_bytes,
                adapter=InsightFaceAdapter(),
                likeness_threshold=self.settings.portrait_likeness_threshold,
            )
            session = self.candidates.create(generation, ranking)
        except (ValueError, RuntimeError) as exc:
            return self.workflows.update(
                job_id,
                status="failed",
                stage="identity_evaluation_failed",
                progress=100,
                error_code="IDENTITY_EVALUATION_FAILED",
                error_message=str(exc),
            )

        return self.workflows.update(
            job_id,
            status="awaiting_selection",
            stage="candidates_ready",
            progress=85,
            candidate_session_id=session.id,
            payload_patch={
                "generation_status": generation.to_dict(),
                "ranking": ranking.to_dict(),
                "_source_image_base64": None,
                "_poll_retry_count": 0,
            },
        )

    def run_once(self, limit: int = 50) -> int:
        processed = 0
        for job in self.workflows.list_active(limit=limit):
            if job.status in {"generating", "evaluating", "queued"}:
                self.advance(job.id)
                processed += 1
        self.candidates.delete_expired()
        return processed

    async def run_forever(self) -> None:
        logger.info("portrait workflow worker started")
        while not self._stop_event.is_set():
            try:
                await asyncio.to_thread(self.run_once)
            except Exception:
                logger.exception("portrait workflow worker iteration failed")
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.settings.workflow_poll_interval_seconds,
                )
            except TimeoutError:
                pass
        logger.info("portrait workflow worker stopped")

    def stop(self) -> None:
        self._stop_event.set()


workflow_engine = WorkflowEngine()
