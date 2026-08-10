"""Unit tests for incremental Neo4j projection counting (W2, D-04 tail).

Uses fake result summaries to verify that only edges whose MERGE actually
created/updated nodes or relationships (``counters.contains_updates``) count
toward ``graph_projected_edges``, and that missing Position nodes surface a
warning instead of silently over-reporting.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.evolution.graph_projection import project_edges_to_neo4j


class _Ctx:
    """Minimal ``async with`` context manager yielding ``enter_val``."""

    def __init__(self, enter_val):
        self._enter_val = enter_val

    async def __aenter__(self):
        return self._enter_val

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSummary:
    def __init__(self, contains_updates: bool):
        counters = MagicMock()
        counters.contains_updates = contains_updates
        self.counters = counters


class _FakeResult:
    def __init__(self, contains_updates: bool):
        self._summary = _FakeSummary(contains_updates)

    async def consume(self):
        return self._summary


class _FakeSession:
    def __init__(self, results):
        self._results = iter(results)
        self.queries: list[str] = []

    async def run(self, query, **params):
        self.queries.append(query)
        return next(self._results)


def _patch_config(results):
    """Return a patch for GraphConfig whose session yields the given summaries."""
    session = _FakeSession(results)
    driver = MagicMock()
    driver.session.return_value = _Ctx(session)
    config = MagicMock()
    config.get_driver.return_value = _Ctx(driver)
    return patch("app.core.evolution.graph_projection.GraphConfig", return_value=config), session


@pytest.mark.asyncio
async def test_counts_only_edges_that_actually_updated():
    """W2: contains_updates=False (Position node missing) → not counted + warned."""
    edges = [
        ("pos-1", "skill-1", "required", 0.9),
        ("pos-2", "skill-2", "required", 0.8),
    ]
    patcher, session = _patch_config([_FakeResult(True), _FakeResult(False)])
    warnings: list[str] = []
    with patcher:
        projected = await project_edges_to_neo4j(edges, warnings)

    assert projected == 1
    assert any("not projected" in w for w in warnings)
    assert len(warnings) == 1


@pytest.mark.asyncio
async def test_all_edges_updated_counts_all():
    patcher, _ = _patch_config([_FakeResult(True), _FakeResult(True)])
    warnings: list[str] = []
    with patcher:
        projected = await project_edges_to_neo4j(
            [("pos-1", "skill-1", "required", 0.9), ("pos-1", "skill-2", "preferred", 0.7)],
            warnings,
        )

    assert projected == 2
    assert warnings == []


@pytest.mark.asyncio
async def test_query_merges_skill_node_for_new_skills():
    """W2: 回写新技能无 Neo4j :Skill 节点时，MERGE 兜底创建而非静默跳过。"""
    patcher, session = _patch_config([_FakeResult(True)])
    warnings: list[str] = []
    with patcher:
        await project_edges_to_neo4j([("pos-1", "skill-1", "required", 0.9)], warnings)

    assert session.queries, "expected the projection query to run"
    query = session.queries[0]
    assert "MATCH (p:Position" in query
    assert "MERGE (s:Skill {canonical_id: $sid})" in query


@pytest.mark.asyncio
async def test_empty_edges_returns_zero_without_querying():
    patcher, session = _patch_config([])
    warnings: list[str] = []
    with patcher:
        projected = await project_edges_to_neo4j([], warnings)

    assert projected == 0
    assert session.queries == []
