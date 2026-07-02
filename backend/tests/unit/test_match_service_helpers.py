"""Unit tests for match service helpers."""
from __future__ import annotations

from app.services.match_service import (
    POSITION_SKILL_PROFILES,
    PREREQUISITE_MAP,
    PROFICIENCY_SCORE,
    _apply_inflation_correction,
    _build_learning_path,
    _canonical_skill_name,
    _fallback_profile,
    _position_key,
    _semantic_similarity,
    score_skill_match,
)


class TestPositionKey:
    def test_strips_and_lowercases(self):
        assert _position_key("Backend Engineer") == "backendengineer"

    def test_empty_string(self):
        assert _position_key("") == ""


class TestCanonicalSkillName:
    def test_basic_skill(self):
        result = _canonical_skill_name("Python")
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
        req, bonus, cii = _apply_inflation_correction(profile)
        assert len(req) == 1
        assert cii > 0

    def test_inflation_correction_for_large_profile(self):
        large_required = [
            {"skill": f"Skill{i}", "proficiency": "熟悉"} for i in range(10)
        ]
        profile = {"required": large_required, "bonus": []}
        req, bonus, cii = _apply_inflation_correction(profile)
        # Some should be downgraded
        assert len(req) < 10
        assert cii > 1.0


class TestBuildLearningPath:
    def test_no_prerequisites(self):
        path = _build_learning_path("Python", set())
        assert "Python" in path

    def test_with_prerequisites(self):
        path = _build_learning_path("Pandas", set())
        assert "Python" in path
        assert "NumPy" in path
        assert "Pandas" in path

    def test_no_cycles(self):
        # Add a cycle
        PREREQUISITE_MAP["CycleTest"] = ["CycleTest"]
        path = _build_learning_path("CycleTest", set())
        assert "CycleTest" in path
        del PREREQUISITE_MAP["CycleTest"]


class TestFallbackProfile:
    def test_exact_match(self):
        profile = _fallback_profile("数据分析师")
        assert "required" in profile

    def test_fuzzy_match(self):
        profile = _fallback_profile("后端")
        assert "required" in profile

    def test_no_match(self):
        profile = _fallback_profile("NonExistent Position XYZ")
        assert "required" in profile  # Falls back to default


class TestProficiencyScore:
    def test_known_levels(self):
        assert PROFICIENCY_SCORE["了解"] == 0.35
        assert PROFICIENCY_SCORE["熟悉"] == 0.65
        assert PROFICIENCY_SCORE["精通"] == 0.9
