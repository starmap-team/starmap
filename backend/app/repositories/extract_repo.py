"""ExtractRepository — extraction data persistence layer.

Sinks raw SQL (sa.text) out of the API layer into a dedicated repository,
keeping the API handlers free of SQL string literals.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.extraction.industry import normalize_industry


async def upsert_position_record(
    session: AsyncSession,
    *,
    name: str,
    industry: str | None = None,
    description: str | None = None,
    review_status: str = "pending_review",
    created_by: str | None = None,
) -> None:
    """Upsert a PositionRecord row by name.

    Phase 23: new extractions default to 'pending_review' so every new
    position is human-curated before publication. On conflict (duplicate
    name), the existing row is left untouched — review_status and other
    review metadata are preserved (admin may have already approved it).
    PRD US-003 C2: industry 归一化：None/空串/「通用」/「综合」等模糊词 → 「未分类」
    字面量（Per Fix C / Architect review），与前端 chip 文案一致；
    真实统计过滤需排除该字面量（见 app/core/extraction/industry.py）。
    """
    industry_value = normalize_industry(industry)

    await session.execute(
        sa.text("""
            INSERT INTO position_records (id, name, industry, description, created_at, review_status, created_by)
            VALUES (gen_random_uuid(), :name, :industry, :description, NOW(), :review_status, :created_by)
            ON CONFLICT (name) DO UPDATE SET industry = COALESCE(EXCLUDED.industry, position_records.industry)
        """),
        {
            "name": name,
            "industry": industry_value,
            "description": description,
            "review_status": review_status,
            "created_by": created_by,
        },
    )


async def upsert_skill_record(
    session: AsyncSession,
    *,
    name: str,
    category: str = "hard_skill",
    review_status: str = "pending_review",
    created_by: str | None = None,
) -> None:
    """Upsert a SkillRecord row by name.

    On conflict, increments source_count and refreshes last_detected_at;
    review_status is preserved (admin may have already approved it).
    """
    await session.execute(
        sa.text("""
            INSERT INTO skill_records (id, name, category, source_count, first_detected_at, last_detected_at, review_status, created_by)
            VALUES (gen_random_uuid(), :name, :category, 1, NOW(), NOW(), :review_status, :created_by)
            ON CONFLICT (name) DO UPDATE SET
                source_count = skill_records.source_count + 1,
                last_detected_at = NOW()
        """),
        {
            "name": name,
            "category": category,
            "review_status": review_status,
            "created_by": created_by,
        },
    )


async def write_extraction_to_pg(
    session: AsyncSession,
    pipeline_data: dict[str, Any],
    *,
    created_by: str | None = "system:extraction",
    review_status: str = "pending_review",
) -> bool | None:
    """Write extraction result to PostgreSQL PositionRecord + SkillRecord (LOOP-05).

    Returns True on success, None on failure (non-blocking).
    Phase 23: defaults to 'pending_review' so extracted positions/skills
    require admin approval before becoming publicly visible.
    """
    if not pipeline_data or not pipeline_data.get("position_name"):
        logger.debug("Skipping PG write: no extraction data or position_name")
        return None

    position_name = pipeline_data["position_name"]

    try:
        await upsert_position_record(
            session,
            name=position_name,
            industry=pipeline_data.get("industry"),
            description=pipeline_data.get("description") or pipeline_data.get("responsibilities_text"),
            review_status=review_status,
            created_by=created_by,
        )

 # Collect all skill names from required + preferred
        all_skills: list[str] = []
        for s in pipeline_data.get("required_skills", []):
            skill_name = s.get("skill") or s.get("name") if isinstance(s, dict) else str(s)
            if skill_name:
                all_skills.append(skill_name)
        for s in pipeline_data.get("preferred_skills", []):
            skill_name = s.get("skill") or s.get("name") if isinstance(s, dict) else str(s)
            if skill_name:
                all_skills.append(skill_name)

        for skill_name in set(all_skills):
            await upsert_skill_record(
                session,
                name=skill_name,
                review_status=review_status,
                created_by=created_by,
            )

 # R5 根治 (2026-08-13): 抽取的 evolves_to 后继岗位（职业演化目标）此前只写
 # Neo4j 图（graph_writer name-MERGE 无 canonical_id）不落 PG → 产生被
 # EVOLVES_TO 引用的无记录图节点（孤儿）。现在一并落 PG（pending_review
 # 待审核），后续 graph_sync 的岗位自愈会补齐 canonical_id 链接。
        for successor in pipeline_data.get("evolves_to", []) or []:
            if isinstance(successor, dict):
                succ_name = str(successor.get("position") or successor.get("name") or "").strip()
            else:
                succ_name = str(successor).strip()
            if succ_name and succ_name != position_name:
                try:
                    await upsert_position_record(
                        session,
                        name=succ_name,
                        industry=pipeline_data.get("industry"),
                        description=None,
                        review_status=review_status,
                        created_by=created_by,
                    )
                except Exception as succ_exc:  # noqa: BLE001 — 单条后继失败不阻断主写入
                    logger.warning("evolves_to successor PG upsert failed for {!r}: {}", succ_name, succ_exc)

        await session.commit()
        logger.info(
            "PG write complete: PositionRecord '{}' + {} skills upserted (+{} evolves_to successors)",
            position_name,
            len(set(all_skills)),
            len(pipeline_data.get("evolves_to", []) or []),
        )
        return True
    except Exception as e:
        await session.rollback()
        logger.warning("PG write failed (non-blocking): {}", e)
        return None
