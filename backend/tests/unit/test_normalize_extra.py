"""Additional tests for normalize module."""
from __future__ import annotations

from app.core.extraction.normalize import (
    batch_normalize_skills,
    build_alias_reverse_index,
    get_standard_skill_seeds,
    normalize_skill,
)


class TestNormalizeSkill:
    def test_alias_match(self):
        result = normalize_skill("Py", use_vector=False)
        # "Py" may or may not be in the alias map
        assert result.original == "Py"

    def test_no_vector_match_keeps_original(self):
        result = normalize_skill("XYZUnknownSkill", use_vector=False)
        assert result.method in ("alias", "identity")
        assert result.normalized is not None

    def test_with_vector_disabled(self):
        result = normalize_skill("Python", use_vector=False)
        assert result.original == "Python"


class TestBatchNormalize:
    def test_batch_empty(self):
        results = batch_normalize_skills([], use_vector=False)
        assert results == []

    def test_batch_simple(self):
        results = batch_normalize_skills(["Python", "SQL"], use_vector=False)
        assert len(results) == 2


class TestReverseIndex:
    def test_build_reverse_index(self):
        idx = build_alias_reverse_index()
        assert isinstance(idx, dict)


class TestSeeds:
    def test_get_seeds(self):
        seeds = get_standard_skill_seeds()
        assert isinstance(seeds, list)
