"""批量回填岗位行业 industry (PRD US-002 C6)。

对 position_records 中 industry 为 NULL 或空字符串的岗位用 LLM 翻译补全。
复用 core/extraction/translation.translate_title_industry —— 该函数同时返回
industry_zh 字段，专为英文 JD 设计。中文 JD 行业缺失率低，英文 JD 是主要
兜底对象（与 D8j2 skill backfill 模式一致）。

用法:
    cd backend
    poetry run python -m scripts.backfill_position_industry [--limit N] [--batch-size B] [--dry-run]
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


async def collect_candidates(session_maker, limit: int) -> list[PositionRecord]:
    """扫描 industry 缺失的岗位（NULL 或空串）。

    限定 `review_status = 'approved'` —— 已发布岗位才有展示 chip 兜底问题；
    pending_review 岗位本身就需要人工审核，不应被脚本覆盖。
    """
    async with session_maker() as session:
        rows = (
            await session.execute(
                select(PositionRecord)
                .where(
                    PositionRecord.industry.is_(None) | (PositionRecord.industry == ""),
                )
                .where(PositionRecord.review_status == "approved")
                .order_by(PositionRecord.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
    return list(rows)


async def translate_one(llm: LLMClient, name: str) -> str | None:
    """单条 LLM 翻译。失败返回 None（不抛 — 局部异常不阻断批次）。"""
    try:
        translated = await translate_title_industry(llm, title=name)
        return translated.get("industry_zh") or None
    except Exception as exc:  # noqa: BLE001 — backfill 必须可降级
        print(f"  ! {name!r} 翻译异常: {exc}")
        return None


async def backfill(limit: int, batch_size: int, dry_run: bool) -> None:
    if batch_size < 1:
        raise ValueError(f"batch_size 必须 >= 1，当前 {batch_size}")
    engine = get_async_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    llm = LLMClient() if not dry_run else None

    candidates = await collect_candidates(sessionmaker, limit)
    print(
        f"[backfill-industry] 扫描到 {len(candidates)} 个 industry 缺失的 approved 岗位"
        + ("（dry-run）" if dry_run else "")
    )

    if not candidates:
        await engine.dispose()
        return

    done = 0
    for idx, pos in enumerate(candidates, start=1):
        name = pos.name
        if has_cjk(name):
            # 中文岗位大概率是种子/中文源，industry 缺失多源于 LLM 返回 "" —— 仍可走翻译兜底
            pass
        if dry_run:
            print(f"  [dry] {name!r} -> (待翻译)")
            done += 1
            continue
        industry_zh = await translate_one(llm, name)
        if industry_zh:
            async with sessionmaker() as s:
                row = (
                    await s.execute(
                        select(PositionRecord).where(PositionRecord.id == pos.id)
                    )
                ).scalar_one_or_none()
                if row is not None and (row.industry is None or row.industry == ""):
                    row.industry = industry_zh
                    await s.commit()
                    print(f"  ✓ {name!r} -> {industry_zh!r}")
                    done += 1
                else:
                    print(f"  - {name!r} 已有 industry={row.industry if row else '?'}（跳过）")
        else:
            print(f"  - {name!r} 翻译失败（跳过）")

        # 批次切分：D8j2 经验（2da90cdd）—— 批量 20 比逐条 15s/个提速 20x。
        # 本脚本采用串行 + 批次打印进度，避免 LLM 限流；
        # 如需并发，可在此处用 asyncio.gather 切片。
        if idx % batch_size == 0 and idx < len(candidates):
            print(f"  … 批次进度 {idx}/{len(candidates)}")

    print(f"[backfill-industry] 完成 {done}/{len(candidates)}")
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="批量回填岗位行业 industry (PRD US-002)")
    parser.add_argument("--limit", type=int, default=100, help="最多处理条数（默认 100）")
    parser.add_argument("--batch-size", type=int, default=20, help="进度打印步长（默认 20）")
    parser.add_argument("--dry-run", action="store_true", help="只扫描不翻译")
    args = parser.parse_args()
    try:
        asyncio.run(backfill(args.limit, args.batch_size, args.dry_run))
    except KeyboardInterrupt:
        sys.exit(1)


if __name__ == "__main__":
    main()
