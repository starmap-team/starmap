"""One-shot: sync PG REQUIRES edges → Neo4j (missing pairs only).

双存储漂移修复收尾：PG 有边而 Neo4j 缺失的对，用无属性 MERGE + SET 写入
（graph_writer 幂等修复后同款写法），使两库边数一致。

用法：poetry run python -m scripts.sync_pg_edges_to_graph
"""
from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime

from sqlalchemy import select

sys.path.insert(0, ".")

from app.core.extraction.graph_writer import GraphConfig  # noqa: E402
from app.db.session import get_async_engine  # noqa: E402
from app.models.extraction_models import PositionSkillRelation  # noqa: E402


async def main() -> None:
    engine = get_async_engine()
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                select(PositionSkillRelation.position_id, PositionSkillRelation.skill_id,
                       PositionSkillRelation.requirement_type, PositionSkillRelation.confidence)
            )
        ).all()
    pg_rels = [(str(p), str(s), rt, float(conf or 1.0)) for p, s, rt, conf in rows]

    config = GraphConfig()
    async with config.get_driver() as driver:
        async with driver.session() as session:
            existing = {
                (str(r["pcid"]), str(r["scid"]))
                for r in await (await session.run(
                    "MATCH (p:Position)-[r:REQUIRES]->(sk:Skill) "
                    "WHERE p.canonical_id IS NOT NULL AND sk.canonical_id IS NOT NULL "
                    "RETURN p.canonical_id AS pcid, sk.canonical_id AS scid"
                )).data()
            }
            missing = [e for e in pg_rels if (e[0], e[1]) not in existing]
            if not missing:
                print("no missing edges; all PG edges already in Neo4j")
                return
            now = datetime.now(UTC).isoformat()
            for pid, sid, rt, conf in missing:
                await session.run(
                    "MATCH (p:Position {canonical_id: $pid}) "
                    "MATCH (s:Skill {canonical_id: $sid}) "
                    "MERGE (p)-[r:REQUIRES]->(s) "
                    "SET r.requirement_type = $rt, r.confidence = $conf, r.synced_at = $now",
                    pid=pid, sid=sid, rt=rt, conf=conf, now=now,
                )
    print(f"synced missing edges: {len(missing)}")


if __name__ == "__main__":
    asyncio.run(main())
