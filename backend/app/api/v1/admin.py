"""Admin API — thin HTTP layer over admin_audit_service.

Business logic lives in app.services.admin_audit_service and app.services.review_service.
This file only handles: request parsing, dependency injection,
domain-exception → HTTP-exception mapping, and response serialization.
"""
from __future__ import annotations

import uuid as uuid_mod
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, get_neo4j_driver, require_admin
from app.schemas.admin import (
    NameCnUpdateRequest,
    PipelineStatusResponse,
    PipelineTriggerResponse,
    ReconcileResult,
    ReviewActionRequest,
    ReviewListResponse,
    SeedResetResponse,
)
from app.services import review_service
from app.services.admin_audit_service import (
    AdminStatsResponse,
    AuditItemNotFound,
    build_admin_stats,
)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


# ── Request / Response models (HTTP-layer only) ──


# ── Helper: domain exception → HTTP ──


def _map_not_found(exc: AuditItemNotFound) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


# ── Endpoints ──


@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminStatsResponse:
    """Admin overview stats."""
    return await build_admin_stats(session)


@router.post("/reconcile-neo4j", response_model=ReconcileResult, dependencies=[Depends(require_admin)])
async def reconcile_neo4j_endpoint(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    driver: Annotated[Any, Depends(get_neo4j_driver)],
) -> ReconcileResult:
    """Phase 5 Step 3: 手动触发 PG → Neo4j 同步 + 孤儿节点剪枝。

    由 admin 手动调用，或由 cron job 定期调用。

    Phase 23 Task 3 (IC-05): 增加 REQUIRES 边计数对账——Neo4j 全边 vs PG approved
    岗位 PSR，健康三档扩展纳入 ±0.5% 容差；边层补缺只 MERGE 不删（多余边记 drift）。
    """
    import time

    from sqlalchemy import func, select, text

    from app.models.extraction_models import PositionRecord, PositionSkillRelation, SkillRecord
    from app.services.graph_projector import GraphProjector

    start = time.time()
    projector = GraphProjector(driver)
    result = await projector.reconcile_all(session)
    duration_ms = int((time.time() - start) * 1000)

 # 验证对齐（节点 + REQUIRES 边）
    async with driver.session() as s:
        r1 = await s.run("MATCH (p:Position) RETURN count(p) AS c")
        neo4j_pos = int((await r1.single())["c"])
        r2 = await s.run("MATCH (s:Skill) RETURN count(s) AS c")
        neo4j_skl = int((await r2.single())["c"])
        r3 = await s.run("MATCH (:Position)-[r:REQUIRES]->(:Skill) RETURN count(r) AS c")
        neo4j_requires = int((await r3.single())["c"])

    pg_pos = (
        await session.execute(
            select(func.count(PositionRecord.id)).where(
                PositionRecord.review_status == "approved"
            )
        )
    ).scalar() or 0
    pg_skl = (await session.execute(select(func.count(SkillRecord.id)))).scalar() or 0
 # : PG 侧只统计 approved 岗位的 PSR（Neo4j 只投影 approved）
    pg_requires = (
        await session.execute(
            select(func.count(PositionSkillRelation.id))
            .join(PositionRecord, PositionRecord.id == PositionSkillRelation.position_id)
            .where(PositionRecord.review_status == "approved")
        )
    ).scalar() or 0
    requires_diff = abs(int(neo4j_requires) - int(pg_requires))

 # 健康度（ 扩展：边 ±0.5% 容差纳入三档）
    edge_tolerance = max(1, int(pg_requires * 0.005))
    nodes_equal = neo4j_pos == pg_pos and neo4j_skl == pg_skl and result.orphans_pruned == 0
    if nodes_equal and requires_diff <= edge_tolerance:
        health = "ok"
    elif requires_diff > edge_tolerance or (
        abs(neo4j_pos - pg_pos) <= 1 and abs(neo4j_skl - pg_skl) <= 1
    ):
        health = "warn"
    else:
        health = "critical"

 # Step 4: 写 audit_events 记录
    try:
        import uuid as _uuid
        from datetime import UTC
        from datetime import datetime as _dt
        await session.execute(
            text("""
                INSERT INTO audit_events (id, event, actor, action, detail, ip, created_at,
                                          entity_type, entity_id)
                VALUES (:id, :event, :actor, :action, :detail, '', :now,
                        :entity_type, :entity_id)
            """),
            {
                "id": str(_uuid.uuid4()),
                "event": "graph_reconcile",
                "actor": "admin",
                "action": "manual_reconcile",
                "detail": (
                    f"health={health},upserted={result.nodes_upserted},"
                    f"skills={result.skills_upserted},orphans={result.orphans_pruned},"
                    f"requires_neo4j={neo4j_requires},requires_pg={pg_requires},"
                    f"requires_diff={requires_diff}"
                ),
                "now": _dt.now(UTC),
 # BUG-18 fix: tag reconcile events with their scope so
 # admin audit log can filter by entity (graph).
                "entity_type": "graph",
                "entity_id": "all",
            },
        )
        await session.commit()
    except Exception as audit_exc:
        logger.warning("Failed to write reconcile audit: {}", audit_exc)

    logger.info(
        "Reconcile complete: health={}, positions_neo4j={} vs pg={}, skills_neo4j={} vs pg={}, "
        "requires_neo4j={} vs pg={} (diff={}), orphans={}, duration={}ms",
        health, neo4j_pos, pg_pos, neo4j_skl, pg_skl,
        neo4j_requires, pg_requires, requires_diff, result.orphans_pruned, duration_ms,
    )

    return ReconcileResult(
        positions_synced=result.nodes_upserted,
        skills_synced=result.skills_upserted,
        orphans_pruned=result.orphans_pruned,
        positions_in_neo4j=neo4j_pos,
        skills_in_neo4j=neo4j_skl,
        positions_in_pg=pg_pos,
        skills_in_pg=pg_skl,
        requires_in_neo4j=neo4j_requires,
        requires_in_pg=pg_requires,
        requires_diff=requires_diff,
        duration_ms=duration_ms,
        health=health,
    )


# Review workflow endpoints ( — D-tier redesign)
# ══════════════════════════════════════════════════════════════


# entity_type → (service module, "skill"|"position")
_REVIEW_TYPE_MAP = {
    "position": "position",
    "skill": "skill",
}


@router.get("/review-items", response_model=ReviewListResponse)
async def list_review_items(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    entity_type: Annotated[Literal["position", "skill"] | None, "过滤实体类型"] = None,
    status: Annotated[Literal["draft", "pending_review", "approved", "rejected"] | None, "审核状态"] = None,
    limit: Annotated[int, "返回数量上限"] = 50,
) -> ReviewListResponse:
    """Unified review queue combining position + skill entities.

    Default: returns all `pending_review` items (the active admin queue).
    Use `?entity_type=position|skill` to narrow; use `?status=...` to view
    a different lifecycle state.
    """
    items = await review_service.list_by_status(
        session,
        entity_type=entity_type,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        limit=limit,
    )
    return ReviewListResponse(
        items=[i.to_dict() for i in items],
        total=len(items),
    )


@router.post("/review/{entity_type}/{entity_id}/submit")
async def submit_for_review_endpoint(
    entity_type: Literal["position", "skill"],
    entity_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    """Submit a draft or rejected entity for admin review."""
    try:
        uid = uuid_mod.UUID(entity_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="entity_id must be a UUID") from exc
    try:
        item = await review_service.submit_for_review(
            session,
            entity_type=entity_type,  # type: ignore[arg-type]
            entity_id=uid,
            actor=user.get("sub", "admin"),
        )
    except review_service.ReviewNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except review_service.InvalidStateTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return item.to_dict()


@router.post("/review/{entity_type}/{entity_id}/approve")
async def approve_review_item_endpoint(
    entity_type: Literal["position", "skill"],
    entity_id: str,
    body: ReviewActionRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[dict[str, Any], Depends(require_admin)],
    neo4j_driver: Annotated[Any, Depends(get_neo4j_driver)],
) -> dict[str, Any]:
    """Approve a pending_review entity. Idempotent for already-approved."""
    try:
        uid = uuid_mod.UUID(entity_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="entity_id must be a UUID") from exc
    try:
        item = await review_service.approve(
            session,
            entity_type=entity_type,  # type: ignore[arg-type]
            entity_id=uid,
            actor=user.get("sub", "admin"),
            reason=body.reason,
        )
    except review_service.ReviewNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except review_service.InvalidStateTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
 # 闭环: 岗位审核通过 → 立即入图 + LLM 补中文名（不等下一轮流水线）
    item_dict = item.to_dict()
 # to_dict 键是 review_status（非 status）
    if entity_type == "position" and item_dict.get("review_status") == "approved":
        position_name = item_dict.get("name", "")
        if position_name:
            from app.tasks.stage3_services import sync_approved_position_to_graph

            try:
                await sync_approved_position_to_graph(position_name)
            except Exception as exc:  # noqa: BLE001 — 入图失败不阻断审核响应
                logger.warning("approve-then-graph failed for {!r}: {}", position_name, exc)
    elif entity_type == "skill" and item_dict.get("review_status") == "approved":
        skill_name = item_dict.get("name", "")
        if skill_name:
            from app.services.admin_audit_service import _sync_neo4j_on_audit

            try:
                await _sync_neo4j_on_audit(neo4j_driver, "skill", skill_name, "approved")
            except Exception as exc:  # noqa: BLE001 — Neo4j 同步失败不阻断审核响应
                logger.warning("skill approve Neo4j sync failed for {!r}: {}", skill_name, exc)
    return item_dict


@router.post("/review/{entity_type}/{entity_id}/reject")
async def reject_review_item_endpoint(
    entity_type: Literal["position", "skill"],
    entity_id: str,
    body: ReviewActionRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[dict[str, Any], Depends(require_admin)],
    neo4j_driver: Annotated[Any, Depends(get_neo4j_driver)],
) -> dict[str, Any]:
    """Reject a pending_review entity. Reason is required."""
    if not body.reason or not body.reason.strip():
        raise HTTPException(status_code=422, detail="reason is required for reject")
    try:
        uid = uuid_mod.UUID(entity_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="entity_id must be a UUID") from exc
    try:
        item = await review_service.reject(
            session,
            entity_type=entity_type,  # type: ignore[arg-type]
            entity_id=uid,
            actor=user.get("sub", "admin"),
            reason=body.reason,
        )
    except review_service.ReviewNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except review_service.InvalidStateTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except review_service.MissingRejectionReason as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    item_dict = item.to_dict()
    if entity_type == "skill":
        skill_name = item_dict.get("name", "")
        if skill_name:
            from app.services.admin_audit_service import _sync_neo4j_on_audit

            try:
                await _sync_neo4j_on_audit(neo4j_driver, "skill", skill_name, "rejected")
            except Exception as exc:  # noqa: BLE001 — Neo4j 同步失败不阻断审核响应
                logger.warning("skill reject Neo4j sync failed for {!r}: {}", skill_name, exc)
    return item_dict


@router.patch("/review/{entity_type}/{entity_id}/name-cn")
async def update_name_cn_endpoint(
    entity_type: Literal["position", "skill"],
    entity_id: str,
    body: NameCnUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    neo4j_driver: Annotated[Any, Depends(get_neo4j_driver)],
    user: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    """调整岗位/技能中文名（name_cn）— 复用内容审核模块（D8i/D8j 手工校准）。

    更新 PG 行 + 同步 Neo4j 节点属性，非破坏、幂等。
    """
    try:
        uid = uuid_mod.UUID(entity_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="entity_id must be a UUID") from exc
    try:
        item = await review_service.update_name_cn(
            session,
            entity_type=entity_type,  # type: ignore[arg-type]
            entity_id=uid,
            name_cn=body.name_cn,
            actor=user.get("sub", "admin"),
        )
    except review_service.ReviewNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

 # 同步 Neo4j 节点 name_cn（图谱展示跟随 PG 权威）
    if neo4j_driver is not None:
        try:
            from app.services.graph_projector import GraphProjector

            projector = GraphProjector(neo4j_driver)
            await projector.apply_change(
                label="Position" if entity_type == "position" else "Skill",
                canonical_id=uid,
                properties={"name_cn": body.name_cn},
            )
        except Exception as exc:  # noqa: BLE001 — 图同步失败不阻断 PG 更新
            logger.warning("name_cn graph sync failed for {} {}: {}", entity_type, entity_id, exc)
    return item.to_dict()


@router.post("/review/{entity_type}/{entity_id}/unpublish")
async def unpublish_review_item_endpoint(
    entity_type: Literal["position", "skill"],
    entity_id: str,
    body: ReviewActionRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    """Unpublish an approved entity (admin override) — moves it back to draft."""
    if not body.reason or not body.reason.strip():
        raise HTTPException(status_code=422, detail="reason is required for unpublish")
    try:
        uid = uuid_mod.UUID(entity_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="entity_id must be a UUID") from exc
    try:
        item = await review_service.unpublish(
            session,
            entity_type=entity_type,  # type: ignore[arg-type]
            entity_id=uid,
            actor=user.get("sub", "admin"),
            reason=body.reason,
        )
    except review_service.ReviewNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except review_service.InvalidStateTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except review_service.MissingRejectionReason as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return item.to_dict()


@router.get("/review-stats")
async def get_review_stats(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, int]:
    """Aggregate count of entities by entity_type × review_status."""
    return await review_service.count_by_status(session)


# ── Pipeline management ──


@router.get("/pipeline/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PipelineStatusResponse:
    """Pipeline status — recent runs + data health stats."""
    import sqlalchemy as sa

    from app.models.extraction_models import (
        JDExtractionRecord,
        PositionRecord,
        ReviewQueue,
        SkillRecord,
    )
    from app.models.pipeline_models import PipelineRun as PR  # noqa: N817

 # Recent 5 runs
    runs_result = await session.execute(
        sa.select(PR).order_by(PR.started_at.desc()).limit(5)
    )
    recent_runs = [
        {
            "id": str(r.id),
            "run_type": r.run_type,
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in runs_result.scalars().all()
    ]

 # Data stats
    jd_count = int((await session.execute(
        sa.select(sa.func.count()).select_from(JDExtractionRecord)
    )).scalar() or 0)
    pos_count = int((await session.execute(
        sa.select(sa.func.count()).select_from(PositionRecord)
    )).scalar() or 0)
    skill_count = int((await session.execute(
        sa.select(sa.func.count()).select_from(SkillRecord)
    )).scalar() or 0)
    pending_review = int((await session.execute(
        sa.select(sa.func.count()).select_from(ReviewQueue)
        .where(ReviewQueue.status == "pending")
    )).scalar() or 0)

    data_stats = {
        "jd_count": jd_count,
        "position_count": pos_count,
        "skill_count": skill_count,
        "pending_review": pending_review,
    }

    return PipelineStatusResponse(recent_runs=recent_runs, data_stats=data_stats)


@router.post("/pipeline/trigger-full", response_model=PipelineTriggerResponse)
async def trigger_full_pipeline(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PipelineTriggerResponse:
    """Trigger a full pipeline run: crawl -> dedup -> clean -> import -> graph_sync."""
    from app.services.pipeline_service import trigger_and_start

    run = await trigger_and_start(run_type="full")

    return PipelineTriggerResponse(
        run_id=str(run.id),
        status=run.status,
        message=f"Full pipeline triggered (run_id={run.id})",
    )


# ── Sub-routers ( admin domain split) ──
from app.api.v1.admin_graph_nodes import router as graph_nodes_router  # noqa: E402
from app.api.v1.admin_prompts import router as prompts_router  # noqa: E402

router.include_router(prompts_router, prefix="")
router.include_router(graph_nodes_router, prefix="")


@router.post("/seed/reset", response_model=SeedResetResponse)
async def reset_demo_seed() -> SeedResetResponse:
    """演示数据一键重置（设计文档 §2.3.3.2 管理角色刚需）。

    以 subprocess 顺序执行 scripts/seed_*.py；生产环境（APP_ENV=production）
    返回 refused=True，不做任何写入。
    """
    from app.services.admin_seed_service import run_demo_seed

    return await run_demo_seed()
