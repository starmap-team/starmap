"""§7.6 因果推理轻量版测试 (DEV-01)。

- fisher_exact_p: 已知 2x2 表精确 p 值 (手算验证)
- phi_coefficient: 效应量边界
- analyze_contingency: 显著/不显著分界
- skill_position_associations: 假 session 集成 (技能 vs 对照)
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from app.core.evolution.causal_inference import (
    analyze_contingency,
    fisher_exact_p,
    phi_coefficient,
    skill_position_associations,
)


class TestFisherExact:
    def test_identity_table_p_value(self) -> None:
        """完全独立表: [[5,5],[5,5]] → p 接近 1 (不拒绝独立)。"""
        p = fisher_exact_p(5, 5, 5, 5)
        assert p > 0.05

    def test_strong_association_low_p(self) -> None:
        """强共现: [[10,0],[0,10]] → p 极小 (拒绝独立)。"""
        p = fisher_exact_p(10, 0, 0, 10)
        assert p < 0.001

    def test_known_small_table(self) -> None:
        """经典小表 [[1,9],[11,3]]: 双侧 p ≈ 0.00275 (R fisher.test 参考值)。"""
        p = fisher_exact_p(1, 9, 11, 3)
        assert abs(p - 0.00275) < 0.0005

    def test_zero_margins_return_1(self) -> None:
        assert fisher_exact_p(0, 0, 0, 0) == 1.0
        assert fisher_exact_p(3, 0, 0, 0) == 1.0

    def test_negative_input_returns_1(self) -> None:
        assert fisher_exact_p(-1, 2, 3, 4) == 1.0


class TestPhiCoefficient:
    def test_perfect_positive(self) -> None:
        assert phi_coefficient(10, 0, 0, 10) == pytest.approx(1.0)

    def test_perfect_negative(self) -> None:
        assert phi_coefficient(0, 10, 10, 0) == pytest.approx(-1.0)

    def test_independent_zero(self) -> None:
        assert phi_coefficient(5, 5, 5, 5) == pytest.approx(0.0)

    def test_zero_denominator(self) -> None:
        assert phi_coefficient(0, 0, 0, 5) == 0.0


class TestAnalyzeContingency:
    def test_significant_association(self) -> None:
        out = analyze_contingency(8, 2, 3, 17)
        assert out["significant"] is True
        assert out["p_value"] < 0.05
        assert out["method"] == "fisher_exact"
        assert -1 <= out["phi"] <= 1

    def test_insignificant_association(self) -> None:
        out = analyze_contingency(5, 5, 5, 5)
        assert out["significant"] is False


class TestSkillPositionAssociations:
    def _ts(self, name: str, positions: list[str] | None) -> SimpleNamespace:
        return SimpleNamespace(skill_name=name, positions=positions)

    @pytest.mark.asyncio
    async def test_finds_significant_association(self) -> None:
        """技能 Python 强关联 '后端', 对照 (SQL) 无此岗位。"""
        # Python 10 条记录: 8 条含后端, 2 条不含 → 对照 SQL 10 条仅 1 条含后端
        records = (
            [self._ts("Python", ["后端", "数据"]) for _ in range(8)]
            + [self._ts("Python", ["数据"]) for _ in range(2)]
        )

        class _R:
            def __init__(self, rows): self._rows = rows
            def scalars(self): return SimpleNamespace(all=lambda: self._rows)

        class _S:
            def __init__(self, by_name: dict):
                self._by_name = by_name
            async def execute(self, stmt):
                # 简化: 按 where 条件分派 (测试中只查 Python)
                name = getattr(stmt, '_test_name', 'Python')
                return _R(self._by_name.get(name, []))

        class _S:
            def __init__(self, rows, other_rows):
                self._rows = rows
                self._other_rows = other_rows
                self._calls = 0
            async def execute(self, stmt):
                # 第一次查询 = 技能记录, 第二次 = 对照集
                self._calls += 1
                return _R(self._rows if self._calls == 1 else self._other_rows)

        session = _S(records, [self._ts("SQL", ["后端", "数据"])] + [self._ts("SQL", ["数据"]) for _ in range(9)])
        out = await skill_position_associations("Python", session)
        assert out["skill"] == "Python"
        assert out["total_records"] == 10
        assert out["control_records"] == 10
        assert isinstance(out["associations"], list)
        # 显著关联应被筛选返回 (Python×后端 3/1 vs 对照 0/1 → 正向关联)
        backend_stats = [a for a in out["associations"] if a["position"] == "后端"]
        assert backend_stats, "Python×后端 应产出显著关联"
        assert backend_stats[0]["phi"] > 0
        assert backend_stats[0]["significant"] is True
