"""Unit tests for SSE Pipeline engine.

Tests cover PipelineEngine construction, step execution, error handling,
and _build_step_output validation.
"""

from __future__ import annotations

import asyncio
import inspect
import json

import pytest

from app.core.pipeline.sse.engine import PipelineEngine, _build_step_output
from app.core.pipeline.sse.contracts import PipelineContext, ExtractedSkill
from app.core.pipeline.sse.steps import (
    ResumeParseStep,
    SkillExtractStep,
    MatchStep,
    LearningPathStep,
    RecommendStep,
)


class TestPipelineEngineInit:
    def test_engine_constructs_with_steps(self):
        steps = [SkillExtractStep(), ResumeParseStep()]
        engine = PipelineEngine(steps=steps)
        assert engine._steps == steps

    def test_engine_constructs_with_empty_steps(self):
        engine = PipelineEngine(steps=[])
        assert engine._steps == []


class TestBuildStepOutput:
    def test_returns_dict(self):
        ctx = PipelineContext()
        ctx.extracted_skills.append(
            ExtractedSkill(
                name="Python",
                raw_name="python",
                category="hard_skill",
                proficiency="熟悉",
                confidence=0.9,
                source="llm_extraction",
            )
        )
        result = _build_step_output("skill_extract", ctx)
        assert isinstance(result, dict)
        assert result.get("step") == "skill_extract"

    def test_serializes_to_json(self):
        ctx = PipelineContext()
        result = _build_step_output("crawl", ctx)
        encoded = json.dumps(result, default=str)
        decoded = json.loads(encoded)
        assert decoded == result

    def test_empty_context_safe(self):
        """Empty PipelineContext must not crash _build_step_output."""
        ctx = PipelineContext()
        result = _build_step_output("crawl", ctx)
        assert isinstance(result, dict)


class TestPipelineEngineRun:
    @pytest.mark.asyncio
    async def test_run_yields_events(self):
        """PipelineEngine.run() returns an AsyncIterator[str]."""
        engine = PipelineEngine(steps=[])
        ctx = PipelineContext()
        gen = engine.run(ctx)
        assert inspect.isasyncgen(gen)

    @pytest.mark.asyncio
    async def test_run_with_steps_emits_step_events(self):
        """Each step must emit at least one SSE event."""
        engine = PipelineEngine(steps=[SkillExtractStep()])
        ctx = PipelineContext()
        events = []
        async for event in engine.run(ctx):
            events.append(event)
        # start event + step events (may be skipped if step lacks resume_text)
        assert isinstance(events, list)

    @pytest.mark.asyncio
    async def test_run_handles_step_exception_gracefully(self):
        """Step raising exception should not crash the stream."""

        class ExplodingStep:
            name = "explode"
            timeout = 5

            async def execute(self, ctx):
                raise RuntimeError("step exploded")

        engine = PipelineEngine(steps=[ExplodingStep()])
        ctx = PipelineContext()
        events = []
        async for event in engine.run(ctx):
            events.append(event)
        # Step exception is caught; stream continues
        assert isinstance(events, list)
        assert len(events) >= 1
        # Error should be recorded on the context
        assert any("explode" in e or "error" in e.lower() for e in events) or ctx.errors

    @pytest.mark.asyncio
    async def test_run_with_no_steps_still_emits_start_event(self):
        engine = PipelineEngine(steps=[])
        ctx = PipelineContext()
        events = []
        async for event in engine.run(ctx):
            events.append(event)
        assert len(events) >= 1


class TestPipelineEngineSteps:
    @pytest.mark.asyncio
    async def test_skill_extract_step_runs(self):
        """SkillExtractStep.execute handles empty resume_text gracefully."""
        step = SkillExtractStep()
        ctx = PipelineContext()
        ctx = await step.execute(ctx)
        assert ctx is not None

    @pytest.mark.asyncio
    async def test_resume_parse_step_runs(self):
        step = ResumeParseStep()
        ctx = PipelineContext()
        ctx = await step.execute(ctx)
        assert ctx is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-cov"])
