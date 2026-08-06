from __future__ import annotations

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _png_bytes() -> bytes:
    image = np.full((64, 64, 3), 160, dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


def test_public_discovery_requests() -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/v1/styles").status_code == 200
    assert client.get("/v1/generators").status_code == 200


def test_unknown_style_and_workflow_return_not_found() -> None:
    assert client.get("/v1/styles/does-not-exist").status_code == 404
    assert client.get("/v1/portrait-jobs/does-not-exist?refresh=false").status_code == 404


def test_unknown_candidate_session_requests_return_not_found() -> None:
    session_id = "does-not-exist"
    assert client.get(f"/v1/candidate-sessions/{session_id}").status_code == 404
    assert (
        client.post(
            f"/v1/candidate-sessions/{session_id}/selection",
            json={"candidate_id": "A"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/v1/candidate-sessions/{session_id}/render",
            json={"output_format": "png"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/v1/candidate-sessions/{session_id}/refine",
            json={
                "style_id": "soft_lifestyle_illustration",
                "operation": "adjust_background",
                "instruction": "Use a clean neutral background.",
            },
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/v1/candidate-sessions/{session_id}/feedback",
            json={
                "candidate_id": "A",
                "rating": 5,
                "accepted": True,
            },
        ).status_code
        == 404
    )
    assert client.get(f"/v1/candidate-sessions/{session_id}/feedback").status_code == 404


def test_plan_and_dry_run_generation_request_contracts() -> None:
    plan = client.post(
        "/v1/plans",
        json={"style_id": "soft_lifestyle_illustration"},
    )
    assert plan.status_code == 200
    assert plan.json()["next_step"] == "generation"

    generation = client.post(
        "/v1/generate",
        json={
            "style_id": "soft_lifestyle_illustration",
            "generator_id": "dry_run",
            "image_reference": "portrait-studio-ai/source.png",
            "candidate_count": 2,
        },
    )
    assert generation.status_code == 200
    assert generation.json()["generation"]["status"] == "validated"


def test_upload_validation_is_consistent_across_image_routes() -> None:
    corrupt = b"not-an-image"
    for path, field_name in (
        ("/v1/analyze", "file"),
        ("/v1/enhance", "file"),
        ("/v1/comfyui/images", "file"),
        ("/v1/candidate-sessions", "original"),
    ):
        data = {"prompt_id": "prompt-1"} if path == "/v1/candidate-sessions" else None
        response = client.post(
            path,
            files={field_name: ("broken.png", corrupt, "image/png")},
            data=data,
        )
        assert response.status_code == 400, (path, response.text)


def test_candidate_session_accepts_valid_image_before_provider_check(monkeypatch) -> None:
    def unavailable(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("app.candidate_api.ComfyUIGenerator.get_job", unavailable)
    response = client.post(
        "/v1/candidate-sessions",
        files={"original": ("source.png", _png_bytes(), "image/png")},
        data={"prompt_id": "prompt-1"},
    )
    assert response.status_code == 503
