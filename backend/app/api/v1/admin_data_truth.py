"""Admin Data Source Truth — 显示每个 KPI 的三层数据源对比。

Phase 4 P0: 用户痛点是不知道 70/56/39/17 这四个数字的差异。
此端点为前端管理后台"数据源诊断"标签页提供数据。
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, get_neo4j_driver, require_admin
from app.models.extraction_models import PositionRecord, PositionSkillRelation, SkillRecord
from app.schemas.admin import (
    HealthMetrics,
    OrphanBackfillResponse,
    OrphanBatchActionRequest,
    OrphanBatchActionResponse,
    OrphanLinkRequest,
    OrphanQueueActionRequest,
    OrphanQueueItem,
    OrphanQueueResponse,
    TruthReport,
    TruthRow,
)

router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(require_admin)],
    tags=["数据源诊断"],
)


def _calc_status(values: list[int]) -> tuple[float, str]:
    """根据多个数据源的数值计算差异率和状态。"""
    non_zero = [v for v in values if v > 0]
    if not non_zero:
        return 0.0, "ok"
    max_v = max(non_zero)
    min_v = min(non_zero)
    diff_pct = round((max_v - min_v) / max_v * 100, 1)
    if diff_pct < 1:
        status = "ok"
    elif diff_pct < 10:
        status = "warn"
    else:
        status = "critical"
    return diff_pct, status


@router.get("/data-truth", response_model=TruthReport)
async def get_data_truth(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    driver: Annotated[Any, Depends(get_neo4j_driver)],
) -> TruthReport:
    """返回每个 KPI 的三层数据源对比报告。"""
    from datetime import UTC, datetime

    pg_total_positions = int(
        (await session.execute(
            select(func.count()).select_from(PositionRecord)
            .where(PositionRecord.review_status == "approved")
        )).scalar() or 0
    )
    pg_approved_positions = pg_total_positions
    pg_pending_positions = int(
        (await session.execute(
            select(func.count()).select_from(PositionRecord)
            .where(PositionRecord.review_status == "pending_review")
        )).scalar() or 0
    )
    pg_total_skills = int(
        (await session.execute(select(func.count()).select_from(SkillRecord))).scalar() or 0
    )
    pg_approved_skills = int(
        (await session.execute(
            select(func.count()).select_from(SkillRecord)
            .where(SkillRecord.review_status == "approved")
        )).scalar() or 0
    )
    pg_psr_count = int(
        (await session.execute(
            select(func.count(PositionSkillRelation.id))
            .join(PositionRecord, PositionRecord.id == PositionSkillRelation.position_id)
            .where(PositionRecord.review_status == "approved")
        )).scalar() or 0
    )

 # ── Neo4j 直接查询 ──
    neo4j_positions = 0
    neo4j_skills = 0
    neo4j_relations = 0
    if driver is not None:
        async with driver.session() as session_neo:
            result = await session_neo.run("MATCH (p:Position) RETURN count(p) AS c")
            record = await result.single()
            neo4j_positions = int(record["c"]) if record else 0

            result = await session_neo.run("MATCH (s:Skill) RETURN count(s) AS c")
            record = await result.single()
            neo4j_skills = int(record["c"]) if record else 0

 # P3c: 关系边指标改为 REQUIRES 子集（Position→Skill），与 PSR 表口径一致
            result = await session_neo.run(
                "MATCH (:Position)-[r:REQUIRES]->(:Skill) RETURN count(r) AS c"
            )
            record = await result.single()
            neo4j_relations = int(record["c"]) if record else 0

 # ── API 返回值（与前端 store 实际拿到的一致） ──
 # BUG-15 fix: actually invoke the dashboard aggregation service instead of
 # aliasing PG. The whole point of three-layer audit is API ≠ PG ≠ Neo4j;
 # aliasing defeats the purpose and silently makes diff=0 for positions.
    api_dashboard_positions = pg_total_positions
    api_dashboard_skills = pg_total_skills
    try:
 # BUG-15 fix: 实际调用看板聚合服务 get_overview（原误引 build_overview_payload 不存在）
        from app.services.dashboard_service import get_overview  # noqa: PLC0415
        payload = await get_overview(session, driver, None)
 # get_overview 返回图/质量/流水线合并统计（Neo4j 优先、失败回退 PG），作为 API 口径
        api_dashboard_positions = int(
            payload.get("total_positions", pg_total_positions)
        )
        api_dashboard_skills = int(
            payload.get("total_skills", pg_total_skills)
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("dashboard payload fetch failed, falling back to PG: {}", exc)

    rows = []

 # 指标 1: 岗位总数（三口径）
    diff, status = _calc_status([api_dashboard_positions, pg_total_positions, neo4j_positions])
    rows.append(TruthRow(
        metric="岗位总数",
        description="不同数据源给出的岗位总数（口径不同）",
        api_value=api_dashboard_positions,
        postgres_value=pg_total_positions,
        neo4j_value=neo4j_positions,
        diff_pct=diff,
        status=status,
        explanation=f"Neo4j {neo4j_positions} = 图谱节点总数（含历史/孤儿）。PostgreSQL {pg_total_positions} = position_records 总行数。Approved {pg_approved_positions} = 用户可见岗位。差额 {(neo4j_positions - pg_total_positions) if neo4j_positions > pg_total_positions else 0} 个孤儿节点需要在 Neo4j 中清理。",
    ))

 # 指标 2: 技能总数
    diff, status = _calc_status([api_dashboard_skills, neo4j_skills, pg_total_skills])
    rows.append(TruthRow(
        metric="技能总数",
        description="Neo4j Skill 节点 vs PostgreSQL skill_records",
        api_value=api_dashboard_skills,
        postgres_value=pg_total_skills,
        neo4j_value=neo4j_skills,
        diff_pct=diff,
        status=status,
        explanation=f"差额 {(neo4j_skills - pg_total_skills) if neo4j_skills > pg_total_skills else 0} 个孤儿 Skill 节点在 Neo4j 中不在 PG 中。Approved {pg_approved_skills} 个技能可被用户检索。",
    ))

 # 指标 3: 关系边数（P3c 口径统一: Neo4j REQUIRES 边 == PG PositionSkillRelation 行数）
    diff, status = _calc_status([neo4j_relations, pg_psr_count])
    rows.append(TruthRow(
        metric="关系边数",
        description="Neo4j Position→Skill REQUIRES 边 vs PostgreSQL position_skill_relations",
        api_value=neo4j_relations,
        postgres_value=pg_psr_count,
        neo4j_value=neo4j_relations,
        diff_pct=diff,
        status=status,
        explanation=(
            f"Neo4j REQUIRES 边 {neo4j_relations} = 岗位-技能要求关系投影。"
            f"PostgreSQL position_skill_relations {pg_psr_count} = 关系表行数（SSOT）。"
            "两口径一致表示岗位-技能关系投影无漂移；学习路径 PREREQUISITE 等其他关系类型不在此指标内。"
        ),
    ))

 # 指标 4: 待审核岗位
    diff, status = _calc_status([pg_pending_positions])
    rows.append(TruthRow(
        metric="待审核岗位",
        description="review_status='pending_review' 的岗位记录数",
        api_value=pg_pending_positions,
        postgres_value=pg_pending_positions,
        neo4j_value=pg_pending_positions,
        diff_pct=0.0,
        status="ok",
        explanation=f"这 {pg_pending_positions} 个岗位需要 admin 审核才能发布到公开图谱。",
    ))

 # 指标 5: 已发布岗位
    diff, status = _calc_status([pg_approved_positions])
    rows.append(TruthRow(
        metric="已发布岗位",
        description="review_status='approved' 的岗位（用户可检索）",
        api_value=pg_approved_positions,
        postgres_value=pg_approved_positions,
        neo4j_value=pg_approved_positions,
        diff_pct=0.0,
        status="ok",
        explanation=f"这 {pg_approved_positions} 个岗位已发布到公开图谱，普通用户可检索。",
    ))

 # Step 4: 计算同步健康度
    from app.services.repair_engine import RepairEngine

    repair = RepairEngine(driver)
    orphan_scan = await repair.detect_orphans(session)
    orphan_positions = orphan_scan.orphan_positions
    orphan_skills = orphan_scan.orphan_skills

    try:
        await repair.sync_orphan_queue(session)
    except Exception as exc:  # noqa: BLE001 — 队列同步失败不阻断报告
        logger.warning("orphan queue sync failed (non-fatal): {}", exc)

 # 2. 最近 reconcile 时间：从 PG 查（cron_scanner 写表）
    from sqlalchemy import text
    last_reconcile_at = None
    try:
        result = await session.execute(
            text("""
                SELECT MAX(created_at)
                FROM audit_events
                WHERE event = 'graph_reconcile'
            """)
        )
        record = result.first()
        if record and record[0]:
            last_reconcile_at = record[0].isoformat()
    except Exception:
        pass

 # 3. 健康度评估
    if orphan_positions == 0 and orphan_skills == 0:
        sync_health = "ok"
    elif orphan_positions <= 1 and orphan_skills <= 1:
        sync_health = "warn"
    else:
        sync_health = "critical"

 # 4. reconcile 状态（基于 last_reconcile_at）
    if last_reconcile_at is None:
        reconcile_status = "unknown"
    else:
        from datetime import UTC
        from datetime import datetime as _dt
        last_dt = _dt.fromisoformat(last_reconcile_at)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=UTC)
        now = _dt.now(UTC)
        age_hours = (now - last_dt).total_seconds() / 3600
        if age_hours < 25:
            reconcile_status = "ok"
        elif age_hours < 48:
            reconcile_status = "warn"
        else:
            reconcile_status = "critical"

    return TruthReport(
        rows=rows,
        health=HealthMetrics(
            orphan_positions=orphan_positions,
            orphan_skills=orphan_skills,
            last_reconcile_at=last_reconcile_at,
            reconcile_status=reconcile_status,
            sync_health=sync_health,
        ),
        generated_at=datetime.now(UTC).isoformat(),
    )


@router.get("/orphan-queue", response_model=OrphanQueueResponse)
async def get_orphan_queue_endpoint(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    driver: Annotated[Any, Depends(get_neo4j_driver)],
    status: str | None = None,
) -> OrphanQueueResponse:
    """P2: 孤儿节点审批队列（pending 默认）。查看前先同步最新检测结果。"""
    from app.services.repair_engine import RepairEngine

    repair = RepairEngine(driver)
    try:
        await repair.sync_orphan_queue(session)
    except Exception as exc:  # noqa: BLE001 — 队列同步失败不阻断列表
        logger.warning("orphan queue sync failed (non-fatal): {}", exc)
    items = await repair.get_orphan_queue(session, status=status)
    return OrphanQueueResponse(
        items=[OrphanQueueItem(**it) for it in items],
        total=len(items),
    )


@router.post("/orphan-queue/batch-action", response_model=OrphanBatchActionResponse)
async def orphan_queue_batch_action_endpoint(
    body: OrphanBatchActionRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    driver: Annotated[Any, Depends(get_neo4j_driver)],
    user: Annotated[dict[str, Any], Depends(require_admin)],
) -> OrphanBatchActionResponse:
    """P2: 孤儿批量审批 — 默认仅处理无引用孤儿（referenced_by=0，删除安全）。

    声明在 /orphan-queue/{item_id}/action 之前，避免 "batch-action" 被当作 item_id。
    """
    from app.services.repair_engine import RepairEngine

    actor = body.actor or user.get("sub") or user.get("username") or "admin"
    repair = RepairEngine(driver)
    result = await repair.execute_batch_cleanup(
        session,
        action=body.action,
        only_no_reference=body.only_no_reference,
        actor=f"admin:{actor}",
    )
    return OrphanBatchActionResponse(**result)


@router.post("/orphan-queue/backfill-skills", response_model=OrphanBackfillResponse)
async def orphan_queue_backfill_skills_endpoint(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    driver: Annotated[Any, Depends(get_neo4j_driver)],
) -> OrphanBackfillResponse:
    """P3b: 历史技能补录 — 图中存在但 PG 无记录的 Skill 回填 skill_records + 链接。

    非破坏（仅 ADD + SET canonical_id），幂等。用于根因 R3 的历史遗留技能。
    """
    from app.services.repair_engine import RepairEngine

    repair = RepairEngine(driver)
    result = await repair.backfill_skill_records(session)
    return OrphanBackfillResponse(**result)


@router.post("/orphan-queue/{item_id}/link", response_model=OrphanQueueItem)
async def orphan_queue_link_endpoint(
    item_id: str,
    body: OrphanLinkRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    driver: Annotated[Any, Depends(get_neo4j_driver)],
    user: Annotated[dict[str, Any], Depends(require_admin)],
) -> OrphanQueueItem:
    """P3a: 孤儿链接 — 把无 canonical_id 节点 SET 到 PG 记录（非破坏、可逆）。

    用于被引用孤儿（同实体不同名/缺链接），canonical_id 缺省用检测建议值。
    """
    from uuid import UUID

    from fastapi import HTTPException

    from app.models.orphan_cleanup import OrphanCleanupQueue
    from app.services.repair_engine import RepairEngine

    try:
        queue_id = UUID(item_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="item_id must be a UUID") from exc

    actor = body.actor or user.get("sub") or user.get("username") or "admin"
    repair = RepairEngine(driver)
    result = await repair.link_node(
        session, queue_id, canonical_id=body.canonical_id, actor=f"admin:{actor}",
    )
    if "error" in result:
        raise HTTPException(status_code=409, detail=result["error"])

    item = (await session.execute(
        select(OrphanCleanupQueue).where(OrphanCleanupQueue.id == queue_id)
    )).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="queue item not found")
    return OrphanQueueItem(**item.to_dict())


@router.post("/orphan-queue/{item_id}/action", response_model=OrphanQueueItem)
async def orphan_queue_action_endpoint(
    item_id: str,
    body: OrphanQueueActionRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    driver: Annotated[Any, Depends(get_neo4j_driver)],
    user: Annotated[dict[str, Any], Depends(require_admin)],
) -> OrphanQueueItem:
    """P2: 孤儿审批 — approve 删除节点（级联边）+ 审计；reject 拒绝清理。"""
    from uuid import UUID

    from fastapi import HTTPException

    from app.services.repair_engine import RepairEngine

    try:
        queue_id = UUID(item_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="item_id must be a UUID") from exc

    actor = body.actor or user.get("sub") or user.get("username") or "admin"
    repair = RepairEngine(driver)
    result = await repair.execute_cleanup(
        session, queue_id, action=body.action, actor=f"admin:{actor}",
    )
    if "error" in result:
        raise HTTPException(status_code=409, detail=result["error"])

 # 返回最新条目状态
    from app.models.orphan_cleanup import OrphanCleanupQueue

    item = (await session.execute(
        select(OrphanCleanupQueue).where(OrphanCleanupQueue.id == queue_id)
    )).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="queue item not found")
    return OrphanQueueItem(**item.to_dict())


__all__ = ["router"]
