"""One-shot: 补齐 PG 有而 Neo4j 缺失的 Skill 节点(幂等, 不动 PG/已有节点)。

2026-08-25: 公网调研发现 PG skill_records=713 vs Neo4j :Skill=601, diff=112。
根因: graph_sync 一致性校验的 neo4j_driver 跨 event loop(Future attached to
different loop), 对账从未真正执行; 新抓取技能只进 PG。

本脚本:
- 只补缺失 Skill 节点(无属性 MERGE, 与 graph_writer 幂等写法一致)
- 不删/不改 Neo4j 已有节点, 不动 PG 任何数据
- 可重复执行(幂等)

用法: docker exec starmap-backend-prod sh -c "cd /app && python scripts/backfill_skills_to_graph.py"
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


async def main() -> None:
    engine = get_async_engine()
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                select(
                    SkillRecord.id,
                    SkillRecord.name,
                    SkillRecord.name_cn,
                    SkillRecord.category,
                    SkillRecord.source_count,
                )
            )
        ).all()
    pg_skills = [
        {
            "id": str(r.id),
            "name": r.name,
            "name_cn": r.name_cn,
            "category": r.category,
            "source_count": int(r.source_count or 0),
        }
        for r in rows
    ]
    print(f"PG Skill 总数: {len(pg_skills)}")

    config = GraphConfig()
    async with config.get_driver() as driver:
        async with driver.session() as session:
            result = await session.run("MATCH (s:Skill) RETURN s.canonical_id AS cid")
            existing = {
                str(rec["cid"]) for rec in await result.data() if rec["cid"] is not None
            }
            missing = [s for s in pg_skills if s["id"] not in existing]
            if not missing:
                print("no missing skills; PG skills already all in Neo4j")
                return
            now = datetime.now(UTC).isoformat()
            for s in missing:
                await session.run(
                    "MERGE (n:Skill {canonical_id: $id}) "
                    "SET n.name = $name, n.name_cn = $name_cn, n.category = $category, "
                    "    n.source_count = $source_count, n.synced_at = $now",
                    id=s["id"], name=s["name"], name_cn=s["name_cn"],
                    category=s["category"], source_count=s["source_count"], now=now,
                )
            # 同一 driver/session 验证写入后计数
            ck = await session.run("MATCH (s:Skill) RETURN count(s) AS c")
            rec = await ck.single()
            print(f"count after write (same session): {rec['c'] if rec else '?'}")

    # 新 driver 连接(同进程)再验证 — 确认提交持久化
    async with config.get_driver() as driver2:
        async with driver2.session() as session2:
            ck2 = await session2.run("MATCH (s:Skill) RETURN count(s) AS c")
            rec2 = await ck2.single()
            print(f"count after write (new connection): {rec2['c'] if rec2 else '?'}")
    print(f"补齐缺失 Skill: {len(missing)}")


if __name__ == "__main__":
    asyncio.run(main())