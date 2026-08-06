from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.http_middleware import ApiMiddleware, SlidingWindowRateLimiter
from app.settings import Settings


def test_sliding_window_rate_limiter_resets_after_window() -> None:
    limiter = SlidingWindowRateLimiter(requests=2, window_seconds=10)

    assert limiter.allow("client", now=0.0) is True
    assert limiter.allow("client", now=1.0) is True
    assert limiter.allow("client", now=2.0) is False
    assert limiter.allow("client", now=11.0) is True


def test_api_key_is_required_when_configured() -> None:
    settings = Settings(
        environment="test",
        api_key="secret",
        rate_limit_requests=100,
        enable_background_worker=False,
    )
    app = FastAPI()
    app.middleware("http")(ApiMiddleware(settings))

    @app.get("/private")
    def private() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    denied = client.get("/private")
    allowed = client.get("/private", headers={"x-api-key": "secret"})

    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert allowed.headers["x-request-id"]


def test_health_remains_public_with_api_key_enabled() -> None:
    settings = Settings(
        environment="test",
        api_key="secret",
        enable_background_worker=False,
    )
    app = FastAPI()
    app.middleware("http")(ApiMiddleware(settings))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    response = TestClient(app).get("/health")

    assert response.status_code == 200
