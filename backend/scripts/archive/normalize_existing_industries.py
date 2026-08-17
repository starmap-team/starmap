"""归一化存量 industry 字段 (2026-08-17 多层防御 Phase 1 补治存量)。

背景：
- 040 迁移把存量 NULL/'' 转「未分类」，但 96 行 system:pipeline 空 industry
  是 040 之后 pipeline 重复抽取写回的（根因已修：stage3_services 接 normalize）。
- 27 行「信息技术/互联网」alias 未归一化到 canonical「互联网/IT」→
  PG / Neo4j 同义不同桶分裂（dashboard 行业分布 3 块 vs 真实 distinct）。

本脚本：
1. industry='' 或 NULL → 「未分类」字面量
2. industry='信息技术/互联网' 等 alias → canonical 桶（复用 industry.py normalize_industry）
3. 只处理已存在行，不触碰新写入路径（新路径已修复）

用法：
    cd backend
    poetry run python -m scripts.normalize_existing_industries [--dry-run]
"""
from __future__ import annotations

import asyncio
import sys

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.extraction.industry import normalize_industry
from app.db.session import get_async_engine
from app.models.extraction_models import PositionRecord


async def run(dry_run: bool = False) -> None:
    engine = get_async_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    changed = 0
    async with sessionmaker() as session:
        rows = (
            await session.execute(
                sa.select(PositionRecord).where(
                    (PositionRecord.industry.is_(None))
                    | (PositionRecord.industry == "")
                    | (PositionRecord.industry == "信息技术/互联网")
                    | (PositionRecord.industry == "Tech")
                    | (PositionRecord.industry == "信息技术")
                    | (PositionRecord.industry == "互联网")
                )
            )
        ).scalars().all()

        for row in rows:
            normalized = normalize_industry(row.industry)
            if normalized != row.industry:
                if dry_run:
                    print(f"  [dry] {row.name!r}: {row.industry!r} -> {normalized!r}")
                else:
                    row.industry = normalized
                    print(f"  ✓ {row.name!r}: {row.industry!r} -> {normalized!r}")
                changed += 1
        if not dry_run:
            await session.commit()
    print(f"\n[normalize-existing] {len(rows)} 行扫描，{changed} 行修改" + ("（dry-run）" if dry_run else ""))
    await engine.dispose()


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    asyncio.run(run(dry_run=dry_run))


if __name__ == "__main__":
    main()
