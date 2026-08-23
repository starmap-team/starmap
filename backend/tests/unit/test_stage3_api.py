"""Stage 3 API contract tests."""
from __future__ import annotations

from datetime import datetime
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
            # 2026-08-23 fix: 先查 max(evaluated_at) 再查 metrics(原 scalar_subquery 在 asyncpg 手动事务下抛错)
            (datetime(2026, 8, 22, 10, 0, 0),),  # 0. latest_evaluated_at
            (0.9, 0.8, 0.85),  # 1. precision, recall, f1
            # P1-5 fix (functional-review 2026-08-13): pending_review 改从
            # position/skill_records 的 pending_review 计数（原 JDExtractionRecord
            # status=pending 恒 0）。新增 2 个查询，extraction_counts 从 3 列变 2 列。
            (1,),              # 2. pending_pos count (PositionRecord pending_review)
            (1,),              # 3. pending_skill count (SkillRecord pending_review)
            (10, 1),           # 4. total_extractions, hallucination_count
            (36,),             # 5. pos_count
            (201,),            # 6. skill_count
            (0,),              # 7. edge_count
            # D2 fix: avg_trust_score comes from avg_skill_trust (metrics module,
            # Neo4j), NOT a session query — the old avg_confidence / avg_source
            # executes are gone.
            (5,),              # 8. high_trust_count
            (10,),             # 9. high_source_count
            # compute_trust_distribution 先查 skill_trust_rows（属性行）再查 conf_rows
            [
                FakeRow(("sk-1", 8, None, "pending_review"), labels=["id", "source_count", "last_detected_at", "review_status"]),
                FakeRow(("sk-2", 2, None, "approved"), labels=["id", "source_count", "last_detected_at", "review_status"]),
            ],                 # 10. skill_trust_rows (.all)
            [],                # 11. conf_rows (skill_id, avg_confidence) — empty
            # fetch_hallucination_trend 返回 (day, total, hallucinated) 3 列行
            [("2026-08-01", 10, 1)],  # 12. ts_rows (hallucination trend)
            [("general", 100), ("hard_skill", 80)],  # 13. source_distribution
            (5,),              # 14. weekly_new_nodes: skill count
            (3,),              # 15. weekly_new_nodes: position count
            (8,),              # 15. approved_count (review_audit_log approve)
            (0,),              # 16. rejected_count (review_audit_log reject)
            [],                # 17. audit_queue pos_rows (pending positions — empty)
            [],                # 18. audit_queue skill_rows (pending skills — empty)
            (5,),              # 19. evaluation_count (Phase 13 baseline_available;>0 → 基线可用)
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
        yield FakeAsyncSession([
            (datetime(2026, 8, 22, 10, 0, 0),),  # 0. latest_evaluated_at (2026-08-23 fix)
            (0.0, 0.0, 0.0),  # 1. precision, recall, f1
            (0,),             # 2. pending_pos count
            (0,),             # 3. pending_skill count
            (0, 0),           # 4. total_extractions, hallucination_count
            (0,),             # 5. pos_count
            (0,),             # 6. skill_count
            (0,),             # 7. edge_count
            # total_extractions=0 → high_trust_count 查询被跳过（见 L153 条件）
            (0,),             # 8. high_source_count
            # compute_trust_distribution 先查 skill_trust_rows 再查 conf_rows
            [FakeRow(("sk-1", 0, None, "pending_review"), labels=["id", "source_count", "last_detected_at", "review_status"])],  # 9. skill_trust_rows
            [],               # 10. conf_rows (skill_id, avg_confidence) — empty
            [("2026-08-01", 0, 0)],  # 11. ts_rows (hallucination trend, 3 列)
            [("general", 0)], # 12. source_distribution
            (0,),             # 13. weekly_new_nodes: skill count
            (0,),             # 14. weekly_new_nodes: position count
            (0,),             # 15. approved_count
            (0,),             # 16. rejected_count
            [],               # 17. audit_queue pos_rows
            [],               # 18. audit_queue skill_rows
            (0,),             # 19. evaluation_count
        ])

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
