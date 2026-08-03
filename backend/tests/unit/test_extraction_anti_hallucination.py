"""Unit tests for anti-hallucination checker module."""

from app.core.extraction.anti_hallucination import (
    AntiHallucinationChecker,
    AntiHallucinationResult,
    normalize_skill_list,
    normalize_str_list,
)


class TestAntiHallucinationCheckerImports:
    """Verify module exports are importable."""

    def test_anti_hallucination_checker_imports(self):
        """Verify all expected symbols are exported."""
        assert AntiHallucinationChecker is not None
        assert AntiHallucinationResult is not None
        assert normalize_skill_list is not None
        assert normalize_str_list is not None


class TestAntiHallucinationChecker:
    """Tests for AntiHallucinationChecker.check_skill."""

    def setup_method(self) -> None:
        self.checker = AntiHallucinationChecker()

    def test_anti_hallucination_valid_skill(self):
        """Verify a valid skill passes the check."""
        is_valid, confidence = self.checker.check_skill("Python", "Python", 0.95)
        assert is_valid is True
        assert confidence == 0.95

    def test_valid_skill_multiple_words(self):
        """Verify multi-word skill names pass."""
        is_valid, confidence = self.checker.check_skill(
            "Natural Language Processing", "Natural Language Processing", 0.9
        )
        assert is_valid is True

    def test_valid_skill_with_hyphen(self):
        """Verify skill names with hyphens pass."""
        is_valid, _ = self.checker.check_skill("scikit-learn", "scikit-learn", 0.8)
        assert is_valid is True

    def test_valid_skill_with_plus(self):
        """Verify skill names with plus signs pass."""
        is_valid, _ = self.checker.check_skill("C++", "C++", 0.9)
        assert is_valid is True

    def test_valid_skill_chinese(self):
        """Verify Chinese skill names pass."""
        is_valid, _ = self.checker.check_skill("项目管理", "项目管理", 0.9)
        assert is_valid is True

    def test_too_short(self):
        """Verify single-character skill names are rejected."""
        is_valid, confidence = self.checker.check_skill("X", "X", 0.9)
        assert is_valid is False
        assert confidence == 0.0

    def test_too_long(self):
        """Verify overly long skill names are rejected."""
        is_valid, confidence = self.checker.check_skill("A" * 101, "A" * 101, 0.9)
        assert is_valid is False
        assert confidence == 0.0

    def test_garbage_characters(self):
        """Verify skill names with garbage characters are rejected."""
        is_valid, _ = self.checker.check_skill("Python{}", "Python{}", 0.9)
        assert is_valid is False

    def test_invalid_pattern(self):
        """Verify skill names starting with special chars are rejected."""
        is_valid, _ = self.checker.check_skill("/skill", "/skill", 0.9)
        assert is_valid is False

    def test_empty_string(self):
        """Verify empty string is rejected."""
        is_valid, confidence = self.checker.check_skill("", "", 0.9)
        assert is_valid is False
        assert confidence == 0.0

    def test_whitespace_trimmed(self):
        """Verify whitespace is trimmed before checking."""
        is_valid, confidence = self.checker.check_skill("  Python  ", "  Python  ", 0.9)
        assert is_valid is True
        assert confidence == 0.9


class TestAntiHallucinationResult:
    """Tests for AntiHallucinationResult model."""

    def test_default_values(self):
        """Verify default values."""
        result = AntiHallucinationResult()
        assert result.is_valid is True
        assert result.hallucinated_skills == []
        assert result.missing_skills == []
        assert result.confidence == 1.0
        assert result.issues == []

    def test_custom_values(self):
        """Verify custom values are stored."""
        result = AntiHallucinationResult(
            is_valid=False,
            hallucinated_skills=["Python"],
            missing_skills=["Docker"],
            confidence=0.5,
            issues=["Low confidence"],
        )
        assert result.is_valid is False
        assert result.hallucinated_skills == ["Python"]
        assert result.missing_skills == ["Docker"]
        assert result.confidence == 0.5
        assert result.issues == ["Low confidence"]


class TestNormalizeHelpers:
    """Tests for normalize_skill_list and normalize_str_list."""

    def test_normalize_skill_list_strings(self):
        """Verify plain strings pass through."""
        result = normalize_skill_list(["Python", "Docker"])
        assert result == ["Python", "Docker"]

    def test_normalize_skill_list_dicts(self):
        """Verify dicts have 'name' key extracted."""
        result = normalize_skill_list([
            {"name": "Python", "reasoning": "common"},
            {"name": "Docker"},
        ])
        assert result == ["Python", "Docker"]

    def test_normalize_str_list_empty(self):
        """Verify empty list returns empty list."""
        assert normalize_str_list([]) == []

    def test_normalize_str_list_strings(self):
        """Verify plain strings pass through."""
        assert normalize_str_list(["a", "b"]) == ["a", "b"]

    def test_normalize_str_list_dicts(self):
        """Verify dicts have 'name' key extracted."""
        result = normalize_str_list([
            {"name": "Python", "reasoning": "common"},
            {"skill": "Docker"},
        ])
        assert result == ["Python", "Docker"]

    def test_normalize_str_list_dict_fallback(self):
        """Verify dicts fall back through keys."""
        result = normalize_str_list([
            {"issue": "missing info"},
        ])
        assert result == ["missing info"]