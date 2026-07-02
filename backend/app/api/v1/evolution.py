"""演化分析 API。对应§5.2 能力更新 + §7.3 岗位演进。

Endpoints:
- GET  /evolution/trends           - 技能热度趋势（已有，增强）
- POST /evolution/analyze          - 触发演化分析（已有，增强）
- GET  /evolution/changelog/{pos}  - 演化变更记录（新增）
- GET  /evolution/paths/{pos}      - 演化路径推荐（新增）
- GET  /evolution/emerging-skills  - 涌现技能列表（新增）
- GET  /evolution/snapshots        - 快照管理（新增）
- GET  /evolution/review-queue     - 人工审核队列（新增）
- GET  /evolution/cii-history/{pos} - CII通胀指数历史（新增）
- GET  /evolution/career-path/{pos} - 职业路径规划（Sprint 2.1 新增）
- GET  /evolution/industry-report   - 行业趋势报告（Sprint 2.1 新增）
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.models.evolution_models import (
    EvolutionChangelog,
    EvolutionPath,
    EvolutionSnapshot,
    SkillTimeseries,
)
from app.models.extraction_models import PositionRecord, PositionSkillRelation, SkillRecord
from app.tasks.celery_app import analyze_evolution_trends

router = APIRouter(prefix="/evolution", tags=["演化分析"])


# ─── Response Models ───


class EvolutionTrend(BaseModel):
    """技能趋势条目。"""

    skill_name: str = Field(..., description="技能名称")
    trend: str = Field(..., description="趋势方向：rising/stable/declining")
    confidence: float = Field(..., ge=0, le=1, description="趋势置信度")
    points: list[float] = Field(default_factory=list, description="CII 时序数据点")
    related_positions: list[str] = Field(default_factory=list, description="相关岗位")


class EvolutionTrendsResponse(BaseModel):
    """演化趋势响应。"""

    items: list[EvolutionTrend] = Field(default_factory=list, description="趋势列表")


class ChangelogEntry(BaseModel):
    """变更日志条目。"""

    id: str
    skill_name: str
    change_type: str
    old_proficiency: str | None = None
    new_proficiency: str | None = None
    old_requirement: str | None = None
    new_requirement: str | None = None
    trust_score: float
    confidence: float
    created_at: datetime


class EvolutionPathEntry(BaseModel):
    """演化路径条目。"""

    id: str
    source_position: str
    target_position: str
    similarity: float
    evidence_count: int
    skill_overlap: list[str]
    key_gaps: list[str]
    trust_score: float


class EmergingSkill(BaseModel):
    """涌现技能条目。"""

    skill_name: str
    level: str  # emerging/rising/stable/declining
    z_score: float
    current_frequency: int
    mean_frequency: float
    source_count: int
    positions: list[str]


class SnapshotEntry(BaseModel):
    """快照条目。"""

    id: str
    position_name: str
    snapshot_date: datetime
    required_skills: list[dict[str, Any]]
    preferred_skills: list[dict[str, Any]]
    source_count: int


class ReviewQueueItem(BaseModel):
    """审核队列条目。"""

    skill_name: str
    position_name: str
    change_type: str
    trust_score: float
    status: str  # pending/approved/rejected
    created_at: datetime


# ─── Endpoints ───


@router.get("/trends", response_model=EvolutionTrendsResponse)
async def get_trends(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    category: Annotated[str | None, Query(description="技能分类筛选")] = None,
    days: Annotated[int, Query(ge=7, le=730, description="分析时间窗口（天）")] = 90,
) -> EvolutionTrendsResponse:
    """技能热度趋势、岗位变迁时间线、新兴岗位预警（§8.3 演化看板）。"""
    _ = days

    # Load real timeseries data first
    ts_stmt = (
        sa.select(SkillTimeseries)
        .order_by(SkillTimeseries.skill_name, SkillTimeseries.window_start.asc())
    )
    ts_result = await session.execute(ts_stmt)
    ts_records = ts_result.scalars().all()

    # If we have timeseries data, use it for real trends
    if ts_records:
        from app.core.evolution.emergence_finder import EmergenceFinder

        # Build skill_data from timeseries
        skill_data: dict[str, dict[str, Any]] = {}
        for r in ts_records:
            name = r.skill_name
            if name not in skill_data:
                skill_data[name] = {
                    "frequencies": [],
                    "current": 0,
                    "sources": r.source_count,
                    "positions": r.positions or [],
                }
            skill_data[name]["frequencies"].append(r.frequency)

        for data in skill_data.values():
            freqs = data["frequencies"]
            if freqs:
                data["current"] = freqs[-1]
                data["frequencies"] = freqs[:-1]

        # Run emergence detection for trend classification
        finder = EmergenceFinder()
        report = finder.scan(skill_data)

        # Build signals lookup
        signals_by_name: dict[str, Any] = {}
        for s in report.emerging + report.rising + report.declining:
            signals_by_name[s.skill_name] = s
        for s in report.stable:
            signals_by_name[s.skill_name] = s

        # Also load position relations
        rel_stmt = (
            sa.select(SkillRecord.name, PositionRecord.name)
            .select_from(SkillRecord)
            .outerjoin(PositionSkillRelation, PositionSkillRelation.skill_id == SkillRecord.id)
            .outerjoin(PositionRecord, PositionRecord.id == PositionSkillRelation.position_id)
        )
        rel_rows = (await session.execute(rel_stmt)).all()
        skill_positions: dict[str, list[str]] = {}
        for skill_name, pos_name in rel_rows:
            if skill_name:
                skill_positions.setdefault(skill_name, [])
                if pos_name and pos_name not in skill_positions[skill_name]:
                    skill_positions[skill_name].append(pos_name)

        items: list[EvolutionTrend] = []
        for name, data in list(skill_data.items())[:20]:
            signal = signals_by_name.get(name)
            trend = signal.level.value if signal else "stable"
            confidence = min(1.0, 0.5 + (signal.z_score / 10) if signal else 0.5)
            # Use all frequencies as CII points
            all_freqs = list(data["frequencies"])
            if data["current"]:
                all_freqs.append(data["current"])
            # Normalize to CII scale (baseline = mean of first half)
            if len(all_freqs) >= 2:
                baseline = sum(all_freqs[:max(1, len(all_freqs)//2)]) / max(1, len(all_freqs)//2)
                cii_points = [(f / baseline * 100) if baseline > 0 else 100.0 for f in all_freqs]
            else:
                cii_points = [100.0]

            items.append(EvolutionTrend(
                skill_name=name,
                trend=trend,
                confidence=round(confidence, 3),
                points=[round(p, 1) for p in cii_points],
                related_positions=skill_positions.get(name, []),
            ))

        return EvolutionTrendsResponse(items=items)

    # Fallback: use SkillRecord source_count (legacy path)
    stmt = (
        sa.select(SkillRecord.name, SkillRecord.source_count, PositionRecord.name)
        .select_from(SkillRecord)
        .outerjoin(PositionSkillRelation, PositionSkillRelation.skill_id == SkillRecord.id)
        .outerjoin(PositionRecord, PositionRecord.id == PositionSkillRelation.position_id)
        .order_by(SkillRecord.source_count.desc(), SkillRecord.name.asc())
        .limit(200)
    )
    if category:
        stmt = stmt.where(SkillRecord.category == category)

    rows = (await session.execute(stmt)).all()
    grouped: dict[str, tuple[int, list[str]]] = {}
    for skill_name, source_count, position_name in rows:
        count, positions = grouped.setdefault(skill_name, (int(source_count or 0), []))
        if position_name and position_name not in positions:
            positions.append(position_name)
        grouped[skill_name] = (count, positions)

    items: list[EvolutionTrend] = []
    for name, (count, related_positions) in list(grouped.items())[:20]:
        confidence = min(1.0, 0.5 + count / 20)
        # Generate simulated CII time-series based on source_count
        base = max(60, min(200, count * 10))
        trend = "rising" if count > 5 else "declining" if count < 2 else "stable"
        if trend == "rising":
            points = [float(base + i * 8) for i in range(4)]
        elif trend == "declining":
            points = [float(base - i * 8) for i in range(4)]
        else:
            points = [float(base) for _ in range(4)]

        items.append(EvolutionTrend(
            skill_name=name,
            trend=trend,
            confidence=confidence,
            points=points,
            related_positions=related_positions,
        ))

    return EvolutionTrendsResponse(items=items)


@router.post("/analyze")
async def analyze_evolution(
    days: Annotated[int, Query(ge=7, le=730, description="分析时间窗口（天）")] = 90,
):
    """触发演化分析流程。"""
    task = analyze_evolution_trends.delay(days)
    return {"message": "queued", "task_id": task.id, "days": days}


@router.get("/changelog/{position}", response_model=list[ChangelogEntry])
async def get_changelog(
    position: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[ChangelogEntry]:
    """获取指定岗位的演化变更记录。"""
    stmt = (
        sa.select(EvolutionChangelog)
        .where(sa.or_(EvolutionChangelog.position_name == position, EvolutionChangelog.skill_name == position))
        .order_by(EvolutionChangelog.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    records = result.scalars().all()

    return [
        ChangelogEntry(
            id=str(r.id),
            skill_name=r.skill_name,
            change_type=r.change_type,
            old_proficiency=r.old_proficiency,
            new_proficiency=r.new_proficiency,
            old_requirement=r.old_requirement,
            new_requirement=r.new_requirement,
            trust_score=r.trust_score,
            confidence=r.confidence,
            created_at=r.created_at,
        )
        for r in records
    ]


@router.get("/paths/all", response_model=list[EvolutionPathEntry])
async def get_all_evolution_paths(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[EvolutionPathEntry]:
    """获取所有演化路径（用于图谱页渲染 EVOLVES_TO 边）。"""
    stmt = sa.select(EvolutionPath).order_by(EvolutionPath.similarity.desc()).limit(limit)
    result = await session.execute(stmt)
    records = result.scalars().all()
    return [
        EvolutionPathEntry(
            id=str(r.id), source_position=r.source_position, target_position=r.target_position,
            similarity=r.similarity, evidence_count=r.evidence_count,
            skill_overlap=r.skill_overlap or [], key_gaps=r.key_gaps or [], trust_score=r.trust_score,
        )
        for r in records
    ]


@router.get("/paths/{position}", response_model=list[EvolutionPathEntry])
async def get_evolution_paths(
    position: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[EvolutionPathEntry]:
    """获取指定岗位的演化路径推荐。"""
    stmt = (
        sa.select(EvolutionPath)
        .where(
            (EvolutionPath.source_position == position)
            | (EvolutionPath.target_position == position)
        )
        .order_by(EvolutionPath.similarity.desc())
        .limit(20)
    )
    result = await session.execute(stmt)
    records = result.scalars().all()

    return [
        EvolutionPathEntry(
            id=str(r.id),
            source_position=r.source_position,
            target_position=r.target_position,
            similarity=r.similarity,
            evidence_count=r.evidence_count,
            skill_overlap=r.skill_overlap or [],
            key_gaps=r.key_gaps or [],
            trust_score=r.trust_score,
        )
        for r in records
    ]


@router.get("/emerging-skills", response_model=list[EmergingSkill])
async def get_emerging_skills(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    level: Annotated[str | None, Query(description="筛选级别: emerging/rising")] = None,
) -> list[EmergingSkill]:
    """获取涌现技能列表。"""
    from app.core.evolution.emergence_finder import EmergenceFinder

    # Load timeseries data
    stmt = (
        sa.select(SkillTimeseries)
        .order_by(SkillTimeseries.window_start.asc())
    )
    result = await session.execute(stmt)
    records = result.scalars().all()

    if not records:
        return []

    # Group by skill
    skill_data: dict[str, dict[str, Any]] = {}
    for r in records:
        name = r.skill_name
        if name not in skill_data:
            skill_data[name] = {
                "frequencies": [],
                "current": 0,
                "sources": r.source_count,
                "positions": r.positions or [],
            }
        skill_data[name]["frequencies"].append(r.frequency)

    # Set current = last
    for data in skill_data.values():
        freqs = data["frequencies"]
        if freqs:
            data["current"] = freqs[-1]
            data["frequencies"] = freqs[:-1]

    # Run emergence detection
    finder = EmergenceFinder()
    report = finder.scan(skill_data)

    # Collect signals
    signals = report.emerging + report.rising
    if level:
        signals = [s for s in signals if s.level.value == level]

    return [
        EmergingSkill(
            skill_name=s.skill_name,
            level=s.level.value,
            z_score=s.z_score,
            current_frequency=s.current_frequency,
            mean_frequency=s.mean_frequency,
            source_count=s.source_count,
            positions=s.positions,
        )
        for s in signals
    ]


@router.get("/snapshots", response_model=list[SnapshotEntry])
async def get_snapshots(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    position: Annotated[str | None, Query(description="岗位名称筛选")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[SnapshotEntry]:
    """获取演化快照列表。"""
    stmt = sa.select(EvolutionSnapshot).order_by(EvolutionSnapshot.snapshot_date.desc())
    if position:
        stmt = stmt.where(EvolutionSnapshot.position_name == position)
    stmt = stmt.limit(limit)

    result = await session.execute(stmt)
    records = result.scalars().all()

    return [
        SnapshotEntry(
            id=str(r.id),
            position_name=r.position_name,
            snapshot_date=r.snapshot_date,
            required_skills=r.required_skills or [],
            preferred_skills=r.preferred_skills or [],
            source_count=r.source_count or 0,
        )
        for r in records
    ]


@router.get("/review-queue", response_model=list[ReviewQueueItem])
async def get_review_queue(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    status: Annotated[str | None, Query(description="筛选状态: pending/approved/rejected")] = "pending",
) -> list[ReviewQueueItem]:
    """获取人工审核队列（低信任度变更）。"""
    stmt = (
        sa.select(EvolutionChangelog)
        .where(EvolutionChangelog.trust_score < 0.5)
        .order_by(EvolutionChangelog.created_at.desc())
        .limit(50)
    )
    result = await session.execute(stmt)
    records = result.scalars().all()

    return [
        ReviewQueueItem(
            skill_name=r.skill_name,
            position_name=r.position_name,
            change_type=r.change_type,
            trust_score=r.trust_score,
            status="pending",
            created_at=r.created_at,
        )
        for r in records
    ]


@router.get("/cii-history/{position}")
async def get_cii_history(
    position: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """获取CII通胀指数历史。"""
    # CII = Count of Inflated skills / Total required skills
    # Simplified: count skills with source_count > 7.2 (1.2x baseline)
    stmt = (
        sa.select(EvolutionSnapshot)
        .where(EvolutionSnapshot.position_name == position)
        .order_by(EvolutionSnapshot.snapshot_date.asc())
    )
    result = await session.execute(stmt)
    records = result.scalars().all()

    history: list[dict[str, Any]] = []
    for r in records:
        required = list(r.required_skills) if r.required_skills else []
        total = len(required)
        inflated = sum(1 for s in required if isinstance(s, dict) and s.get("source_count", 0) > 7)
        cii = inflated / total if total > 0 else 0.0
        history.append({
            "snapshot_date": r.snapshot_date.isoformat(),
            "cii": round(cii, 3),
            "total_skills": total,
            "inflated_skills": inflated,
        })

    return {"position": position, "history": history}


# ─── Sprint 2.1: Career Path Planning & Industry Report ───


class CareerPathNode(BaseModel):
    """A node in the career path graph."""

    position: str
    similarity: float = 0.0
    skill_overlap: list[str] = Field(default_factory=list)
    key_gaps: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    direction: str = Field(default="forward", description="forward | lateral | up")


class CareerPathResponse(BaseModel):
    """Career path planning response."""

    origin: str
    nodes: list[CareerPathNode] = Field(default_factory=list)
    total_paths: int = 0


@router.get("/career-path/{position}", response_model=CareerPathResponse)
async def get_career_path(
    position: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    depth: Annotated[int, Query(ge=1, le=4, description="路径搜索深度")] = 2,
) -> CareerPathResponse:
    """Get career path planning from a given position.

    Uses EVOLVES_TO relationships to discover potential career transitions,
    including direct transitions and multi-step paths. Classifies each
    transition as forward (promotion), lateral, or up (senior).
    """
    # Fetch direct evolution paths (depth 1)
    stmt = (
        sa.select(EvolutionPath)
        .where(
            (EvolutionPath.source_position == position)
            | (EvolutionPath.target_position == position)
        )
        .order_by(EvolutionPath.similarity.desc())
        .limit(50)
    )
    result = await session.execute(stmt)
    records = result.scalars().all()

    nodes: list[CareerPathNode] = []
    seen_positions: set[str] = set()

    for r in records:
        # Determine direction: from source → target
        if r.source_position == position:
            target = r.target_position
            direction = "forward"
        else:
            target = r.source_position
            direction = "lateral"

        if target in seen_positions:
            continue
        seen_positions.add(target)

        # Classify direction heuristically based on title keywords
        senior_keywords = {"高级", "资深", "专家", "主管", "经理", "总监", "架构师", "senior", "lead", "principal"}
        target_lower = target.lower()
        if any(kw in target_lower for kw in senior_keywords):
            direction = "up"

        nodes.append(CareerPathNode(
            position=target,
            similarity=r.similarity,
            skill_overlap=r.skill_overlap or [],
            key_gaps=r.key_gaps or [],
            evidence_count=r.evidence_count,
            direction=direction,
        ))

    # Depth 2: follow the best forward paths for multi-step discovery
    if depth >= 2:
        second_hop_nodes: list[CareerPathNode] = []
        for first_hop in nodes[:5]:  # Top 5 first-hop positions
            stmt2 = (
                sa.select(EvolutionPath)
                .where(EvolutionPath.source_position == first_hop.position)
                .order_by(EvolutionPath.similarity.desc())
                .limit(5)
            )
            result2 = await session.execute(stmt2)
            records2 = result2.scalars().all()

            for r2 in records2:
                target2 = r2.target_position
                if target2 in seen_positions or target2 == position:
                    continue
                seen_positions.add(target2)

                senior_keywords = {"高级", "资深", "专家", "主管", "经理", "总监", "架构师", "senior", "lead", "principal"}
                direction2 = "up" if any(kw in target2.lower() for kw in senior_keywords) else "forward"

                second_hop_nodes.append(CareerPathNode(
                    position=target2,
                    similarity=round(r2.similarity * first_hop.similarity, 3),
                    skill_overlap=r2.skill_overlap or [],
                    key_gaps=list(set(first_hop.key_gaps) | set(r2.key_gaps or [])),
                    evidence_count=r2.evidence_count,
                    direction=direction2,
                ))

        nodes.extend(second_hop_nodes)

    # Sort by similarity descending
    nodes.sort(key=lambda n: n.similarity, reverse=True)

    return CareerPathResponse(
        origin=position,
        nodes=nodes,
        total_paths=len(nodes),
    )


class SkillTrendItem(BaseModel):
    """Skill trend in industry report."""

    skill_name: str
    trend: str  # rising | stable | declining
    frequency: int = 0
    source_count: int = 0
    related_positions: list[str] = Field(default_factory=list)


class IndustryReportResponse(BaseModel):
    """Industry trend report response."""

    total_skills: int = 0
    rising_skills: list[SkillTrendItem] = Field(default_factory=list)
    declining_skills: list[SkillTrendItem] = Field(default_factory=list)
    stable_skills: list[SkillTrendItem] = Field(default_factory=list)
    top_positions: list[dict[str, Any]] = Field(default_factory=list)
    summary: str = ""


@router.get("/industry-report", response_model=IndustryReportResponse)
async def get_industry_report(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    category: Annotated[str | None, Query(description="技能分类筛选")] = None,
) -> IndustryReportResponse:
    """Get industry trend report with skill demand changes.

    Aggregates skill frequency data, timeseries trends, and position
    requirements to provide a comprehensive industry overview.
    """
    # Get skill trends from timeseries data
    ts_stmt = sa.select(SkillTimeseries).order_by(
        SkillTimeseries.skill_name,
        SkillTimeseries.window_start.asc(),
    )
    if category:
        ts_stmt = ts_stmt.where(SkillTimeseries.category == category)
    ts_result = await session.execute(ts_stmt)
    ts_records = ts_result.scalars().all()

    # Build skill data grouped by name
    skill_data: dict[str, dict[str, Any]] = {}
    for r in ts_records:
        name = r.skill_name
        if name not in skill_data:
            skill_data[name] = {
                "frequencies": [],
                "source_count": r.source_count,
                "positions": r.positions or [],
            }
        skill_data[name]["frequencies"].append(r.frequency)

    # If we have timeseries data, use emergence detection
    rising: list[SkillTrendItem] = []
    declining: list[SkillTrendItem] = []
    stable: list[SkillTrendItem] = []

    if skill_data:
        from app.core.evolution.emergence_finder import EmergenceFinder

        # Prepare for emergence finder (current = last, history = rest)
        finder_input: dict[str, dict[str, Any]] = {}
        for name, data in skill_data.items():
            freqs = data["frequencies"]
            finder_input[name] = {
                "frequencies": freqs[:-1] if len(freqs) > 1 else [],
                "current": freqs[-1] if freqs else 0,
                "sources": data["source_count"],
                "positions": data["positions"],
            }

        finder = EmergenceFinder()
        report = finder.scan(finder_input)

        for signal in report.rising:
            data = skill_data.get(signal.skill_name, {})
            rising.append(SkillTrendItem(
                skill_name=signal.skill_name,
                trend="rising",
                frequency=signal.current_frequency,
                source_count=signal.source_count,
                related_positions=signal.positions,
            ))

        for signal in report.declining:
            data = skill_data.get(signal.skill_name, {})
            declining.append(SkillTrendItem(
                skill_name=signal.skill_name,
                trend="declining",
                frequency=signal.current_frequency,
                source_count=signal.source_count,
                related_positions=signal.positions,
            ))

        for signal in report.stable[:20]:
            stable.append(SkillTrendItem(
                skill_name=signal.skill_name,
                trend="stable",
                frequency=signal.current_frequency,
                source_count=signal.source_count,
                related_positions=signal.positions,
            ))
    else:
        # Fallback: use SkillRecord for basic stats
        fallback_stmt = (
            sa.select(SkillRecord.name, SkillRecord.source_count, SkillRecord.category)
            .order_by(SkillRecord.source_count.desc())
            .limit(50)
        )
        if category:
            fallback_stmt = fallback_stmt.where(SkillRecord.category == category)

        fallback_result = await session.execute(fallback_stmt)
        fallback_records = fallback_result.all()

        for name, source_count, cat in fallback_records:
            # Get positions for this skill
            pos_stmt = (
                sa.select(PositionRecord.name)
                .select_from(PositionSkillRelation)
                .join(PositionRecord, PositionRecord.id == PositionSkillRelation.position_id)
                .join(SkillRecord, SkillRecord.id == PositionSkillRelation.skill_id)
                .where(SkillRecord.name == name)
                .limit(10)
            )
            pos_result = await session.execute(pos_stmt)
            positions = [row[0] for row in pos_result.all()]

            trend = "rising" if source_count > 5 else "declining" if source_count < 2 else "stable"
            item = SkillTrendItem(
                skill_name=name,
                trend=trend,
                frequency=source_count,
                source_count=source_count,
                related_positions=positions,
            )
            if trend == "rising":
                rising.append(item)
            elif trend == "declining":
                declining.append(item)
            else:
                stable.append(item)

    # Top positions by skill count
    top_pos_stmt = (
        sa.select(PositionRecord.name, sa.func.count(PositionSkillRelation.skill_id).label("skill_count"))
        .select_from(PositionRecord)
        .join(PositionSkillRelation, PositionSkillRelation.position_id == PositionRecord.id)
        .group_by(PositionRecord.name)
        .order_by(sa.text("skill_count DESC"))
        .limit(10)
    )
    top_pos_result = await session.execute(top_pos_stmt)
    top_positions = [
        {"position": name, "skill_count": count}
        for name, count in top_pos_result.all()
    ]

    # Generate summary
    total = len(rising) + len(declining) + len(stable)
    summary_parts = []
    if rising:
        summary_parts.append(f"{len(rising)} 个技能呈上升趋势")
    if declining:
        summary_parts.append(f"{len(declining)} 个技能呈下降趋势")
    summary_parts.append(f"共跟踪 {total} 个技能")
    summary = "，".join(summary_parts) + "。"

    return IndustryReportResponse(
        total_skills=total,
        rising_skills=rising[:20],
        declining_skills=declining[:20],
        stable_skills=stable[:20],
        top_positions=top_positions,
        summary=summary,
    )


# ─── Sprint 2.3: Emerging Skill Alerts & Portability ───


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
    stmt = (
        sa.select(SkillTimeseries)
        .order_by(SkillTimeseries.window_start.asc())
    )
    result = await session.execute(stmt)
    records = result.scalars().all()

    if not records:
        return EmergingAlertsResponse(alerts=[], total=0, summary="暂无时序数据")

    # Group by skill
    skill_data: dict[str, dict[str, Any]] = {}
    for r in records:
        name = r.skill_name
        if name not in skill_data:
            skill_data[name] = {
                "frequencies": [],
                "current": 0,
                "sources": r.source_count,
                "positions": r.positions or [],
                "category": r.category,
            }
        skill_data[name]["frequencies"].append(r.frequency)

    # Set current = last
    for data in skill_data.values():
        freqs = data["frequencies"]
        if freqs:
            data["current"] = freqs[-1]
            data["frequencies"] = freqs[:-1]

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


class PortabilityDetail(BaseModel):
    """Skill portability analysis response."""

    skill_name: str = Field(..., description="技能名称")
    portability_score: float = Field(default=0.0, ge=0, le=1, description="可迁移性得分")
    domains: list[str] = Field(default_factory=list, description="所属领域")
    domain_count: int = 0
    positions_by_domain: dict[str, list[str]] = Field(
        default_factory=dict, description="各领域关联岗位",
    )
    total_positions: int = 0
    transferability_tier: str = Field(default="low", description="可迁移性等级")
    related_skills: list[str] = Field(default_factory=list, description="相关跨领域技能")
    recommendation: str = Field(default="", description="建议")


@router.get("/portability/{skill}", response_model=PortabilityDetail)
async def get_skill_portability(
    skill: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PortabilityDetail:
    """获取指定技能的可迁移性分析。"""
    from app.core.evolution.emergence_finder import EmergenceFinder

    # Load timeseries data
    stmt = (
        sa.select(SkillTimeseries)
        .order_by(SkillTimeseries.window_start.asc())
    )
    result = await session.execute(stmt)
    records = result.scalars().all()

    if not records:
        raise HTTPException(status_code=404, detail=f"无时序数据，无法分析技能 '{skill}' 的可迁移性")

    # Group by skill
    skill_data: dict[str, dict[str, Any]] = {}
    for r in records:
        name = r.skill_name
        if name not in skill_data:
            skill_data[name] = {
                "frequencies": [],
                "current": 0,
                "sources": r.source_count,
                "positions": r.positions or [],
                "category": r.category,
            }
        skill_data[name]["frequencies"].append(r.frequency)

    for data in skill_data.values():
        freqs = data["frequencies"]
        if freqs:
            data["current"] = freqs[-1]
            data["frequencies"] = freqs[:-1]

    finder = EmergenceFinder()
    analysis = finder.get_portability_analysis(skill, skill_data)

    if analysis is None:
        raise HTTPException(status_code=404, detail=f"技能 '{skill}' 未在数据中找到")

    return PortabilityDetail(
        skill_name=analysis.skill_name,
        portability_score=analysis.portability_score,
        domains=analysis.domains,
        domain_count=analysis.domain_count,
        positions_by_domain=analysis.positions_by_domain,
        total_positions=analysis.total_positions,
        transferability_tier=analysis.transferability_tier,
        related_skills=analysis.related_skills,
        recommendation=analysis.recommendation,
    )
