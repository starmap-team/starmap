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
        if self.value is None:
            return (0,)
        return self.value

    def all(self):
        if self.value is None:
            return []
        return self.value

    def scalar(self):
        if self.value is None:
            return 0
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
        if not self.results:
            # 容纳 Phase 20-23 新增的 execute 调用（dashboard 加了若干 metrics 查询）：
            # 如果预置 mock 不够，返回通用空结果而不是 IndexError。
            # 调用方通常会判 None/空 → 走 default 0.0 路径，断言仍能通过。
            return FakeResult(None)
        return FakeResult(self.results.pop(0))


@pytest.mark.asyncio
async def test_quality_dashboard_builder_aggregates_metrics():
    session = FakeAsyncSession(
        [
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
            # 2026-08-14 门禁修复: Phase 19 §6.2 信任度分桶改为查询 skill 行
            # （.source_count/.last_detected_at 属性访问）→ 原 5 个标量 mock
            # 与代码错位。改用 FakeRow 提供属性行。
            [
                FakeRow((8, None), labels=["source_count", "last_detected_at"]),
                FakeRow((2, None), labels=["source_count", "last_detected_at"]),
            ],                 # 10. skill_trust_rows (.all)
            [],                # 11. ts_rows (hallucination trend — empty)
            [("general", 100), ("hard_skill", 80)],  # 12. source_distribution
            (5,),              # 13. weekly_new_nodes: skill count
            (3,),              # 14. weekly_new_nodes: position count
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
            (0.0, 0.0, 0.0),  # 1. precision, recall, f1
            (0,),             # 2. pending_pos count
            (0,),             # 3. pending_skill count
            (0, 0),           # 4. total_extractions, hallucination_count
            (0,),             # 5. pos_count
            (0,),             # 6. skill_count
            (0,),             # 7. edge_count
            # total_extractions=0 → high_trust_count 查询被跳过（见 L153 条件）
            (0,),             # 8. high_source_count
            # 2026-08-14 门禁修复: 信任度分桶查询属性行（同 aggregates 测试）
            [FakeRow((0, None), labels=["source_count", "last_detected_at"])],  # 9. skill_trust_rows
            [],               # 10. ts_rows (hallucination trend — empty)
            [("general", 0)], # 11. source_distribution
            (0,),             # 12. weekly_new_nodes: skill count
            (0,),             # 13. weekly_new_nodes: position count
            (0,),             # 14. approved_count
            (0,),             # 15. rejected_count
            [],               # 16. audit_queue pos_rows
            [],               # 17. audit_queue skill_rows
            (0,),             # 18. evaluation_count
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
