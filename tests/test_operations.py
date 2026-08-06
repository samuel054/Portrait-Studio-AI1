from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_reports_backend_version() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["version"] == app.version


def test_openapi_contains_core_backend_contract() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    expected = {
        "/v1/analyze",
        "/v1/enhance",
        "/v1/styles",
        "/v1/portrait-jobs",
        "/v1/portrait-jobs/{job_id}",
        "/v1/candidate-sessions",
        "/v1/candidate-sessions/{session_id}/selection",
        "/v1/candidate-sessions/{session_id}/render",
        "/v1/candidate-sessions/{session_id}/refine",
        "/v1/candidate-sessions/{session_id}/feedback",
    }
    assert expected.issubset(paths)


def test_corrupt_upload_is_rejected_before_analysis() -> None:
    response = client.post(
        "/v1/analyze",
        files={"file": ("broken.png", b"not-an-image", "image/png")},
    )

    assert response.status_code == 400
    assert "corrupt" in response.json()["detail"].lower()


def test_unsupported_upload_type_is_rejected() -> None:
    response = client.post(
        "/v1/analyze",
        files={"file": ("portrait.gif", b"GIF89a", "image/gif")},
    )

    assert response.status_code == 415
