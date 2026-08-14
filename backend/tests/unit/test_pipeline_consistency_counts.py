"""P1-13 (functional-review 2026-08-13): pipeline_consistency 一致性计数非占位。

此前 _fetch_counts 恒返回 (0, 0) → check_pg_neo4j_consistency 永远
severity="ok"，D-06 告警是 no-op。现实现真实 PG/Neo4j 计数。
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from app.services.pipeline_consistency import check_pg_neo4j_consistency


class FakeNeo4jSession:
    def __init__(self, count: int) -> None:
        self._count = count

    async def run(self, cypher: str, **params):
        count = self._count

        class _Result:
            async def single(self):
                return {"total": count}

        return _Result()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class FakeNeo4jDriver:
    def __init__(self, count: int) -> None:
        self._count = count

    def session(self):
        return FakeNeo4jSession(self._count)


class FakeCountResult:
    def scalar(self):
        return 42


class FakePgSession:
    async def execute(self, stmt):
        return FakeCountResult()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


async def test_consistent_counts_no_alert():
    """PG=42, Neo4j=42 → diff=0, severity=ok, alerted=False."""
    with patch("app.services.pipeline_consistency.get_session_factory", return_value=lambda: FakePgSession()), \
         patch("app.services.pipeline_consistency.app_resources", MagicMock(neo4j_driver=FakeNeo4jDriver(42))):
        result = await check_pg_neo4j_consistency(uuid.uuid4())

    assert result["pg_count"] == 42
    assert result["neo4j_count"] == 42
    assert result["diff"] == 0
    assert result["severity"] == "ok"
    assert result["alerted"] is False


async def test_large_diff_triggers_alert():
    """PG=42, Neo4j=1000 → diff=958 > max(0, 100) → warning + alerted."""
    with patch("app.services.pipeline_consistency.get_session_factory", return_value=lambda: FakePgSession()), \
         patch("app.services.pipeline_consistency.app_resources", MagicMock(neo4j_driver=FakeNeo4jDriver(1000))):
        result = await check_pg_neo4j_consistency(uuid.uuid4())

    assert result["pg_count"] == 42
    assert result["neo4j_count"] == 1000
    assert result["diff"] == 958
    assert result["severity"] == "warning"
    assert result["alerted"] is True


async def test_neo4j_unavailable_degrades_to_zero():
    """Neo4j driver None → neo4j_count=0，PG 仍正常读取，不抛错。"""
    with patch("app.services.pipeline_consistency.get_session_factory", return_value=lambda: FakePgSession()), \
         patch("app.services.pipeline_consistency.app_resources", MagicMock(neo4j_driver=None)):
        result = await check_pg_neo4j_consistency(uuid.uuid4())

    assert result["pg_count"] == 42
    assert result["neo4j_count"] == 0
    # diff=42，阈值 max(int(42*0.01),100)=100 → 42<100 → ok（降级不误报）
    assert result["severity"] == "ok"
    assert result["alerted"] is False
