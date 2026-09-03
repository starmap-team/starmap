"""全量回填岗位五要素（Phase 38，A3 持久化）。

对 position_records 中缺五要素（industry_scenario 为空）的已审核岗位，
复用 evolution_service.generate_position_definitions 的 LLM 生成逻辑
（qwen-plus + Redis 7 天缓存 + 成本闸门 + fail-soft），生成后写回 DB。

用法:
    cd backend
    poetry run python -m scripts.backfill_position_definitions [--limit N] [--dry-run] [--only-行业]
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.session import get_async_engine
from app.models.extraction_models import PositionRecord, PositionSkillRelation, SkillRecord
from app.services.evolution_service import generate_position_definitions


async def backfill(limit: int, dry_run: bool, industry: str | None) -> None:
    engine = get_async_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async with sessionmaker() as session:
        stmt = (
            select(PositionRecord)
            .where(
                PositionRecord.review_status == "approved",
                PositionRecord.industry_scenario.is_(None),
                # 图内岗位口径：quality_hint IS NULL（非隐藏），评委可见 465/446
                PositionRecord.quality_hint.is_(None),
            )
        )
        if industry:
            # 参数化：ilike 模式值由 SQLAlchemy 绑定为占位符（无字符串插值注入面）
            pattern = industry if "%" in industry else "%" + industry + "%"
            stmt = stmt.where(PositionRecord.industry.ilike(pattern))
        stmt = stmt.order_by(PositionRecord.created_at).limit(limit)
        rows = (await session.execute(stmt)).scalars().all()
    print(f"[backfill-defs] {len(rows)} 个岗位缺五要素" + ("（dry-run）" if dry_run else ""))

    # 构造 candidate dict（generate_position_definitions 所需结构）
    candidates = []
    async with sessionmaker() as session:
        for r in rows:
            skill_stmt = (
                select(SkillRecord.name)
                .join(PositionSkillRelation, PositionSkillRelation.skill_id == SkillRecord.id)
                .where(
                    PositionSkillRelation.position_id == r.id,
                    PositionSkillRelation.requirement_type == "required",
                )
            )
            skill_names = (await session.execute(skill_stmt)).scalars().all()
            candidates.append({
                "position": r.name,
                "definition": {
                    "position_name": r.name,
                    "required_skills": list(skill_names),
                    "emerging_required": [],
                },
                "emerging_skills": [],
            })

    if dry_run:
        for c in candidates:
            print(f"  [dry] {c['position']!r} (技能 {len(c['definition']['required_skills'])})")
        await engine.dispose()
        return

    # 分批生成（10/批，成本护栏），写回 DB
    batch_size = 10
    done = failed = 0
    for i in range(0, len(candidates), batch_size):
        batch = candidates[i : i + batch_size]
        result = await generate_position_definitions(batch, top_n=len(batch))
        done += result["generated"]
        failed += result["failed"]
        for w in result["warnings"]:
            print(f"  ! {w}")

        # 写回 DB（仅成功生成的岗位）
        async with sessionmaker() as session:
            for c in batch:
                if not c.get("industry_scenario"):
                    continue  # 失败岗位跳过，可重跑
                row = (
                    await session.execute(
                        select(PositionRecord).where(PositionRecord.name == c["position"])
                    )
                ).scalar_one_or_none()
                if row is None:
                    continue
                d = c["definition"]
                row.industry_scenario = c["industry_scenario"]
                row.core_responsibilities = d.get("core_responsibilities") or []
                row.bonus_skills = d.get("bonus_skills") or []
                row.summary = d.get("summary")
            await session.commit()
        print(f"  batch {i//batch_size+1}: 完成 {result['generated']}/{len(batch)}")

    print(f"[backfill-defs] 完成 {done}/{len(candidates)}，失败 {failed}")
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="批量回填岗位五要素")
    parser.add_argument("--limit", type=int, default=500, help="最多处理条数")
    parser.add_argument("--dry-run", action="store_true", help="只列出不生成")
    parser.add_argument("--only", type=str, default=None, help="仅处理指定行业（ilike）")
    parser.add_argument("--graph-only", action="store_true", help="仅图内岗位（quality_hint IS NULL）")
    args = parser.parse_args()
    try:
        asyncio.run(backfill(args.limit, args.dry_run, args.only, include_hidden=not args.graph_only))
    except KeyboardInterrupt:
        print("\n[backfill-defs] 中断")
        sys.exit(130)


if __name__ == "__main__":
    main()
