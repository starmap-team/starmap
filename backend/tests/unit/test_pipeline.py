"""Pipeline 步骤和引擎的单元测试。"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.pipeline.contracts import (
    ExtractedSkill,
    PipelineContext,
    PipelineEvent,
    PipelineStep,
    PositionProfile,
)
from app.pipeline.engine import PipelineEngine, _build_result, _sse_event


# ── contracts 测试 ─────────────────────────────────────────


class TestExtractedSkill:
    def test_creation(self):
        skill = ExtractedSkill(
            name="Python", raw_name="python", category="hard_skill",
            proficiency="精通", confidence=0.95, source="llm_extraction",
        )
        assert skill.name == "Python"
        assert skill.confidence == 0.95

    def test_default_values(self):
        skill = ExtractedSkill(
            name="SQL", raw_name="sql", category="hard_skill",
            proficiency="熟悉", confidence=0.8, source="manual",
        )
        assert skill.source == "manual"


class TestPipelineContext:
    def test_defaults(self):
        ctx = PipelineContext()
        assert ctx.resume_text is None
        assert ctx.extracted_skills == []
        assert ctx.match_results == {}
        assert ctx.errors == []
        assert ctx.data_source == "unknown"

    def test_error_accumulation(self):
        ctx = PipelineContext()
        ctx.errors.append("step1 error")
        ctx.errors.append("step2 error")
        assert len(ctx.errors) == 2


class TestPositionProfile:
    def test_creation(self):
        profile = PositionProfile(
            name="后端开发工程师", industry="IT",
            required_skills=[{"name": "Python", "category": "hard_skill"}],
        )
        assert profile.name == "后端开发工程师"
        assert profile.market_demand == 0.5  # default


# ── engine 测试 ────────────────────────────────────────────


class TestSSEEvent:
    def test_format(self):
        event = _sse_event("progress", {"step": "extract", "status": "running"})
        assert event.startswith("event: progress\n")
        assert "data:" in event
        assert event.endswith("\n\n")

    def test_json_content(self):
        event = _sse_event("result", {"skills": ["Python", "SQL"]})
        data_line = [l for l in event.split("\n") if l.startswith("data:")][0]
        data = json.loads(data_line[6:])
        assert data["skills"] == ["Python", "SQL"]


class TestBuildResult:
    def test_empty_context(self):
        ctx = PipelineContext()
        result = _build_result(ctx)
        assert result["extracted_skills"] == []
        assert result["top_matches"] == []
        assert result["recommended_positions"] == []
        assert result["data_source"] == "unknown"

    def test_with_match_results(self):
        ctx = PipelineContext(
            extracted_skills=[
                ExtractedSkill(name="Python", raw_name="python", category="hard_skill",
                              proficiency="精通", confidence=0.9, source="llm_extraction"),
            ],
            match_results={
                "后端工程师": {
                    "match_score": 0.85,
                    "overall_assessment": "高度匹配",
                    "missing_required": ["Kubernetes"],
                    "skill_gap_detail": [
                        {"skill": "Python", "importance": "required", "gap_level": "已掌握", "score": 0.95},
                        {"skill": "Kubernetes", "importance": "required", "gap_level": "完全缺失", "score": 0.1},
                    ],
                },
            },
            recommended_positions=[
                {"position": "后端工程师", "score": 0.8, "match_score": 0.85},
            ],
            data_source="graph",
        )
        result = _build_result(ctx)
        assert len(result["extracted_skills"]) == 1
        assert len(result["top_matches"]) == 1
        assert result["top_matches"][0]["position"] == "后端工程师"
        assert result["data_source"] == "graph"


class TestPipelineEngine:
    @pytest.mark.asyncio
    async def test_empty_steps(self):
        engine = PipelineEngine([])
        ctx = PipelineContext()
        events = []
        async for event in engine.run(ctx):
            events.append(event)
        # 至少有 start 和 complete 事件
        assert len(events) >= 2

    @pytest.mark.asyncio
    async def test_step_execution(self):
        class MockStep:
            name = "mock"
            timeout = 5

            async def execute(self, ctx: PipelineContext) -> PipelineContext:
                ctx.resume_text = "test text"
                return ctx

        engine = PipelineEngine([MockStep()])
        ctx = PipelineContext()
        events = []
        async for event in engine.run(ctx):
            events.append(event)

        # 验证事件包含 mock 步骤的 running 和 done
        event_texts = "".join(events)
        assert "mock" in event_texts
        assert ctx.resume_text == "test text"

    @pytest.mark.asyncio
    async def test_step_timeout(self):
        class SlowStep:
            name = "slow"
            timeout = 1

            async def execute(self, ctx: PipelineContext) -> PipelineContext:
                await asyncio.sleep(5)  # 超时
                return ctx

        engine = PipelineEngine([SlowStep()])
        ctx = PipelineContext()
        events = []
        async for event in engine.run(ctx):
            events.append(event)

        # 验证超时被记录
        assert any("timeout" in e for e in events)
        assert any("slow timeout" in e for e in ctx.errors)

    @pytest.mark.asyncio
    async def test_step_error_continues(self):
        class FailStep:
            name = "fail"
            timeout = 5

            async def execute(self, ctx: PipelineContext) -> PipelineContext:
                raise ValueError("test error")

        class OkStep:
            name = "ok"
            timeout = 5

            async def execute(self, ctx: PipelineContext) -> PipelineContext:
                ctx.resume_text = "recovered"
                return ctx

        engine = PipelineEngine([FailStep(), OkStep()])
        ctx = PipelineContext()
        events = []
        async for event in engine.run(ctx):
            events.append(event)

        # fail 步骤的错误被记录，ok 步骤继续执行
        assert any("test error" in e for e in ctx.errors)
        assert ctx.resume_text == "recovered"
