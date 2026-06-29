"""Match service Golden Set tests.

Validates that the match engine produces correct match/no-match decisions
for the golden_set_match.jsonl fixture.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.match_service import run_match

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"
GOLDEN_MATCH = FIXTURE_DIR / "golden_match_sample.jsonl"


def _load_golden():
    samples = []
    with open(GOLDEN_MATCH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples


@pytest.mark.asyncio
@pytest.mark.parametrize("sample", _load_golden(), ids=[s["id"] for s in _load_golden()])
async def test_match_golden_set(sample):
    """Each golden sample should produce the expected match decision."""
    result = await run_match(
        target_position=sample["target_position"],
        person_skills=sample["person_skills"],
        threshold=0.6,
        driver=None,
    )

    score = result["match_score"]
    expected_match = sample["expected_match"]
    min_score = sample.get("min_score", 0.0)

    if expected_match:
        assert score >= min_score, (
            f"[{sample['id']}] Expected match with score >= {min_score}, got {score}"
        )
    else:
        assert score < 0.6, (
            f"[{sample['id']}] Expected no-match (score < 0.6), got {score}"
        )

    # Structural assertions
    assert "match_id" in result
    assert "match_score" in result
    assert "skill_gap_detail" in result
    assert "overall_assessment" in result
    assert 0.0 <= score <= 1.0


@pytest.mark.asyncio
async def test_match_empty_skills():
    """Empty skills should produce a low match score."""
    result = await run_match(
        target_position="数据分析师",
        person_skills=[],
        threshold=0.6,
        driver=None,
    )
    assert result["match_score"] < 0.5
    assert len(result["missing_required"]) > 0


@pytest.mark.asyncio
async def test_match_perfect_overlap():
    """All required + bonus skills at mastery should produce high score."""
    result = await run_match(
        target_position="数据分析师",
        person_skills=[
            {"name": "Python", "proficiency": "精通"},
            {"name": "SQL", "proficiency": "精通"},
            {"name": "Excel", "proficiency": "精通"},
            {"name": "统计学", "proficiency": "精通"},
            {"name": "Pandas", "proficiency": "精通"},
            {"name": "数据可视化", "proficiency": "精通"},
            {"name": "Tableau", "proficiency": "精通"},
            {"name": "Machine Learning", "proficiency": "精通"},
        ],
        threshold=0.6,
        driver=None,
    )
    assert result["match_score"] >= 0.85
    assert len(result["missing_required"]) == 0


@pytest.mark.asyncio
async def test_match_result_persisted():
    """Match results should be retrievable by match_id."""
    from app.services.match_service import get_match_result

    result = await run_match(
        target_position="前端开发工程师",
        person_skills=[{"name": "JavaScript", "proficiency": "精通"}],
        threshold=0.6,
        driver=None,
    )
    match_id = result["match_id"]
    retrieved = await get_match_result(match_id)
    assert retrieved is not None
    assert retrieved["match_id"] == match_id
    assert retrieved["target_position"] == "前端开发工程师"
