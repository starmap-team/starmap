"""Backfill quality_hint for legacy positions (Batch 0, 2026-08-28).

对存量岗位打质量标记（只更新 quality_hint 列，不删数据、不改 name/industry）：
- no_skills: 无任何 PSR 关联的 approved 岗位
- unclassified: industry 三态未分类（NULL/空/'未分类'）
- non_it: industry 明确非 IT（不在 IT 白名单）

幂等：仅当 quality_hint IS NULL 时才写（已标记的不覆盖）。
用法:
    cd backend
    poetry run python -m scripts.backfill_quality_hint [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.extraction.industry_gate import IT_INDUSTRY_WHITELIST
from app.db.session import get_async_engine
from app.models.extraction_models import PositionRecord, PositionSkillRelation

logger = logging.getLogger(__name__)


async def _no_skill_ids(session: object) -> set[str]:
    from sqlalchemy import exists

    rows = await session.execute(
        select(PositionRecord.id).where(
            ~exists(
                select(PositionSkillRelation.id).where(
                    PositionSkillRelation.position_id == PositionRecord.id
                )
            )
        )
    )
    return {str(r[0]) for r in rows.all()}


async def backfill(dry_run: bool) -> dict[str, int]:
    engine = get_async_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    stats = {"no_skills": 0, "unclassified": 0, "non_it": 0}

    async with sessionmaker() as session:
        no_skill_ids = await _no_skill_ids(session)
        rows = (
            await session.execute(
                select(PositionRecord).where(PositionRecord.quality_hint.is_(None))
            )
        ).scalars().all()
        for row in rows:
            if str(row.id) in no_skill_ids:
                hint = "no_skills"
                stats["no_skills"] += 1
            elif row.industry in (None, "", "未分类"):
                hint = "unclassified"
                stats["unclassified"] += 1
            elif row.industry not in IT_INDUSTRY_WHITELIST:
                hint = "non_it"
                stats["non_it"] += 1
            else:
                continue  # 健康岗位不标记
            if dry_run:
                logger.info("[dry-run] %s -> %s", row.name[:40], hint)
                continue
            row.quality_hint = hint
        if not dry_run:
            await session.commit()
    await engine.dispose()
    return stats


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    stats = await backfill(args.dry_run)
    logger.info("backfill done: %s", stats)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
