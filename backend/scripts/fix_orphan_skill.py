"""修复孤儿 Skill 节点: DBT 补 canonical_id + 对齐 PG 属性(保留关系)

孤儿节点: Neo4j (n:Skill {name:'DBT'}) 无 canonical_id, 带 PREREQUISITE->Python。
PG 有对应技能 dbt(id=1a622804-78a0-4902-b107-6bc44a6d3adc, source_count=7)。
处置: 补 canonical_id/name_cn/source_count, 与 backfill 同款 MERGE 幂等写法,
不动 PG, 保留节点与关系。

用法: docker exec starmap-backend-prod sh -c "cd /app && python scripts/fix_orphan_skill.py"
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

ORPHAN_NAME = "dbt"  # toLower 匹配


async def main() -> None:
    engine = get_async_engine()
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                select(SkillRecord.id, SkillRecord.name, SkillRecord.name_cn,
                       SkillRecord.category, SkillRecord.source_count)
                .where(SkillRecord.name.ilike(ORPHAN_NAME))
            )
        ).all()
    if not rows:
        print(f"PG 无 {ORPHAN_NAME} 技能, 跳过")
        return
    pg = rows[0]
    print(f"PG 匹配: id={pg.id} name={pg.name} name_cn={pg.name_cn} source_count={pg.source_count}")

    config = GraphConfig()
    now = datetime.now(UTC).isoformat()
    async with config.get_driver() as driver:
        async with driver.session() as session:
            # 查孤儿节点
            r = await session.run(
                "MATCH (n:Skill) WHERE n.canonical_id IS NULL AND toLower(n.name) = $name "
                "RETURN n.name AS nm, count(n) AS c",
                name=ORPHAN_NAME,
            )
            recs = list(await r.data())
            print(f"孤儿节点数: {len(recs)}")
            if not recs:
                print("无孤儿节点, 已处理过")
                return
            # 补 canonical_id + 对齐属性(仅更新孤儿, 不触碰其它)
            result = await session.run(
                "MATCH (n:Skill) WHERE n.canonical_id IS NULL AND toLower(n.name) = $name "
                "SET n.canonical_id = $cid, n.source_count = $sc, "
                "    n.synced_at = $now, n.name = $pg_name "
                "RETURN count(n) AS fixed",
                name=ORPHAN_NAME, cid=str(pg.id), sc=int(pg.source_count or 0),
                now=now, pg_name=pg.name,
            )
            rec = await result.single()
            print(f"修复孤儿: {rec['fixed'] if rec else 0}")
            # 验证
            r2 = await session.run(
                "MATCH (n:Skill {canonical_id: $cid}) RETURN n.name AS nm, n.source_count AS sc",
                cid=str(pg.id),
            )
            async for rec2 in r2:
                print(f"验证: name={rec2['nm']} source_count={rec2['sc']}")
            # 确认无剩余孤儿
            r3 = await session.run("MATCH (n:Skill) WHERE n.canonical_id IS NULL RETURN count(n) AS c")
            rec3 = await r3.single()
            print(f"剩余孤儿: {rec3['c'] if rec3 else '?'}")


if __name__ == "__main__":
    asyncio.run(main())
