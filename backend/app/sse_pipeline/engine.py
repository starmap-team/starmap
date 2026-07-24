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

from app.sse_pipeline.contracts import PipelineContext


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
                # Phase 3: 每步成功后推送详细输出供前端可视化核验
                step_output = _build_step_output(step.name, ctx)
                yield _sse_event("step_output", step_output)
            except TimeoutError:
                ctx.errors.append(f"{step.name} timeout ({step.timeout}s)")
                ctx.progress[step.name] = "timeout"
                yield _sse_event("progress", {
                    "step": step.name,
                    "status": "timeout",
                })
                yield _sse_event("step_output", {
                    "step": step.name,
                    "status": "timeout",
                    "error": f"超时 ({step.timeout}s)",
                    "verification": {"passed": False, "checks": [{"check": "执行超时", "ok": False}]},
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
                yield _sse_event("step_output", {
                    "step": step.name,
                    "status": "error",
                    "error": str(exc),
                    "verification": {"passed": False, "checks": [{"check": f"执行异常: {exc}", "ok": False}]},
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
    _display = {"resume_parse": "简历解析", "skill_extract": "技能提取", "match": "岗位匹配",
                "learning_path": "学习路径", "recommend": "岗位推荐"}
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
    step_name: str, display_name: str, ctx: PipelineContext,
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
            "ok": any('\u4e00' <= c <= '\u9fff' for c in text),
            "detail": "文本包含中文" if any('\u4e00' <= c <= '\u9fff' for c in text) else "文本不含中文，可能解析异常",
        },
    ]

    return {
        "step": step_name,
        "display_name": display_name,
        "status": "done",
        "input_summary": {"file_type": "简历文件 (PDF/DOCX)"},
        "output_summary": {
            "text_length": text_len,
            "preview": text[:300] + ("..." if text_len > 300 else ""),
        },
        "samples": [
            {"label": "解析文本预览", "value": text[:200] + ("..." if text_len > 200 else "")},
        ],
        "verification": {"passed": all(c["ok"] for c in checks), "checks": checks},
    }


def _build_skill_extract_output(
    step_name: str, display_name: str, ctx: PipelineContext,
) -> dict[str, Any]:
    """技能提取步骤的输出和验证。"""
    skills = ctx.extracted_skills
    skill_count = len(skills)
    categories: dict[str, int] = {}
    for s in skills:
        cat = s.category or "unknown"
        categories[cat] = categories.get(cat, 0) + 1

    checks = [
        {
            "check": "技能提取数量",
            "ok": skill_count >= 3,
            "detail": f"提取到 {skill_count} 个技能 (建议≥3)" if skill_count >= 3 else f"仅 {skill_count} 个技能，可能提取不足",
        },
        {
            "check": "技能分类完整",
            "ok": len(categories) >= 2,
            "detail": f"覆盖 {len(categories)} 个分类: {categories}" if len(categories) >= 2 else f"仅 {len(categories)} 个分类",
        },
        {
            "check": "技能置信度",
            "ok": all(s.confidence > 0.3 for s in skills) if skills else False,
            "detail": "所有技能置信度>0.3" if skills and all(s.confidence > 0.3 for s in skills) else "存在低置信度技能",
        },
    ]
    if skill_count == 0:
        checks.append({"check": "致命: 无技能数据", "ok": False, "detail": "未提取到任何技能，后续匹配将无法正常进行"})

    return {
        "step": step_name,
        "display_name": display_name,
        "status": "done",
        "input_summary": {"resume_text_length": len(ctx.resume_text or "")},
        "output_summary": {
            "skill_count": skill_count,
            "categories": categories,
            "avg_confidence": round(sum(s.confidence for s in skills) / skill_count, 3) if skill_count > 0 else 0,
        },
        "samples": [
            {"label": f"提取技能 (共{skill_count}个)", "value": [s.name for s in skills[:15]]},
        ],
        "verification": {"passed": all(c["ok"] for c in checks), "checks": checks},
    }


def _build_match_output(
    step_name: str, display_name: str, ctx: PipelineContext,
) -> dict[str, Any]:
    """岗位匹配步骤的输出和验证。"""
    match_count = len(ctx.match_results)
    sorted_matches = sorted(
        ctx.match_results.items(),
        key=lambda x: x[1].get("match_score", 0),
        reverse=True,
    )
    top_score = sorted_matches[0][1].get("match_score", 0) if sorted_matches else 0

    checks = [
        {
            "check": "匹配岗位数量",
            "ok": match_count >= 1,
            "detail": f"匹配到 {match_count} 个岗位" if match_count >= 1 else "未匹配到任何岗位",
        },
        {
            "check": "最高匹配度",
            "ok": top_score >= 0.3,
            "detail": f"最高匹配度: {top_score:.1%}" if top_score >= 0.3 else f"最高匹配度仅 {top_score:.1%}，匹配度偏低",
        },
        {
            "check": f"数据源: {ctx.data_source}",
            "ok": ctx.data_source != "hardcoded_fallback",
            "detail": "使用图谱数据匹配" if ctx.data_source != "hardcoded_fallback" else "使用硬编码回退数据，结果仅供参考",
        },
    ]

    top_samples = []
    for pos_name, pos_result in sorted_matches[:5]:
        top_samples.append({
            "position": pos_name,
            "match_score": round(pos_result.get("match_score", 0), 3),
            "assessment": (pos_result.get("overall_assessment", "") or "")[:100],
            "gap_count": len(pos_result.get("missing_required", [])),
        })

    return {
        "step": step_name,
        "display_name": display_name,
        "status": "done",
        "input_summary": {
            "skill_count": len(ctx.extracted_skills),
            "target_positions": ctx.target_positions,
        },
        "output_summary": {
            "match_count": match_count,
            "top_match": sorted_matches[0][0] if sorted_matches else None,
            "top_score": round(top_score, 3),
            "data_source": ctx.data_source,
        },
        "samples": [
            {"label": f"岗位匹配 Top-5 (共{match_count}个)", "value": top_samples},
        ],
        "verification": {"passed": all(c["ok"] for c in checks), "checks": checks},
    }


def _build_learning_path_output(
    step_name: str, display_name: str, ctx: PipelineContext,
) -> dict[str, Any]:
    """学习路径步骤的输出和验证。"""
    total_gaps = 0
    gaps_with_path = 0
    gaps_with_resources = 0
    enriched_positions = 0

    for _pos_name, result in ctx.match_results.items():
        gaps = result.get("skill_gap_detail", [])
        if not gaps:
            continue
        enriched_positions += 1
        for gap in gaps:
            total_gaps += 1
            if gap.get("learning_path"):
                gaps_with_path += 1
            if gap.get("learning_resources"):
                gaps_with_resources += 1

    checks = [
        {
            "check": "学习路径覆盖",
            "ok": gaps_with_path > 0,
            "detail": f"{gaps_with_path}/{total_gaps} 个技能差距有学习路径" if total_gaps > 0 else "无技能差距数据",
        },
        {
            "check": "学习资源丰富度",
            "ok": gaps_with_resources > 0,
            "detail": f"{gaps_with_resources}/{total_gaps} 个技能差距有学习资源推荐" if total_gaps > 0 else "无学习资源",
        },
        {
            "check": "岗位覆盖",
            "ok": enriched_positions >= 1,
            "detail": f"已为 {enriched_positions} 个岗位生成学习路径",
        },
    ]

    return {
        "step": step_name,
        "display_name": display_name,
        "status": "done",
        "input_summary": {"matched_positions": len(ctx.match_results)},
        "output_summary": {
            "enriched_positions": enriched_positions,
            "total_gaps": total_gaps,
            "gaps_with_path": gaps_with_path,
            "gaps_with_resources": gaps_with_resources,
        },
        "samples": [
            {"label": "学习路径覆盖统计", "value": {
                "技能差距总数": total_gaps,
                "有学习路径": gaps_with_path,
                "有学习资源": gaps_with_resources,
                "覆盖岗位数": enriched_positions,
            }},
        ],
        "verification": {"passed": all(c["ok"] for c in checks), "checks": checks},
    }


def _build_recommend_output(
    step_name: str, display_name: str, ctx: PipelineContext,
) -> dict[str, Any]:
    """岗位推荐步骤的输出和验证。"""
    recs = ctx.recommended_positions
    rec_count = len(recs)

    checks = [
        {
            "check": "推荐岗位数量",
            "ok": rec_count >= 1,
            "detail": f"共推荐 {rec_count} 个岗位" if rec_count >= 1 else "未生成推荐",
        },
        {
            "check": "推荐分数合理性",
            "ok": all(r.get("score", 0) > 0 for r in recs) if recs else False,
            "detail": "所有推荐分数>0" if recs and all(r.get("score", 0) > 0 for r in recs) else "存在零分推荐",
        },
    ]

    return {
        "step": step_name,
        "display_name": display_name,
        "status": "done",
        "input_summary": {"skill_count": len(ctx.extracted_skills)},
        "output_summary": {
            "recommendation_count": rec_count,
            "avg_score": round(sum(r.get("score", 0) for r in recs) / rec_count, 3) if rec_count > 0 else 0,
        },
        "samples": [
            {"label": f"推荐岗位 (共{rec_count}个)", "value": [
                {
                    "position": r.get("position", ""),
                    "score": round(r.get("score", 0), 3),
                    "match_score": round(r.get("match_score", 0), 3),
                    "developability": round(r.get("developability", 0), 3),
                }
                for r in recs[:5]
            ]},
        ],
        "verification": {"passed": all(c["ok"] for c in checks), "checks": checks},
    }


# 步骤构建器注册表
_STEP_BUILDERS: dict[str, Any] = {
    "resume_parse": _build_resume_parse_output,
    "skill_extract": _build_skill_extract_output,
    "match": _build_match_output,
    "learning_path": _build_learning_path_output,
    "recommend": _build_recommend_output,
}
