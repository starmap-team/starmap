"""Unit tests for skill normalization pipeline."""

import pytest

from app.core.extraction.normalize import (
    NormalizationResult,
    batch_normalize_skills,
    normalize_by_alias,
    normalize_skill,
)


class TestNormalizeByAlias:
    """Tests for normalize_by_alias function."""

    def test_exact_match(self):
        """Test exact alias match returns canonical name."""
        result = normalize_by_alias("Python")
        assert result == "Python"

    def test_alias_match(self):
        """Test known alias returns canonical name."""
        result = normalize_by_alias("golang")
        assert result == "Go"

        result = normalize_by_alias("reactjs")
        assert result == "React"

        result = normalize_by_alias("k8s")
        assert result == "Kubernetes"

        result = normalize_by_alias("ml")
        assert result == "Machine Learning"

    def test_no_match(self):
        """Test unknown skill returns None."""
        result = normalize_by_alias("completely_unknown_skill_12345")
        assert result is None

    def test_empty_string(self):
        """Test empty string returns None."""
        result = normalize_by_alias("")
        assert result is None

    def test_whitespace_handling(self):
        """Test that whitespace is properly stripped."""
        result = normalize_by_alias("  Python  ")
        assert result == "Python"

    def test_case_insensitive(self):
        """Test that matching is case-insensitive."""
        result = normalize_by_alias("PYTHON")
        assert result == "Python"

        result = normalize_by_alias("GOLANG")
        assert result == "Go"


class TestNormalizeSkillPipeline:
    """Tests for the full normalize_skill pipeline."""

    def test_normalize_skill_alias_hit(self):
        """Test pipeline returns alias match with high confidence."""
        result = normalize_skill("python3")
        assert isinstance(result, NormalizationResult)
        assert result.normalized == "Python"
        assert result.method == "alias"
        assert result.confidence == 0.95
        assert result.is_valid is True

    def test_normalize_skill_no_match(self):
        """Test pipeline returns identity when no match found."""
        result = normalize_skill("some_random_tech")
        assert result.normalized == "some_random_tech"
        assert result.method == "identity"
        assert result.confidence == 0.5
        assert result.is_valid is True
        assert "note" in result.metadata

    def test_normalize_skill_preserves_original(self):
        """Test that the original input is preserved in result."""
        result = normalize_skill("golang")
        assert result.original == "golang"
        assert result.normalized == "Go"


class TestBatchNormalize:
    """Tests for batch normalization."""

    def test_batch_normalize(self):
        """Test batch normalization returns results for all inputs."""
        skills = ["Python", "golang", "reactjs", "unknown_xyz"]
        results = batch_normalize_skills(skills)

        assert len(results) == 4
        assert all(isinstance(r, NormalizationResult) for r in results)

    def test_batch_normalize_mixed_results(self):
        """Test batch handles mix of known and unknown skills."""
        skills = ["Python", "nonexistent_skill_999"]
        results = batch_normalize_skills(skills)

        assert results[0].normalized == "Python"
        assert results[0].method == "alias"

        assert results[1].normalized == "nonexistent_skill_999"
        assert results[1].method == "identity"

    def test_batch_normalize_empty(self):
        """Test batch with empty list returns empty list."""
        results = batch_normalize_skills([])
        assert results == []

    def test_batch_normalize_case_variations(self):
        """Test batch handles case variations."""
        skills = ["PYTHON", "GoLang", "REACTJS"]
        results = batch_normalize_skills(skills)

        assert results[0].normalized == "Python"
        assert results[1].normalized == "Go"
        assert results[2].normalized == "React"

    def test_batch_normalize_canonical_names(self):
        """Test canonical names normalize to themselves."""
        skills = ["Python", "JavaScript", "TypeScript", "Java"]
        results = batch_normalize_skills(skills)

        for r in results:
            assert r.normalized == r.original
            assert r.method == "alias"
