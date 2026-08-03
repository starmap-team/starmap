"""Unit tests for SkillNormalizer class and backward-compatible functions."""

from app.core.extraction.normalize import (
    SKILL_ALIAS,
    SkillNormalizer,
    build_alias_reverse_index,
    extract_dict_skills,
    get_standard_skill_seeds,
    normalize_by_alias,
)


class TestSkillNormalizerImports:
    """Verify module exports are importable."""

    def test_skill_normalizer_imports(self):
        """Verify SkillNormalizer class and backward-compatible symbols are exported."""
        assert SkillNormalizer is not None
        assert SKILL_ALIAS is not None
        assert normalize_by_alias is not None
        assert extract_dict_skills is not None
        assert get_standard_skill_seeds is not None
        assert build_alias_reverse_index is not None


class TestSkillNormalizerClass:
    """Tests for the SkillNormalizer class directly."""

    def setup_method(self) -> None:
        self.normalizer = SkillNormalizer()

    def test_normalize_function_exists(self):
        """Verify backward-compatible normalize_by_alias works."""
        # Delegates to the singleton instance
        result = normalize_by_alias("Python")
        assert result == "Python"

    def test_normalize_by_alias_exact(self):
        """Verify exact match returns canonical name."""
        result = self.normalizer.normalize_by_alias("Python")
        assert result == "Python"

    def test_normalize_by_alias_alias(self):
        """Verify known alias returns canonical name."""
        result = self.normalizer.normalize_by_alias("golang")
        assert result == "Go"

    def test_normalize_by_alias_no_match(self):
        """Verify unknown skill returns None."""
        result = self.normalizer.normalize_by_alias("nonexistent_skill_xyz")
        assert result is None

    def test_normalize_by_alias_empty(self):
        """Verify empty string returns None."""
        result = self.normalizer.normalize_by_alias("")
        assert result is None

    def test_normalize_by_alias_whitespace(self):
        """Verify whitespace is stripped."""
        result = self.normalizer.normalize_by_alias("  Python  ")
        assert result == "Python"

    def test_normalize_by_alias_case_insensitive(self):
        """Verify case-insensitive matching."""
        result = self.normalizer.normalize_by_alias("PYTHON")
        assert result == "Python"

    def test_get_aliases_known(self):
        """Verify get_aliases returns alias list for known skill."""
        aliases = self.normalizer.get_aliases("Python")
        assert "python" in aliases
        assert "python3" in aliases

    def test_get_aliases_unknown(self):
        """Verify get_aliases returns empty list for unknown skill."""
        aliases = self.normalizer.get_aliases("nonexistent_skill_xyz")
        assert aliases == []

    def test_get_standard_skill_seeds(self):
        """Verify get_standard_skill_seeds returns sorted canonical names."""
        seeds = self.normalizer.get_standard_skill_seeds()
        assert "Python" in seeds
        assert "JavaScript" in seeds
        assert "Docker" in seeds
        assert seeds == sorted(seeds)

    def test_extract_dict_skills(self):
        """Verify extract_dict_skills finds skills in text."""
        text = "We need Python and Docker experience"
        skills = self.normalizer.extract_dict_skills(text)
        assert "Python" in skills
        assert "Docker" in skills

    def test_extract_dict_skills_empty(self):
        """Verify extract_dict_skills returns empty set for empty text."""
        assert self.normalizer.extract_dict_skills("") == set()
        assert self.normalizer.extract_dict_skills(None) == set()

    def test_build_reverse_index(self):
        """Verify build_reverse_index returns a complete reverse index."""
        idx = self.normalizer.build_reverse_index()
        assert idx["golang"] == "Go"
        assert idx["python"] == "Python"


class TestBackwardCompatFunctions:
    """Tests for backward-compatible module-level functions."""

    def test_module_level_normalize_by_alias(self):
        """Verify module-level normalize_by_alias delegates correctly."""
        assert normalize_by_alias("golang") == "Go"
        assert normalize_by_alias("unknown_xyz") is None

    def test_module_level_extract_dict_skills(self):
        """Verify module-level extract_dict_skills delegates correctly."""
        skills = extract_dict_skills("We need Python and Docker")
        assert "Python" in skills
        assert "Docker" in skills

    def test_module_level_get_standard_skill_seeds(self):
        """Verify module-level get_standard_skill_seeds returns sorted list."""
        seeds = get_standard_skill_seeds()
        assert "Python" in seeds
        assert seeds == sorted(seeds)

    def test_module_level_build_alias_reverse_index(self):
        """Verify module-level build_alias_reverse_index returns index."""
        idx = build_alias_reverse_index()
        assert idx["golang"] == "Go"

    def test_skill_alias_is_dict(self):
        """Verify SKILL_ALIAS is still a dict and contains known skills."""
        assert isinstance(SKILL_ALIAS, dict)
        assert "Python" in SKILL_ALIAS
        assert "Docker" in SKILL_ALIAS
