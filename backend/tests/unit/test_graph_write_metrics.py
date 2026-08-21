"""Phase 23 Task 7 — source_count max 语义探针与回归测试 (IC-06/IS-01).

断言：
- ``merge_skill`` 的 Cypher 使用 **max 语义**（``max(coalesce(s.source_count, 0),
  $source_count)``），同 skill 重复 MERGE / outbox 重放不累加（不膨胀）。
- ``dashboard_service._fetch_graph_stats`` 的 source_count 漂移探针：Neo4j 不可用
  时 fail-soft 返回兜底（0），不抛异常；PG 侧 max(source_count) 正常取回。
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.extraction.graph_writer import merge_skill

# ── Fake Neo4j session / driver ─────────────────────────────────────────────


class _FakeAsyncResult:
    def __init__(self, records: list) -> None:
        self._records = list(records)

    def __aiter__(self):
        self._idx = 0
        return self

    async def __anext__(self):
        if self._idx >= len(self._records):
            raise StopAsyncIteration
        rec = self._records[self._idx]
        self._idx += 1
        return rec

    async def single(self):
        return self._records[0] if self._records else None


class _FakeAsyncSession:
    def __init__(self, run_side_effect=None):
        self._run_side_effect = run_side_effect
        self.calls: list = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False

    async def run(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self._run_side_effect is not None:
            if callable(self._run_side_effect):
                return self._run_side_effect(*args, **kwargs)
            return self._run_side_effect
        return _FakeAsyncResult([])


class _FakeDriver:
    def __init__(self, session):
        self._session = session

    def session(self):
        return self._session


class _DownDriver:
    """Neo4j 不可用：session() 直接抛异常（模拟连接失败）。"""

    def session(self):
        raise RuntimeError("neo4j down")


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    async def _instant(*_a, **_kw):
        return None

    monkeypatch.setattr(asyncio, "sleep", _instant)


# ── merge_skill max 语义回归 ────────────────────────────────────────────────


class TestMergeSkillMaxSemantics:
    @pytest.mark.asyncio
    async def test_merge_skill_query_uses_max_semantics(self) -> None:
        captured: dict = {}

        def smart_run(*args, **kwargs):
            captured["query"] = args[0] if args else ""
            captured["kwargs"] = kwargs
            return _FakeAsyncResult([{"s": {"name": "Python"}}])

        session = _FakeAsyncSession(run_side_effect=smart_run)
        with patch("app.core.trust.entity_trust.EntityTrustScorer") as mock_scorer:
            mock_scorer.return_value.score.return_value = 0.5
            await merge_skill(_FakeDriver(session), "Python", {"source_count": 5}, canonical_id="sk-1")

        q = captured["query"]
        # max 语义（Task 1 落地，Task 7 回归锁定）——不允许回归为累加
        assert "max(coalesce(s.source_count, 0), $source_count)" in q
        assert "coalesce(s.source_count, 0) + $source_count" not in q
        assert captured["kwargs"]["source_count"] == 5

    @pytest.mark.asyncio
    async def test_repeat_merge_source_count_does_not_inflate(self) -> None:
        """同 skill 重复 merge（source_count=5 两次）→ 传入恒为 5，max 语义不累加。"""
        session = _FakeAsyncSession(
            run_side_effect=_FakeAsyncResult([{"s": {"name": "Python"}}])
        )
        with patch("app.core.trust.entity_trust.EntityTrustScorer") as mock_scorer:
            mock_scorer.return_value.score.return_value = 0.5
            for _ in range(2):
                await merge_skill(_FakeDriver(session), "Python", {"source_count": 5}, canonical_id="sk-1")

        assert len(session.calls) == 2
        for args, kwargs in session.calls:
            q = args[0]
            assert "max(coalesce(s.source_count, 0), $source_count)" in q
            # 两次传入都是 5 —— 若回归为累加，第二次会传入 10
            assert kwargs["source_count"] == 5

    @pytest.mark.asyncio
    async def test_merge_skill_query_never_uses_additive_source_count(self) -> None:
        """冒烟：任何分支不得再出现累加写法 ``coalesce(...) + $source_count``。"""
        captured: dict = {}

        def smart_run(*args, **kwargs):
            captured["query"] = args[0] if args else ""
            return _FakeAsyncResult([{"s": {"name": "Go"}}])

        session = _FakeAsyncSession(run_side_effect=smart_run)
        with patch("app.core.trust.entity_trust.EntityTrustScorer") as mock_scorer:
            mock_scorer.return_value.score.return_value = 0.5
            await merge_skill(_FakeDriver(session), "Go", {"source_count": 3}, canonical_id="sk-2")
        assert "coalesce(s.source_count, 0) + $source_count" not in captured["query"]


# ── source_count 漂移探针（dashboard_service） ──────────────────────────────


class _FakePgResult:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        return self.value

    def scalar_one_or_none(self):
        return self.value

    def all(self):
        return self.value if isinstance(self.value, list) else [self.value]
