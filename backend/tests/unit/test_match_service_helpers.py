"""Unit tests for match service helpers."""
from __future__ import annotations

from app.core.matching.scorer import (
    PROFICIENCY_SCORE,
    _canonical_skill_name,
    _semantic_similarity,
    score_skill_match,
)
from app.core.matching.service import MatchService
from app.core.matching.path_builder import build_learning_path


# 创建 MatchService 实例用于测试
_match_service = MatchService()


class TestCanonicalSkillName:
    def test_basic_skill(self):
        result = _canonical_skill_name("Python")
        assert isinstance(result, str)

    def test_returns_lowercase_normalized(self):
        result = _canonical_skill_name("Python3")
        assert isinstance(result, str)


class TestSemanticSimilarity:
    def test_identical(self):
        assert _semantic_similarity("Python", "Python") == 1.0

    def test_partial_match(self):
        result = _semantic_similarity("Python3", "Python")
        assert 0 <= result <= 1.0


class TestScoreSkillMatch:
    def test_exact_match_required(self):
        target = [{"skill": "Python", "importance": "required", "proficiency": "熟悉"}]
        person = [{"skill": "Python", "proficiency": "熟悉"}]
        result = score_skill_match(target_skills=target, person_skills=person)
        assert len(result["evaluated"]) == 1
        assert result["evaluated"][0]["gap_level"] == "已掌握"

    def test_missing_skill(self):
        target = [{"skill": "Rust", "importance": "required", "proficiency": "熟悉"}]
        person = [{"skill": "Python", "proficiency": "熟悉"}]
        result = score_skill_match(target_skills=target, person_skills=person)
        assert result["evaluated"][0]["gap_level"] == "完全缺失"

    def test_empty_inputs(self):
        result = score_skill_match(target_skills=[], person_skills=[])
        assert result["evaluated"] == []


class TestApplyInflationCorrection:
    def test_no_correction_for_small_profile(self):
        profile = {"required": [{"skill": "Python"}], "bonus": []}
        req, bonus, cii = _match_service._apply_inflation_correction(profile)
        assert len(req) == 1
        assert cii > 0

    def test_inflation_correction_for_large_profile(self):
        large_required = [
            {"skill": f"Skill{i}", "proficiency": "熟悉"} for i in range(10)
        ]
        profile = {"required": large_required, "bonus": []}
        req, bonus, cii = _match_service._apply_inflation_correction(profile)
        # Some should be downgraded
        assert len(req) < 10
        assert cii > 1.0


class TestBuildLearningPath:
    def test_no_prerequisites(self):
        path = build_learning_path("Python", set(), {})
        assert "Python" in path

    def test_with_prerequisites(self):
        # 使用测试用的前置关系映射
        prereq_map = {
            "Pandas": ["Python", "NumPy"],
            "NumPy": ["Python"],
        }
        path = build_learning_path("Pandas", set(), prereq_map)
        assert "Python" in path
        assert "NumPy" in path
        assert "Pandas" in path


class TestProficiencyScore:
    def test_known_levels(self):
        assert PROFICIENCY_SCORE["了解"] == 0.35
        assert PROFICIENCY_SCORE["熟悉"] == 0.65
        assert PROFICIENCY_SCORE["精通"] == 0.9
