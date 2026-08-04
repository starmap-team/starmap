"""Unit tests for SSE Pipeline steps.

Tests cover the step classes used by the SSE pipeline:
ResumeParseStep, SkillExtractStep, MatchStep, LearningPathStep, RecommendStep.

Each step is a class with a `name` class attribute and an async `execute`
method that takes a PipelineContext.
"""

from __future__ import annotations

import inspect

import pytest

from app.core.pipeline.sse.steps import (
    LearningPathStep,
    MatchStep,
    RecommendStep,
    ResumeParseStep,
    SkillExtractStep,
)


class TestResumeParseStep:
    def test_has_name_attribute(self):
        assert hasattr(ResumeParseStep, "name")
        assert isinstance(ResumeParseStep.name, str)
        assert ResumeParseStep.name == "resume_parse"

    def test_execute_is_async(self):
        assert inspect.iscoroutinefunction(ResumeParseStep.execute)


class TestSkillExtractStep:
    def test_has_name_attribute(self):
        assert SkillExtractStep.name == "skill_extract"

    def test_execute_is_async(self):
        assert inspect.iscoroutinefunction(SkillExtractStep.execute)


class TestMatchStep:
    def test_has_name_attribute(self):
        assert MatchStep.name == "match"

    def test_execute_is_async(self):
        assert inspect.iscoroutinefunction(MatchStep.execute)


class TestLearningPathStep:
    def test_has_name_attribute(self):
        assert LearningPathStep.name == "learning_path"

    def test_execute_is_async(self):
        assert inspect.iscoroutinefunction(LearningPathStep.execute)


class TestRecommendStep:
    def test_has_name_attribute(self):
        assert RecommendStep.name == "recommend"

    def test_execute_is_async(self):
        assert inspect.iscoroutinefunction(RecommendStep.execute)


class TestStepImports:
    def test_all_step_classes_exported(self):
        from app.core.pipeline.sse import steps

        for name in (
            "SkillExtractStep",
            "MatchStep",
            "RecommendStep",
            "LearningPathStep",
            "ResumeParseStep",
        ):
            assert hasattr(steps, name), f"Missing export: {name}"

    def test_step_names_are_unique(self):
        """Step names must be unique — they're used as registry keys."""
        step_names = [
            ResumeParseStep.name,
            SkillExtractStep.name,
            MatchStep.name,
            LearningPathStep.name,
            RecommendStep.name,
        ]
        assert len(step_names) == len(set(step_names)), f"Duplicate step names found: {step_names}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-cov"])
