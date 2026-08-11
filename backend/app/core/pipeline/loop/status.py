"""Loop status / history retrieval + per-step verification (Phase 07-02 D-02).

Extracted from ``loop_orchestrator.py``:
  - ``get_loop_status``   — query loop_results → pipeline_runs → in-memory
  - ``get_loop_history``  — list recent runs (same fallback chain)
  - ``_build_loop_verification`` / ``_loop_step_checks`` — step-level verification
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pipeline.loop.common import (
    _LOOP_RESULTS,
    LoopStepResult,
    StepStatus,
)
from app.exceptions import PipelineStageError, StarMapError

if TYPE_CHECKING:
    pass


async def get_loop_status(
    run_id: str,
    session: AsyncSession | None = None,
    user_id: str = "system",      # SEC-04
    is_admin: bool = False,        # SEC-04
) -> dict[str, Any] | None:
    """Return status of a loop run by ID, querying loop_results first, then pipeline_runs, then in-memory fallback."""
    if session is not None:
        # Primary: query loop_results table
        try:
            from app.models.pipeline_models import LoopResultRecord

            query = select(LoopResultRecord).where(
                LoopResultRecord.run_id == run_id,
            )
            # SEC-04: IDOR guard — non-admin users only see their own runs
            if not is_admin:
                query = query.where(LoopResultRecord.user_id == user_id)

            result = await session.execute(query)
            row = result.scalar_one_or_none()
            if row is not None:
                data = dict(row.steps_json) if row.steps_json else {}
                data["run_id"] = row.run_id
                data["status"] = row.status
                return data
        except PipelineStageError:
            raise
        except StarMapError:
            raise
        except Exception as exc:
            logger.exception("Failed to read loop status from loop_results, trying pipeline_runs: {}", exc)

        # Secondary: query pipeline_runs table (legacy)
        try:
            from app.models.pipeline_models import PipelineRun

            result = await session.execute(
                select(PipelineRun).where(PipelineRun.id == uuid.UUID(run_id))
            )
            row = result.scalar_one_or_none()
            if row is not None and row.stages is not None:
                data = dict(row.stages)
                data["run_id"] = str(row.id)
                data["status"] = row.status
                if "steps" not in data:
                    data["steps"] = row.stages.get("steps", [])
                return data
        except PipelineStageError:
            raise
        except StarMapError:
            raise
        except Exception as exc:
            logger.exception("Failed to read loop status from pipeline_runs, falling back to in-memory: {}", exc)

    # Fallback: in-memory
    result = _LOOP_RESULTS.get(run_id)
    if result is None:
        return None
    return result.to_dict()


async def get_loop_history(
    limit: int = 50,
    session: AsyncSession | None = None,
    user_id: str = "system",      # SEC-04
    is_admin: bool = False,        # SEC-04
) -> list[dict[str, Any]]:
    """Return recent loop run history, querying loop_results first, then pipeline_runs, then in-memory fallback."""
    if session is not None:
        # Primary: query loop_results table
        try:
            from app.models.pipeline_models import LoopResultRecord

            query = select(LoopResultRecord).order_by(
                LoopResultRecord.created_at.desc()
            )
            # SEC-04: IDOR guard — non-admin users only see their own runs
            if not is_admin:
                query = query.where(LoopResultRecord.user_id == user_id)

            query = query.limit(limit)
            result = await session.execute(query)
            rows = result.scalars().all()
            if rows:
                items = []
                for row in rows:
                    data = dict(row.steps_json) if row.steps_json else {}
                    data["run_id"] = row.run_id
                    data["status"] = row.status
                    items.append(data)
                return items
        except PipelineStageError:
            raise
        except StarMapError:
            raise
        except Exception as exc:
            logger.exception("Failed to read loop history from loop_results, trying pipeline_runs: {}", exc)

        # Secondary: query pipeline_runs table (legacy)
        try:
            from app.models.pipeline_models import PipelineRun

            result = await session.execute(
                select(PipelineRun)
                .where(PipelineRun.run_type == "loop")
                .order_by(PipelineRun.started_at.desc())
                .limit(limit)
            )
            rows = result.scalars().all()
            if rows:
                items = []
                for row in rows:
                    data = dict(row.stages) if row.stages else {}
                    data["run_id"] = str(row.id)
                    data["status"] = row.status
                    items.append(data)
                return items
        except PipelineStageError:
            raise
        except StarMapError:
            raise
        except Exception as exc:
            logger.exception("Failed to read loop history from pipeline_runs, falling back to in-memory: {}", exc)

    # Fallback: in-memory
    items = list(_LOOP_RESULTS.values())
    items.sort(key=lambda r: r.total_duration_seconds, reverse=False)
    return [r.to_dict() for r in list(_LOOP_RESULTS.values())[-limit:]][::-1]


# ---------------------------------------------------------------------------
# Phase 3: 闭环管道逐步核验
# ---------------------------------------------------------------------------

def _build_loop_verification(steps: list[LoopStepResult]) -> dict[str, Any]:
    """为闭环管道构建每步核验摘要。

    Returns:
        {
            "overall_passed": bool,
            "steps": [
                {"step": int, "name": str, "passed": bool, "checks": [...]},
            ]
        }
    """
    step_verifications = []
    for s in steps:
        checks = _loop_step_checks(s)
        step_verifications.append({
            "step": s.step,
            "name": s.name,
            "passed": all(c["ok"] for c in checks),
            "checks": checks,
        })
    overall_passed = all(sv["passed"] for sv in step_verifications if sv["checks"])
    return {
        "overall_passed": overall_passed,
        "steps": step_verifications,
    }


def _loop_step_checks(step: LoopStepResult) -> list[dict[str, Any]]:
    """为单个闭环步骤生成验证检查项。"""
    checks: list[dict[str, Any]] = []

    if step.status == StepStatus.FAILED:
        return [{"check": "步骤执行失败", "ok": False, "detail": step.error or "未知错误"}]
    if step.status == StepStatus.SKIPPED:
        return [{"check": "步骤已跳过", "ok": True, "detail": step.note or "无需执行"}]

    # Step 1: JD输入
    if step.step == 1:
        jd_len = step.data.get("jd_length", 0)
        checks.append({
            "check": "JD文本非空",
            "ok": jd_len > 0,
            "detail": f"JD长度: {jd_len} 字符" if jd_len > 0 else "JD为空",
        })
        checks.append({
            "check": "目标岗位已指定",
            "ok": bool(step.data.get("target_position")),
            "detail": f"目标: {step.data.get('target_position')}",
        })

    # Step 2: 技能提取
    elif step.step == 2:
        skills = step.data.get("skills", [])
        checks.append({
            "check": "提取技能数量充足",
            "ok": len(skills) >= 3,
            "detail": f"提取 {len(skills)} 个技能",
        })
        checks.append({
            "check": "岗位名称已识别",
            "ok": bool(step.data.get("position_name")),
            "detail": f"岗位: {step.data.get('position_name', '未识别')}",
        })

    # Step 3: 图谱更新
    elif step.step == 3:
        synced = step.data.get("synced", False)
        checks.append({
            "check": "图谱同步成功",
            "ok": synced,
            "detail": f"写入 {step.data.get('nodes_written', 0)} 节点, {step.data.get('edges_written', 0)} 关系",
        })

    # Step 4: 匹配诊断
    elif step.step == 4:
        match_score = step.data.get("match_score", 0)
        gap_detail = step.data.get("skill_gap_detail", [])
        checks.append({
            "check": "匹配分数合理",
            "ok": match_score > 0,
            "detail": f"匹配度: {match_score:.1%}" if match_score > 0 else "匹配分数为0",
        })
        checks.append({
            "check": "技能差距分析完整",
            "ok": len(gap_detail) > 0,
            "detail": f"分析 {len(gap_detail)} 项技能差距",
        })

    # Step 5: 学习路径
    elif step.step == 5:
        path_items = step.data.get("path_items", [])
        plan_id = step.data.get("plan_id")
        checks.append({
            "check": "学习路径已生成",
            "ok": len(path_items) > 0,
            "detail": f"生成 {len(path_items)} 条学习路径",
        })
        if plan_id:
            checks.append({
                "check": "学习计划已创建",
                "ok": True,
                "detail": f"计划ID: {plan_id}",
            })

    return checks


__all__ = [
    "get_loop_status",
    "get_loop_history",
    "_build_loop_verification",
    "_loop_step_checks",
]
