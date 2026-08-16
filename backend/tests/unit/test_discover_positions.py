"""Unit tests for discover_emerging_positions (P1-4 新岗位发现)。

验证：
- 时序数据不足 → insufficient_data
- 涌现技能 + 岗位画像交叉 → 候选岗位（含 definition 字段）
- 无候选 → no_candidates
- threshold 过滤
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.evolution_service import discover_emerging_positions


class _FakeReport:
    def __init__(self, emerging: list, rising: list) -> None:
        self.emerging = emerging
        self.rising = rising


class _FakeSignal:
    def __init__(self, name: str) -> None:
        self.skill_name = name


class _FakeResult:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def all(self) -> list:
        return self._rows


class _FakeSession:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    async def execute(self, stmt, params=None) -> _FakeResult:  # noqa: ANN001
        return _FakeResult(self._rows)


@pytest.mark.asyncio
async def test_insufficient_timeseries_data() -> None:
    session = _FakeSession([])
    with patch(
        "app.services.evolution_service.load_skill_timeseries_data",
        new=AsyncMock(return_value={}),
    ):
        result = await discover_emerging_positions(session)
    assert result["status"] == "insufficient_data"
    assert result["candidates"] == []


@pytest.mark.asyncio
async def test_discovers_emerging_position_candidate() -> None:
    """岗位 required 技能中涌现占比 ≥ threshold → 候选岗位 + definition。"""
    session = _FakeSession([
        # 后端工程师: 4 required 中 3 个涌现 → ratio 0.75 ≥ 0.5
        ("后端工程师", "Python"),
        ("后端工程师", "FastAPI"),
        ("后端工程师", "向量数据库"),
        ("后端工程师", "Java"),
        # 前端工程师: 2 required 中 0 个涌现 → 不入选
        ("前端工程师", "HTML5"),
        ("前端工程师", "CSS3"),
    ])
    report = _FakeReport(
        emerging=[_FakeSignal("向量数据库"), _FakeSignal("FastAPI")],
        rising=[_FakeSignal("Python")],
    )
    with (
        patch(
            "app.services.evolution_service.load_skill_timeseries_data",
            new=AsyncMock(return_value={"skill_a": {"freq": [1, 2, 5]}}),
        ),
        patch("app.services.evolution_service.EmergenceFinder") as mock_finder,
    ):
        mock_finder.return_value.scan.return_value = report
        result = await discover_emerging_positions(session, threshold=0.5)

    assert result["status"] == "completed"
    assert len(result["candidates"]) == 1
    cand = result["candidates"][0]
    assert cand["position"] == "后端工程师"
    assert set(cand["emerging_skills"]) == {"Python", "FastAPI", "向量数据库"}
    assert cand["emerging_ratio"] == 0.75
    assert cand["definition"]["position_name"] == "后端工程师"
    assert "required_skills" in cand["definition"]
    assert cand["definition"]["emerging_required"] == sorted(["向量数据库", "Python", "FastAPI"])


@pytest.mark.asyncio
async def test_threshold_filters_low_ratio() -> None:
    """涌现占比低于 threshold → 不入选。"""
    session = _FakeSession([
        ("普通岗位", "Python"),
        ("普通岗位", "Java"),
        ("普通岗位", "Go"),
        ("普通岗位", "Rust"),
    ])
    report = _FakeReport(emerging=[_FakeSignal("Python")], rising=[])
    with (
        patch(
            "app.services.evolution_service.load_skill_timeseries_data",
            new=AsyncMock(return_value={"skill_a": {"freq": [1, 2, 5]}}),
        ),
        patch("app.services.evolution_service.EmergenceFinder") as mock_finder,
    ):
        mock_finder.return_value.scan.return_value = report
        result = await discover_emerging_positions(session, threshold=0.5)

    # 4 个技能中 1 个涌现 → ratio 0.25 < 0.5
    assert result["status"] == "no_candidates"
    assert result["candidates"] == []
    assert result["analyzed_positions"] == 1
