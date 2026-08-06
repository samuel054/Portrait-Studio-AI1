from __future__ import annotations

import base64

import numpy as np

from app.candidate_sessions import CandidateSessionStore
from app.comfyui import ComfyUIImage, ComfyUIJobResult
from app.identity_score import IdentityFirstEvaluation, IdentityFirstRanking
from app.settings import Settings
from app.workflow_engine import WorkflowEngine
from app.workflow_jobs import PortraitWorkflowStore


class FakeAdapter:
    id = "fake"

    def embed(self, _image_bytes: bytes) -> np.ndarray:
        return np.array([1.0, 0.0], dtype=np.float32)


class CompletedGenerator:
    def get_job(self, prompt_id: str, include_images: bool = True) -> ComfyUIJobResult:
        assert prompt_id == "prompt-1"
        assert include_images is True
        return ComfyUIJobResult(
            prompt_id=prompt_id,
            status="completed",
            images=(
                ComfyUIImage(
                    filename="candidate.png",
                    subfolder="",
                    image_type="output",
                    content_type="image/png",
                    image_base64=base64.b64encode(b"candidate").decode("ascii"),
                ),
            ),
        )


class FailingGenerator:
    def get_job(self, _prompt_id: str, include_images: bool = True) -> ComfyUIJobResult:
        raise RuntimeError("ComfyUI unavailable")


def _ranking() -> IdentityFirstRanking:
    return IdentityFirstRanking(
        evaluations=(
            IdentityFirstEvaluation(
                index=0,
                rank=1,
                final_score=92.0,
                status="pass",
                structural_score=90.0,
                likeness_score=93.0,
                cosine_similarity=0.9,
                reasons=("Identity preserved.",),
            ),
        ),
        recommended_index=0,
        method="test",
        likeness_threshold=0.35,
    )


def _settings(tmp_path, retries: int = 3) -> Settings:
    return Settings(
        environment="test",
        portrait_workflow_db=tmp_path / "workflows.db",
        portrait_candidate_db=tmp_path / "candidates.db",
        portrait_feedback_db=tmp_path / "feedback.db",
        workflow_max_retries=retries,
        enable_background_worker=False,
    )


def test_completed_generation_creates_persistent_candidate_session(tmp_path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    workflows = PortraitWorkflowStore(settings.portrait_workflow_db)
    candidates = CandidateSessionStore(settings.portrait_candidate_db)
    engine = WorkflowEngine(
        workflows=workflows,
        candidates=candidates,
        generator=CompletedGenerator(),
        likeness_adapter=FakeAdapter(),
        settings=settings,
    )
    monkeypatch.setattr("app.workflow_engine.rank_identity_first_candidates", lambda **_: _ranking())
    job = workflows.create(
        filename="source.png",
        style_id="soft_watercolor",
        prompt_id="prompt-1",
        payload={"_source_image_base64": base64.b64encode(b"source").decode("ascii")},
    )

    updated = engine.advance(job.id)

    assert updated.status == "awaiting_selection"
    assert updated.stage == "candidates_ready"
    assert updated.candidate_session_id is not None
    session = candidates.get(updated.candidate_session_id)
    assert session.status == "awaiting_selection"
    assert session.candidates[0].id == "A"
    assert "_source_image_base64" not in updated.to_dict()["payload"]


def test_polling_failure_stops_after_configured_retries(tmp_path) -> None:
    settings = _settings(tmp_path, retries=1)
    workflows = PortraitWorkflowStore(settings.portrait_workflow_db)
    engine = WorkflowEngine(
        workflows=workflows,
        candidates=CandidateSessionStore(settings.portrait_candidate_db),
        generator=FailingGenerator(),
        likeness_adapter=FakeAdapter(),
        settings=settings,
    )
    job = workflows.create(
        filename="source.png",
        style_id="soft_watercolor",
        prompt_id="prompt-1",
        payload={"_source_image_base64": base64.b64encode(b"source").decode("ascii")},
    )

    first = engine.advance(job.id)
    second = engine.advance(job.id)

    assert first.status == "generating"
    assert first.stage == "generation_retry_scheduled"
    assert second.status == "failed"
    assert second.error_code == "GENERATION_UNAVAILABLE"


def test_missing_prompt_id_fails_cleanly(tmp_path) -> None:
    settings = _settings(tmp_path)
    workflows = PortraitWorkflowStore(settings.portrait_workflow_db)
    engine = WorkflowEngine(
        workflows=workflows,
        candidates=CandidateSessionStore(settings.portrait_candidate_db),
        generator=CompletedGenerator(),
        likeness_adapter=FakeAdapter(),
        settings=settings,
    )
    job = workflows.create(
        filename="source.png",
        style_id="soft_watercolor",
        prompt_id=None,
        payload={"_source_image_base64": base64.b64encode(b"source").decode("ascii")},
    )

    updated = engine.advance(job.id)

    assert updated.status == "failed"
    assert updated.error_code == "MISSING_PROMPT_ID"
