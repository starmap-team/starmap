"""Unit tests for skill normalization pipeline."""


from app.core.extraction.normalize import (
    NormalizationResult,
    batch_normalize_skills,
    build_alias_reverse_index,
    get_standard_skill_seeds,
    load_skill_aliases_from_yaml,
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


class TestYamlAliasLoading:
    """Tests for YAML taxonomy alias loading (new in M2)."""

    def test_load_from_nonexistent_path(self):
        """Test returns empty dict when YAML file doesn't exist."""
        from pathlib import Path
        result = load_skill_aliases_from_yaml(Path("/tmp/_nonexistent_starmap_taxonomy.yaml"))
        assert result == {}

    def test_load_from_valid_yaml(self, tmp_path):
        """Test parses valid taxonomy YAML correctly."""
        import yaml
        taxonomy = {
            "ontology": {
                "domains": [
                    {
                        "name": "Programming Languages",
                        "subdomains": [
                            {
                                "name": "General",
                                "skills": [
                                    {"name": "Python", "aliases": ["py", "python3", "python37"]},
                                    {"name": "Java", "aliases": ["java8", "java11", "java17"]},
                                ],
                            }
                        ],
                    }
                ]
            }
        }
        p = tmp_path / "skill_taxonomy.yaml"
        with open(p, "w", encoding="utf-8") as f:
            yaml.dump(taxonomy, f)

        result = load_skill_aliases_from_yaml(p)
        assert "Python" in result
        assert result["Python"] == ["py", "python3", "python37"]
        assert "Java" in result
        assert len(result) == 2

    def test_load_empty_domains(self, tmp_path):
        """Test returns empty dict when domains list is empty."""
        import yaml
        taxonomy = {"ontology": {"domains": []}}
        p = tmp_path / "empty.yaml"
        with open(p, "w", encoding="utf-8") as f:
            yaml.dump(taxonomy, f)
        result = load_skill_aliases_from_yaml(p)
        assert result == {}


class TestReverseIndexAndSeeds:
    """Tests for reverse index builder and skill seed functions."""

    def test_build_alias_reverse_index(self):
        """Test reverse index maps all aliases to correct standard names."""
        idx = build_alias_reverse_index()
        assert isinstance(idx, dict)
        assert len(idx) > 100  # should have hundreds of entries
        assert idx["python"] == "Python"
        assert idx["golang"] == "Go"
        assert idx["reactjs"] == "React"
        assert idx["typescript"] == "TypeScript"

    def test_build_alias_reverse_index_preserves_standard(self):
        """Test standard name maps to itself in the index."""
        idx = build_alias_reverse_index()
        assert idx["python"] == "Python"
        assert idx["go"] == "Go"
        assert idx["java"] == "Java"

    def test_get_standard_skill_seeds(self):
        """Test returns sorted list of canonical skill names."""
        seeds = get_standard_skill_seeds()
        assert isinstance(seeds, list)
        assert len(seeds) > 50
        assert seeds == sorted(seeds)
        assert "Python" in seeds
        assert "Java" in seeds
        assert "React" in seeds

    def test_get_standard_skill_seeds_includes_new_aliases(self):
        """Test newly added M2 aliases appear in seeds."""
        seeds = get_standard_skill_seeds()
        assert "Element Plus" in seeds
        assert "Celery" in seeds
        assert "Matplotlib" in seeds


class TestNewAliasesM2:
    """Tests for the M2 extended alias library."""

    def test_element_plus_alias(self):
        """Test Element Plus aliases."""
        for alias in ["element plus", "element-plus", "elementplus", "element ui", "element-ui"]:
            result = normalize_by_alias(alias)
            assert result == "Element Plus", f"Alias '{alias}' should map to Element Plus"

    def test_celery_alias(self):
        """Test Celery aliases."""
        for alias in ["celery", "celery task", "celery queue"]:
            result = normalize_by_alias(alias)
            assert result == "Celery", f"Alias '{alias}' should map to Celery"

    def test_sap_hana_alias(self):
        """Test SAP HANA aliases."""
        for alias in ["sap hana", "sap hana db", "hana", "hana db"]:
            result = normalize_by_alias(alias)
            assert result == "SAP HANA", f"Alias '{alias}' should map to SAP HANA"

    def test_mybatis_alias(self):
        """Test MyBatis aliases."""
        for alias in ["mybatis", "mybatis plus", "mybatis-plus", "mybatis3"]:
            result = normalize_by_alias(alias)
            assert result == "MyBatis", f"Alias '{alias}' should map to MyBatis"

    def test_matplotlib_alias(self):
        """Test Matplotlib aliases."""
        for alias in ["matplotlib", "matplotlib plot", "mpl"]:
            result = normalize_by_alias(alias)
            assert result == "Matplotlib", f"Alias '{alias}' should map to Matplotlib"
