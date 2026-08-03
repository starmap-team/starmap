"""Smoke tests for pipeline steps — basic structure verification.

Covers:
- Step name attributes
- Step timeout attributes
- Step class existence
- PipelineContext dataclass
- ExtractedSkill dataclass
"""

from __future__ import annotations

from app.core.pipeline.sse.contracts import ExtractedSkill, PipelineContext
from app.core.pipeline.sse.steps import LearningPathStep, MatchStep, RecommendStep, ResumeParseStep, SkillExtractStep


class TestStepNames:
    """Tests for pipeline step name attributes."""

    def test_resume_parse_step_name(self):
        step = ResumeParseStep()
        assert step.name == "resume_parse"

    def test_skill_extract_step_name(self):
        step = SkillExtractStep()
        assert step.name == "skill_extract"

    def test_match_step_name(self):
        step = MatchStep.__new__(MatchStep)
        assert step.name == "match"

    def test_learning_path_step_name(self):
        step = LearningPathStep.__new__(LearningPathStep)
        assert step.name == "learning_path"

    def test_recommend_step_name(self):
        step = RecommendStep.__new__(RecommendStep)
        assert step.name == "recommend"


class TestStepTimeouts:
    """Tests for pipeline step timeout attributes."""

    def test_resume_parse_timeout(self):
        step = ResumeParseStep()
        assert step.timeout == 60

    def test_skill_extract_timeout(self):
        step = SkillExtractStep()
        assert step.timeout == 30

    def test_match_step_timeout(self):
        step = MatchStep.__new__(MatchStep)
        assert step.timeout == 120

    def test_learning_path_timeout(self):
        step = LearningPathStep.__new__(LearningPathStep)
        assert step.timeout == 30

    def test_recommend_timeout(self):
        step = RecommendStep.__new__(RecommendStep)
        assert step.timeout == 120


class TestPipelineContext:
    """Tests for PipelineContext dataclass."""

    def test_default_context(self):
        ctx = PipelineContext()
        assert ctx.resume_text is None
        assert ctx.resume_file is None
        assert ctx.extracted_skills == []
        assert ctx.match_results == {}
        assert ctx.errors == []

    def test_context_with_resume_text(self):
        ctx = PipelineContext(resume_text="Hello, I am a developer")
        assert ctx.resume_text == "Hello, I am a developer"


class TestExtractedSkill:
    """Tests for ExtractedSkill dataclass."""

    def test_basic_skill(self):
        skill = ExtractedSkill(
            name="Python",
            raw_name="python",
            category="hard_skill",
            proficiency="精通",
            confidence=0.9,
            source="llm_extraction",
        )
        assert skill.name == "Python"
        assert skill.category == "hard_skill"
        assert skill.confidence == 0.9

    def test_skill_source(self):
        skill = ExtractedSkill(
            name="React",
            raw_name="react",
            category="hard_skill",
            proficiency="熟悉",
            confidence=0.8,
            source="graph",
        )
        assert skill.source == "graph"
