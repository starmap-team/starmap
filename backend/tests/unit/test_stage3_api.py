"""Stage 3 API contract tests."""
from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.api.v1.quality import _build_quality_dashboard
from app.dependencies import get_db_session
from app.main import app


class FakeResult:
    def __init__(self, value):
        self.value = value

    def one(self):
        return self.value

    def all(self):
        return self.value


class FakeAsyncSession:
    def __init__(self, results):
        self.results = list(results)

    async def execute(self, _stmt):
        return FakeResult(self.results.pop(0))


@pytest.mark.asyncio
async def test_quality_dashboard_builder_aggregates_metrics():
    session = FakeAsyncSession(
        [
            (0.9, 0.8, 0.85),
            (10, 2, 1),
        ]
    )

    dashboard = await _build_quality_dashboard(session)

    assert dashboard.report.precision == 0.9
    assert dashboard.report.recall == 0.8
    assert dashboard.report.f1 == 0.85
    assert dashboard.total_extractions == 10
    assert dashboard.pending_review == 2
    assert dashboard.hallucination_rate == 0.1


def test_quality_dashboard_endpoint_contract(client):
    async def override_session():
        yield FakeAsyncSession([(0.0, 0.0, 0.0), (0, 0, 0)])

    app.dependency_overrides[get_db_session] = override_session
    try:
        resp = client.get("/api/v1/quality/dashboard")
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"report", "total_extractions", "pending_review", "hallucination_rate"}
    assert set(body["report"]) == {"precision", "recall", "f1", "warning_level", "details"}


def test_evolution_analyze_queues_task(client):
    task = type("Task", (), {"id": "task-123"})()
    with pytest.MonkeyPatch.context() as monkeypatch:
        delay = Mock(return_value=task)
        monkeypatch.setattr("app.api.v1.evolution.analyze_evolution_trends.delay", delay)
        resp = client.post("/api/v1/evolution/analyze", params={"days": 30})

    assert resp.status_code == 200
    assert resp.json() == {"message": "queued", "task_id": "task-123", "days": 30}
