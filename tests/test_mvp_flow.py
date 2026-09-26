"""HTTP workflow integration. Only the image engine and face model are test doubles."""

from __future__ import annotations

import base64
import io
import json
from datetime import UTC, datetime, timedelta
from dataclasses import replace

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.candidate_sessions import CandidateSessionStore
from app.comfyui import ComfyUIConfig, ComfyUIGenerator
from app.generators import GenerationRequest
from app.identity import FaceRegion, IdentityReport
from app.likeness import _normalize
from app.main import app
from app.planner import build_portrait_plan
from app.refinement import build_refinement_plan
from app.settings import Settings
from app.workflow_engine import WorkflowEngine
from app.workflow_jobs import PortraitWorkflowStore


def png(value: int = 180) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (256, 256), (value, value, value)).save(output, "PNG")
    return output.getvalue()


class FakeEmbeddingModel:
    id = "test_model_not_real_inference"

    def embed(self, data):
        value = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR).mean()
        return np.array([1.0 if value > 100 else -1.0, 0.0])


@pytest.fixture
def flow(tmp_path, monkeypatch):
    workflows = PortraitWorkflowStore(tmp_path / "jobs.db")
    candidates = CandidateSessionStore(tmp_path / "candidates.db")
    settings = Settings(environment="test", enable_background_worker=False)
    engine = WorkflowEngine(
        workflows=workflows,
        candidates=candidates,
        likeness_adapter=FakeEmbeddingModel(),
        settings=settings,
    )
    for module in ["app.main", "app.candidate_api", "app.refinement_api", "app.render_api"]:
        monkeypatch.setattr(module + ".portrait_workflow_store", workflows)
    for module in ["app.candidate_api", "app.refinement_api", "app.render_api", "app.feedback_api"]:
        monkeypatch.setattr(module + ".candidate_session_store", candidates)
    monkeypatch.setattr("app.main.workflow_engine", engine)
    monkeypatch.setattr("app.runtime.workflow_engine", engine)
    identity = IdentityReport(1, (FaceRegion(64, 64, 128, 128, 0.25),), 0.25, "ready", "low", ())
    for module in ["app.main", "app.evaluator", "app.enhancer"]:
        monkeypatch.setattr(module + ".analyze_identity", lambda _: identity)
    monkeypatch.setattr("app.evaluator._quality_score", lambda _: 90.0)
    submitted = []

    class Response:
        headers = type("Headers", (), {"get_content_type": lambda _: "image/png"})()

        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return self.body

    def transport(request, **kwargs):
        url = request if isinstance(request, str) else request.full_url
        if url.endswith("/upload/image"):
            return Response(b'{"name":"portrait.png","subfolder":"portrait-studio-ai"}')
        if url.endswith("/prompt"):
            submitted.append(json.loads(request.data))
            return Response(json.dumps({"prompt_id": f"prompt-{len(submitted)}"}).encode())
        if "/history/" in url:
            prompt_id = url.rsplit("/", 1)[1]
            return Response(
                json.dumps(
                    {
                        prompt_id: {
                            "status": {"completed": True, "status_str": "success"},
                            "outputs": {
                                "6": {
                                    "images": [
                                        {"filename": name, "type": "output"}
                                        for name in ["good.png", "other-person.png", "second.png"]
                                    ]
                                }
                            },
                        }
                    }
                ).encode()
            )
        if "/view?" in url:
            return Response(png(30 if "other-person" in url else 180))
        raise AssertionError(url)

    monkeypatch.setattr("urllib.request.urlopen", transport)
    return TestClient(app), workflows, candidates, engine, submitted


def test_upload_select_refine_reselect_and_export_use_checked_candidates(flow):
    client, workflows, candidates, engine, submitted = flow
    created = client.post(
        "/v1/portrait-jobs",
        files={"file": ("me.png", png(), "image/png")},
        data={"style_id": "soft_lifestyle_illustration", "candidate_count": "3"},
    )
    assert created.status_code == 202, created.text
    job_id = created.json()["job"]["id"]
    ready = client.get(f"/v1/portrait-jobs/{job_id}").json()["job"]
    assert ready["status"] == "awaiting_selection", ready
    assert "image_base64" not in json.dumps(ready)
    session_id = ready["candidate_session_id"]
    shown = client.get(f"/v1/candidate-sessions/{session_id}").json()["session"]
    assert [item["id"] for item in shown["candidates"]] == ["A", "B"]
    assert all(item["filename"] != "other-person.png" for item in shown["candidates"])
    original_anchor = candidates.source_bytes(session_id)
    for choice in ["A", "B"]:
        selected = client.post(
            f"/v1/candidate-sessions/{session_id}/selection", json={"candidate_id": choice}
        )
        assert selected.json()["session"]["selected_candidate_id"] == choice
        assert selected.json()["session"]["candidates"][0]["image_base64"]
    refinement = client.post(
        f"/v1/candidate-sessions/{session_id}/refine",
        json={
            "style_id": "soft_lifestyle_illustration",
            "operation": "lighting",
            "instruction": "Soften the lighting.",
            "strength": 0.2,
        },
    )
    assert refinement.status_code == 202, refinement.text
    refined_job = refinement.json()["job"]
    assert "image_base64" not in json.dumps(refinement.json())
    assert submitted[-1]["prompt"]["4"]["inputs"]["denoise"] == 0.2
    assert submitted[-1]["prompt"]["12"]["inputs"]["amount"] == 2
    refined_ready = client.get(f"/v1/portrait-jobs/{refined_job['id']}").json()["job"]
    refined_id = refined_ready["candidate_session_id"]
    assert candidates.source_bytes(refined_id) == original_anchor
    client.post(f"/v1/candidate-sessions/{refined_id}/selection", json={"candidate_id": "B"})
    for fmt in ["png", "jpeg", "webp"]:
        exported = client.post(
            f"/v1/candidate-sessions/{refined_id}/render", json={"output_format": fmt}
        )
        assert exported.status_code == 200, exported.text
        result = exported.json()["render"]
        assert result["candidate_id"] == "B"
        with Image.open(io.BytesIO(base64.b64decode(result["image_base64"]))) as image:
            assert image.format.lower() == fmt
    assert workflows.find_by_candidate_session(refined_id).status == "completed"


def test_uncertain_or_rejected_images_cannot_leak_through_status(flow):
    client, *_ = flow
    response = client.get("/v1/generations/prompt-1?include_images=true")
    assert response.status_code == 200
    assert response.json()["generation"]["images"] == []


def test_only_pass_candidates_are_exposed(flow):
    client, workflows, candidates, engine, _ = flow
    from tests.test_candidate_sessions import _job, _ranking

    ranking = _ranking()
    ranking = replace(
        ranking, evaluations=tuple(replace(item, status="review") for item in ranking.evaluations)
    )
    with pytest.raises(ValueError, match="All generated candidates failed"):
        candidates.create(_job(), ranking)


def test_expired_session_and_job_cannot_be_reopened(flow):
    _, workflows, candidates, _, _ = flow
    from tests.test_candidate_sessions import _job, _ranking

    session = candidates.create(_job(), _ranking(), source_image_bytes=png())
    job = workflows.create(
        filename=None,
        style_id="soft_watercolor",
        prompt_id="p",
        payload={"_source_image_base64": "private"},
    )
    old = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    with candidates._connect() as conn:
        conn.execute("UPDATE candidate_sessions SET created_at = ?", (old,))
    with workflows._connect() as conn:
        conn.execute("UPDATE portrait_workflow_jobs SET created_at = ?", (old,))
    with pytest.raises(KeyError, match="expired"):
        candidates.source_bytes(session.id)
    with pytest.raises(KeyError, match="expired"):
        workflows.get(job.id)


def test_real_template_batches_and_uses_numeric_sampling_options():
    generator = ComfyUIGenerator(ComfyUIConfig())
    plan = build_refinement_plan(
        style_id="soft_lifestyle_illustration",
        operation="lighting",
        instruction="Softer light",
        strength=0.17,
    )
    payload = generator.build_payload(
        GenerationRequest(plan, "portrait.png", seed=7, candidate_count=4)
    )["prompt"]
    assert payload["4"]["inputs"]["seed"] == 7
    assert payload["4"]["inputs"]["denoise"] == 0.17
    assert payload["12"]["inputs"]["amount"] == 4
    assert "REPLACE_WITH" not in json.dumps(payload) and "{{" not in json.dumps(payload)
    a = generator.build_payload(
        GenerationRequest(build_portrait_plan("soft_lifestyle_illustration"), "portrait.png")
    )
    b = generator.build_payload(
        GenerationRequest(build_portrait_plan("soft_lifestyle_illustration"), "portrait.png")
    )
    assert a["prompt"]["4"]["inputs"]["seed"] != b["prompt"]["4"]["inputs"]["seed"]


@pytest.mark.parametrize("vector", [[float("nan"), 0], [float("inf"), 0], [], [[1, 0]], [0, 0]])
def test_invalid_embedding_fails_closed(vector):
    with pytest.raises(ValueError):
        _normalize(np.asarray(vector))


def test_upload_removes_exif_and_applies_orientation():
    source = Image.new("RGB", (64, 96), "red")
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = "private photo metadata"
    image = io.BytesIO()
    source.save(image, "JPEG", exif=exif)
    from app.uploads import normalize_upload

    with Image.open(io.BytesIO(normalize_upload(image.getvalue()))) as clean:
        assert clean.size == (96, 64)
        assert not clean.getexif()


def test_alpha_is_preserved_in_png_and_webp_and_flattened_in_jpeg():
    from app.final_render import render_selected_candidate

    image = io.BytesIO()
    Image.new("RGBA", (300, 300), (255, 0, 0, 0)).save(image, "PNG")
    for fmt in ["png", "webp", "jpeg"]:
        result = render_selected_candidate(
            candidate_id="A",
            source_filename="portrait.png",
            image_base64=base64.b64encode(image.getvalue()).decode(),
            output_format=fmt,
        )
        with Image.open(io.BytesIO(base64.b64decode(result.image_base64))) as output:
            if fmt == "jpeg":
                assert min(output.getpixel((0, 0))) >= 250
            else:
                assert output.getchannel("A").getextrema() == (0, 0)
