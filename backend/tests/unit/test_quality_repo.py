"""Coverage boost: repositories/quality_repo.py — 幻觉趋势聚合 (PLAN-013)。

fetch_hallucination_trend 使用假 AsyncSession（execute → all() 返回假行），
验证聚合口径：低来源(<3)计为幻觉代理，rate=low/total 舍入 3 位。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.repositories.quality_repo import fetch_hallucination_trend


class _FakeSession:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    async def execute(self, _stmt: Any) -> SimpleNamespace:
        return SimpleNamespace(all=lambda: self._rows)


def _row(total: int, low_source: int, month: str) -> SimpleNamespace:
    return SimpleNamespace(total=total, low_source=low_source, month=month)


class TestFetchHallucinationTrend:
    @pytest.mark.asyncio
    async def test_empty_returns_empty_list(self) -> None:
        out = await fetch_hallucination_trend(_FakeSession([]))
        assert out == []

    @pytest.mark.asyncio
    async def test_rate_rounded_to_3_decimals(self) -> None:
        # 2/3 = 0.666... → 0.667
        out = await fetch_hallucination_trend(_FakeSession([_row(3, 2, "2026-01-01 00:00:00")]))
        assert out == [{"date": "2026-01", "rate": 0.667}]

    @pytest.mark.asyncio
    async def test_zero_total_does_not_divide_by_zero(self) -> None:
        out = await fetch_hallucination_trend(_FakeSession([_row(0, 0, "2026-01-01 00:00:00")]))
        assert out == [{"date": "2026-01", "rate": 0.0}]

    @pytest.mark.asyncio
    async def test_multiple_months_sorted_by_input_order(self) -> None:
        out = await fetch_hallucination_trend(_FakeSession([
            _row(10, 3, "2026-01-01 00:00:00"),
            _row(8, 0, "2026-02-01 00:00:00"),
        ]))
        assert out == [
            {"date": "2026-01", "rate": 0.3},
            {"date": "2026-02", "rate": 0.0},
        ]
