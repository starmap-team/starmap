"""ensure_prerequisite_map 单元测试（NEW-03）。

锁定：共享 PREREQUISITE_MAP 必须能从 Neo4j 幂等加载、
driver 缺失时降级为空且不抛错。
"""
from __future__ import annotations

import pytest

from app.services import match_service


class _AsyncRows:
    """Async iterator over rows (mirrors neo4j result)."""

    def __init__(self, rows):
        self._it = iter(rows)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration from None


class _FakeNeoSession:
    def __init__(self, rows):
        self._rows = rows

    async def run(self, cypher):
        return _AsyncRows(self._rows)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _FakeDriver:
    def __init__(self, rows):
        self._rows = rows

    def session(self):
        return _FakeNeoSession(self._rows)


@pytest.fixture(autouse=True)
def _reset_shared_map():
    match_service.PREREQUISITE_MAP.clear()
    match_service._PREREQUISITE_LOADED = False
    yield
    match_service.PREREQUISITE_MAP.clear()
    match_service._PREREQUISITE_LOADED = False


async def test_load_populates_shared_map_in_place():
    driver = _FakeDriver([
        {"src": "Python", "tgt": "基础编程"},
        {"src": "Python", "tgt": "SQL"},
        {"src": "机器学习", "tgt": "Python"},
    ])
    result = await match_service.ensure_prerequisite_map(driver)
    assert result is match_service.PREREQUISITE_MAP  # 同一对象, import 方共享
    assert match_service.PREREQUISITE_MAP == {
        "Python": ["基础编程", "SQL"],
        "机器学习": ["Python"],
    }


async def test_idempotent_second_call_skips_driver():
    driver = _FakeDriver([{"src": "A", "tgt": "B"}])
    await match_service.ensure_prerequisite_map(driver)

    class _ExplodingDriver:
        def session(self):
            raise AssertionError("第二次调用不应再访问 Neo4j")

    await match_service.ensure_prerequisite_map(_ExplodingDriver())
    assert match_service.PREREQUISITE_MAP == {"A": ["B"]}


async def test_no_driver_degrades_to_empty(monkeypatch):
    from types import SimpleNamespace

    import app.services.resources as res_mod

    monkeypatch.setattr(
        res_mod, "resources", SimpleNamespace(neo4j_driver=None), raising=False
    )
    result = await match_service.ensure_prerequisite_map(None)
    assert result == {}


async def test_driver_failure_degrades_to_empty():
    class _BrokenSession:
        async def run(self, cypher):
            raise RuntimeError("neo4j down")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class _BrokenDriver:
        def session(self):
            return _BrokenSession()

    result = await match_service.ensure_prerequisite_map(_BrokenDriver())
    assert result == {}
