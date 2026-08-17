"""D5 (2026-08-12): 抽取批次的图孤儿节点链接 canonical_id。

PG 有行（system:pipeline 抽取产物）但 Neo4j 节点缺 canonical_id 的孤儿 —— 按名匹配 PG
skill_records/position_records，回填 canonical_id；未命中 PG 的孤儿输出报告供决策。
"""
from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.db.session import get_session_factory
from app.services.resources import init_resources, resources


async def main() -> None:
    await init_resources()
    driver = resources.neo4j_driver
    if driver is None:
        raise RuntimeError("neo4j_driver unavailable")

    factory = get_session_factory()
    async with factory() as session:
        pg_skills = dict(
            (await session.execute(text("SELECT LOWER(name), id FROM skill_records"))).all()
        )
        pg_positions = dict(
            (await session.execute(text("SELECT LOWER(name), id FROM position_records"))).all()
        )

    matched = 0
    unmatched: list[str] = []
    async with driver.session() as dbs:
        for label, pg_map in (("Skill", pg_skills), ("Position", pg_positions)):
            res = await dbs.run(
                f"MATCH (n:{label}) WHERE n.canonical_id IS NULL RETURN n.name AS name"
            )
            names = [r["name"] async for r in res]
            for name in names:
                pid = pg_map.get(str(name).strip().lower())
                if pid:
                    await dbs.run(
                        f"MATCH (n:{label} {{name: $name}}) WHERE n.canonical_id IS NULL "
                        "SET n.canonical_id = $cid",
                        name=name, cid=str(pid),
                    )
                    matched += 1
                else:
                    unmatched.append(f"{label}:{name}")

    print(f"linked: {matched}")
    print(f"unmatched (graph-only, PG 无行): {len(unmatched)}")
    for u in unmatched:
        print("  -", u)


if __name__ == "__main__":
    asyncio.run(main())
