from fastapi.testclient import TestClient

from app.generators import GenerationRequest, get_generator, list_generators, run_generation
from app.main import app
from app.planner import build_portrait_plan

client = TestClient(app)


def test_generator_registry_exposes_supported_generators() -> None:
    items = list_generators()
    by_id = {item["id"]: item for item in items}

    assert set(by_id) == {"dry_run", "comfyui"}
    assert by_id["dry_run"]["open_source"] is True
    assert by_id["comfyui"]["open_source"] is True
    assert by_id["comfyui"]["local_execution"] is True
    assert get_generator("dry_run") is not None
    assert get_generator("comfyui") is not None


def test_dry_run_builds_model_payload() -> None:
    plan = build_portrait_plan("soft_lifestyle_illustration")
    result = run_generation(
        "dry_run",
        GenerationRequest(
            plan=plan,
            image_reference="memory://portrait-001",
            seed=42,
            candidate_count=4,
        ),
    )

    assert result.status == "validated"
    assert result.candidate_count == 4
    assert result.request_payload["seed"] == 42
    assert result.request_payload["style_id"] == "soft_lifestyle_illustration"
    assert "different face" in str(result.request_payload["negative_prompt"])


def test_unknown_generator_is_rejected() -> None:
    plan = build_portrait_plan("soft_lifestyle_illustration")

    try:
        run_generation(
            "missing",
            GenerationRequest(plan=plan, image_reference="memory://portrait-001"),
        )
    except ValueError as exc:
        assert "Unknown generator" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_generator_endpoints() -> None:
    registry = client.get("/v1/generators")
    assert registry.status_code == 200
    generators = {item["id"] for item in registry.json()["generators"]}
    assert generators == {"dry_run", "comfyui"}

    response = client.post(
        "/v1/generate",
        json={
            "generator_id": "dry_run",
            "image_reference": "memory://portrait-001",
            "style_id": "soft_lifestyle_illustration",
            "crop": "half_body",
            "background": "keep",
            "output_type": "social",
            "candidate_count": 2,
            "seed": 7,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["generation"]["status"] == "validated"
    assert body["generation"]["candidate_count"] == 2
    assert body["next_step"] == "model_inference"
