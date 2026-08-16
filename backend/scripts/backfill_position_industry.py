"""批量回填岗位行业 industry (PRD US-002 C6 + 批量提速)。

对 position_records 中 industry 为 NULL 或空字符串的岗位用 LLM 翻译补全。
复用 core/extraction/translation.translate_title_industry —— 该函数同时返回
industry_zh 字段，专为英文 JD 设计。中文 JD 行业缺失率低，英文 JD 是主要
兜底对象（与 D8j2 skill backfill 模式一致）。

批量模式（参考 backfill_skill_name_cn_batch.py D8j2 经验，实测提速 20x）：
- 岗位 title 通常 1-2 个词，一次 LLM 调用翻译一批（默认 10 条），比逐条快。
- 批量失败时降级为逐条 translate_title_industry（不丢数据）。
- 语义：只写**真实行业**。LLM 返回空 / 「通用」等模糊词时跳过该岗位，
  不写「未分类」字面量 —— 那是落库兜底（extract_repo）的事，回填脚本
  职责是"把缺失补成真实值"。

用法:
    cd backend
    poetry run python -m scripts.backfill_position_industry [--limit N] [--batch B] [--progress-every N] [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.extraction.industry import is_generic_industry
from app.core.extraction.llm_client import LLMClient
from app.core.extraction.translation import translate_title_industry
from app.db.session import get_async_engine
from app.models.extraction_models import PositionRecord

DEFAULT_BATCH_SIZE = 10


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


async def _translate_batch(llm: LLMClient, names: list[str]) -> dict[str, str]:
    """一次 LLM 调用翻译一批岗位名为行业，返回 {original_title: industry_zh}。

    失败返回 {}（调用方降级逐条）。只保留有效行业值 —— 空值 / 模糊词
    （通用/综合等）不进入结果，调用方会跳过该岗位。
    """
    if not names:
        return {}
    prompt = (
        "You are a recruiting industry classifier. For each job position title, "
        "return the most specific industry it belongs to, in Simplified Chinese.\n"
        "Respond ONLY as JSON object mapping each original title to its industry.\n"
        "Rules: concise Chinese industry name (e.g. 互联网/IT, 金融科技, 智能制造, "
        "医疗健康, 电子商务, 游戏); if a title truly cannot be classified, map it to null.\n"
        "Output format: {\"title1\": \"行业1\", \"title2\": \"行业2\", ...}\n"
        f"Titles to classify: {json.dumps(names, ensure_ascii=False)}\n"
    )
    try:
        raw = await llm.generate(prompt, json_mode=True, temperature=0.0)
        data = json.loads(raw)
        out: dict[str, str] = {}
        for orig in names:
            val = (data.get(orig) or "").strip()
            if val and not is_generic_industry(val):
                out[orig] = val
        return out
    except Exception as exc:  # noqa: BLE001 — 单批失败降级逐条
        print(f"  ! batch classify error: {type(exc).__name__}: {exc}")
        return {}


async def _write_industry(session_maker, pos: PositionRecord, industry_zh: str) -> bool:
    """把 industry 写回 DB（仅在行仍缺失时写入，防 TOCTOU）。"""
    async with session_maker() as s:
        row = (
            await s.execute(select(PositionRecord).where(PositionRecord.id == pos.id))
        ).scalar_one_or_none()
        if row is not None and (row.industry is None or row.industry == ""):
            row.industry = industry_zh
            await s.commit()
            return True
    return False


async def backfill(
    limit: int,
    progress_every: int,
    dry_run: bool,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> None:
    """回填脚本主入口。

    参数:
      limit: 最多处理条数
      progress_every: 进度打印步长（每 N 个岗位打印一次进度）
      dry_run: 只扫描不写 DB
      batch_size: 每批 LLM 调用的岗位数（默认 10，参考 D8j2 批量 20x 提速）
    """
    if progress_every < 1:
        raise ValueError(f"progress_every 必须 >= 1，当前 {progress_every}")
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
    for start in range(0, len(candidates), batch_size):
        batch = candidates[start : start + batch_size]
        names = [p.name for p in batch]
        if dry_run:
            for n in names:
                print(f"  [dry] {n!r} -> (待分类)")
                done += 1
            continue

        translated = await _translate_batch(llm, names)
        for pos in batch:
            industry_zh = translated.get(pos.name)
            if not industry_zh:
                # 批量漏掉 → 降级逐条（LLM 对个别 title 的 key 可能略改）
                industry_zh = await translate_one(llm, pos.name)
            if industry_zh:
                if await _write_industry(sessionmaker, pos, industry_zh):
                    print(f"  ✓ {pos.name!r} -> {industry_zh!r}")
                    done += 1
                else:
                    print(f"  - {pos.name!r} 已有 industry（跳过）")
            else:
                print(f"  - {pos.name!r} 分类失败/无有效行业（跳过）")

        if len(candidates) > progress_every and start + batch_size >= progress_every:
            if (start + batch_size) % progress_every == 0 or start + batch_size >= len(candidates):
                print(f"  … 进度 {min(start + batch_size, len(candidates))}/{len(candidates)}")

    print(f"[backfill-industry] 完成 {done}/{len(candidates)}")
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="批量回填岗位行业 industry (PRD US-002)")
    parser.add_argument("--limit", type=int, default=100, help="最多处理条数（默认 100）")
    parser.add_argument(
        "--batch", type=int, default=DEFAULT_BATCH_SIZE,
        help=f"每批 LLM 调用的岗位数（默认 {DEFAULT_BATCH_SIZE}，一次调用分类多条提速）",
    )
    parser.add_argument(
        "--progress-every", type=int, default=DEFAULT_BATCH_SIZE,
        help="进度打印步长（默认 = batch 数）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只扫描不翻译")
    args = parser.parse_args()
    try:
        asyncio.run(backfill(
            limit=args.limit,
            progress_every=args.progress_every,
            dry_run=args.dry_run,
            batch_size=args.batch,
        ))
    except KeyboardInterrupt:
        sys.exit(1)


if __name__ == "__main__":
    main()
