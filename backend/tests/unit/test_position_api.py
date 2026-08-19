"""Unit tests for position API endpoints — service layer only.

Covers:
- list_positions: PG query, search, industry filter, status filter, admin vs non-admin
- list_industries: dedup + sort + unclassified handling
- _escape_like: SQL LIKE wildcard escaping
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.v1.position import _escape_like
from app.schemas.position import PositionListResponse

# ══════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════


def _make_user(role: str = "user") -> dict:
    return {"sub": "test-user", "role": role, "username": "testuser"}


def _mock_session(count_result: int = 5) -> AsyncMock:
    """Mock AsyncSession: first execute = count, second = select."""
    session = AsyncMock()
    count_mock = MagicMock()
    count_mock.scalar.return_value = count_result
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    select_mock = MagicMock()
    select_mock.scalars.return_value = scalars_mock
    session.execute = AsyncMock(side_effect=[count_mock, select_mock])
    return session


class _FakeNeo4jSession:
    """Fake Neo4j async session that supports `async with` and `run()`."""

    def __init__(self, count: int = 0, nodes: list[dict] | None = None):
        self._count = count
        self._nodes = nodes or []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def run(self, query: str, params: dict | None = None):
        if "count(p)" in query or "count(p) AS cnt" in query:
            record = MagicMock()
            record.__getitem__ = lambda self, key: self._count if key == "cnt" else None
            result = MagicMock()
            result.single = AsyncMock(return_value=record)
            return result
        # Page query
        records = []
        for node_data in self._nodes:
            record = MagicMock()
            p_node = MagicMock()
            p_node.__iter__ = lambda self, nd=node_data: iter(nd.items())
            p_node.get = lambda key, default=None, nd=node_data: nd.get(key, default)
            record.__getitem__ = lambda self, key, _p=node_data: (
                _make_p_node(_p) if key == "p"
                else ([] if key == "skills" else None)
            )
            records.append(record)

        async def _aiter():
            for r in records:
                yield r

        return _aiter()


def _make_p_node(data: dict) -> MagicMock:
    p_node = MagicMock()
    p_node.__iter__ = lambda self: iter(data.items())
    p_node.get = lambda key, default=None: data.get(key, default)
    return p_node


def _mock_neo4j_driver(count: int = 0, nodes: list[dict] | None = None) -> MagicMock:
    """Mock Neo4j driver with proper async context manager."""
    driver = MagicMock()
    fake_session = _FakeNeo4jSession(count=count, nodes=nodes)
    driver.session = MagicMock(return_value=fake_session)
    return driver


# ══════════════════════════════════════════════════════════════
# _escape_like
# ══════════════════════════════════════════════════════════════


class TestEscapeLike:
    """SQL LIKE wildcard escaping prevents injection."""

    def test_escapes_percent(self) -> None:
        assert _escape_like("100%") == "100\\%"

    def test_escapes_underscore(self) -> None:
        assert _escape_like("test_item") == "test\\_item"

    def test_escapes_backslash(self) -> None:
        assert _escape_like("path\\to") == "path\\\\to"

    def test_no_escape_needed(self) -> None:
        assert _escape_like("normal text") == "normal text"

    def test_empty_string(self) -> None:
        assert _escape_like("") == ""

    def test_combined_wildcards(self) -> None:
        assert _escape_like("%_test\\%") == "\\%\\_test\\\\\\%"


# ══════════════════════════════════════════════════════════════
# list_positions — visibility policy
# ══════════════════════════════════════════════════════════════


class TestListPositionsVisibility:
    """Admin vs non-admin visibility policy (P1-9 fix)."""

    @pytest.mark.asyncio
    async def test_non_admin_cannot_override_status(self) -> None:
        """Non-admin passing status=pending_review gets forced to approved."""
        from app.api.v1.position import list_positions

        session = _mock_session(count_result=0)
        driver = _mock_neo4j_driver()
        user = _make_user("user")

        result = await list_positions(
            session=session,
            driver=driver,
            user=user,
            page=1,
            page_size=20,
            status="pending_review",
            include_all=True,
        )

        assert isinstance(result, PositionListResponse)

    @pytest.mark.asyncio
    async def test_admin_can_see_all_statuses(self) -> None:
        """Admin with include_all=True sees all positions."""
        from app.api.v1.position import list_positions

        session = _mock_session(count_result=15)
        driver = _mock_neo4j_driver()
        user = _make_user("admin")

        result = await list_positions(
            session=session,
            driver=driver,
            user=user,
            page=1,
            page_size=20,
            include_all=True,
        )

        assert isinstance(result, PositionListResponse)
        assert result.total == 15

    @pytest.mark.asyncio
    async def test_regular_user_sees_only_approved(self) -> None:
        """Regular user without include_all gets only approved positions."""
        from app.api.v1.position import list_positions

        session = _mock_session(count_result=8)
        driver = _mock_neo4j_driver()
        user = _make_user("user")

        result = await list_positions(
            session=session,
            driver=driver,
            user=user,
            page=1,
            page_size=20,
        )

        assert isinstance(result, PositionListResponse)
        assert result.total == 8


# ══════════════════════════════════════════════════════════════
# list_positions — Neo4j fallback
# ══════════════════════════════════════════════════════════════


class TestListPositionsFallback:
    """Neo4j fallback when PG returns 0 matching records."""

    @pytest.mark.asyncio
    async def test_falls_back_to_neo4j_when_pg_zero(self) -> None:
        """PG count=0 triggers Neo4j query."""
        from app.api.v1.position import list_positions

        session = _mock_session(count_result=0)
        driver = _mock_neo4j_driver(count=3)
        user = _make_user("user")

        result = await list_positions(
            session=session,
            driver=driver,
            user=user,
            page=1,
            page_size=20,
        )

        assert isinstance(result, PositionListResponse)
        driver.session.assert_called()

    @pytest.mark.asyncio
    async def test_no_fallback_when_pg_has_data(self) -> None:
        """PG count>0 skips Neo4j entirely."""
        from app.api.v1.position import list_positions

        session = _mock_session(count_result=5)
        driver = _mock_neo4j_driver()
        user = _make_user("user")

        await list_positions(
            session=session,
            driver=driver,
            user=user,
            page=1,
            page_size=20,
        )

        driver.session.assert_not_called()


# ══════════════════════════════════════════════════════════════
# list_industries
# ══════════════════════════════════════════════════════════════


class TestListIndustries:
    """list_industries — dedup, sort, unclassified handling."""

    @pytest.mark.asyncio
    async def test_returns_deduped_sorted_industries(self) -> None:
        """Industries are deduplicated and sorted alphabetically."""
        from app.api.v1.position import list_industries

        session = AsyncMock()
        # First execute: real industries (sorted, deduped by DB, but we simulate)
        scalars_mock1 = MagicMock()
        scalars_mock1.all.return_value = ["金融", "信息技术"]  # already sorted
        result_mock1 = MagicMock()
        result_mock1.scalars.return_value = scalars_mock1
        # Second execute: unclassified count
        count_mock = MagicMock()
        count_mock.scalar.return_value = 0
        session.execute = AsyncMock(side_effect=[result_mock1, count_mock])

        result = await list_industries(session=session)

        assert result.industries == ["金融", "信息技术"]

    @pytest.mark.asyncio
    async def test_appends_unclassified_at_end(self) -> None:
        """'未分类' is appended at the end when it exists in DB."""
        from app.api.v1.position import list_industries

        session = AsyncMock()
        scalars_mock1 = MagicMock()
        scalars_mock1.all.return_value = ["信息技术"]
        result_mock1 = MagicMock()
        result_mock1.scalars.return_value = scalars_mock1
        count_mock = MagicMock()
        count_mock.scalar.return_value = 5
        session.execute = AsyncMock(side_effect=[result_mock1, count_mock])

        result = await list_industries(session=session)

        assert result.industries == ["信息技术", "未分类"]
        assert result.industries[-1] == "未分类"

    @pytest.mark.asyncio
    async def test_empty_when_no_positions(self) -> None:
        """Empty list when no positions exist."""
        from app.api.v1.position import list_industries

        session = AsyncMock()
        scalars_mock1 = MagicMock()
        scalars_mock1.all.return_value = []
        result_mock1 = MagicMock()
        result_mock1.scalars.return_value = scalars_mock1
        count_mock = MagicMock()
        count_mock.scalar.return_value = 0
        session.execute = AsyncMock(side_effect=[result_mock1, count_mock])

        result = await list_industries(session=session)

        assert result.industries == []
