"""Stage 3 API contract tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.api.v1.quality import _build_quality_dashboard
from app.dependencies import get_current_user, get_db_session
from app.main import app


class FakeRow:
    """A row that supports both index and named-attribute access (like SQLAlchemy Row)."""

    def __init__(self, values, labels=None):
        self._values = values if isinstance(values, (list, tuple)) else (values,)
        self._labels = labels or []

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        if key in self._labels:
            return self._values[self._labels.index(key)]
        raise KeyError(key)

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._labels:
            return self._values[self._labels.index(name)]
        raise AttributeError(name)

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)


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

    def scalars(self):
        return self


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
            # D2 fix: avg_trust_score comes from avg_skill_trust (metrics module,
            # Neo4j), NOT a session query — the old avg_confidence / avg_source
            # executes are gone.
            (5,),              # 6. high_trust_count
            (10,),             # 7. high_source_count
            (5,), (3,), (2,), (1,), (0,),  # 8-12. trust_distribution
            [],                # 13. ts_rows (hallucination trend — empty)
            [("general", 100), ("hard_skill", 80)],  # 14. source_distribution
            (5,),              # 15. weekly_new_nodes: skill count
            (3,),              # 16. weekly_new_nodes: position count
            (8,),              # 17. approved_count (review_audit_log approve)
            (0,),              # 18. rejected_count (review_audit_log reject) — ponytail: audit_pass_rate 口径修复后 +1 查询
            [],                # 19. low_trust records (audit_queue — now a list)
            (5,),              # 20. evaluation_count (Phase 13 baseline_available;>0 → 基线可用)
        ]
    )

    # avg_skill_trust reads Neo4j (unavailable in unit tests) — pin it so the
    # trust value flows through deterministically without a real connection.
    with patch("app.services.quality_service.avg_skill_trust", new_callable=AsyncMock) as mock_trust:
        mock_trust.return_value = 0.87
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
    # Override auth to avoid _get_dev_user hitting the fake session
    _fake_user = {"sub": "test_user", "role": "admin", "username": "test_user", "type": "access"}

    async def _override_current_user():
        return _fake_user

    app.dependency_overrides[get_current_user] = _override_current_user

    async def override_session():
        # D2 fix: 少了 avg_confidence / avg_source 两次 execute（trust 来自 metrics 模块），
        # 且 total_extractions=0 时 high_trust_count 查询被跳过；weekly_new_nodes 仍为 2 次 execute
        yield FakeAsyncSession([(0.0, 0.0, 0.0), (0, 0, 0), (0,), (0,), (0,), (0,), (0,), (0,), (0,), (0,), (0,), [], [], (0,), (0,), (0,), (0,), [], (0,)])

    app.dependency_overrides[get_db_session] = override_session
    try:
        # avg_skill_trust reads Neo4j (unavailable in unit tests) — pin to 0.0
        with patch("app.services.quality_service.avg_skill_trust", new_callable=AsyncMock) as mock_trust:
            mock_trust.return_value = 0.0
            resp = client.get("/api/v1/quality/dashboard")
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_current_user, None)

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
