"""Unit tests for PG ↔ Neo4j consistency check (D-07, read-only).

Constructs mismatch fixtures for the PG rows (mocked session) and Neo4j edges
(mocked driver), asserts the mismatch report structure, and asserts no write
Cypher (MERGE/SET/CREATE/DELETE) was ever issued.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.evolution.consistency import check_pg_neo4j_consistency

_POS1 = uuid.uuid4()
_POS2 = uuid.uuid4()
_SK1 = uuid.uuid4()
_SK2 = uuid.uuid4()

# PG PSR rows: (position_id, skill_id, requirement_type, confidence)
PG_ROWS = [
    (_POS1, _SK1, "required", 0.9),   # also in Neo4j with same attrs
    (_POS2, _SK2, "preferred", 0.7),  # PG-only
]
# Neo4j REQUIRES edges: [{pcid, scid, conf, rt}]
NEO_ROWS = [
    {"pcid": str(_POS1), "scid": str(_SK1), "conf": 0.9, "rt": "required"},
    {"pcid": str(_POS1), "scid": str(_SK2), "conf": 0.8, "rt": "required"},  # Neo4j-only
]


class _FakeRowsResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeNeoResult:
    def __init__(self, records):
        self._records = records

    async def data(self):
        return self._records


class _FakeNeoSession:
    def __init__(self, records):
        self._records = records
        self.queries: list[str] = []

    async def run(self, query, **params):
        self.queries.append(query)
        return _FakeNeoResult(self._records)


class _FakeNeoSessionCtx:
    def __init__(self, records):
        self._session = _FakeNeoSession(records)

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeNeoDriver:
    def __init__(self, records):
        self._session_ctx = _FakeNeoSessionCtx(records)

    def session(self):
        return self._session_ctx


class _FakeDriverCtx:
    def __init__(self, driver):
        self._driver = driver

    async def __aenter__(self):
        return self._driver

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _make_session_factory(pg_rows):
    """A fake async sessionmaker yielding a session with fixed PSR rows."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_FakeRowsResult(pg_rows))

    factory = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    factory.return_value = cm
    return factory


def _patch_graph_config(neo_rows):
    """Return a patch for GraphConfig whose driver yields the given edges."""
    driver = _FakeNeoDriver(neo_rows)
    config = MagicMock()
    config.get_driver.return_value = _FakeDriverCtx(driver)
    patcher = patch("app.core.evolution.consistency.GraphConfig", return_value=config)
    return patcher, driver


@pytest.mark.asyncio
async def test_consistent_report_ok():
    """Same edges both sides with same attributes → status ok, empty diffs."""
    pg_rows = [(_POS1, _SK1, "required", 0.9)]
    neo_rows = [{"pcid": str(_POS1), "scid": str(_SK1), "conf": 0.9, "rt": "required"}]
    factory = _make_session_factory(pg_rows)
    patcher, _ = _patch_graph_config(neo_rows)
    with patcher:
        report = await check_pg_neo4j_consistency(factory)

    assert report["status"] == "ok"
    assert report["pg_only"] == []
    assert report["neo4j_only"] == []
    assert report["attribute_mismatches"] == []
    assert "checked_at" in report


@pytest.mark.asyncio
async def test_mismatch_report_structure():
    """PG-only + Neo4j-only edges → status mismatch with both sides listed."""
    factory = _make_session_factory(PG_ROWS)
    patcher, _ = _patch_graph_config(NEO_ROWS)
    with patcher:
        report = await check_pg_neo4j_consistency(factory)

    assert report["status"] == "mismatch"
    assert report["pg_only"] == [{"position_id": str(_POS2), "skill_id": str(_SK2), "requirement_type": "preferred"}]
    assert report["neo4j_only"] == [{"position_id": str(_POS1), "skill_id": str(_SK2), "requirement_type": "required"}]


@pytest.mark.asyncio
async def test_attribute_mismatch_detected():
    """Same pair but different confidence → attribute_mismatches populated."""
    pg_rows = [(_POS1, _SK1, "required", 0.9)]
    neo_rows = [{"pcid": str(_POS1), "scid": str(_SK1), "conf": 0.4, "rt": "required"}]
    factory = _make_session_factory(pg_rows)
    patcher, _ = _patch_graph_config(neo_rows)
    with patcher:
        report = await check_pg_neo4j_consistency(factory)

    assert report["status"] == "mismatch"
    assert len(report["attribute_mismatches"]) == 1
    mismatch = report["attribute_mismatches"][0]
    assert mismatch["position_id"] == str(_POS1)
    assert mismatch["pg"]["confidence"] == 0.9
    assert mismatch["neo4j"]["confidence"] == 0.4


@pytest.mark.asyncio
async def test_requirement_type_mismatch_detected():
    """Same pair, same confidence, different requirement_type → pg_only + neo4j_only (W4).

    按 (position_id, skill_id, requirement_type) 分键后，PG 的 required 行与 Neo4j 的
    preferred 边是两条不同记录，各自出现在对侧缺失列表 —— 状态仍为 mismatch。
    """
    pg_rows = [(_POS1, _SK1, "required", 0.9)]
    neo_rows = [{"pcid": str(_POS1), "scid": str(_SK1), "conf": 0.9, "rt": "preferred"}]
    factory = _make_session_factory(pg_rows)
    patcher, _ = _patch_graph_config(neo_rows)
    with patcher:
        report = await check_pg_neo4j_consistency(factory)

    assert report["status"] == "mismatch"
    assert report["pg_only"] == [{"position_id": str(_POS1), "skill_id": str(_SK1), "requirement_type": "required"}]
    assert report["neo4j_only"] == [{"position_id": str(_POS1), "skill_id": str(_SK1), "requirement_type": "preferred"}]
    assert report["attribute_mismatches"] == []


@pytest.mark.asyncio
async def test_duplicate_pair_both_requirement_types_no_false_mismatch():
    """W4: 同 (position, skill) 的 required+preferred 并存且图谱一致 → 状态 ok，不误报。"""
    pg_rows = [
        (_POS1, _SK1, "required", 0.9),
        (_POS1, _SK1, "preferred", 0.7),
    ]
    neo_rows = [
        {"pcid": str(_POS1), "scid": str(_SK1), "conf": 0.9, "rt": "required"},
        {"pcid": str(_POS1), "scid": str(_SK1), "conf": 0.7, "rt": "preferred"},
    ]
    factory = _make_session_factory(pg_rows)
    patcher, _ = _patch_graph_config(neo_rows)
    with patcher:
        report = await check_pg_neo4j_consistency(factory)

    assert report["status"] == "ok"
    assert report["pg_only"] == []
    assert report["neo4j_only"] == []
    assert report["attribute_mismatches"] == []


@pytest.mark.asyncio
async def test_duplicate_pair_missing_one_edge_reports_pg_only():
    """W4: PG 双行但 Neo4j 只有 required 边 → preferred 行报告为 pg_only（不再被折叠掩盖）。"""
    pg_rows = [
        (_POS1, _SK1, "required", 0.9),
        (_POS1, _SK1, "preferred", 0.7),
    ]
    neo_rows = [
        {"pcid": str(_POS1), "scid": str(_SK1), "conf": 0.9, "rt": "required"},
    ]
    factory = _make_session_factory(pg_rows)
    patcher, _ = _patch_graph_config(neo_rows)
    with patcher:
        report = await check_pg_neo4j_consistency(factory)

    assert report["status"] == "mismatch"
    assert report["pg_only"] == [{"position_id": str(_POS1), "skill_id": str(_SK1), "requirement_type": "preferred"}]
    assert report["neo4j_only"] == []


@pytest.mark.asyncio
async def test_no_write_cypher_issued():
    """D-07: only read Cypher — no MERGE/SET/CREATE/DELETE ever issued."""
    factory = _make_session_factory(PG_ROWS)
    patcher, driver = _patch_graph_config(NEO_ROWS)
    with patcher:
        await check_pg_neo4j_consistency(factory)

    assert driver._session_ctx._session.queries, "expected at least one read query"
    for query in driver._session_ctx._session.queries:
        upper = query.upper()
        assert "MATCH" in upper
        assert "RETURN" in upper
        for forbidden in ("MERGE", "CREATE", "SET", "DELETE"):
            assert forbidden not in upper


@pytest.mark.asyncio
async def test_neo4j_failure_returns_error_status_not_raise():
    """Neo4j read failure → status 'error', no exception propagates (fail-soft)."""
    factory = _make_session_factory(PG_ROWS)
    config = MagicMock()
    config.get_driver.side_effect = RuntimeError("neo4j down")
    with patch("app.core.evolution.consistency.GraphConfig", return_value=config):
        report = await check_pg_neo4j_consistency(factory)

    assert report["status"] == "error"
    assert "neo4j" in report.get("error", "")
