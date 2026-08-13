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

import uuid
from typing import Annotated, Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, get_neo4j_driver, require_admin
from app.exceptions import StarMapError
from app.models.evolution_models import (
    EvolutionChangelog,
    EvolutionPath,
    EvolutionSnapshot,
)
from app.schemas.evolution import (
    CausalAnalysisResponse,
    ChangelogEntry,
    EmergingSkill,
    EvolutionKpiResponse,
    EvolutionPathEntry,
    EvolutionTrend,
    EvolutionTrendsResponse,
    PortabilityDetail,
    ReviewQueueItem,
    SnapshotEntry,
)
from app.services.evolution_service import LOW_TRUST_THRESHOLD, load_skill_timeseries_data
from app.tasks.celery_app import analyze_evolution_trends

router = APIRouter(prefix="/evolution", tags=["演化分析"])

# ─── Named Constants ───

DEFAULT_SIMILARITY = 0.5
"""Default similarity score when no relationship property exists."""

CII_SOURCE_THRESHOLD = 7
"""Source count threshold for classifying a skill as 'inflated' in CII calculation."""


# ─── Response Models ───


# ─── Endpoints ───


@router.get("/trends", response_model=EvolutionTrendsResponse)
async def get_trends(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    days: Annotated[int, Query(ge=7, le=730, description="分析时间窗口（天）")] = 90,
) -> EvolutionTrendsResponse:
    """技能热度趋势、岗位变迁时间线、新兴岗位预警（§8.3 演化看板）。"""
    from app.services.evolution_service import build_evolution_trends

    items = await build_evolution_trends(session, days=days)
    return EvolutionTrendsResponse(items=[EvolutionTrend(**item) for item in items])


@router.get("/kpi", response_model=EvolutionKpiResponse)
async def get_kpi(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    days: Annotated[int, Query(ge=7, le=730, description="分析时间窗口（天）")] = 90,
) -> EvolutionKpiResponse:
    """演化看板 KPI 行（涌现数/信任均值/CII 均值/预警数，D-11）。"""
    from app.services.evolution_service import build_evolution_kpi

    return EvolutionKpiResponse(**await build_evolution_kpi(session, days=days))


@router.post("/analyze")
async def analyze_evolution(
    days: Annotated[int, Query(ge=7, le=730, description="分析时间窗口（天）")] = 90,
) -> dict[str, Any]:
    """触发演化分析流程。"""
    task = analyze_evolution_trends.delay(days)
    return {"message": "queued", "task_id": task.id, "days": days}


@router.get("/changelog/{identifier}", response_model=list[ChangelogEntry])
async def get_changelog(
    identifier: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[ChangelogEntry]:
    """获取指定技能或岗位的演化变更记录 (LOOP-12)。

    identifier 可以是技能名或岗位名，同时查询两种匹配。
    """
    stmt = (
        sa.select(EvolutionChangelog)
        .where(sa.or_(EvolutionChangelog.position_name == identifier, EvolutionChangelog.skill_name == identifier))
        .order_by(EvolutionChangelog.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    records = result.scalars().all()

    return [
        ChangelogEntry(
            id=str(r.id),
            position_name=r.position_name,
            skill_name=r.skill_name,
            change_type=r.change_type,
            old_proficiency=r.old_proficiency,
            new_proficiency=r.new_proficiency,
            old_requirement=r.old_requirement,
            new_requirement=r.new_requirement,
            trust_score=r.trust_score,
            confidence=r.confidence,
            status=r.status,
            written_back=r.written_back,
            evidence_json=r.evidence_json or {},
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
    # Load emergence signals to enrich trend field (graceful degradation)
    from app.services.evolution_service import EmergenceFinder

    signals_by_name: dict[str, Any] = {}
    try:
        skill_data = await load_skill_timeseries_data(session)
        if skill_data:
            finder = EmergenceFinder()
            report = finder.scan(skill_data)
            for s in report.all_signals:
                signals_by_name.setdefault(s.skill_name, s)
    except StarMapError:
        raise
    except Exception as exc:
        logger.debug("Emergence enrichment skipped for /paths/all: {}", exc)

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
                    "       coalesce(r.key_gaps, []) AS key_gaps, "
                    "       coalesce(r.trend, 'stable') AS trend "
                    "ORDER BY trust_score DESC, similarity DESC LIMIT $limit"
                )
                result = await neo4j_session.run(cypher, limit=limit)
                entries = []
                async for r in result:
                    raw_trend = r.get("trend", "stable") or "stable"
                    # If Neo4j trend is default, try enrichment from emergence signals
                    if raw_trend == "stable":
                        sig = signals_by_name.get(r["src"] or "")
                        if sig:
                            raw_trend = sig.level.value
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
                            trend=raw_trend,
                        )
                    )
                if entries:
                    return entries
        except StarMapError:
            raise
        except Exception as e:
            logger.warning("Neo4j EVOLVES_TO read failed, falling back to PG: {}", e)

    # Fallback: PostgreSQL evolution_paths 表
    stmt = sa.select(EvolutionPath).order_by(EvolutionPath.similarity.desc()).limit(limit)
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


@router.get("/paths/{position}", response_model=list[EvolutionPathEntry])
async def get_evolution_paths(
    position: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    driver: Annotated[Any, Depends(get_neo4j_driver)],
) -> list[EvolutionPathEntry]:
    """获取指定岗位的演化路径推荐。"""
    # Load emergence signals to enrich trend field (graceful degradation)
    from app.services.evolution_service import EmergenceFinder

    signals_by_name: dict[str, Any] = {}
    try:
        skill_data = await load_skill_timeseries_data(session)
        if skill_data:
            finder = EmergenceFinder()
            report = finder.scan(skill_data)
            for s in report.all_signals:
                signals_by_name.setdefault(s.skill_name, s)
    except StarMapError:
        raise
    except Exception as exc:
        logger.debug("Emergence enrichment skipped for /paths/{{position}}: {}", exc)

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
                    "       coalesce(r.key_gaps, []) AS key_gaps, "
                    "       coalesce(r.trend, 'stable') AS trend "
                    "ORDER BY trust_score DESC, similarity DESC LIMIT 20"
                )
                result = await neo4j_session.run(cypher, position=position)
                entries = []
                async for r in result:
                    raw_trend = r.get("trend", "stable") or "stable"
                    if raw_trend == "stable":
                        sig = signals_by_name.get(r["src"] or "")
                        if sig:
                            raw_trend = sig.level.value
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
                            trend=raw_trend,
                        )
                    )
                if entries:
                    return entries
        except StarMapError:
            raise
        except Exception as e:
            logger.warning("Neo4j EVOLVES_TO read failed, falling back to PG: {}", e)

    # Fallback: PostgreSQL
    stmt = (
        sa.select(EvolutionPath)
        .where((EvolutionPath.source_position == position) | (EvolutionPath.target_position == position))
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
    from app.services.evolution_service import build_emerging_skills

    items = await build_emerging_skills(session, level=level)
    return [EmergingSkill(**item) for item in items]


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
    limit: Annotated[int, Query(ge=1, le=500, description="返回条数上限")] = 200,
    offset: Annotated[int, Query(ge=0, description="分页偏移")] = 0,
) -> list[ReviewQueueItem]:
    """获取人工审核队列（低信任度变更）。

    E21 fix: hard-coded `limit(50)` capped Tab 3 (演化变更) rendering at
    50 rows even when the actual queue has 143+ items. The KPI on the
    admin overview still showed 143 (because it does its own count),
    which confused users. Now accept a `limit` query param (default 200)
    and `offset` for pagination.
    """
    # EV-02: respect the status parameter
    stmt = (
        sa.select(EvolutionChangelog)
        .where(EvolutionChangelog.status == status)
        .where(EvolutionChangelog.trust_score < LOW_TRUST_THRESHOLD)
        .order_by(EvolutionChangelog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    records = result.scalars().all()

    return [
        ReviewQueueItem(
            id=str(r.id),  # E22: include changelog id for per-row action
            skill_name=r.skill_name,
            position_name=r.position_name,
            change_type=r.change_type,
            trust_score=r.trust_score,
            status=r.status,
            created_at=r.created_at,
        )
        for r in records
    ]


@router.post("/review-queue/batch-action", dependencies=[Depends(require_admin)])
async def batch_review_queue_action(
    body: dict[str, Any],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, int]:
    """E21 fix: bulk approve/reject all current low-trust pending items.

    Body: {"action": "approve" | "reject", "filter": {"position_name": "..."} | {}}
    Returns: {"updated": N, "matched": N}
    """
    action = body.get("action")
    if action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")
    target_status = "approved" if action == "approve" else "rejected"
    f = body.get("filter") or {}
    stmt = sa.select(EvolutionChangelog).where(
        EvolutionChangelog.status == "pending",
        EvolutionChangelog.trust_score < LOW_TRUST_THRESHOLD,
    )
    if "position_name" in f:
        stmt = stmt.where(EvolutionChangelog.position_name == f["position_name"])
    if "change_type" in f:
        stmt = stmt.where(EvolutionChangelog.change_type == f["change_type"])
    if "min_trust" in f:
        stmt = stmt.where(EvolutionChangelog.trust_score >= float(f["min_trust"]))
    if "max_trust" in f:
        stmt = stmt.where(EvolutionChangelog.trust_score <= float(f["max_trust"]))
    records = list((await session.execute(stmt)).scalars().all())
    for r in records:
        r.status = target_status
    await session.commit()
    return {"updated": len(records), "matched": len(records)}


@router.post("/review-queue/{changelog_id}/action", dependencies=[Depends(require_admin)])
async def review_queue_single_action(
    changelog_id: uuid.UUID,
    body: dict[str, Any],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, str]:
    """E22 fix: per-item approve/reject action.

    Body: {"action": "approve" | "reject"}
    Returns: {"changelog_id": "...", "status": "approved" | "rejected"}
    """
    action = body.get("action")
    if action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")
    row = (
        await session.execute(
            sa.select(EvolutionChangelog).where(EvolutionChangelog.id == changelog_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="EvolutionChangelog not found")
    target_status = "approved" if action == "approve" else "rejected"
    row.status = target_status
    await session.commit()
    # D8f 闭环: 演化变更审核通过 → 立即写回 position_skill_relations（技能/岗位关系
    # 真实生效 + 后续 graph_sync 投影 Neo4j）。原实现只改 status 无下游动作（断链）。
    if action == "approve":
        try:
            from app.core.evolution.write_back import write_back_changelog_row

            warnings: list[str] = []
            await write_back_changelog_row(session, row, warnings)
            await session.commit()
        except Exception as exc:  # noqa: BLE001 — 写回失败不阻断审核响应
            # P0-AUDIT-FIX (2026-08-13): the previous code did a local
            # `import logging as _logging` and called stdlib `getLogger` —
            # but the rest of this module uses loguru. Mixed channels made
            # this write-back failure invisible to the project-level audit
            # pipeline (which only tails loguru). Use the module-level loguru
            # logger so monitoring catches the regression.
            logger.warning(
                "evolution review approve write-back failed (non-fatal): {}", exc
            )
    return {"changelog_id": str(changelog_id), "status": target_status}


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
        history.append(
            {
                "snapshot_date": r.snapshot_date.isoformat(),
                "cii": round(cii, 3),
                "total_skills": total,
                "inflated_skills": inflated,
            }
        )

    return {"position": position, "history": history}


# ─── Sprint 2.3: Emerging Skill Alerts & Portability ───


@router.get("/portability/{skill}", response_model=PortabilityDetail)
async def get_skill_portability(
    skill: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PortabilityDetail:
    """获取指定技能的可迁移性分析。

    x-audit-note: L2 — Internal API, no frontend consumer. Used by backend analysis pipelines.
    """
    from app.services.evolution_service import EmergenceFinder

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
from app.api.v1.evolution_career_path import router as career_path_router  # noqa: E402

router.include_router(career_path_router, prefix="")


@router.get("/causal/{skill}", response_model=CausalAnalysisResponse)
async def get_skill_causal_analysis(
    skill: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CausalAnalysisResponse:
    """§7.6 因果推理轻量版: 技能-岗位关联显著性 (Fisher 精确检验, DEV-01)。"""
    from app.services.evolution_service import skill_position_associations

    data = await skill_position_associations(skill, session)
    return CausalAnalysisResponse(**data)
