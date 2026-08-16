"""Pipeline 步骤和引擎的单元测试。"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock

import pytest

from app.core.pipeline.sse.contracts import (
    ExtractedSkill,
    PipelineContext,
    PositionProfile,
)
from app.core.pipeline.sse.engine import PipelineEngine, _build_result, _sse_event
from app.core.pipeline.sse.steps import (
    LearningPathStep,
    MatchStep,
    RecommendStep,
    ResumeParseStep,
    SkillExtractStep,
)

# ── contracts 测试 ─────────────────────────────────────────


class TestExtractedSkill:
    def test_creation(self):
        skill = ExtractedSkill(
            name="Python",
            raw_name="python",
            category="hard_skill",
            proficiency="精通",
            confidence=0.95,
            source="llm_extraction",
        )
        assert skill.name == "Python"
        assert skill.confidence == 0.95

    def test_default_values(self):
        skill = ExtractedSkill(
            name="SQL",
            raw_name="sql",
            category="hard_skill",
            proficiency="熟悉",
            confidence=0.8,
            source="manual",
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
            name="后端开发工程师",
            industry="IT",
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
        data_line = [line for line in event.split("\n") if line.startswith("data:")][0]
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
                ExtractedSkill(
                    name="Python",
                    raw_name="python",
                    category="hard_skill",
                    proficiency="精通",
                    confidence=0.9,
                    source="llm_extraction",
                ),
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


class TestResumeParseStep:
    @pytest.mark.asyncio
    async def test_skip_when_text_exists(self):
        step = ResumeParseStep()
        ctx = PipelineContext(resume_text="already parsed")
        result = await step.execute(ctx)
        assert result.resume_text == "already parsed"

    @pytest.mark.asyncio
    async def test_no_file_content(self):
        step = ResumeParseStep()
        ctx = PipelineContext()
        result = await step.execute(ctx)
        assert "无文件内容" in result.errors[-1]


class TestSkillExtractStep:
    @pytest.mark.asyncio
    async def test_no_resume_text(self):
        step = SkillExtractStep()
        ctx = PipelineContext()
        result = await step.execute(ctx)
        assert "无简历文本" in result.errors[-1]

    @pytest.mark.asyncio
    async def test_empty_text(self):
        step = SkillExtractStep()
        ctx = PipelineContext(resume_text="")
        result = await step.execute(ctx)
        assert "无简历文本" in result.errors[-1]


class TestMatchStep:
    @pytest.mark.asyncio
    async def test_no_skills(self):
        repo = MagicMock()
        step = MatchStep(repo=repo)
        ctx = PipelineContext()
        result = await step.execute(ctx)
        assert "无技能数据" in result.errors[-1]


class TestLearningPathStep:
    @pytest.mark.asyncio
    async def test_no_match_results(self):
        step = LearningPathStep()
        ctx = PipelineContext()
        result = await step.execute(ctx)
        assert "无匹配结果" in result.errors[-1]


class TestRecommendStep:
    @pytest.mark.asyncio
    async def test_no_skills(self):
        repo = MagicMock()
        step = RecommendStep(repo=repo)
        ctx = PipelineContext()
        result = await step.execute(ctx)
        assert "无技能数据" in result.errors[-1]


class TestBuildResultLearningPathNone:
    """Phase 24 P0 fix: gap.learning_path 显式为 None 时不得进入 learning_path_summary。

    复现用户可见崩溃: "Cannot read properties of undefined (reading 'length')"。
    后端 gap.get("learning_path", []) 在字段显式 None 时返回 None → 前端
    v-for path.length 崩溃。修复后 None 被 `or []` 过滤为 []。
    """

    def test_learning_path_none_does_not_crash(self):
        ctx = PipelineContext(
            extracted_skills=[
                ExtractedSkill(
                    name="Python", raw_name="python", category="hard_skill",
                    proficiency="精通", confidence=0.9, source="llm_extraction",
                ),
            ],
            match_results={
                "前端工程师": {
                    "match_score": 0.6,
                    "overall_assessment": "部分匹配",
                    "missing_required": ["React"],
                    "skill_gap_detail": [
                        {
                            "skill": "React", "importance": "required",
                            "gap_level": "完全缺失", "score": 0.1,
                            # 模拟后端返回 None（而非缺省）——旧代码此处会漏进 result
                            "learning_path": None,
                        },
                    ],
                },
            },
            recommended_positions=[],
            data_source="graph",
        )
        result = _build_result(ctx)
        # learning_path_summary 必须不含 None 元素（前端 v-for path.length 崩溃点）
        assert result["learning_path_summary"] == [[]]
        for path in result["learning_path_summary"]:
            assert path is not None
        assert all(isinstance(p, list) for p in result["learning_path_summary"])
