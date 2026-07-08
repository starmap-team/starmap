"""Evolution emerging-skill alerts endpoint — extracted from evolution.py (Phase 7 evolution domain split).

业务说明：新兴技能预警 API，基于 Z-score 检测 emerging/rising/declining 信号并生成预警。
注册到 evolution.py 的主 router（prefix="/evolution"），最终路径 /evolution/emerging-alerts。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.evolution.timeseries_loader import load_skill_timeseries_data
from app.dependencies import get_db_session


class EmergingAlert(BaseModel):
    """An emerging skill alert with full context."""

    skill_name: str = Field(..., description="技能名称")
    category: str = Field(default="", description="分类")
    level: str = Field(..., description="分类: emerging/rising/declining/stable")
    z_score: float = Field(default=0.0, description="Z-score 值")
    current_frequency: int = Field(default=0, description="当前频次")
    mean_frequency: float = Field(default=0.0, description="历史均值频次")
    source_count: int = Field(default=0, description="来源数")
    domains: list[str] = Field(default_factory=list, description="所属领域")
    positions: list[str] = Field(default_factory=list, description="关联岗位")
    trend: str = Field(default="stable", description="趋势方向")
    portability_score: float = Field(default=0.0, ge=0, le=1, description="可迁移性得分")
    alert_message: str = Field(default="", description="预警描述")


class EmergingAlertsResponse(BaseModel):
    """Emerging skill alerts response."""

    alerts: list[EmergingAlert] = Field(default_factory=list, description="预警列表")
    total: int = 0
    summary: str = ""


router = APIRouter(tags=["新兴技能预警"])


@router.get("/emerging-alerts", response_model=EmergingAlertsResponse)
async def get_emerging_alerts(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    level: Annotated[str | None, Query(description="筛选级别: emerging/rising/declining")] = None,
    domain: Annotated[str | None, Query(description="筛选领域: IT/AI/BigData/IoT")] = None,
    min_z_score: Annotated[float, Query(description="最小 Z-score 阈值")] = 0.0,
) -> EmergingAlertsResponse:
    """获取新兴技能预警列表，含分类、Z-score、领域、趋势详情。"""
    from app.core.evolution.emergence_finder import EmergenceFinder

    # Load timeseries data
    skill_data = await load_skill_timeseries_data(session, include_category=True)

    if not skill_data:
        return EmergingAlertsResponse(alerts=[], total=0, summary="暂无时序数据")

    # Run emergence detection
    finder = EmergenceFinder()
    report = finder.scan(skill_data)

    # Build alerts from all non-stable signals
    alerts: list[EmergingAlert] = []
    all_signals = report.emerging + report.rising + report.declining

    for signal in all_signals:
        # Apply filters
        if level and signal.level.value != level:
            continue
        if abs(signal.z_score) < abs(min_z_score):
            continue

        data = skill_data.get(signal.skill_name, {})
        domains = signal.metadata.get("domains", [])

        if domain and domain not in domains:
            continue

        # Build alert message
        if signal.level.value == "emerging":
            alert_msg = (
                f"新兴技能预警: {signal.skill_name} Z-score={signal.z_score:.2f}，"
                f"当前频次 {signal.current_frequency}（均值 {signal.mean_frequency:.1f}），"
                f"涉及 {len(domains)} 个领域"
            )
        elif signal.level.value == "rising":
            alert_msg = (
                f"上升技能提示: {signal.skill_name} Z-score={signal.z_score:.2f}，"
                f"频次呈上升趋势"
            )
        else:
            alert_msg = (
                f"下降技能提示: {signal.skill_name} Z-score={signal.z_score:.2f}，"
                f"频次呈下降趋势"
            )

        # Compute portability
        portability = finder.portability_score(signal.skill_name)

        alerts.append(EmergingAlert(
            skill_name=signal.skill_name,
            category=data.get("category", ""),
            level=signal.level.value,
            z_score=signal.z_score,
            current_frequency=signal.current_frequency,
            mean_frequency=signal.mean_frequency,
            source_count=signal.source_count,
            domains=domains,
            positions=signal.positions,
            trend=signal.level.value,
            portability_score=portability,
            alert_message=alert_msg,
        ))

    # Sort by z_score descending for emerging/rising, ascending for declining
    alerts.sort(key=lambda a: a.z_score, reverse=True)

    total = len(alerts)
    emerging_count = sum(1 for a in alerts if a.level == "emerging")
    rising_count = sum(1 for a in alerts if a.level == "rising")
    declining_count = sum(1 for a in alerts if a.level == "declining")
    summary = f"共 {total} 条预警: {emerging_count} 新兴, {rising_count} 上升, {declining_count} 下降"

    return EmergingAlertsResponse(
        alerts=alerts,
        total=total,
        summary=summary,
    )
