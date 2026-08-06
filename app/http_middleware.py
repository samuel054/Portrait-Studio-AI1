from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict, deque
from threading import RLock

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from app.settings import Settings, get_settings

logger = logging.getLogger(__name__)
_PUBLIC_PATHS = {"/health", "/ready", "/docs", "/openapi.json", "/redoc"}


class SlidingWindowRateLimiter:
    def __init__(self, requests: int, window_seconds: int) -> None:
        self.requests = requests
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = RLock()

    def allow(self, key: str, now: float | None = None) -> bool:
        timestamp = now if now is not None else time.monotonic()
        cutoff = timestamp - self.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.requests:
                return False
            events.append(timestamp)
            return True


class ApiMiddleware:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.limiter = SlidingWindowRateLimiter(
            self.settings.rate_limit_requests,
            self.settings.rate_limit_window_seconds,
        )

    async def __call__(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        started = time.perf_counter()
        client_key = request.client.host if request.client else "unknown"

        if request.url.path not in _PUBLIC_PATHS:
            if self.settings.api_key:
                supplied = request.headers.get("x-api-key")
                if supplied != self.settings.api_key:
                    return JSONResponse(
                        status_code=401,
                        content={
                            "detail": "A valid API key is required.",
                            "request_id": request_id,
                        },
                        headers={"x-request-id": request_id},
                    )
            if not self.limiter.allow(client_key):
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Rate limit exceeded.",
                        "request_id": request_id,
                    },
                    headers={
                        "x-request-id": request_id,
                        "retry-after": str(self.settings.rate_limit_window_seconds),
                    },
                )

        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled request error", extra={"request_id": request_id})
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "An unexpected server error occurred.",
                    "request_id": request_id,
                },
                headers={"x-request-id": request_id},
            )

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["x-request-id"] = request_id
        response.headers["x-process-time-ms"] = str(duration_ms)
        logger.info(
            "request completed method=%s path=%s status=%s duration_ms=%s request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        return response
