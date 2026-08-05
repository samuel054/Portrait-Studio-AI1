from fastapi.testclient import TestClient

from app.main import app
from app.styles import get_style, list_styles

client = TestClient(app)


def test_style_catalog_contains_identity_first_styles() -> None:
    styles = list_styles()

    assert len(styles) == 5
    assert all(style["identity_priority"] in {"high", "very_high"} for style in styles)


def test_style_catalog_filters_by_category() -> None:
    styles = list_styles("illustration")

    assert len(styles) == 2
    assert all(style["category"] == "illustration" for style in styles)


def test_get_style_returns_none_for_unknown_id() -> None:
    assert get_style("unknown") is None


def test_styles_endpoint_returns_catalog() -> None:
    response = client.get("/v1/styles")

    assert response.status_code == 200
    assert response.json()["count"] == 5


def test_style_detail_returns_404_for_unknown_style() -> None:
    response = client.get("/v1/styles/not-a-style")

    assert response.status_code == 404
