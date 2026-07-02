"""Pipeline 引擎 — 流程编排和 SSE 事件推送。

PipelineEngine 编排 PipelineStep 序列，支持单步超时、部分失败和 SSE 进度推送。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

from loguru import logger

from app.pipeline.contracts import PipelineContext, PipelineEvent, PipelineStep


class PipelineEngine:
    """Pipeline 流程编排引擎。

    按顺序执行步骤列表，每步支持独立超时和错误处理。
    通过 AsyncIterator[PipelineEvent] 推送 SSE 进度事件。
    """

    def __init__(self, steps: list[PipelineStep]) -> None:
        self._steps = steps

    async def run(self, ctx: PipelineContext) -> AsyncIterator[str]:
        """执行 Pipeline 并生成 SSE 事件流。

        Yields:
            SSE 格式的字符串（"event: xxx\\ndata: xxx\\n\\n"）。
        """
        yield _sse_event("progress", {"step": "start", "status": "running"})

        for step in self._steps:
            ctx.progress[step.name] = "running"
            yield _sse_event("progress", {
                "step": step.name,
                "status": "running",
            })

            try:
                ctx = await asyncio.wait_for(
                    step.execute(ctx),
                    timeout=step.timeout,
                )
                ctx.progress[step.name] = "done"
                yield _sse_event("progress", {
                    "step": step.name,
                    "status": "done",
                })
            except asyncio.TimeoutError:
                ctx.errors.append(f"{step.name} timeout ({step.timeout}s)")
                ctx.progress[step.name] = "timeout"
                yield _sse_event("progress", {
                    "step": step.name,
                    "status": "timeout",
                })
                logger.warning("[Pipeline] Step {} timed out after {}s", step.name, step.timeout)
            except Exception as exc:
                ctx.errors.append(f"{step.name} error: {exc}")
                ctx.progress[step.name] = "error"
                yield _sse_event("progress", {
                    "step": step.name,
                    "status": "error",
                    "error": str(exc),
                })
                logger.error("[Pipeline] Step {} failed: {}", step.name, exc)

        # 构建最终结果
        result = _build_result(ctx)
        yield _sse_event("result", result)
        yield _sse_event("progress", {"step": "complete", "status": "done"})


def _sse_event(event: str, data: Any) -> str:
    """格式化 SSE 事件。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _build_result(ctx: PipelineContext) -> dict[str, Any]:
    """从 PipelineContext 构建最终结果字典。"""
    # 按匹配分数排序的岗位匹配结果
    sorted_matches = sorted(
        ctx.match_results.items(),
        key=lambda x: x[1].get("match_score", 0),
        reverse=True,
    )

    # 取 top-1 岗位的差距和学习路径
    top_match = sorted_matches[0][1] if sorted_matches else {}
    skill_gaps = top_match.get("skill_gap_detail", [])
    learning_path = [
        gap.get("learning_path", [])
        for gap in skill_gaps
        if gap.get("gap_level") != "已掌握"
    ]

    return {
        "extracted_skills": [
            {
                "name": s.name,
                "raw_name": s.raw_name,
                "category": s.category,
                "proficiency": s.proficiency,
                "confidence": s.confidence,
            }
            for s in ctx.extracted_skills
        ],
        "top_matches": [
            {
                "position": name,
                "match_score": result.get("match_score", 0),
                "assessment": result.get("overall_assessment", ""),
                "gap_count": len(result.get("missing_required", [])),
            }
            for name, result in sorted_matches[:10]
        ],
        "recommended_positions": ctx.recommended_positions[:10],
        "skill_gaps": skill_gaps,
        "learning_path_summary": learning_path[:5],
        "data_source": ctx.data_source,
        "errors": ctx.errors,
    }
