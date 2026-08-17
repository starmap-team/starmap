"""批量回填技能中文名（D8i 技能中文化）——批量版。

技能名短（通常 1-2 词），一次 LLM 调用翻译多个技能，比逐条翻译快 10-20 倍。
用法:
    cd backend
    poetry run python -m scripts.backfill_skill_name_cn_batch [--batch N] [--limit N] [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.extraction.llm_client import LLMClient
from app.core.extraction.translation import has_cjk
from app.db.session import get_async_engine
from app.models.extraction_models import SkillRecord


async def _translate_batch(llm: LLMClient, names: list[str]) -> dict[str, str]:
    """一次 LLM 调用翻译一批技能名，返回 {original: translated}。"""
    if not names:
        return {}
    prompt = (
        "You are a technical recruiter translating software skill names into Simplified Chinese.\n"
        "Respond ONLY as JSON object mapping each original skill name to its Chinese translation.\n"
        "Rules: faithful concise translation; keep well-known brand/tool names in original spelling "
        "(Python, Docker, Kubernetes, SQL, Redis, Tableau, Java... keep as-is); "
        "translate generic skill phrases (Written Communication → 书面沟通).\n"
        "Output format: {\"skill1\": \"翻译1\", \"skill2\": \"翻译2\", ...}\n"
        f"Skills to translate: {json.dumps(names, ensure_ascii=False)}\n"
    )
    try:
        raw = await llm.generate(prompt, json_mode=True, temperature=0.0)
        data = json.loads(raw)
        # 过滤：只保留有效条目（翻译含中文或保持原名的知名技术）
        out: dict[str, str] = {}
        for orig in names:
            val = (data.get(orig) or "").strip()
            if val:
                out[orig] = val
        return out
    except Exception as exc:  # noqa: BLE001 — 单批失败降级逐条
        print(f"  ! batch translate error: {type(exc).__name__}: {exc}")
        return {}


async def backfill(batch_size: int, limit: int, dry_run: bool) -> None:
    engine = get_async_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    llm = LLMClient() if not dry_run else None

    async with sessionmaker() as session:
        rows = (
            await session.execute(
                select(SkillRecord)
                .where(
                    SkillRecord.name_cn.is_(None) | (SkillRecord.name_cn == ""),
                )
                .order_by(SkillRecord.source_count.desc())
                .limit(limit)
            )
        ).scalars().all()

    pending = [sk for sk in rows if not has_cjk(sk.name)]
    print(f"[backfill-skills-batch] {len(pending)} 个英文技能待翻译" + ("（dry-run）" if dry_run else ""))

    done = 0
    for i in range(0, len(pending), batch_size):
        batch = pending[i : i + batch_size]
        names = [sk.name for sk in batch]
        if dry_run:
            for n in names:
                print(f"  [dry] {n!r} -> (待翻译)")
                done += 1
            continue
        translated = await _translate_batch(llm, names)
        for sk in batch:
            name_cn = translated.get(sk.name)
            if name_cn:
                async with sessionmaker() as s:
                    row = (
                        await s.execute(select(SkillRecord).where(SkillRecord.id == sk.id))
                    ).scalar_one_or_none()
                    if row is not None:
                        row.name_cn = name_cn
                        await s.commit()
                print(f"  ✓ {sk.name!r} -> {name_cn!r}")
                done += 1
            else:
                print(f"  - {sk.name!r} 翻译失败（跳过）")
        await asyncio.sleep(0.5)  # 批间限速

    print(f"[backfill-skills-batch] 完成 {done}/{len(pending)}")
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="批量回填技能中文名（批量版）")
    parser.add_argument("--batch", type=int, default=20, help="每批翻译数量")
    parser.add_argument("--limit", type=int, default=700, help="最多处理条数")
    parser.add_argument("--dry-run", action="store_true", help="只列出不翻译")
    args = parser.parse_args()
    try:
        asyncio.run(backfill(args.batch, args.limit, args.dry_run))
    except KeyboardInterrupt:
        sys.exit(1)


if __name__ == "__main__":
    main()
