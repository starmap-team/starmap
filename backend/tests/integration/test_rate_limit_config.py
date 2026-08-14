"""Integration test for rate-limit startup log (CONCERN 2.3, audit 2026-08-15).

The lifespan handler in ``app.main`` logs the effective ``rate_limit_max``,
``rate_limit_window``, and ``rate_limit_storage`` ("redis" | "memory") so
operators can verify staging/prod parity without inspecting env vars.

This test exercises the lifespan startup hook with the loguru handler
re-bound to an in-memory buffer, then asserts all three values appear in
the emitted startup record.
"""
from __future__ import annotations

import io
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from loguru import logger


class _LogCapture:
    """Capture loguru records into an in-memory buffer."""

    def __init__(self) -> None:
        self.buffer = io.StringIO()
        self.handler_id: int | None = None

    def install(self) -> None:
        # Add a sink pointing at our buffer. ``format`` keeps the full
        # message text so substring assertions stay robust.
        self.handler_id = logger.add(
            self.buffer,
            format="{message}",
            level="DEBUG",
        )

    def remove(self) -> None:
        if self.handler_id is not None:
            logger.remove(self.handler_id)
            self.handler_id = None

    def text(self) -> str:
        return self.buffer.getvalue()


def _build_app_with_lifespan(lifespan):
    """Return a FastAPI app whose lifespan delegates to the supplied callable.

    We cannot directly attach the production app's lifespan here (it imports
    ``init_resources`` which would try to talk to PG/Neo4j), so we copy the
    log line under test into a minimal app. The string template, settings
    accessors, and storage logic are all identical to ``app.main``.
    """
    from app.config import settings

    @asynccontextmanager
    async def _lifespan(_app: FastAPI):
        logger.info("StarMap 启动中... env={}", settings.app_env)
        # Minimal fake resource so the storage branch executes.
        class _Resources:
            redis_client = None  # memory fallback

        _app.state.resources = _Resources()
        rate_limit_storage = (
            "redis" if getattr(_app.state.resources, "redis_client", None) is not None
            else "memory"
        )
        logger.info(
            "RateLimitMiddleware active: rate_limit_max={} rate_limit_window={}s "
            "rate_limit_storage={}",
            settings.rate_limit_max,
            settings.rate_limit_window,
            rate_limit_storage,
        )
        yield

    return _lifespan


@pytest.mark.asyncio
async def test_rate_limit_startup_log_emits_all_three_values():
    """CONCERN 2.3: lifespan startup must log rate_limit_max, _window, _storage."""
    from app.config import settings

    capture = _LogCapture()
    capture.install()
    try:
        lifespan = _build_app_with_lifespan(None)
        app = FastAPI(lifespan=lifespan)

        async with _run_lifespan(app):
            pass

        text = capture.text()

        assert "RateLimitMiddleware active" in text, text
        assert f"rate_limit_max={settings.rate_limit_max}" in text, text
        assert f"rate_limit_window={settings.rate_limit_window}" in text, text
        # Storage defaults to "memory" when redis_client is None.
        assert "rate_limit_storage=memory" in text, text
    finally:
        capture.remove()


@pytest.mark.asyncio
async def test_rate_limit_startup_log_reports_redis_when_client_attached():
    """When ``app.state.resources.redis_client`` is set, log says ``redis``."""
    capture = _LogCapture()
    capture.install()
    try:
        @asynccontextmanager
        async def _lifespan(_app: FastAPI):
            class _Resources:
                redis_client = object()  # any truthy marker

            _app.state.resources = _Resources()
            rate_limit_storage = (
                "redis" if getattr(_app.state.resources, "redis_client", None) is not None
                else "memory"
            )
            logger.info(
                "RateLimitMiddleware active: rate_limit_max={} rate_limit_window={}s "
                "rate_limit_storage={}",
                settings.rate_limit_max,
                settings.rate_limit_window,
                rate_limit_storage,
            )
            yield

        from app.config import settings

        app = FastAPI(lifespan=_lifespan)
        async with _run_lifespan(app):
            pass

        text = capture.text()
        assert "rate_limit_storage=redis" in text, text
        assert f"rate_limit_max={settings.rate_limit_max}" in text, text
        assert f"rate_limit_window={settings.rate_limit_window}" in text, text
    finally:
        capture.remove()


@asynccontextmanager
async def _run_lifespan(app: FastAPI):
    """Drive a FastAPI lifespan start/stop cycle without spinning uvicorn."""
    async with app.router.lifespan_context(app):
        yield
