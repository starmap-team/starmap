"""Pipeline 引擎 — 流程编排和 SSE 事件推送。

PipelineEngine 编排步骤序列，支持单步超时、部分失败和 SSE 进度推送。
Phase 3: 每步成功后增加 step_output SSE 事件，支持前端逐步可视化核验。
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from loguru import logger

from app.core.constants import GAP_LEVEL_MASTERED
from app.core.pipeline.sse.contracts import PipelineContext


class PipelineEngine:
    """Pipeline 流程编排引擎。

    按顺序执行步骤列表，每步支持独立超时和错误处理。
    通过 AsyncIterator[str] 推送 SSE 进度事件。
    每步成功后推送 step_output 事件供前端可视化核验。
    """

    def __init__(self, steps: list) -> None:
        self._steps = steps

    async def run(self, ctx: PipelineContext) -> AsyncIterator[str]:
        """执行 Pipeline 并生成 SSE 事件流。

        Yields:
            SSE 格式的字符串（"event: xxx\\ndata: xxx\\n\\n"）。
        """
        yield _sse_event("progress", {"step": "start", "status": "running"})

        for step in self._steps:
            ctx.progress[step.name] = "running"
            yield _sse_event(
                "progress",
                {
                    "step": step.name,
                    "status": "running",
                },
            )

            try:
                ctx = await asyncio.wait_for(
                    step.execute(ctx),
                    timeout=step.timeout,
                )
                ctx.progress[step.name] = "done"
                yield _sse_event(
                    "progress",
                    {
                        "step": step.name,
                        "status": "done",
                    },
                )
                # Phase 3: 每步成功后推送详细输出供前端可视化核验
                step_output = _build_step_output(step.name, ctx)
                yield _sse_event("step_output", step_output)
            except TimeoutError:
                ctx.errors.append(f"{step.name} timeout ({step.timeout}s)")
                ctx.progress[step.name] = "timeout"
                yield _sse_event(
                    "progress",
                    {
                        "step": step.name,
                        "status": "timeout",
                    },
                )
                yield _sse_event(
                    "step_output",
                    {
                        "step": step.name,
                        "status": "timeout",
                        "error": f"超时 ({step.timeout}s)",
                        "verification": {"passed": False, "checks": [{"check": "执行超时", "ok": False}]},
                    },
                )
                logger.warning("[Pipeline] Step {} timed out after {}s", step.name, step.timeout)
            except Exception as exc:
                ctx.errors.append(f"{step.name} error: {exc}")
                ctx.progress[step.name] = "error"
                yield _sse_event(
                    "progress",
                    {
                        "step": step.name,
                        "status": "error",
                        "error": str(exc),
                    },
                )
                yield _sse_event(
                    "step_output",
                    {
                        "step": step.name,
                        "status": "error",
                        "error": str(exc),
                        "verification": {"passed": False, "checks": [{"check": f"执行异常: {exc}", "ok": False}]},
                    },
                )
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
    learning_path = [gap.get("learning_path", []) for gap in skill_gaps if gap.get("gap_level") != GAP_LEVEL_MASTERED]

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


# ---------------------------------------------------------------------------
# Phase 3: 逐步可视化核验 — 每步的输出摘要和验证检查
# ---------------------------------------------------------------------------


def _build_step_output(step_name: str, ctx: PipelineContext) -> dict[str, Any]:
    """构建单个步骤的输出摘要和验证结果。

    返回结构:
        {
            "step": str,           # 步骤标识名
            "display_name": str,   # 中文显示名
            "status": "done",
            "input_summary": {...},  # 输入摘要
            "output_summary": {...}, # 输出摘要
            "samples": [...],       # 数据样本（供前端展示）
            "verification": {       # 验证检查结果
                "passed": bool,
                "checks": [{"check": str, "ok": bool, "detail": str}, ...]
            },
        }
    """
    _display = {
        "resume_parse": "简历解析",
        "skill_extract": "技能提取",
        "match": "岗位匹配",
        "learning_path": "学习路径",
        "recommend": "岗位推荐",
    }
    display_name = _display.get(step_name, step_name)
    builder = _STEP_BUILDERS.get(step_name)
    if builder is None:
        return {
            "step": step_name,
            "display_name": display_name,
            "status": "done",
            "input_summary": {},
            "output_summary": {"note": f"未知步骤类型: {step_name}"},
            "samples": [],
            "verification": {"passed": True, "checks": []},
        }
    return builder(step_name, display_name, ctx)


def _build_resume_parse_output(
    step_name: str,
    display_name: str,
    ctx: PipelineContext,
) -> dict[str, Any]:
    """简历解析步骤的输出和验证。"""
    text = ctx.resume_text or ""
    text_len = len(text)
    checks = [
        {
            "check": "文件解析成功",
            "ok": text_len > 0,
            "detail": f"解析后文本长度: {text_len} 字符" if text_len > 0 else "未获取到文本内容",
        },
        {
            "check": "文本长度合理",
            "ok": text_len >= 100,
            "detail": f"{text_len} 字符 (建议≥100)" if text_len >= 100 else f"仅 {text_len} 字符，可能解析不完整",
        },
        {
            "check": "包含中文字符",
            "ok": any("\u4e00" <= c <= "\u9fff" for c in text),
            "detail": "文本包含中文" if any("\u4e00" <= c <= "\u9fff" for c in text) else "文本不含中文，可能解析异常",
        },
    ]

    return {
        "step": step_name,
        "display_name": display_name,
        "status": "done",
        "input_summary": {
            "filename": "resume file" if text else "无输入",
            "file_size": f"{len(text)} chars",
        },
        "output_summary": {
            "text_length": text_len,
            "text_preview": text[:200] + ("..." if text_len > 200 else ""),
        },
        "samples": [{"text_preview": text[:500]}],
        "verification": {
            "passed": all(c["ok"] for c in checks),
            "checks": checks,
        },
    }


def _build_skill_extract_output(
    step_name: str,
    display_name: str,
    ctx: PipelineContext,
) -> dict[str, Any]:
    """技能提取步骤的输出和验证。"""
    skills = ctx.extracted_skills
    categories: dict[str, int] = {}
    for s in skills:
        categories[s.category] = categories.get(s.category, 0) + 1

    high_confidence = sum(1 for s in skills if s.confidence >= 0.7)
    low_confidence = sum(1 for s in skills if s.confidence < 0.4)

    skill_names = [s.name for s in skills]
    unique_skills = len(set(skill_names))

    checks = [
        {
            "check": "技能提取数量",
            "ok": len(skills) >= 3,
            "detail": f"提取到 {len(skills)} 个技能 (建议≥3)",
        },
        {
            "check": "去重比例",
            "ok": unique_skills >= len(skills) * 0.7 if skills else True,
            "detail": f"{unique_skills}/{len(skills)} 唯一技能" if skills else "无技能",
        },
        {
            "check": "高置信度比例",
            "ok": high_confidence >= len(skills) * 0.5 if skills else True,
            "detail": f"{high_confidence}/{len(skills)} 高置信度 (≥0.7)",
        },
    ]
    if low_confidence > 0:
        checks.append(
            {
                "check": "低置信度预警",
                "ok": low_confidence <= len(skills) * 0.3,
                "detail": f"{low_confidence}/{len(skills)} 低置信度 (<0.4)",
            }
        )

    return {
        "step": step_name,
        "display_name": display_name,
        "status": "done",
        "input_summary": {"text_length": len(ctx.resume_text or "")},
        "output_summary": {
            "total_skills": len(skills),
            "unique_skills": unique_skills,
            "categories": categories,
            "avg_confidence": round(sum(s.confidence for s in skills) / len(skills), 2) if skills else 0,
        },
        "samples": [{"name": s.name, "category": s.category, "confidence": s.confidence} for s in skills[:10]],
        "verification": {
            "passed": all(c["ok"] for c in checks),
            "checks": checks,
        },
    }


def _build_match_output(
    step_name: str,
    display_name: str,
    ctx: PipelineContext,
) -> dict[str, Any]:
    """岗位匹配步骤的输出和验证。"""
    if not ctx.match_results:
        return {
            "step": step_name,
            "display_name": display_name,
            "status": "done",
            "input_summary": {},
            "output_summary": {"note": "无匹配结果"},
            "samples": [],
            "verification": {
                "passed": False,
                "checks": [
                    {"check": "匹配结果存在", "ok": False, "detail": "无岗位匹配结果"},
                ],
            },
        }

    sorted_matches = sorted(
        ctx.match_results.items(),
        key=lambda x: x[1].get("match_score", 0),
        reverse=True,
    )

    checks = [
        {
            "check": "匹配到至少一个岗位",
            "ok": len(sorted_matches) > 0,
            "detail": f"匹配到 {len(sorted_matches)} 个岗位",
        },
        {
            "check": "Top-1 匹配度",
            "ok": sorted_matches[0][1].get("match_score", 0) >= 0.3 if sorted_matches else False,
            "detail": f"Top-1 匹配度: {sorted_matches[0][1].get('match_score', 0):.2f}" if sorted_matches else "无匹配",
        },
        {
            "check": "数据源可用",
            "ok": ctx.data_source != "unknown",
            "detail": f"数据源: {ctx.data_source}",
        },
    ]

    top_results = []
    for pos_name, result in sorted_matches[:10]:
        top_results.append(
            {
                "position": pos_name,
                "match_score": result.get("match_score", 0),
                "assessment": result.get("overall_assessment", ""),
                "matched": result.get("matched_skills", 0),
                "missing": result.get("missing_required", []),
            }
        )

    return {
        "step": step_name,
        "display_name": display_name,
        "status": "done",
        "input_summary": {"skills": len(ctx.extracted_skills), "targets": ctx.target_positions},
        "output_summary": {
            "total_matches": len(sorted_matches),
            "top_score": sorted_matches[0][1].get("match_score", 0) if sorted_matches else 0,
            "data_source": ctx.data_source,
        },
        "samples": top_results,
        "verification": {
            "passed": all(c["ok"] for c in checks),
            "checks": checks,
        },
    }


def _build_learning_path_output(
    step_name: str,
    display_name: str,
    ctx: PipelineContext,
) -> dict[str, Any]:
    """学习路径步骤的输出和验证。"""
    if not ctx.match_results:
        return {
            "step": step_name,
            "display_name": display_name,
            "status": "done",
            "input_summary": {},
            "output_summary": {"note": "无匹配结果，无法生成学习路径"},
            "samples": [],
            "verification": {
                "passed": False,
                "checks": [{"check": "匹配结果", "ok": False, "detail": "无匹配结果"}],
            },
        }

    # 统计有多少个岗位有学习路径条目
    paths_count = sum(
        1
        for result in ctx.match_results.values()
        if any(gap.get("learning_path", []) for gap in result.get("skill_gap_detail", []))
    )

    total_gaps = sum(len(result.get("missing_required", [])) for result in ctx.match_results.values())

    checks = [
        {
            "check": "技能差距分析",
            "ok": total_gaps > 0,
            "detail": f"共 {total_gaps} 个技能差距",
        },
        {
            "check": "学习路径生成",
            "ok": paths_count > 0,
            "detail": f"{paths_count} 个岗位有详细学习路径" if paths_count > 0 else "暂无学习路径",
        },
    ]

    return {
        "step": step_name,
        "display_name": display_name,
        "status": "done",
        "input_summary": {"matches": len(ctx.match_results)},
        "output_summary": {
            "total_gaps": total_gaps,
            "paths_generated": paths_count,
        },
        "samples": [],
        "verification": {
            "passed": all(c["ok"] for c in checks),
            "checks": checks,
        },
    }


def _build_recommend_output(
    step_name: str,
    display_name: str,
    ctx: PipelineContext,
) -> dict[str, Any]:
    """岗位推荐步骤的输出和验证。"""
    recs = ctx.recommended_positions

    checks = [
        {
            "check": "推荐结果存在",
            "ok": len(recs) > 0,
            "detail": f"推荐了 {len(recs)} 个岗位",
        },
        {
            "check": "推荐质量",
            "ok": len(recs) >= 3,
            "detail": f"推荐 {len(recs)} 个 (建议≥3)",
        },
    ]

    return {
        "step": step_name,
        "display_name": display_name,
        "status": "done",
        "input_summary": {"matches": len(ctx.match_results)},
        "output_summary": {"total_recommendations": len(recs)},
        "samples": [{"position": r.get("position"), "score": r.get("score")} for r in recs[:10]],
        "verification": {
            "passed": all(c["ok"] for c in checks),
            "checks": checks,
        },
    }


# 步骤输出构建器查找表
_STEP_BUILDERS = {
    "resume_parse": _build_resume_parse_output,
    "skill_extract": _build_skill_extract_output,
    "match": _build_match_output,
    "learning_path": _build_learning_path_output,
    "recommend": _build_recommend_output,
}
