from fastapi.testclient import TestClient

from app.main import app
from app.planner import build_portrait_plan


client = TestClient(app)


def test_build_plan_contains_identity_and_negative_rules() -> None:
    plan = build_portrait_plan(
        style_id="soft_lifestyle_illustration",
        crop="half_body",
        background="replace",
        output_type="canvas",
    )

    assert plan.style_id == "soft_lifestyle_illustration"
    assert "recognizable facial identity" in plan.prompt
    assert "Do not invent a different face" in plan.prompt
    assert any("Preserve the original clothing" in rule for rule in plan.style_rules)


def test_build_plan_rejects_unsupported_style_combination() -> None:
    try:
        build_portrait_plan(
            style_id="storybook_character",
            background="transparent",
            output_type="canvas",
        )
    except ValueError as exc:
        assert "does not support" in str(exc)
    else:
        raise AssertionError("Expected unsupported combination to fail")


def test_plan_endpoint_returns_generation_ready_plan() -> None:
    response = client.post(
        "/v1/plans",
        json={
            "style_id": "friendly_caricature",
            "crop": "face",
            "background": "transparent",
            "output_type": "social",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["next_step"] == "generation"
    assert payload["plan"]["style_id"] == "friendly_caricature"


def test_plan_endpoint_returns_clear_validation_error() -> None:
    response = client.post(
        "/v1/plans",
        json={
            "style_id": "premium_chibi",
            "background": "keep",
            "output_type": "sticker",
        },
    )

    assert response.status_code == 422
    assert "does not support" in response.json()["detail"]
