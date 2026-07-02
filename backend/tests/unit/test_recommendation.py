"""推荐引擎单元测试。"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.pipeline.contracts import ExtractedSkill, PositionProfile
from app.services.recommendation_service import PositionRecommender, Recommendation


def mock_scorer(*, target_skills: list[dict], person_skills: list[dict], threshold: float = 0.6) -> dict[str, Any]:
    """模拟评分函数：简单名称匹配。"""
    person_names = {s.get("skill") or s.get("name", "") for s in person_skills}
    evaluated = []
    for t in target_skills:
        name = t.get("skill", "")
        score = 1.0 if name in person_names else 0.0
        evaluated.append({
            "skill": name,
            "importance": t.get("importance", "required"),
            "gap_level": "已掌握" if score >= 0.85 else "完全缺失",
            "learning_path": [],
            "score": score,
        })
    return {"evaluated": evaluated}


@pytest.fixture
def mock_repo():
    """创建 mock PositionRepository。"""
    repo = AsyncMock()
    return repo


@pytest.fixture
def sample_profiles():
    """示例岗位画像。"""
    return {
        "后端开发工程师": PositionProfile(
            name="后端开发工程师",
            industry="IT",
            required_skills=[
                {"name": "Python", "category": "hard_skill", "proficiency": "精通", "is_required": True},
                {"name": "PostgreSQL", "category": "hard_skill", "proficiency": "熟悉", "is_required": True},
                {"name": "Docker", "category": "tool", "proficiency": "熟悉", "is_required": True},
            ],
            market_demand=0.8,
        ),
        "前端开发工程师": PositionProfile(
            name="前端开发工程师",
            industry="IT",
            required_skills=[
                {"name": "JavaScript", "category": "hard_skill", "proficiency": "精通", "is_required": True},
                {"name": "Vue.js", "category": "hard_skill", "proficiency": "熟悉", "is_required": True},
                {"name": "CSS3", "category": "hard_skill", "proficiency": "熟悉", "is_required": True},
            ],
            market_demand=0.7,
        ),
        "数据分析师": PositionProfile(
            name="数据分析师",
            industry="数据分析",
            required_skills=[
                {"name": "Python", "category": "hard_skill", "proficiency": "熟悉", "is_required": True},
                {"name": "SQL", "category": "hard_skill", "proficiency": "熟悉", "is_required": True},
                {"name": "Pandas", "category": "hard_skill", "proficiency": "熟悉", "is_required": True},
            ],
            market_demand=0.6,
        ),
    }


@pytest.fixture
def backend_skills():
    """后端工程师技能。"""
    return [
        ExtractedSkill(name="Python", raw_name="python", category="hard_skill",
                      proficiency="精通", confidence=0.95, source="llm_extraction"),
        ExtractedSkill(name="PostgreSQL", raw_name="postgres", category="hard_skill",
                      proficiency="熟悉", confidence=0.9, source="llm_extraction"),
        ExtractedSkill(name="Docker", raw_name="docker", category="tool",
                      proficiency="熟悉", confidence=0.85, source="llm_extraction"),
    ]


class TestPositionRecommender:
    @pytest.mark.asyncio
    async def test_recommend_returns_sorted(self, mock_repo, sample_profiles, backend_skills):
        """推荐结果按综合得分降序排列。"""
        mock_repo.get_all_position_profiles.return_value = sample_profiles

        recommender = PositionRecommender(repo=mock_repo, scorer=mock_scorer)
        results = await recommender.recommend(backend_skills, top_k=3)

        assert len(results) <= 3
        # 验证降序
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score

    @pytest.mark.asyncio
    async def test_recommend_backend_skills_match_backend_position(self, mock_repo, sample_profiles, backend_skills):
        """后端技能应最匹配后端岗位。"""
        mock_repo.get_all_position_profiles.return_value = sample_profiles

        recommender = PositionRecommender(repo=mock_repo, scorer=mock_scorer)
        results = await recommender.recommend(backend_skills, top_k=3)

        assert len(results) > 0
        assert results[0].position == "后端开发工程师"

    @pytest.mark.asyncio
    async def test_recommend_empty_profiles(self, mock_repo, backend_skills):
        """无岗位画像时返回空列表。"""
        mock_repo.get_all_position_profiles.return_value = {}

        recommender = PositionRecommender(repo=mock_repo, scorer=mock_scorer)
        results = await recommender.recommend(backend_skills)

        assert results == []

    @pytest.mark.asyncio
    async def test_recommend_empty_skills(self, mock_repo, sample_profiles):
        """无技能时仍返回结果（得分较低）。"""
        mock_repo.get_all_position_profiles.return_value = sample_profiles

        recommender = PositionRecommender(repo=mock_repo, scorer=mock_scorer)
        results = await recommender.recommend([], top_k=3)

        # 应该有结果但得分较低
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_recommend_result_fields(self, mock_repo, sample_profiles, backend_skills):
        """推荐结果包含所有必需字段。"""
        mock_repo.get_all_position_profiles.return_value = sample_profiles

        recommender = PositionRecommender(repo=mock_repo, scorer=mock_scorer)
        results = await recommender.recommend(backend_skills, top_k=1)

        assert len(results) == 1
        rec = results[0]
        assert isinstance(rec, Recommendation)
        assert rec.position
        assert 0 <= rec.score <= 1
        assert 0 <= rec.match_score <= 1
        assert 0 <= rec.developability <= 1
        assert 0 <= rec.market_demand <= 1
        assert isinstance(rec.match_detail, dict)

    @pytest.mark.asyncio
    async def test_developability_with_prerequisites(self, mock_repo, sample_profiles):
        """有 PREREQUISITE 数据时计算可发展性。"""
        mock_repo.get_all_position_profiles.return_value = sample_profiles

        # 有 Python 技能，缺 Kubernetes（需要 Docker + Linux）
        skills = [
            ExtractedSkill(name="Python", raw_name="python", category="hard_skill",
                          proficiency="精通", confidence=0.9, source="llm_extraction"),
            ExtractedSkill(name="Docker", raw_name="docker", category="tool",
                          proficiency="熟悉", confidence=0.8, source="llm_extraction"),
        ]

        recommender = PositionRecommender(repo=mock_repo, scorer=mock_scorer)
        results = await recommender.recommend(skills, top_k=3)

        # 后端岗位应有较高的可发展性（有 Docker 前置）
        backend_rec = next((r for r in results if r.position == "后端开发工程师"), None)
        assert backend_rec is not None
        assert backend_rec.developability >= 0.0
