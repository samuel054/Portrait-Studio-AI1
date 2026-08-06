from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.workflow_jobs import PortraitWorkflowStore

client = TestClient(app)


@dataclass
class FakeImageReport:
    needs_enhancement: bool = True

    def to_dict(self) -> dict[str, object]:
        return {"needs_enhancement": self.needs_enhancement}


@dataclass
class FakeIdentityReport:
    identity_readiness: str = "ready"

    def to_dict(self) -> dict[str, object]:
        return {"identity_readiness": self.identity_readiness}


@dataclass
class FakeEnhancementReport:
    identity_after: FakeIdentityReport

    def to_dict(self) -> dict[str, object]:
        return {"identity_after": self.identity_after.to_dict()}


class FakeUpload:
    image_reference = "portrait-studio-ai/source.png"

    def to_dict(self) -> dict[str, object]:
        return {"image_reference": self.image_reference}


class FakeGeneration:
    status = "queued"

    def to_dict(self) -> dict[str, object]:
        return {"status": self.status, "request_payload": {"prompt_id": "prompt-1"}}


class FakeCompletedGeneration:
    status = "completed"

    def to_dict(self) -> dict[str, object]:
        return {"status": self.status, "images": []}


def make_image_bytes() -> bytes:
    image = np.full((128, 128, 3), 170, dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


def test_portrait_job_runs_full_pipeline(monkeypatch, tmp_path) -> None:
    store = PortraitWorkflowStore(tmp_path / "workflows.db")
    monkeypatch.setattr("app.main.portrait_workflow_store", store)
    monkeypatch.setattr("app.main.analyze_image", lambda _data: FakeImageReport())
    monkeypatch.setattr("app.main.analyze_identity", lambda _data: FakeIdentityReport())
    monkeypatch.setattr(
        "app.main.enhance_image",
        lambda _data: (b"enhanced", FakeEnhancementReport(FakeIdentityReport())),
    )
    monkeypatch.setattr(
        "app.main.ComfyUIGenerator.upload_image",
        lambda *_args, **_kwargs: FakeUpload(),
    )
    monkeypatch.setattr("app.main.run_generation", lambda *_args, **_kwargs: FakeGeneration())

    response = client.post(
        "/v1/portrait-jobs",
        files={"file": ("source.png", make_image_bytes(), "image/png")},
        data={
            "style_id": "soft_lifestyle_illustration",
            "candidate_count": "2",
            "seed": "42",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job"]["status"] == "generating"
    assert payload["job"]["prompt_id"] == "prompt-1"
    assert payload["job"]["payload"]["enhancement_applied"] is True
    assert payload["job"]["payload"]["image_reference"] == "portrait-studio-ai/source.png"
    assert payload["next_step"] == "poll_portrait_job"

    stored = store.get(payload["job"]["id"])
    assert stored.prompt_id == "prompt-1"
    assert stored.style_id == "soft_lifestyle_illustration"


def test_portrait_job_status_refreshes_completed_generation(monkeypatch, tmp_path) -> None:
    store = PortraitWorkflowStore(tmp_path / "workflows.db")
    job = store.create(
        filename="source.png",
        style_id="soft_watercolor",
        prompt_id="prompt-2",
        payload={"generation": {"status": "queued"}},
    )
    monkeypatch.setattr("app.main.portrait_workflow_store", store)
    monkeypatch.setattr(
        "app.main.ComfyUIGenerator.get_job",
        lambda *_args, **_kwargs: FakeCompletedGeneration(),
    )

    response = client.get(f"/v1/portrait-jobs/{job.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["job"]["status"] == "evaluating"
    assert payload["job"]["stage"] == "generation_completed"
    assert payload["next_step"] == "create_candidate_session"


def test_portrait_job_status_returns_404_for_unknown_job(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.main.portrait_workflow_store", PortraitWorkflowStore(tmp_path / "workflows.db")
    )

    response = client.get("/v1/portrait-jobs/missing")

    assert response.status_code == 404


def test_portrait_job_rejects_unusable_identity(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.main.portrait_workflow_store", PortraitWorkflowStore(tmp_path / "workflows.db")
    )
    monkeypatch.setattr("app.main.analyze_image", lambda _data: FakeImageReport(False))
    monkeypatch.setattr(
        "app.main.analyze_identity",
        lambda _data: FakeIdentityReport("needs_better_photo"),
    )

    response = client.post(
        "/v1/portrait-jobs",
        files={"file": ("source.png", make_image_bytes(), "image/png")},
        data={"style_id": "soft_lifestyle_illustration"},
    )

    assert response.status_code == 422
    assert "better photo" in response.json()["detail"].lower()
