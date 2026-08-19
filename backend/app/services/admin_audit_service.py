"""Admin audit service — business logic for review queue operations.

Extracted from admin.py so that the API layer remains a thin HTTP wrapper.
All functions accept an AsyncSession and return domain objects or raise
domain exceptions (AuditItemNotFound, etc.) — no HTTPException here.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from loguru import logger
from neo4j.exceptions import Neo4jError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.quality import _build_quality_dashboard
from app.core.extraction.industry import is_unclassified
from app.exceptions import StarMapError
from app.models.extraction_models import (
    JDExtractionRecord,
    PositionRecord,
    PositionSkillRelation,
    ReviewQueue,
    SkillRecord,
)

# ── Domain exceptions ──


class AuditItemNotFound(Exception):  # noqa: N818
    """Raised when a review-queue item does not exist."""


# ── Pydantic-like result types (shared with API layer) ──
# Kept here so service functions return typed objects instead of raw dicts.

from pydantic import BaseModel, Field  # noqa: E402

from app.schemas.admin import AuditItem  # noqa: E402


class AdminStatsResponse(BaseModel):
    total_nodes: int = Field(ge=0)
    total_edges: int = Field(ge=0)
    total_positions: int = Field(ge=0)
    total_skills: int = Field(ge=0)
    avg_confidence: float = Field(ge=0.0, le=1.0)
    hallucination_rate: float = Field(ge=0.0, le=1.0)
    pending_review: int = Field(ge=0)


# ── Helpers ──

_SKILL_ENTITY_TYPES = frozenset({"skill", "skill_alias", "new_skill"})
_POSITION_ENTITY_TYPES = frozenset({"position", "new_position"})

# Phase 02 D-01/D-02: single source of the Position MERGE Cypher.
# Extracted verbatim from _sync_neo4j_on_audit so the one-off bulk backfill
# (sync_all_positions_to_neo4j) reuses the exact same idempotent write path
# instead of introducing a second sync implementation.
_POSITION_MERGE_CYPHER = """
                    MERGE (n:Position {canonical_id: $cid})
                    SET n.name = $name,
                        n.industry = $industry,
                        n.review_status = $review_status,
                        n.trust_score = $trust,
                        n.status = $status,
                        n.synced_at = datetime()
                    """


# Phase 02 D-01: 剪枝早期按 name MERGE 产生的遗留 Position 节点（无 canonical_id，不受 SSOT 管理）。
# GraphProjector.reconcile_all 的孤儿剪枝带 `WHERE n.canonical_id IS NOT NULL` 前置条件，够不到这批。
_POSITION_PRUNE_LEGACY_CYPHER = """
                    MATCH (n:Position)
                    WHERE n.canonical_id IS NULL
                    DETACH DELETE n
                    RETURN count(*) AS deleted
                    """


def _trust_from_payload(payload: dict | None) -> int:
    """Extract trust score from ReviewQueue payload, default 50."""
    return int((payload or {}).get("trust", 50))


# LOOP-07: Neo4j sync on approve/reject
async def _sync_neo4j_on_audit(neo4j_driver: Any, item_type: str, item_name: str, status: str) -> None:
    """Sync audit result to Neo4j graph (non-blocking).

    Phase 5 Step 2 修复: 用 MERGE 而非 MATCH+SET，确保节点不存在时自动创建。
    canonical_id 是 Neo4j 与 PG 同步的桥梁。
    """
    if not neo4j_driver:
        return
    label_map = {"position": "Position", "new_position": "Position", "skill": "Skill", "skill_alias": "Skill", "new_skill": "Skill"}
    label = label_map.get(item_type)
    if not label:
        return
    if not label.isalnum():
        return
    try:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.db.session import get_async_engine
        from app.models.extraction_models import PositionRecord, SkillRecord

        # 查 PG 拿到 canonical_id（用 PG 实际字段名）
        engine = get_async_engine()
        async with engine.begin() as conn:
            session = AsyncSession(bind=conn)
            if label == "Position":
                result = await session.execute(
                    select(PositionRecord.id, PositionRecord.name, PositionRecord.industry, PositionRecord.review_status)
                    .where(PositionRecord.name == item_name)
                )
                row = result.first()
                if not row:
                    logger.warning("Neo4j sync: PG PositionRecord not found for '{}'", item_name)
                    return
                canonical_id = str(row[0])
                name = row[1]
                # Architect review (PRD US-003 B): DB「未分类」字面量同步到 Neo4j
                # 会污染 _classify_industry 聚类 —— 归一化为空字符串写入，Neo4j
                # 侧空字符串和 None 在 _classify_industry 都不进入聚类。
                raw_industry = row[2] or ""
                industry = "" if is_unclassified(raw_industry) else raw_industry
                review_status = row[3] or status
            else:  # Skill
                result = await session.execute(
                    select(SkillRecord.id, SkillRecord.name, SkillRecord.review_status)
                    .where(SkillRecord.name == item_name)
                )
                row = result.first()
                if not row:
                    logger.warning("Neo4j sync: PG SkillRecord not found for '{}'", item_name)
                    return
                canonical_id = str(row[0])
                name = row[1]
                review_status = row[2] or status
                industry = ""

        trust = 1.0 if status == "approved" else 0.0

        # 用 canonical_id MERGE，确保幂等
        async with neo4j_driver.session() as s:
            if label == "Position":
                await s.run(
                    _POSITION_MERGE_CYPHER,
                    cid=canonical_id,
                    name=name,
                    industry=industry,
                    review_status=review_status,
                    trust=trust,
                    status=status,
                )
            else:
                await s.run(
                    """
                    MERGE (n:Skill {canonical_id: $cid})
                    SET n.name = $name,
                        n.review_status = $review_status,
                        n.trust_score = $trust,
                        n.status = $status,
                        n.synced_at = datetime()
                    """,
                    cid=canonical_id,
                    name=name,
                    review_status=review_status,
                    trust=trust,
                    status=status,
                )
        logger.info("Neo4j sync: {} '{}' (canonical={}) → status={}", label, name, canonical_id, status)
    except (Neo4jError, SQLAlchemyError) as e:
        logger.warning("Neo4j sync failed (non-blocking): {}", e)
    except Exception as e:
        logger.exception("Unexpected error in Neo4j sync (non-blocking): {}", e)


async def sync_all_positions_to_neo4j(
    session_factory: Any, neo4j_driver: Any, *, prune_legacy: bool = False,
) -> dict[str, Any]:
    """D-01/D-02: 全量补跑 PG PositionRecord → Neo4j Position 节点（幂等 MERGE）。

    复用 `_sync_neo4j_on_audit` 的 `_POSITION_MERGE_CYPHER`（同一 MERGE 路径，不新建 sync 逻辑）。
    `canonical_id = str(PositionRecord.id)`，与 `_sync_neo4j_on_audit` 一致（D-06 canonical_id 复用）。

    单条失败不影响其余记录：错误收集进 `failed` 列表后继续（沿 M3 D-06 仅观察不阻断）。

    Args:
        session_factory: async_sessionmaker（如 `app.db.session.get_session_factory()` 的返回值）
        neo4j_driver: Neo4j AsyncDriver；为 None 时直接返回 0 同步结果
        prune_legacy: True 时在 MERGE 之后 DETACH DELETE 所有 `canonical_id IS NULL` 的
            Position 节点（早期按 name MERGE 的遗留节点，不受 SSOT 管理；
            `GraphProjector.reconcile_all` 的孤儿剪枝只覆盖带 canonical_id 的节点，
            够不到这批）。**破坏性操作，默认关闭**。

    Returns:
        `{"synced": N, "failed": [{"name": ..., "canonical_id": ..., "error": ...}], "total": N,
          "pruned": N, "started_at": iso, "finished_at": iso}`
    """
    started_at = datetime.now(UTC)
    synced = 0
    pruned = 0
    failed: list[dict[str, Any]] = []

    if neo4j_driver is None:
        logger.warning("sync_all_positions_to_neo4j: neo4j_driver is None, skipping")
        return {
            "synced": 0,
            "failed": [],
            "total": 0,
            "pruned": 0,
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
        }

    async with session_factory() as session:
        result = await session.execute(
            sa.select(
                PositionRecord.id,
                PositionRecord.name,
                PositionRecord.industry,
                PositionRecord.review_status,
            ).order_by(PositionRecord.name)
        )
        rows = result.all()

    for row in rows:
        canonical_id = str(row[0])
        name = row[1] or ""
        industry = row[2] or ""
        review_status = row[3] or "pending_review"
        trust = 1.0 if review_status == "approved" else 0.0
        try:
            async with neo4j_driver.session() as s:
                await s.run(
                    _POSITION_MERGE_CYPHER,
                    cid=canonical_id,
                    name=name,
                    industry=industry,
                    review_status=review_status,
                    trust=trust,
                    status=review_status,
                )
            synced += 1
        except Exception as exc:  # noqa: BLE001 — 单条失败不阻断全量补跑
            logger.warning("sync_all_positions_to_neo4j: '{}' ({}) failed: {}", name, canonical_id, exc)
            failed.append({"name": name, "canonical_id": canonical_id, "error": str(exc)[:500]})

    if prune_legacy:
        try:
            async with neo4j_driver.session() as s:
                prune_result = await s.run(_POSITION_PRUNE_LEGACY_CYPHER)
                record = await prune_result.single()
                pruned = int(record["deleted"]) if record else 0
            logger.info("sync_all_positions_to_neo4j: pruned {} legacy Position node(s)", pruned)
        except Exception as exc:  # noqa: BLE001 — 剪枝失败不影响已完成的 MERGE
            logger.warning("sync_all_positions_to_neo4j: legacy prune failed: {}", exc)
            failed.append({"name": "<legacy-prune>", "canonical_id": None, "error": str(exc)[:500]})

    finished_at = datetime.now(UTC)
    logger.info(
        "sync_all_positions_to_neo4j: synced={} failed={} total={} pruned={} in {:.2f}s",
        synced, len(failed), len(rows), pruned, (finished_at - started_at).total_seconds(),
    )
    return {
        "synced": synced,
        "failed": failed,
        "total": len(rows),
        "pruned": pruned,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
    }


def _audit_item_from_row(row: ReviewQueue, *, status_override: str | None = None) -> AuditItem:    return AuditItem(
        id=row.id,
        type=row.entity_type,
        name=row.entity_name,
        trust=_trust_from_payload(row.payload),
        status=status_override or row.status,
    )


async def _count_neo4j_edges() -> int:
    """Count dedup REQUIRES edges in Neo4j (single source of truth).

    PG position_skill_relations may contain duplicate (position_id, skill_id)
    rows from historical backfills. Neo4j graph uses MERGE so the count
    there is canonical.
    """
    try:
        from app.dependencies import get_neo4j_driver
        driver = get_neo4j_driver()
    except TypeError:
        # get_neo4j_driver requires a Request — fall back to ad-hoc connection.
        from neo4j import AsyncGraphDatabase
        from app.config import settings as _settings
        neo4j_uri = getattr(_settings, "neo4j_uri", "bolt://neo4j:7687")
        neo4j_user = getattr(_settings, "neo4j_user", "neo4j")
        neo4j_password = getattr(_settings, "neo4j_password", "starmap123456")
        driver = AsyncGraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    try:
        async with driver.session() as session:
            result = await session.run("MATCH ()-[r:REQUIRES]->() RETURN count(r) AS c")
            record = await result.single()
            return int(record["c"]) if record else 0
    except Exception:
        return 0
    finally:
        if hasattr(driver, "close"):
            await driver.close()


# ── Service functions ──


async def build_admin_stats(session: AsyncSession) -> AdminStatsResponse:
    """Aggregate DB counts + quality dashboard into admin stats."""
    dashboard = await _build_quality_dashboard(session)

    try:
        total_positions = int(
            (await session.execute(
                sa.select(sa.func.count()).select_from(PositionRecord)
            )).scalar() or 0
        )
        total_skills = int(
            (await session.execute(
                sa.select(sa.func.count()).select_from(SkillRecord)
            )).scalar() or 0
        )
        total_edges = await _count_neo4j_edges()
        avg_value = float(
            (await session.execute(
                sa.select(
                    sa.func.coalesce(
                        sa.func.avg(JDExtractionRecord.confidence), 0.0
                    )
                )
            )).scalar() or 0.0
        )
        pending_count = int(
            (await session.execute(
                sa.select(sa.func.count()).select_from(ReviewQueue)
                .where(ReviewQueue.status == "pending")
            )).scalar() or 0
        )
        # 合并 position/skill 的 pending_review（统一审核流）
        from app.services.review_service import count_by_status as _review_counts
        review_status_counts = await _review_counts(session)
        pending_count += (
            review_status_counts.get("position_pending_review", 0)
            + review_status_counts.get("skill_pending_review", 0)
        )
    except (SQLAlchemyError, StarMapError):
        total_positions = 0
        total_skills = 0
        total_edges = 0
        avg_value = 0.0
        pending_count = 0
        logger.warning("Admin stats DB query failed, using fallback")
    except Exception:
        total_positions = 0
        total_skills = 0
        total_edges = 0
        avg_value = 0.0
        pending_count = 0
        logger.exception("Unexpected error in admin stats DB query")

    return AdminStatsResponse(
        total_nodes=total_positions + total_skills,
        total_edges=total_edges,
        total_positions=total_positions,
        total_skills=total_skills,
        avg_confidence=avg_value,
        hallucination_rate=dashboard.hallucination_rate,
        pending_review=pending_count,
    )


async def get_review_queue(session: AsyncSession) -> list[AuditItem]:
    """Return all pending review-queue items."""
    stmt = (
        sa.select(ReviewQueue)
        .where(ReviewQueue.status == "pending")
        .order_by(ReviewQueue.id.desc())
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [_audit_item_from_row(r) for r in rows]


async def approve_audit(
    item_id: int,
    session: AsyncSession,
    neo4j_driver: Any | None = None,
    actor: str = "admin:review_queue",
) -> AuditItem:
    """Approve a review-queue item and sync to skill/position tables + Neo4j (LOOP-07).

    Phase 24 fix: when a new SkillRecord / PositionRecord is created
    from an approved ReviewQueue row, set review_status='approved' so
    the new Phase 23 review-workflow column stays consistent. Previously
    the row was created with the column default 'pending_review' —
    meaning the entity was effectively invisible to /positions and the
    admin would have to re-approve it through the content-review tab.
    """
    result = await session.execute(
        sa.select(ReviewQueue).where(ReviewQueue.id == item_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise AuditItemNotFound(f"Audit item {item_id} not found")

    row.status = "approved"

    now = datetime.now(UTC)

    # Sync approved data to actual tables
    if row.entity_type in _SKILL_ENTITY_TYPES:
        existing = await session.execute(
            sa.select(SkillRecord).where(SkillRecord.name == row.entity_name)
        )
        if existing.scalar_one_or_none() is None:
            # Preserve category from payload if the operator set one
            # (Phase 24 evolution orchestrator stores it under
            # payload["category"]; legacy path leaves it None).
            payload = row.payload or {}
            category = payload.get("category") or "general"
            session.add(SkillRecord(
                name=row.entity_name,
                category=category,
                source_count=1,
                review_status="approved",
                reviewed_by=actor,
                reviewed_at=now,
            ))
    elif row.entity_type in _POSITION_ENTITY_TYPES:
        existing = await session.execute(
            sa.select(PositionRecord).where(PositionRecord.name == row.entity_name)
        )
        if existing.scalar_one_or_none() is None:
            session.add(PositionRecord(
                name=row.entity_name,
                review_status="approved",
                reviewed_by=actor,
                reviewed_at=now,
            ))

    await session.commit()

    # Sync to Neo4j (non-blocking)
    await _sync_neo4j_on_audit(neo4j_driver, row.entity_type, row.entity_name, "approved")

    return _audit_item_from_row(row, status_override="approved")


async def reject_audit(item_id: int, session: AsyncSession, neo4j_driver: Any | None = None) -> AuditItem:
    """Reject a review-queue item and sync to Neo4j (LOOP-07)."""
    result = await session.execute(
        sa.select(ReviewQueue).where(ReviewQueue.id == item_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise AuditItemNotFound(f"Audit item {item_id} not found")

    row.status = "rejected"
    await session.commit()

    # Sync to Neo4j (non-blocking)
    await _sync_neo4j_on_audit(neo4j_driver, row.entity_type, row.entity_name, "rejected")

    return _audit_item_from_row(row, status_override="rejected")


async def update_review_queue_item(
    item_id: int, *, name: str | None = None, trust: int | None = None,
    session: AsyncSession | None = None,
) -> AuditItem:
    """Partial update of a review-queue item's name and/or trust."""
    if session is None:
        raise AuditItemNotFound("Session is required for update_review_queue_item")
    result = await session.execute(
        sa.select(ReviewQueue).where(ReviewQueue.id == item_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise AuditItemNotFound(f"Audit item {item_id} not found")

    if name is not None:
        row.entity_name = name
    if trust is not None:
        # Reassign dict so SQLAlchemy JSON dirty-tracking fires
        payload = dict(row.payload or {})
        payload["trust"] = trust
        row.payload = payload

    await session.commit()
    return _audit_item_from_row(row)


async def batch_audit(
    item_ids: list[int], action: str, session: AsyncSession,
    actor: str = "admin:batch",
) -> list[AuditItem]:
    """Batch approve or reject multiple review-queue items.

    Phase 24 fix: same as approve_audit — newly-created SkillRecord /
    PositionRecord get review_status='approved' so the Phase 23 column
    stays consistent.
    """
    result = await session.execute(
        sa.select(ReviewQueue).where(ReviewQueue.id.in_(item_ids))
    )
    rows = result.scalars().all()
    if not rows:
        raise AuditItemNotFound("No audit items found for the given IDs")

    now = datetime.now(UTC)
    results: list[AuditItem] = []
    for row in rows:
        if action == "approve":
            row.status = "approved"
            if row.entity_type in _SKILL_ENTITY_TYPES:
                existing = await session.execute(
                    sa.select(SkillRecord).where(SkillRecord.name == row.entity_name)
                )
                if existing.scalar_one_or_none() is None:
                    payload = row.payload or {}
                    category = payload.get("category") or "general"
                    session.add(SkillRecord(
                        name=row.entity_name,
                        category=category,
                        source_count=1,
                        review_status="approved",
                        reviewed_by=actor,
                        reviewed_at=now,
                    ))
            elif row.entity_type in _POSITION_ENTITY_TYPES:
                existing = await session.execute(
                    sa.select(PositionRecord).where(PositionRecord.name == row.entity_name)
                )
                if existing.scalar_one_or_none() is None:
                    session.add(PositionRecord(
                        name=row.entity_name,
                        review_status="approved",
                        reviewed_by=actor,
                        reviewed_at=now,
                    ))
        else:
            row.status = "rejected"

        results.append(_audit_item_from_row(row))

    await session.commit()
    return results
