"""Evolution write-back — persist high-trust changes into the PG SSOT.

D-04/D-05/D-06: the four D-04 change types (added_required / added_preferred /
promoted / demoted) are upserted into ``position_skill_relations`` when their
trust score meets ``WRITEBACK_TRUST_THRESHOLD`` (0.6, D-05). The upsert uses
the SELECT-then-INSERT idempotent pattern from ``stage3_services`` because the
PSR table has no ``(position_id, skill_id)`` unique constraint — PostgreSQL
``ON CONFLICT`` is therefore unavailable.

Semantics:
- added_required / added_preferred  → triple-key upsert (position, skill, requirement_type)
- promoted / demoted                → locate the existing (position, skill) row and
                                      SET requirement_type (per mapping) with
                                      confidence = max(existing, new); avoids a
                                      duplicate required+preferred pair (D-04).
- removed / retained                → never written back (D-04: removed only goes
                                      to review; retained is a no-op).
- unresolved position               → skip + warning (D-08: never fabricate a
                                      PositionRecord mapping).

Failures never raise — every path is try/except'd and appended to ``warnings``
(D-06 fail-soft).
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.evolution.trust_scorer import WRITEBACK_TRUST_THRESHOLD
from app.models.evolution_models import EvolutionChangelog
from app.models.extraction_models import PositionRecord, PositionSkillRelation, SkillRecord

# : change type → PSR requirement_type
CHANGE_TO_REQUIREMENT_TYPE: dict[str, str] = {
    "added_required": "required",
    "added_preferred": "preferred",
    "promoted": "required",
    "demoted": "preferred",
}

# : only these change types are eligible for write-back.
# : removed 纳入 —— 原设计 excluded（"removed only goes to alert"），但审核即
# 生效闭环要求 removed 审核通过后真实删除 position_skill_relations 关系；
# 仍受 trust 阈值门槛保护（未审核/low-trust 不删）。
WRITEBACK_CHANGE_TYPES: set[str] = {"added_required", "added_preferred", "promoted", "demoted", "removed"}


async def _resolve_position_id(session: AsyncSession, name: str) -> uuid.UUID | None:
    """Return the ``PositionRecord.id`` for ``name`` or None when unresolvable.

    D-08: an unresolvable position returns None — the caller skips + warns
    rather than fabricating a mapping.
    """
    stmt = sa.select(PositionRecord.id).where(PositionRecord.name == name)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _resolve_skill_id(session: AsyncSession, name: str, category: str = "general") -> uuid.UUID:
    """Return the ``SkillRecord.id`` for ``name``, creating the row if missing.

    Uses the same SELECT-then-INSERT pattern as ``stage3_services._upsert_skill``
    so a skill that only exists in the evolution snapshots is materialized into
    the SSOT before the PSR row references it.
    """
    stmt = sa.select(SkillRecord).where(SkillRecord.name == name)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing.id

    record = SkillRecord(
        id=uuid.uuid4(),
        name=name,
        category=category,
        source_count=1,
        created_by="system:evolution",
    )
    session.add(record)
    await session.flush()
    return record.id


async def write_back_changelog_row(
    session: AsyncSession,
    row: EvolutionChangelog,
    warnings: list[str],
) -> float | None:
    """Upsert one changelog row into ``position_skill_relations``.

    Returns the effective confidence stored on the PSR row (``max(existing,
    new)`` — the value callers should project to Neo4j) when the row was
    eligible and written back (idempotent upsert — also returned when it
    already existed and was updated). Returns ``None`` for non-eligible change
    types, sub-threshold trust, unresolved positions, and any exception
    (appended to ``warnings``). Never raises (D-06 fail-soft).
    """
    try:
        if row.change_type not in WRITEBACK_CHANGE_TYPES:
            return None
 # (/): 审核态感知闸门——`status='approved'`（含
 # trust>=LOW_TRUST_THRESHOLD 自动 approved 与管理员手动 approved）直接放行；
 # 未审核 pending 行仍受 WRITEBACK_TRUST_THRESHOLD(0.6) 保守保护。
 # 修复「单源新技能手动审核即写回」闭环断裂（）：此前闸门只看 trust，
 # 单源 added_required≈0.418 / added_preferred≈0.348 永远 <0.6 被静默拦截。
        if row.status != "approved" and float(row.trust_score or 0.0) < WRITEBACK_TRUST_THRESHOLD:
            return None

        position_id = await _resolve_position_id(session, row.position_name)
        if position_id is None:
            warnings.append(
                f"write_back: position '{row.position_name}' not resolvable, skipping "
                f"{row.skill_name} ({row.change_type}) — no fabricated mapping (D-08)"
            )
            logger.warning(
                "evolution write_back: position '{}' not resolvable, skipping {} ({})",
                row.position_name, row.skill_name, row.change_type,
            )
            return None

 # : removed 类型 —— 技能从岗位移除 → 删除 position_skill_relations 关系
        if row.change_type == "removed":
            skill_id = await _resolve_skill_id(session, row.skill_name)
            rel = (
                await session.execute(
                    sa.select(PositionSkillRelation).where(
                        PositionSkillRelation.position_id == position_id,
                        PositionSkillRelation.skill_id == skill_id,
                    )
                )
            ).scalar_one_or_none()
            if rel is not None:
                await session.delete(rel)
                logger.info(
                    "evolution write_back: removed relation {} ← {} ({})",
                    row.position_name, row.skill_name, row.change_type,
                )
 # P0-AUDIT-FIX (2026-08-13): closed the loop on PG side (delete
 # the PSR row), but returning `row.confidence` here caused the
 # orchestrator to project that confidence onto Neo4j — producing a
 # "ghost REQUIRES edge" (PG deleted, Neo4j still present). Return
 # None to signal "no projection" — same convention used when
 # _resolve_position_id fails.
            return None

        skill_id = await _resolve_skill_id(session, row.skill_name)
        requirement_type = CHANGE_TO_REQUIREMENT_TYPE[row.change_type]
        confidence = float(row.confidence or 0.0)

        if row.change_type in ("promoted", "demoted"):
            effective = await _upsert_promoted_demoted(session, position_id, skill_id, requirement_type, confidence)
        else:
            effective = await _upsert_added(session, position_id, skill_id, requirement_type, confidence)
        return effective
    except Exception as exc:  # noqa: BLE001 — D-06 fail-soft, never propagate
        warnings.append(
            f"write_back: failed for {row.position_name}/{row.skill_name} "
            f"({row.change_type}): {type(exc).__name__}: {exc}"
        )
        logger.warning("evolution write_back: failed for {}: {}", row, exc)
        return None


async def _upsert_added(
    session: AsyncSession,
    position_id: uuid.UUID,
    skill_id: uuid.UUID,
    requirement_type: str,
    confidence: float,
) -> float:
    """Triple-key (position, skill, requirement_type) SELECT-then-INSERT upsert.

    Returns the effective confidence actually stored on the PSR row — the max
    when a row already existed, else ``confidence``. Callers project this value
    to Neo4j so the graph edge mirrors the PSR row (W1: PG ↔ Neo4j 不漂移).
    """
    stmt = sa.select(PositionSkillRelation).where(
        PositionSkillRelation.position_id == position_id,
        PositionSkillRelation.skill_id == skill_id,
        PositionSkillRelation.requirement_type == requirement_type,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        existing.confidence = max(float(existing.confidence or 0.0), confidence)
        return float(existing.confidence)
    session.add(
        PositionSkillRelation(
            position_id=position_id,
            skill_id=skill_id,
            requirement_type=requirement_type,
            confidence=confidence,
        )
    )
    return confidence


async def _upsert_promoted_demoted(
    session: AsyncSession,
    position_id: uuid.UUID,
    skill_id: uuid.UUID,
    requirement_type: str,
    confidence: float,
) -> float:
    """Locate existing (position, skill) rows, SET requirement_type + max confidence.

    Promoted/demoted collapses any duplicate required+preferred pair (D-04) into
    the single target-requirement row: the row already carrying the target
    requirement_type wins (deterministic ORDER BY requirement_type, created_at —
    no arbitrary ``existing_rows[0]``), and the redundant other row is deleted so
    the "no duplicate pair" invariant holds even for pre-existing extraction data.
    When no row exists, INSERT one.

    Returns the effective confidence stored on the PSR row (max semantics) so
    callers can project the identical value to Neo4j (W1).
    """
    stmt = (
        sa.select(PositionSkillRelation)
        .where(
            PositionSkillRelation.position_id == position_id,
            PositionSkillRelation.skill_id == skill_id,
        )
        .order_by(
            PositionSkillRelation.requirement_type,
            PositionSkillRelation.created_at,
        )
    )
    existing_rows = (await session.execute(stmt)).scalars().all()
    if not existing_rows:
        session.add(
            PositionSkillRelation(
                position_id=position_id,
                skill_id=skill_id,
                requirement_type=requirement_type,
                confidence=confidence,
            )
        )
        return confidence

    target = next(
        (r for r in existing_rows if r.requirement_type == requirement_type),
        existing_rows[0],
    )
    target.requirement_type = requirement_type
    target.confidence = max(float(target.confidence or 0.0), confidence)
    for other in existing_rows:
        if other is not target:
            await session.delete(other)
    return float(target.confidence)
