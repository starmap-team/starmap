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
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.evolution.timeseries_loader import load_skill_timeseries_data
from app.dependencies import get_db_session, get_neo4j_driver
from app.models.evolution_models import (
    EvolutionChangelog,
    EvolutionPath,
    EvolutionSnapshot,
)
from app.models.extraction_models import PositionRecord, PositionSkillRelation, SkillRecord
from app.tasks.celery_app import analyze_evolution_trends

router = APIRouter(prefix="/evolution", tags=["演化分析"])

# ─── Named Constants ───

DEFAULT_SIMILARITY = 0.5
"""Default similarity score when no relationship property exists."""

CII_SOURCE_THRESHOLD = 7
"""Source count threshold for classifying a skill as 'inflated' in CII calculation."""


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
    # Load real timeseries data filtered by days parameter
    skill_data = await load_skill_timeseries_data(session, days=days)

    # If no timeseries data, return empty array with helpful message
    if not skill_data:
        logger.info("No timeseries data found for trends in the last {} days", days)
        return EvolutionTrendsResponse(items=[])

    from app.core.evolution.emergence_finder import EmergenceFinder

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
    driver: Annotated[Any, Depends(get_neo4j_driver)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[EvolutionPathEntry]:
    """获取所有演化路径（用于图谱页渲染 EVOLVES_TO 边）。"""
    # 优先从 Neo4j 读取（真实 EVOLVES_TO 关系 — phase 2 orchestrator 写入）
    if driver is not None:
        try:
            async with driver.session() as neo4j_session:
                cypher = (
                    "MATCH (a:Position)-[r:EVOLVES_TO]->(b:Position) "
                    "RETURN elementId(r) AS id, a.name AS src, b.name AS tgt, "
                    f"       coalesce(r.similarity, {DEFAULT_SIMILARITY}) AS similarity, "
                    f"       coalesce(r.trust_score, {DEFAULT_SIMILARITY}) AS trust_score, "
                    "       coalesce(r.skill_overlap, []) AS skill_overlap, "
                    "       coalesce(r.key_gaps, []) AS key_gaps "
                    "ORDER BY trust_score DESC, similarity DESC LIMIT $limit"
                )
                result = await neo4j_session.run(cypher, limit=limit)
                entries = []
                async for r in result:
                    entries.append(
                        EvolutionPathEntry(
                            id=str(r["id"]),
                            source_position=r["src"] or "Unknown",
                            target_position=r["tgt"] or "Unknown",
                            similarity=float(r["similarity"] or DEFAULT_SIMILARITY),
                            evidence_count=0,
                            skill_overlap=list(r["skill_overlap"] or []),
                            key_gaps=list(r["key_gaps"] or []),
                            trust_score=float(r["trust_score"] or DEFAULT_SIMILARITY),
                        )
                    )
                if entries:
                    return entries
        except Exception as e:  # noqa: BLE001
            logger.warning("Neo4j EVOLVES_TO read failed, falling back to PG: {}", e)

    # Fallback: PostgreSQL evolution_paths 表
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
    driver: Annotated[Any, Depends(get_neo4j_driver)],
) -> list[EvolutionPathEntry]:
    """获取指定岗位的演化路径推荐。"""
    # 优先从 Neo4j 读取
    if driver is not None:
        try:
            async with driver.session() as neo4j_session:
                cypher = (
                    "MATCH (a:Position)-[r:EVOLVES_TO]->(b:Position) "
                    "WHERE a.name = $position OR b.name = $position "
                    "RETURN elementId(r) AS id, a.name AS src, b.name AS tgt, "
                    f"       coalesce(r.similarity, {DEFAULT_SIMILARITY}) AS similarity, "
                    f"       coalesce(r.trust_score, {DEFAULT_SIMILARITY}) AS trust_score, "
                    "       coalesce(r.skill_overlap, []) AS skill_overlap, "
                    "       coalesce(r.key_gaps, []) AS key_gaps "
                    "ORDER BY trust_score DESC, similarity DESC LIMIT 20"
                )
                result = await neo4j_session.run(cypher, position=position)
                entries = []
                async for r in result:
                    entries.append(
                        EvolutionPathEntry(
                            id=str(r["id"]),
                            source_position=r["src"] or "Unknown",
                            target_position=r["tgt"] or "Unknown",
                            similarity=float(r["similarity"] or DEFAULT_SIMILARITY),
                            evidence_count=0,
                            skill_overlap=list(r["skill_overlap"] or []),
                            key_gaps=list(r["key_gaps"] or []),
                            trust_score=float(r["trust_score"] or DEFAULT_SIMILARITY),
                        )
                    )
                if entries:
                    return entries
        except Exception as e:  # noqa: BLE001
            logger.warning("Neo4j EVOLVES_TO read failed, falling back to PG: {}", e)

    # Fallback: PostgreSQL
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
    skill_data = await load_skill_timeseries_data(session)

    if not skill_data:
        return []

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
        inflated = sum(1 for s in required if isinstance(s, dict) and s.get("source_count", 0) > CII_SOURCE_THRESHOLD)
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
        from app.core.matching.constants import SENIOR_KEYWORDS
        target_lower = target.lower()
        if any(kw in target_lower for kw in SENIOR_KEYWORDS):
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

                direction2 = "up" if any(kw in target2.lower() for kw in SENIOR_KEYWORDS) else "forward"

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


# ─── Sprint 2.3: Emerging Skill Alerts & Portability ───


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
    skill_data = await load_skill_timeseries_data(session, include_category=True)

    if not skill_data:
        raise HTTPException(status_code=404, detail=f"无时序数据，无法分析技能 '{skill}' 的可迁移性")

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

# ── Sub-routers (Phase 7 evolution domain split) ──
from app.api.v1.evolution_industry_report import router as industry_report_router  # noqa: E402

router.include_router(industry_report_router, prefix="")
from app.api.v1.evolution_emerging_alerts import router as emerging_alerts_router  # noqa: E402

router.include_router(emerging_alerts_router, prefix="")
