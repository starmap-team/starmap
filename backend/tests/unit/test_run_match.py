"""Tests for run_match function in match_service."""
from __future__ import annotations

import pytest

from app.services.match_service import run_match


@pytest.mark.asyncio
async def test_run_match_simple():
    result = await run_match(
        target_position="数据分析师",
        person_skills=[
            {"skill": "Python", "proficiency": "熟悉"},
            {"skill": "SQL", "proficiency": "熟悉"},
        ],
    )
    assert "match_id" in result
    assert "match_score" in result
    assert "skill_gap_detail" in result
    assert result["target_position"] == "数据分析师"
    assert result["match_score"] >= 0


@pytest.mark.asyncio
async def test_run_match_no_skills():
    result = await run_match(
        target_position="前端开发工程师",
        person_skills=[],
    )
    assert result["match_score"] >= 0
    assert result["missing_required"]


@pytest.mark.asyncio
async def test_run_match_unknown_position():
    result = await run_match(
        target_position="UnknownXYZ Position",
        person_skills=[{"skill": "Python", "proficiency": "熟悉"}],
    )
    assert "match_score" in result


@pytest.mark.asyncio
async def test_run_match_high_proficiency():
    result = await run_match(
        target_position="后端开发工程师",
        person_skills=[
            {"skill": "Python", "proficiency": "精通"},
            {"skill": "FastAPI", "proficiency": "熟悉"},
            {"skill": "Docker", "proficiency": "熟悉"},
        ],
    )
    assert result["match_score"] > 0.3


@pytest.mark.asyncio
async def test_run_match_with_thresholds():
    result = await run_match(
        target_position="数据分析师",
        person_skills=[{"skill": "Python", "proficiency": "熟悉"}],
        threshold=0.8,
    )
    assert "match_score" in result
