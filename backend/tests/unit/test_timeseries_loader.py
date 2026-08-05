"""Coverage boost: core/evolution/timeseries_loader.py — 时序加载与分组 (PLAN-013)。

使用假 AsyncSession（execute → scalars().all()），不触 DB。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.core.evolution.timeseries_loader import load_skill_timeseries_data
from app.models.evolution_models import SkillTimeseries


class _FakeScalars:
    def __init__(self, records: list[Any]) -> None:
        self._records = records

    def all(self) -> list[Any]:
        return self._records


class _FakeResult:
    def __init__(self, records: list[Any]) -> None:
        self._records = records

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._records)


class _FakeSession:
    def __init__(self, records: list[Any]) -> None:
        self._records = records
        self.executed_stmt: Any = None

    async def execute(self, stmt: Any) -> _FakeResult:
        self.executed_stmt = stmt
        return _FakeResult(self._records)


def _ts(name: str, freq: int, *, source_count: int = 1, category: str = "hard_skill",
        positions: list[str] | None = None, window_start: datetime | None = None) -> SkillTimeseries:
    return SkillTimeseries(
        skill_name=name,
        frequency=freq,
        source_count=source_count,
        category=category,
        positions=positions,
        window_start=window_start or datetime(2026, 1, 1, tzinfo=UTC),
    )


class TestLoadSkillTimeseriesData:
    @pytest.mark.asyncio
    async def test_empty_records_returns_empty_dict(self) -> None:
        session = _FakeSession([])
        out = await load_skill_timeseries_data(session)
        assert out == {}

    @pytest.mark.asyncio
    async def test_groups_by_skill_and_splits_last_window(self) -> None:
        """frequencies = 除最后窗口外全部；current = 最后窗口频率。"""
        session = _FakeSession([
            _ts("Python", 5),
            _ts("Python", 8),
            _ts("Python", 12),
            _ts("SQL", 3),
        ])
        out = await load_skill_timeseries_data(session)
        assert set(out) == {"Python", "SQL"}
        assert out["Python"]["frequencies"] == [5, 8]
        assert out["Python"]["current"] == 12
        assert out["SQL"]["frequencies"] == []
        assert out["SQL"]["current"] == 3

    @pytest.mark.asyncio
    async def test_sources_and_positions_from_first_record(self) -> None:
        session = _FakeSession([
            _ts("Python", 5, source_count=7, positions=["后端"]),
            _ts("Python", 8, source_count=99, positions=["大数据"]),  # 后续记录不得覆盖
        ])
        out = await load_skill_timeseries_data(session)
        assert out["Python"]["sources"] == 7
        assert out["Python"]["positions"] == ["后端"]

    @pytest.mark.asyncio
    async def test_include_category_gates_category_field(self) -> None:
        session = _FakeSession([_ts("Python", 5, category="tool")])
        without = await load_skill_timeseries_data(session)
        assert "category" not in without["Python"]
        with_cat = await load_skill_timeseries_data(session, include_category=True)
        assert with_cat["Python"]["category"] == "tool"

    @pytest.mark.asyncio
    async def test_filters_build_where_clauses(self) -> None:
        """days/category/position_name 参数必须体现在构造的 stmt 上（防回归：过滤失效）。"""
        session = _FakeSession([_ts("Python", 5)])
        await load_skill_timeseries_data(
            session, days=30, category="hard_skill", position_name="后端"
        )
        stmt = session.executed_stmt
        # SQLAlchemy 惰性构造：递归收集 where 条件树中的所有列比较（positions.contains 嵌套更深）
        from sqlalchemy.sql.elements import BinaryExpression

        left_cols: set[str] = set()

        def walk(node: Any) -> None:
            if isinstance(node, BinaryExpression):
                if hasattr(node.left, "name"):
                    left_cols.add(node.left.name)
            for child in node.get_children():
                walk(child)

        walk(stmt.whereclause)  # type: ignore[arg-type]
        assert {"window_start", "category", "positions"} <= left_cols

    @pytest.mark.asyncio
    async def test_single_record_yields_empty_frequencies(self) -> None:
        session = _FakeSession([_ts("Python", 9)])
        out = await load_skill_timeseries_data(session)
        assert out["Python"]["frequencies"] == []
        assert out["Python"]["current"] == 9
