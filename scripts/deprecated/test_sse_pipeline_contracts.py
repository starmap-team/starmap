"""Unit tests for SSE Pipeline contracts.

Tests cover the contract types used by the SSE pipeline:
PipelineContext, ExtractedSkill, PositionProfile, DataQualityStats.

These are plain Python classes (not dataclasses) with mutable defaults.
The contract tests verify the class shape and that constructors don't crash.
"""

from __future__ import annotations

import pytest

from app.core.pipeline.sse.contracts import (
    DataQualityStats,
    ExtractedSkill,
    PipelineContext,
    PositionProfile,
)


class TestPipelineContext:
    def test_default_construction(self):
        ctx = PipelineContext()
        assert ctx is not None

    def test_extracted_skills_default_empty(self):
        ctx = PipelineContext()
        assert ctx.extracted_skills == []

    def test_mutable_state_independent(self):
        """Two contexts should have independent mutable state (default_factory)."""
        ctx_a = PipelineContext()
        ctx_b = PipelineContext()
        ctx_a.extracted_skills.append(
            ExtractedSkill(
                name="Python",
                raw_name="python",
                category="hard_skill",
                proficiency="熟悉",
                confidence=0.9,
                source="llm_extraction",
            )
        )
        assert ctx_b.extracted_skills == []
        assert len(ctx_a.extracted_skills) == 1


class TestExtractedSkill:
    def test_construction(self):
        skill = ExtractedSkill(
            name="Python",
            raw_name="python",
            category="hard_skill",
            proficiency="熟悉",
            confidence=0.9,
            source="llm_extraction",
        )
        assert skill.name == "Python"
        assert skill.category == "hard_skill"
        assert skill.confidence == 0.9


class TestPositionProfile:
    def test_construction(self):
        profile = PositionProfile(
            name="Data Scientist",
            industry="AI",
            required_skills=[],
        )
        assert profile.name == "Data Scientist"
        assert profile.industry == "AI"
        assert profile.required_skills == []


class TestDataQualityStats:
    def test_construction(self):
        stats = DataQualityStats(
            total_positions=10,
            positions_with_skills=8,
            coverage_ratio=0.8,
            total_skills=100,
            skills_with_sources=80,
            skill_trust_ratio=0.8,
            prerequisite_count=50,
        )
        assert stats.total_positions == 10
        assert stats.coverage_ratio == 0.8


class TestContractImports:
    def test_all_contracts_exported(self):
        from app.core.pipeline.sse import contracts

        for name in (
            "PipelineContext",
            "ExtractedSkill",
            "PositionProfile",
            "DataQualityStats",
        ):
            assert hasattr(contracts, name), f"Missing export: {name}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-cov"])
