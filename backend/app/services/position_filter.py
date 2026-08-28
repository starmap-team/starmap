"""position_filter — 岗位是否入图/展示的唯一判定（批0 真相源, 2026-08-28）。

共识计划 ADR 决策：13 模块展示一致性收敛到单一过滤函数，防 reconcile 振荡。
- is_graph_eligible: 岗位是否可入图（approved + IT 域 + 有 approved 技能）
- has_approved_skill: 该岗位是否有至少一条「关联 SkillRecord.review_status=='approved'」的 PSR
  （PSR 无 status 列，挂靠 SkillRecord；与 graph_projector 边回填查询口径一致）
- 存量扫描: unclassified / no_skill / duplicate 三组 SQL（供审核队列 category 筛选复用）
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.extraction.industry_gate import IT_INDUSTRY_WHITELIST
from app.models.extraction_models import PositionRecord, PositionSkillRelation, SkillRecord

# 隐藏原因（quality_hint 取值）
HIDDEN_NO_SKILL = "no_skills"
HIDDEN_NON_IT = "non_it"

# 未分类判定（industry 三态）
UNCLASSIFIED_VALUES = (None, "", "未分类")


async def has_approved_skill(session: AsyncSession, position_id: UUID) -> bool:
    """岗位是否有 ≥1 条关联 approved 技能的 PSR。"""
    stmt = (
        select(
            exists(
                select(PositionSkillRelation.id)
                .join(SkillRecord, SkillRecord.id == PositionSkillRelation.skill_id)
                .where(
                    PositionSkillRelation.position_id == position_id,
                    SkillRecord.review_status == "approved",
                )
            )
        )
    )
    return bool((await session.execute(stmt)).scalar())


async def is_graph_eligible(
    session: AsyncSession,
    position: PositionRecord,
    *,
    check_skill: bool = True,
) -> bool:
    """岗位是否可入图：approved + industry∈IT白名单 + 有 approved 技能。"""
    if position.review_status != "approved":
        return False
    if not position.industry or position.industry not in IT_INDUSTRY_WHITELIST:
        return False
    if check_skill:
        return await has_approved_skill(session, position.id)
    return True


def unclassified_positions_stmt():
    """industry 三态未分类岗位查询。"""
    return select(PositionRecord).where(PositionRecord.industry.in_(UNCLASSIFIED_VALUES))


def no_skill_positions_stmt():
    """无任何 PSR 关联的岗位查询（含 pending 技能视为无技能——入图需 approved 技能）。"""
    return select(PositionRecord).where(
        ~exists(
            select(PositionSkillRelation.id).where(
                PositionSkillRelation.position_id == PositionRecord.id
            )
        )
    )


def duplicate_name_positions_stmt():
    """name_cn 重复分组（>1 组）的岗位查询。"""
    dup = (
        select(PositionRecord.name_cn)
        .where(PositionRecord.name_cn.is_not(None), PositionRecord.name_cn != "")
        .group_by(PositionRecord.name_cn)
        .having(func.count() > 1)
        .subquery()
    )
    return select(PositionRecord).join(dup, PositionRecord.name_cn == dup.c.name_cn)
