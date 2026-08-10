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
from app.models.extraction_models import PositionRecord, SkillRecord
from app.schemas.admin import HealthMetrics, TruthReport, TruthRow

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

            result = await session_neo.run("MATCH ()-[r]->() RETURN count(r) AS c")
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
        from app.core.dashboard.dashboard_service import get_overview  # noqa: PLC0415
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
    diff, status = _calc_status([neo4j_positions, pg_total_positions, pg_approved_positions])
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
    diff, status = _calc_status([neo4j_skills, pg_total_skills])
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

    # 指标 3: 关系边数
    rows.append(TruthRow(
        metric="关系边数",
        description="Neo4j 关系总数（实时）",
        api_value=neo4j_relations,
        postgres_value=neo4j_relations,  # 暂无 PG 边表查询
        neo4j_value=neo4j_relations,
        diff_pct=0.0,
        status="ok",
        explanation="Neo4j 中所有 (:Start)-[r]->(:End) 关系总数。注意：admin/stats 报告的 582 是 PositionSkillRelation 表记录数（仅岗位-技能），不包括其他关系类型。",
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
    # 1. 孤儿节点：Neo4j 中存在但 PG 中找不到的（按 canonical_id 对齐）
    pg_position_cids = {
        str(r[0]) for r in (
            await session.execute(select(PositionRecord.id))
        ).all()
    }
    pg_skill_cids = {
        str(r[0]) for r in (
            await session.execute(select(SkillRecord.id))
        ).all()
    }

    async with driver.session() as s:
        result = await s.run(
            "MATCH (p:Position) WHERE p.canonical_id IS NOT NULL RETURN p.canonical_id AS cid"
        )
        neo4j_pos_cids = set()
        async for record in result:
            cid = record["cid"]
            if cid:
                neo4j_pos_cids.add(str(cid))

        result = await s.run(
            "MATCH (s:Skill) WHERE s.canonical_id IS NOT NULL RETURN s.canonical_id AS cid"
        )
        neo4j_skl_cids = set()
        async for record in result:
            cid = record["cid"]
            if cid:
                neo4j_skl_cids.add(str(cid))

    orphan_positions = len(neo4j_pos_cids - pg_position_cids)
    orphan_skills = len(neo4j_skl_cids - pg_skill_cids)

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


__all__ = ["router"]
