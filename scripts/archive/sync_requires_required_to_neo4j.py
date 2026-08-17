"""同步 PG requirement_type → Neo4j REQUIRES 边 required 属性（双库一致）。

背景：deflate 治理（backfill_deflate_profiles.py）把 49 个岗位的 required
技能降级为 preferred，但早期版本只改了 PG 没同步 Neo4j → 匹配引擎从 Neo4j
读画像仍看到膨胀（大模型应用工程师 Neo4j 13 技能 vs PG 7）。本脚本以 PG
position_skill_relations.requirement_type 为准，全量刷新 Neo4j REQUIRES 边的
required 属性。

用法:
    cd backend
    poetry run python ../scripts/sync_requires_required_to_neo4j.py [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.session import get_async_engine
from app.models.extraction_models import PositionRecord, PositionSkillRelation, SkillRecord
from app.services.resources import init_resources


async def collect_edges(session_maker) -> list[tuple[str, str, bool]]:
    """从 PG 读 (岗位名, 技能名, required) — 仅 approved 岗位。"""
    async with session_maker() as session:
        rows = (
            await session.execute(
                select(
                    PositionRecord.name,
                    SkillRecord.name,
                    PositionSkillRelation.requirement_type,
                )
                .select_from(PositionSkillRelation)
                .join(PositionRecord, PositionRecord.id == PositionSkillRelation.position_id)
                .join(SkillRecord, SkillRecord.id == PositionSkillRelation.skill_id)
                .where(PositionRecord.review_status == "approved")
            )
        ).all()
    return [(name, skill, req == "required") for name, skill, req in rows]


async def main() -> None:
    parser = argparse.ArgumentParser(description="PG requirement_type → Neo4j REQUIRES.required 全量同步")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    engine = get_async_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)
    try:
        edges = await collect_edges(sm)
        print(f"[sync-requires] PG 读取 {len(edges)} 条 REQUIRES 关系（approved 岗位）")
        if args.dry_run:
            req_count = sum(1 for _, _, req in edges if req)
            print(f"  [dry] required={req_count} preferred={len(edges)-req_count}（不写 Neo4j）")
            return

        res = await init_resources()
        driver = res.neo4j_driver
        if driver is None:
            print("[sync-requires] Neo4j driver 不可用")
            return
        # 按岗位批量更新：先全部置 false，再把 required 的置 true（幂等）
        async with driver.session() as session:
            # 全部 REQUIRES 边 required=false（以 PG 为准，缺失的降级）
            await session.run("MATCH ()-[r:REQUIRES]->() SET r.required = false")
            required_edges = [(p, s) for p, s, req in edges if req]
            for i in range(0, len(required_edges), 200):
                batch = required_edges[i:i + 200]
                for pos, skill in batch:
                    await session.run(
                        "MATCH (p:Position {name: $pos})-[r:REQUIRES]->(s:Skill {name: $skill}) "
                        "SET r.required = true",
                        pos=pos, skill=skill,
                    )
            print(f"[sync-requires] Neo4j 更新完成：{len(edges)} 边（required={len(required_edges)}）")
        await res.close()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())