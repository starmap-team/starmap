"""Match service Golden Set tests.

Validates that the match engine produces correct match/no-match decisions
for the golden_set_match.jsonl fixture.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services.match_service import run_match

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"
GOLDEN_MATCH = FIXTURE_DIR / "golden_match_sample.jsonl"


# D6 fix: run_match/get_match_result 现在经 app.core.metrics.match_trust_score 读 Neo4j。
# 该函数内部调用 init_resources() 直接在模块级 resources 单例上创建真实 driver；
# 单元测试打桩它，避免真实连接泄漏到后续 TestClient 生命周期（关闭时崩）。
@pytest.fixture(autouse=True)
def _no_real_neo4j_trust(monkeypatch):
    async def _fake_trust(matched_skills):  # noqa: ANN001
        return 0.0

    monkeypatch.setattr("app.core.metrics.match_trust_score", _fake_trust)


# Target profiles used by golden tests
_GOLDEN_PROFILES = {
    "数据分析师": {
        "required": [
            {"skill": "Python", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "SQL", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Excel", "category": "tool", "proficiency": "熟悉"},
            {"skill": "统计学", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Pandas", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "数据可视化", "category": "hard_skill", "proficiency": "熟悉"},
        ],
        "bonus": [
            {"skill": "Tableau", "category": "tool", "proficiency": "了解"},
            {"skill": "Machine Learning", "category": "hard_skill", "proficiency": "了解"},
        ],
    },
    "前端开发工程师": {
        "required": [
            {"skill": "JavaScript", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Vue.js", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "CSS3", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "HTML5", "category": "hard_skill", "proficiency": "熟悉"},
        ],
        "bonus": [],
    },
    "后端开发工程师": {
        "required": [
            {"skill": "Python", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "FastAPI", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "PostgreSQL", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Redis", "category": "hard_skill", "proficiency": "了解"},
        ],
        "bonus": [
            {"skill": "Docker", "category": "tool", "proficiency": "了解"},
        ],
    },
    "高级后端工程师": {
        "required": [
            {"skill": "Python", "category": "hard_skill", "proficiency": "精通"},
            {"skill": "FastAPI", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "PostgreSQL", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Redis", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Docker", "category": "tool", "proficiency": "熟悉"},
            {"skill": "Kubernetes", "category": "tool", "proficiency": "了解"},
            {"skill": "System Design", "category": "hard_skill", "proficiency": "熟悉"},
        ],
        "bonus": [],
    },
}


def _mock_load_target_profile(driver, target_position, db_session=None, repo=None):
    """Return a profile for known positions, or None for unknown.

    _load_target_profile now returns None (not raises) when position is not found.
    The HTTPException(404) is raised by run_match.
    """
    profile = _GOLDEN_PROFILES.get(target_position)
    return profile


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
    with patch("app.core.matching.service.MatchService._load_target_profile", new=AsyncMock(side_effect=_mock_load_target_profile)):
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
    with patch("app.core.matching.service.MatchService._load_target_profile", new=AsyncMock(side_effect=_mock_load_target_profile)):
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
    with patch("app.core.matching.service.MatchService._load_target_profile", new=AsyncMock(side_effect=_mock_load_target_profile)):
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

    with patch("app.core.matching.service.MatchService._load_target_profile", new=AsyncMock(side_effect=_mock_load_target_profile)):
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
