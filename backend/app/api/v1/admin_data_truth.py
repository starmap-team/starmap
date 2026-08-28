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

# PLAN-007a (NEW-01): /admin/* 端点必须叠加 require_admin，
# 此前仅挂在 api_router 的 get_current_user 上，任意登录用户可读三口径对账数据。
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

    # ── PostgreSQL 直接查询 ──
    pg_total_positions = int(
        (await session.execute(select(func.count()).select_from(PositionRecord))).scalar() or 0
    )
    pg_approved_positions = int(
        (await session.execute(
            select(func.count()).select_from(PositionRecord)
            .where(PositionRecord.review_status == "approved")
        )).scalar() or 0
    )
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
    # P3c: PSR 关系行数（关系边指标口径 = PositionSkillRelation 表，与 admin/stats 对齐）
    # 2026-08-21 (debug 修复): 改为 approved 岗位 + approved 技能双口径 —— 图投影只投影
    # approved 岗位→approved 技能的 REQUIRES 边（未审核岗位/技能不入图是正确门控），
    # 此前 approved 岗位口径仍含 96 条「approved岗位→pending技能」边（技能待审核不入图
    # → 边建不出来）→ Neo4j 949 vs PG 1042 恒报 8.9% 误导用户。双 approved 才是可收敛
    # 的正确对比。
    pg_psr_count = int(
        (await session.execute(
            select(func.count())
            .select_from(PositionSkillRelation)
            .join(PositionRecord, PositionRecord.id == PositionSkillRelation.position_id)
            .join(SkillRecord, SkillRecord.id == PositionSkillRelation.skill_id)
            .where(
                PositionRecord.review_status == "approved",
                SkillRecord.review_status == "approved",
            )
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
    # 2026-08-28 (对账全面优化): 岗位总数行改用 PG 可入图口径（见下），
    # 此处仅保留 skills 的 API 口径。
    api_dashboard_skills = pg_total_skills
    try:
        # BUG-15 fix: 实际调用看板聚合服务 get_overview（原误引 build_overview_payload 不存在）
        from app.services.dashboard_service import get_overview  # noqa: PLC0415
        payload = await get_overview(session, driver, None)
        # get_overview 返回图/质量/流水线合并统计（Neo4j 优先、失败回退 PG），作为 API 口径
        api_dashboard_skills = int(
            payload.get("total_skills", pg_total_skills)
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("dashboard payload fetch failed, falling back to PG: {}", exc)

    rows = []

    # 指标 1: 岗位总数（三口径）
    # 2026-08-12 (admin 联调修复): 原 `[neo4j, pg_total, pg_approved]` 把"总数(233)"与
    # "已发布(179)"混作跨源比较 → 23.2% 假 critical（三源其实一致）。差异应只比较同一
    # 指标（总数）的三个来源：API / PostgreSQL / Neo4j。已发布数是独立指标（见指标 5）。
    # 2026-08-21 (debug 修复): 全量含 pending（pending 按 approved-only 架构不入图），
    # 全量 vs Neo4j 永远不等 → 83.4% 假「严重差异」让 operator 不知所措。
    # diff/status 改为比较「PG approved vs Neo4j」（真正可对齐口径）；全量仅作参考展示。
    # 2026-08-28 (对账全面优化): 岗位总数可对齐口径 = PG「可入图岗位」
    # （approved + IT 白名单 + 非 no_skills）vs Neo4j。此前把 api(Neo4j 423) 与
    # pg_approved(789) 混比——789 含 366 个设计性隐藏岗位（非IT/空技能/待审），
    # 46.4% 假 critical。可入图数才是与图谱真正可对齐的基线。
    from app.core.extraction.industry_gate import IT_INDUSTRY_WHITELIST

    pg_eligible_positions = int(
        (await session.execute(
            select(func.count()).select_from(PositionRecord).where(
                PositionRecord.review_status == "approved",
                PositionRecord.industry.in_(IT_INDUSTRY_WHITELIST),
                (PositionRecord.quality_hint.is_(None))
                | (PositionRecord.quality_hint != "no_skills"),
            )
        )).scalar() or 0
    )
    diff, status = _calc_status([pg_eligible_positions, neo4j_positions])
    rows.append(TruthRow(
        metric="岗位总数",
        description="不同数据源给出的岗位总数（口径不同）",
        api_value=pg_eligible_positions,
        postgres_value=pg_total_positions,
        neo4j_value=neo4j_positions,
        diff_pct=diff,
        status=status,
        explanation=(
            f"Neo4j {neo4j_positions} = 图谱节点总数。"
            f"PostgreSQL {pg_total_positions} = position_records 总行数"
            f"（含 {pg_total_positions - pg_approved_positions} 条待审核 + "
            f"{pg_approved_positions - pg_eligible_positions} 条设计性隐藏"
            f"（非IT/空技能/未分类），均不入图属设计）。"
            f"可入图 {pg_eligible_positions} = approved + IT 域 + 有技能。"
            f"差异率 {diff}% 按 可入图({pg_eligible_positions}) vs Neo4j({neo4j_positions}) 计算。"
        ),
    ))

    # 指标 2: 技能总数
    diff, status = _calc_status([api_dashboard_skills, pg_approved_skills, neo4j_skills])
    rows.append(TruthRow(
        metric="技能总数",
        description="Neo4j Skill 节点 vs PostgreSQL skill_records",
        api_value=api_dashboard_skills,
        postgres_value=pg_total_skills,
        neo4j_value=neo4j_skills,
        diff_pct=diff,
        status=status,
        explanation=(
            f"PostgreSQL {pg_total_skills} = skill_records 总行数"
            f"（含 {pg_total_skills - pg_approved_skills} 条待审核，待审核不入图属设计）。"
            f"Approved {pg_approved_skills} = 用户可见技能。"
            f"差异率 {diff}% 按 approved({pg_approved_skills}) vs Neo4j({neo4j_skills}) 计算。"
        ),
    ))

    # 指标 3: 关系边数（P3c 口径统一: Neo4j REQUIRES 边 == PG PositionSkillRelation 行数）
    # 2026-08-28 (对账全面优化): 可对齐口径 = 仅「可入图岗位」的边。此前 pg_psr_count
    # 含 31 个非IT/未分类岗位的 275 条边（这些岗位不入图 → 边自然不在 Neo4j），
    # 11.3% 假 critical。排除设计性隐藏岗位的边后才是真实漂移。
    pg_eligible_edges = int(
        (await session.execute(
            select(func.count())
            .select_from(PositionSkillRelation)
            .join(PositionRecord, PositionRecord.id == PositionSkillRelation.position_id)
            .join(SkillRecord, SkillRecord.id == PositionSkillRelation.skill_id)
            .where(
                PositionRecord.review_status == "approved",
                SkillRecord.review_status == "approved",
                PositionRecord.industry.in_(IT_INDUSTRY_WHITELIST),
                (PositionRecord.quality_hint.is_(None))
                | (PositionRecord.quality_hint != "no_skills"),
            )
        )).scalar() or 0
    )
    diff, status = _calc_status([neo4j_relations, pg_eligible_edges])
    rows.append(TruthRow(
        metric="关系边数",
        description="Neo4j Position→Skill REQUIRES 边 vs PostgreSQL 可入图岗位的 PSR 边",
        api_value=neo4j_relations,
        postgres_value=pg_psr_count,
        neo4j_value=neo4j_relations,
        diff_pct=diff,
        status=status,
        explanation=(
            f"Neo4j REQUIRES 边 {neo4j_relations} = 岗位-技能要求关系投影。"
            f"PostgreSQL {pg_psr_count} = approved岗位→approved技能 的 PSR 边数（SSOT），"
            f"含 {pg_psr_count - pg_eligible_edges} 条设计性隐藏岗位的边"
            f"（非IT/未分类岗位不入图，其边不在 Neo4j 属设计）。"
            f"可对齐 {pg_eligible_edges} 条（可入图岗位）。"
            f"差异率 {diff}% 按 可对齐({pg_eligible_edges}) vs Neo4j({neo4j_relations}) 计算。"
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

    # Phase 5 Step 4: 计算同步健康度
    # P2 修复 (R2/R3): 旧口径只对齐 canonical_id 非空节点 → 漏掉无 canonical_id 的
    # 历史孤儿（正是 346-311=35 / 843-752=91 差额的来源），健康卡与总数表自相矛盾。
    # 统一走 RepairEngine.detect_orphans 严格口径（含 no_canonical_id 节点）。
    from app.services.repair_engine import RepairEngine

    repair = RepairEngine(driver)
    orphan_scan = await repair.detect_orphans(session)
    orphan_positions = orphan_scan.orphan_positions
    orphan_skills = orphan_scan.orphan_skills

    # P2: 报告生成即同步审批队列（自愈式报告：每次查看数据源诊断都会刷新孤儿清单）
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
    # 2026-08-21 (debug 修复): 涵盖 unlinked 半孤立 —— 此前只算 orphan_*
    # (Neo4j 有 PG 无的真孤儿)，unlinked_* (Neo4j 有 + PG 有 + 缺 canonical_id)
    # 不计入健康度 → 用户看到「孤立 0 同步健康度 正常」实际队列 23 pending
    # 标 stale 不一致。修复：unlinked_* 也参与健康度分级，半孤立多说明
    # 「补链接」链路未及时跟随 reconcile。
    # 2026-08-25 (BUG#2): warn 时把具体原因（孤儿/半孤立名）写进
    # HealthMetrics.notes，避免「5 KPI 全 ok 但同步健康度 warn」的自相矛盾
    # 观感——operator 应能看到是哪个实体在告警。
    total_orphan = orphan_positions + orphan_skills
    total_unlinked = orphan_scan.unlinked_positions + orphan_scan.unlinked_skills
    if total_orphan == 0 and total_unlinked < 10:
        sync_health = "ok"
    elif total_orphan <= 1 and total_unlinked < 50:
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

    # 2026-08-25 (BUG#2): 收集具体告警原因（孤儿/半孤立实体名），
    # 让健康度 warn 不显得与「5 KPI 全 ok」矛盾。
    health_notes: list[str] = []
    if orphan_positions > 0:
        orphan_pos_names = [
            it.name for it in orphan_scan.items
            if it.node_type == "position" and it.reason == "orphan_canonical_id"
        ][:5]
        health_notes.append(f"{orphan_positions} 个孤立岗位: {', '.join(orphan_pos_names) or '未知'}")
    if orphan_skills > 0:
        orphan_sk_names = [
            it.name for it in orphan_scan.items
            if it.node_type == "skill"
        ][:5]
        health_notes.append(f"{orphan_skills} 个孤立技能: {', '.join(orphan_sk_names) or '未知'}")
    if orphan_scan.unlinked_positions > 0:
        health_notes.append(f"{orphan_scan.unlinked_positions} 个半孤立岗位（缺 canonical_id）")
    if orphan_scan.unlinked_skills > 0:
        health_notes.append(f"{orphan_scan.unlinked_skills} 个半孤立技能（缺 canonical_id）")

    return TruthReport(
        rows=rows,
            health=HealthMetrics(
                orphan_positions=orphan_positions,
                orphan_skills=orphan_skills,
                # 2026-08-21 (debug 修复): unlinked_* 维度补全 —— Neo4j 有 + PG 有但
                # 缺 canonical_id 的"半孤儿"（不是真孤儿但需自动补链接）。不加这
                # 个维度，operator 看到「孤立 0/0 正常」会误以为无问题，实际队列里
                # 还有 23 pending 待 sync_orphan_queue 标记 linked。
                unlinked_positions=orphan_scan.unlinked_positions,
                unlinked_skills=orphan_scan.unlinked_skills,
                last_reconcile_at=last_reconcile_at,
                reconcile_status=reconcile_status,
                sync_health=sync_health,
                notes=health_notes,
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
