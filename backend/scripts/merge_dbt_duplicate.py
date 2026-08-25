"""合并 dbt 重复节点: 保留业务节点(REQUIRES 关系), 迁移孤儿关系后删除孤儿

保留: EID=4:...:533 (source_count=3→7, REQUIRES->3 岗位, name_cn 有)
删除: EID=4:...:1093 (孤儿修复节点, PREREQUISITE->Python, source_count=7)

步骤(幂等):
1. 迁移孤儿的 PREREQUISITE->Python 关系到保留节点(若无重复)
2. 对齐保留节点 source_count = max(3, 7)
3. DETACH DELETE 孤儿节点
"""
from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime

from sqlalchemy import select

sys.path.insert(0, ".")

from app.core.extraction.graph_writer import GraphConfig  # noqa: E402
from app.db.session import get_async_engine  # noqa: E402
from app.models.extraction_models import SkillRecord  # noqa: E402

KEEP_EID = "4:9df09e45-a580-4848-9c2d-f88b610f5cfc:533"
DROP_EID = "4:9df09e45-a580-4848-9c2d-f88b610f5cfc:1093"


async def main() -> None:
    # PG source_count(权威)
    engine = get_async_engine()
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                select(SkillRecord.id, SkillRecord.source_count)
                .where(SkillRecord.name == "dbt")
            )
        ).first()
    pg_sc = int(row.source_count or 0) if row else 0
    print(f"PG dbt source_count: {pg_sc}")

    config = GraphConfig()
    now = datetime.now(UTC).isoformat()
    async with config.get_driver() as driver:
        async with driver.session() as session:
            # 1. 迁移 PREREQUISITE 关系(孤儿→保留, 若保留节点无同名关系)
            r = await session.run(
                "MATCH (drop) WHERE elementId(drop) = $drop "
                "MATCH (keep) WHERE elementId(keep) = $keep "
                "OPTIONAL MATCH (drop)-[rel:PREREQUISITE]->(target:Skill) "
                "WITH keep, drop, rel, target "
                "WHERE rel IS NOT NULL AND NOT EXISTS { (keep)-[:PREREQUISITE]->(target) } "
                "CREATE (keep)-[:PREREQUISITE]->(target) "
                "RETURN count(rel) AS migrated",
                drop=DROP_EID, keep=KEEP_EID,
            )
            rec = await r.single()
            print(f"迁移关系: {rec['migrated'] if rec else 0}")
            # 2. 对齐保留节点 source_count(先读当前值, 再取 max 写入)
            r2 = await session.run(
                "MATCH (keep) WHERE elementId(keep) = $keep RETURN coalesce(keep.source_count, 0) AS sc",
                keep=KEEP_EID,
            )
            rec2 = await r2.single()
            cur_sc = int(rec2["sc"]) if rec2 else 0
            final_sc = max(cur_sc, pg_sc)
            r2b = await session.run(
                "MATCH (keep) WHERE elementId(keep) = $keep "
                "SET keep.source_count = $sc, keep.updated_at = datetime($now) "
                "RETURN keep.source_count AS sc",
                keep=KEEP_EID, sc=final_sc, now=now,
            )
            rec2b = await r2b.single()
            print(f"保留节点 source_count(was {cur_sc}): {rec2b['sc'] if rec2b else '?'}")
            # 3. 删除孤儿
            r3 = await session.run(
                "MATCH (drop) WHERE elementId(drop) = $drop DETACH DELETE drop RETURN count(drop) AS deleted",
                drop=DROP_EID,
            )
            rec3 = await r3.single()
            print(f"删除孤儿: {rec3['deleted'] if rec3 else 0}")
            # 4. 验证: dbt 唯一 + 总数
            r4 = await session.run("MATCH (n:Skill) WHERE toLower(n.name)='dbt' RETURN count(n) AS c")
            rec4 = await r4.single()
            print(f"dbt 节点数: {rec4['c'] if rec4 else '?'}")
            r5 = await session.run("MATCH (n:Skill) RETURN count(n) AS c")
            rec5 = await r5.single()
            print(f"Skill 总数: {rec5['c'] if rec5 else '?'}")


if __name__ == "__main__":
    asyncio.run(main())