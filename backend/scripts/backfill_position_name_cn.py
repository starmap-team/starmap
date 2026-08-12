"""批量回填岗位中文名（D8f 中文化）。

对 position_records 中 name_cn 为空的岗位用 LLM 翻译补全。
用法:
    cd backend
    poetry run python -m scripts.backfill_position_name_cn [--limit N] [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.extraction.llm_client import LLMClient
from app.core.extraction.translation import has_cjk, translate_title_industry
from app.db.session import get_async_engine
from app.models.extraction_models import PositionRecord


async def backfill(limit: int, dry_run: bool) -> None:
    engine = get_async_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    llm = LLMClient() if not dry_run else None

    async with sessionmaker() as session:
        rows = (
            await session.execute(
                select(PositionRecord)
                .where(
                    PositionRecord.name_cn.is_(None) | (PositionRecord.name_cn == ""),
                    PositionRecord.review_status == "approved",
                )
                .order_by(PositionRecord.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()

    print(f"[backfill] {len(rows)} 个已发布岗位缺中文名" + ("（dry-run）" if dry_run else ""))

    done = 0
    for pos in rows:
        name = pos.name
        if has_cjk(name):
            continue  # 已是中文
        if dry_run:
            print(f"  [dry] {name!r} -> (待翻译)")
            done += 1
            continue
        try:
            translated = await translate_title_industry(llm, title=name)
            name_cn = translated.get("name_cn")
            if name_cn:
                async with sessionmaker() as s:
                    row = (
                        await s.execute(select(PositionRecord).where(PositionRecord.id == pos.id))
                    ).scalar_one_or_none()
                    if row is not None:
                        row.name_cn = name_cn
                        await s.commit()
                print(f"  ✓ {name!r} -> {name_cn!r}")
                done += 1
            else:
                print(f"  - {name!r} 翻译失败（跳过）")
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {name!r} 异常: {exc}")

    print(f"[backfill] 完成 {done}/{len(rows)}")
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="批量回填岗位中文名")
    parser.add_argument("--limit", type=int, default=100, help="最多处理条数")
    parser.add_argument("--dry-run", action="store_true", help="只列出不翻译")
    args = parser.parse_args()
    try:
        asyncio.run(backfill(args.limit, args.dry_run))
    except KeyboardInterrupt:
        sys.exit(1)


if __name__ == "__main__":
    main()
