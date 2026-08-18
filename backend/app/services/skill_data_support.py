"""Skill data support score (2026-08-17 多模块联动 Phase 2).

背景: 评估「岗位技能数据是否足够支撑匹配/雷达图/学习计划」——
59 个 approved 岗位 0 技能（无数据）、35 个 1-2 技能（雷达图要求 ≥3）、
91 个 3+ 技能（合格）。无量化指标 → 运营不知道哪些岗位需要补数据。

data_support_score 设计:
- skill_count_score: min(1, skill_count / FULL_COVERAGE_THRESHOLD) × 0.5
- confidence_score: avg(relation.confidence) × 0.3
- source_count_score: min(1, max_source_count / SOURCE_RICHNESS_THRESHOLD) × 0.2
- total = skill_count_score + confidence_score + source_count_score (0-1)

判定:
- score >= 0.7 → 完整画像（full_coverage）
- 0.4 <= score < 0.7 → 部分数据（partial_coverage）
- score < 0.4 → 数据不足（low_data_support）

下游:
- dashboard_service._fetch_graph_stats 注入 4 个 KPI
- IndustryQualityMonitor 加新检测 → 告警「低数据支撑岗位过多」
- admin /content-review 面板筛选「低数据」岗位 → 触发「补抽取」流程
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction_models import (
    PositionRecord,
    PositionSkillRelation,
    SkillRecord,
)

# 配置常量（与项目数据规模匹配）
FULL_COVERAGE_THRESHOLD = 5  # 5+ 项技能 = 完整画像
SOURCE_RICHNESS_THRESHOLD = 3  # source_count >= 3 = 数据丰富

# 数据支撑档位
SCORE_FULL_COVERAGE = 0.7
SCORE_PARTIAL_COVERAGE = 0.4


@dataclass
class PositionDataSupport:
    """单岗位数据支撑评分。"""

    position_id: str
    position_name: str
    skill_count: int = 0
    avg_confidence: float = 0.0
    max_source_count: int = 0
    score: float = 0.0
    tier: str = "no_data"  # full_coverage / partial_coverage / low_data_support / no_data


@dataclass
class DataSupportReport:
    """全量数据支撑报告（喂给 dashboard KPI）。"""

    avg_score: float = 0.0
    total_positions: int = 0
    full_coverage_count: int = 0
    partial_coverage_count: int = 0
    low_data_support_count: int = 0
    no_data_count: int = 0
    # 详细列表（admin 端点用）
    low_data_positions: list[PositionDataSupport] = field(default_factory=list)
    zero_source_skills: list[str] = field(default_factory=list)
    low_confidence_skills: list[str] = field(default_factory=list)


def _compute_score(skill_count: int, avg_confidence: float, max_source_count: int) -> float:
    """3 维度加权得分。"""
    skill_score = min(1.0, skill_count / FULL_COVERAGE_THRESHOLD) * 0.5
    confidence_score = (avg_confidence or 0.0) * 0.3
    source_score = min(1.0, (max_source_count or 0) / SOURCE_RICHNESS_THRESHOLD) * 0.2
    return round(skill_score + confidence_score + source_score, 4)


def _classify_tier(score: float, skill_count: int) -> str:
    """根据 score + skill_count 判定档位。"""
    if skill_count == 0:
        return "no_data"
    if score >= SCORE_FULL_COVERAGE:
        return "full_coverage"
    if score >= SCORE_PARTIAL_COVERAGE:
        return "partial_coverage"
    return "low_data_support"


async def compute_data_support_report(
    session: AsyncSession,
    *,
    approved_only: bool = True,
) -> DataSupportReport:
    """计算所有岗位的数据支撑报告（默认仅已发布 approved 口径，与 dashboard 保持一致）。"""
    report = DataSupportReport(total_positions=0)

    # 1. 单岗位 skill_count + avg_confidence + max_source_count
    base_query = (
        sa.select(
            PositionRecord.id,
            PositionRecord.name,
            sa.func.count(PositionSkillRelation.skill_id).label("skill_count"),
            sa.func.coalesce(sa.func.avg(PositionSkillRelation.confidence), 0.0).label("avg_conf"),
            sa.func.coalesce(sa.func.max(SkillRecord.source_count), 0).label("max_source"),
        )
        .select_from(PositionRecord)
        .outerjoin(PositionSkillRelation, PositionSkillRelation.position_id == PositionRecord.id)
        .outerjoin(SkillRecord, SkillRecord.id == PositionSkillRelation.skill_id)
        .group_by(PositionRecord.id, PositionRecord.name)
    )
    if approved_only:
        base_query = base_query.where(PositionRecord.review_status == "approved")

    rows = (await session.execute(base_query)).all()
    if not rows:
        return report

    total_score = 0.0
    for row in rows:
        score = _compute_score(row.skill_count, row.avg_conf, row.max_source)
        tier = _classify_tier(score, row.skill_count)
        total_score += score

        if tier == "full_coverage":
            report.full_coverage_count += 1
        elif tier == "partial_coverage":
            report.partial_coverage_count += 1
        elif tier == "low_data_support":
            report.low_data_support_count += 1
            report.low_data_positions.append(PositionDataSupport(
                position_id=str(row.id),
                position_name=row.name,
                skill_count=row.skill_count,
                avg_confidence=float(row.avg_conf),
                max_source_count=int(row.max_source),
                score=score,
                tier=tier,
            ))
        else:  # no_data
            report.no_data_count += 1
            report.low_data_positions.append(PositionDataSupport(
                position_id=str(row.id),
                position_name=row.name,
                skill_count=0,
                avg_confidence=0.0,
                max_source_count=0,
                score=0.0,
                tier="no_data",
            ))

    report.total_positions = len(rows)
    report.avg_score = round(total_score / len(rows), 4)

    # 2. zero_source_skills: source_count = 0 的技能
    zero_source_stmt = sa.select(SkillRecord.name).where(SkillRecord.source_count == 0).limit(50)
    report.zero_source_skills = list((await session.execute(zero_source_stmt)).scalars().all())

    # 3. low_confidence_skills: conf < 0.5 的技能（孤儿/低质量抽取）
    low_conf_stmt = sa.select(SkillRecord.name).where(
        sa.exists().where(
            PositionSkillRelation.skill_id == SkillRecord.id,
            PositionSkillRelation.confidence < 0.5,
        )
    ).limit(50)
    report.low_confidence_skills = list((await session.execute(low_conf_stmt)).scalars().all())

    return report


def report_to_dict(report: DataSupportReport) -> dict[str, Any]:
    """DataSupportReport → dict (喂给 dashboard JSON 序列化)。"""
    return {
        "avg_score": report.avg_score,
        "total_positions": report.total_positions,
        "full_coverage_count": report.full_coverage_count,
        "partial_coverage_count": report.partial_coverage_count,
        "low_data_support_count": report.low_data_support_count,
        "no_data_count": report.no_data_count,
        "low_data_position_count": len(report.low_data_positions),
        "low_data_position_sample": [
            {
                "position_id": p.position_id,
                "position_name": p.position_name,
                "skill_count": p.skill_count,
                "score": p.score,
                "tier": p.tier,
            }
            for p in report.low_data_positions[:10]  # 限制 top 10 给 dashboard
        ],
        "zero_source_skills_count": len(report.zero_source_skills),
        "low_confidence_skills_count": len(report.low_confidence_skills),
    }
