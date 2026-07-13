"""ExtractRepository — extraction data persistence layer.

Sinks raw SQL (sa.text) out of the API layer into a dedicated repository,
keeping the API handlers free of SQL string literals.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession


async def upsert_position_record(
    session: AsyncSession,
    *,
    name: str,
    industry: str | None = None,
    description: str | None = None,
) -> None:
    """Upsert a PositionRecord row by name.

    On conflict (duplicate name), updates industry only if the new value is non-null.
    """
    await session.execute(
        sa.text("""
            INSERT INTO position_records (id, name, industry, description, created_at)
            VALUES (gen_random_uuid(), :name, :industry, :description, NOW())
            ON CONFLICT (name) DO UPDATE SET industry = COALESCE(EXCLUDED.industry, position_records.industry)
        """),
        {"name": name, "industry": industry, "description": description},
    )


async def upsert_skill_record(
    session: AsyncSession,
    *,
    name: str,
    category: str = "hard_skill",
) -> None:
    """Upsert a SkillRecord row by name.

    On conflict, increments source_count and refreshes last_detected_at.
    """
    await session.execute(
        sa.text("""
            INSERT INTO skill_records (id, name, category, source_count, first_detected_at, last_detected_at)
            VALUES (gen_random_uuid(), :name, :category, 1, NOW(), NOW())
            ON CONFLICT (name) DO UPDATE SET
                source_count = skill_records.source_count + 1,
                last_detected_at = NOW()
        """),
        {"name": name, "category": category},
    )


async def write_extraction_to_pg(
    session: AsyncSession,
    pipeline_data: dict[str, Any],
) -> bool | None:
    """Write extraction result to PostgreSQL PositionRecord + SkillRecord (LOOP-05).

    Returns True on success, None on failure (non-blocking).
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
            await upsert_skill_record(session, name=skill_name)

        await session.commit()
        logger.info(
            "PG write complete: PositionRecord '{}' + {} skills upserted",
            position_name,
            len(set(all_skills)),
        )
        return True
    except Exception as e:
        await session.rollback()
        logger.warning("PG write failed (non-blocking): {}", e)
        return None
