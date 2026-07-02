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

    def scalar(self):
        if isinstance(self.value, (list, tuple)) and len(self.value) == 1:
            return self.value[0]
        return self.value


class FakeAsyncSession:
    def __init__(self, results):
        self.results = list(results)
        self._call_count = 0

    async def execute(self, _stmt):
        self._call_count += 1
        return FakeResult(self.results.pop(0))


@pytest.mark.asyncio
async def test_quality_dashboard_builder_aggregates_metrics():
    session = FakeAsyncSession(
        [
            (0.9, 0.8, 0.85),  # 1. precision, recall, f1
            (10, 2, 1),        # 2. total_extractions, hallucination_count, pending_review
            (36,),             # 3. pos_count
            (201,),            # 4. skill_count
            (0,),              # 5. edge_count
            (0.87,),           # 6. avg_confidence
            (8.0,),            # 7. avg_source
            (5,),              # 8. high_trust_count
            (10,),             # 9. high_source_count
            (5,), (3,), (2,), (1,), (0,),  # 10-14. trust_distribution
            [("general", 100), ("hard_skill", 80)],  # 15. source_distribution
        ]
    )

    dashboard = await _build_quality_dashboard(session)

    assert dashboard.report.precision == 0.9
    assert dashboard.report.recall == 0.8
    assert dashboard.report.f1 == 0.85
    assert dashboard.total_extractions == 10
    assert dashboard.pending_review == 2
    assert dashboard.hallucination_rate == 0.1
    assert dashboard.avg_trust_score == 0.87
    assert dashboard.high_trust_ratio > 0.0


def test_quality_dashboard_endpoint_contract(client):
    async def override_session():
        yield FakeAsyncSession([(0.0, 0.0, 0.0), (0, 0, 0), (0,), (0,), (0,), (0.0,), (0,), (0,), (0,), (0,), (0,), (0,), []])

    app.dependency_overrides[get_db_session] = override_session
    try:
        resp = client.get("/api/v1/quality/dashboard")
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert resp.status_code == 200
    body = resp.json()
    required_keys = {"report", "total_extractions", "pending_review", "hallucination_rate", "total_nodes", "total_edges", "total_positions", "total_skills", "avg_trust_score", "high_trust_ratio"}
    assert required_keys.issubset(set(body))
    assert set(body["report"]) == {"precision", "recall", "f1", "warning_level", "details"}


def test_evolution_analyze_queues_task(client):
    task = type("Task", (), {"id": "task-123"})()
    with pytest.MonkeyPatch.context() as monkeypatch:
        delay = Mock(return_value=task)
        monkeypatch.setattr("app.api.v1.evolution.analyze_evolution_trends.delay", delay)
        resp = client.post("/api/v1/evolution/analyze", params={"days": 30})

    assert resp.status_code == 200
    assert resp.json() == {"message": "queued", "task_id": "task-123", "days": 30}
