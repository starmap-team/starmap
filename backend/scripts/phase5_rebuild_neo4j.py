"""Phase 5 Step 1: 修复 Neo4j 字段映射 + 清空 + 从 PG 重建

策略（方案 B 全量版本）：
  1. 备份 Neo4j 全部节点到 .planning/phase-5-backups/
  2. 清空 Neo4j 全部 Position/Skill 节点
  3. 从 PG position_records 重建 Position 节点
  4. 从 PG skill_records 重建 Skill 节点
  5. 验证：Neo4j 节点数 == PG 记录数

执行：docker exec starmap-backend bash -c "cd /app && python scripts/phase5_rebuild_neo4j.py"
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from neo4j import AsyncGraphDatabase
from sqlalchemy import select

from app.db.session import get_async_engine
from app.models.extraction_models import PositionRecord, SkillRecord


NEO4J_URI = "bolt://neo4j:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "starmap123456"


async def backup_neo4j(driver) -> dict:
    """导出 Neo4j 全部节点和关系到 JSON 文件。"""
    backup = {"positions": [], "skills": [], "edges": []}
    async with driver.session() as s:
        result = await s.run("MATCH (p:Position) RETURN p")
        async for record in result:
            node = record["p"]
            backup["positions"].append(dict(node))

        result = await s.run("MATCH (s:Skill) RETURN s")
        async for record in result:
            node = record["s"]
            backup["skills"].append(dict(node))

        result = await s.run("MATCH ()-[r]->() RETURN r, type(r) AS t")
        async for record in result:
            r = record["r"]
            edge = dict(r)
            edge["__type"] = record["t"]
            backup["edges"].append(edge)

    backup_path = Path("/app/.planning/phase-5-backups/neo4j-full-backup.json")
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=2, default=str)
    print(f"备份已保存: {backup_path}")
    print(f"  Position: {len(backup['positions'])}")
    print(f"  Skill: {len(backup['skills'])}")
    print(f"  Edge: {len(backup['edges'])}")
    return backup


async def clear_neo4j(driver) -> None:
    """清空 Neo4j 全部节点（DETACH DELETE 包括关系）。"""
    async with driver.session() as s:
        result = await s.run("MATCH (n) DETACH DELETE n RETURN count(n) AS deleted")
        record = await result.single()
        deleted = int(record["deleted"]) if record else 0
        print(f"已清空 {deleted} 个节点")


async def rebuild_positions_from_pg(driver, session) -> int:
    """从 PG position_records 重建 Position 节点。"""
    result = await session.execute(
        select(
            PositionRecord.id,
            PositionRecord.name,
            PositionRecord.industry,
            PositionRecord.review_status,
        )
    )
    rows = result.all()
    if not rows:
        print("PG position_records 为空")
        return 0

    # 批量写入 Neo4j
    async with driver.session() as s:
        await s.run(
            """
            UNWIND $positions AS p
            MERGE (n:Position {canonical_id: p.id})
            SET n.name = p.name,
                n.industry = p.industry,
                n.review_status = p.review_status,
                n.synced_at = datetime()
            RETURN count(n) AS created
            """,
            positions=[
                {"id": str(r[0]), "name": r[1], "industry": r[2] or "", "review_status": r[3]}
                for r in rows
            ],
        )
        result = await s.run("MATCH (p:Position) RETURN count(p) AS c")
        record = await result.single()
        return int(record["c"]) if record else 0


async def rebuild_skills_from_pg(driver, session) -> int:
    """从 PG skill_records 重建 Skill 节点。"""
    result = await session.execute(
        select(
            SkillRecord.id,
            SkillRecord.name,
            SkillRecord.review_status,
        )
    )
    rows = result.all()
    if not rows:
        print("PG skill_records 为空")
        return 0

    async with driver.session() as s:
        await s.run(
            """
            UNWIND $skills AS sk
            MERGE (n:Skill {canonical_id: sk.id})
            SET n.name = sk.name,
                n.review_status = sk.review_status,
                n.synced_at = datetime()
            RETURN count(n) AS created
            """,
            skills=[
                {"id": str(r[0]), "name": r[1], "review_status": r[2]}
                for r in rows
            ],
        )
        result = await s.run("MATCH (s:Skill) RETURN count(s) AS c")
        record = await result.single()
        return int(record["c"]) if record else 0


async def main() -> None:
    """执行 Phase 5 Step 1：备份 → 清空 → 从 PG 重建。"""
    from app.services.resources import init_resources

    resources = await init_resources()
    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        async with driver.session() as s:
            result = await s.run("RETURN 1 AS ok")
            await result.single()
            print("Neo4j 连接成功")

        # Step 1: 备份
        print("\n=== Step 1: 备份 Neo4j ===")
        await backup_neo4j(driver)

        # Step 2: 清空
        print("\n=== Step 2: 清空 Neo4j 全部节点 ===")
        await clear_neo4j(driver)

        # Step 3: 从 PG 重建
        print("\n=== Step 3: 从 PG 重建 Neo4j ===")
        engine = get_async_engine()
        async with engine.begin() as conn:
            from sqlalchemy.ext.asyncio import AsyncSession
            session = AsyncSession(bind=conn)

            positions_count = await rebuild_positions_from_pg(driver, session)
            print(f"Position 重建完成: {positions_count} 个节点")

            skills_count = await rebuild_skills_from_pg(driver, session)
            print(f"Skill 重建完成: {skills_count} 个节点")

        # Step 4: 验证
        print("\n=== Step 4: 验证 ===")
        async with driver.session() as s:
            result = await s.run("MATCH (p:Position) RETURN count(p) AS pos")
            pos_count = int((await result.single())["pos"])

            result = await s.run("MATCH (s:Skill) RETURN count(s) AS skl")
            skl_count = int((await result.single())["skl"])

        # PG 计数
        async with engine.begin() as conn:
            from sqlalchemy.ext.asyncio import AsyncSession
            session = AsyncSession(bind=conn)
            pg_pos = (await session.execute(select(PositionRecord.id))).all()
            pg_skl = (await session.execute(select(SkillRecord.id))).all()

        print(f"Neo4j Position: {pos_count} vs PG: {len(pg_pos)}")
        print(f"Neo4j Skill:    {skl_count} vs PG: {len(pg_skl)}")

        match_pos = pos_count == len(pg_pos)
        match_skl = skl_count == len(pg_skl)
        print(f"\n匹配结果: Position {'✅' if match_pos else '❌'}, Skill {'✅' if match_skl else '❌'}")

    finally:
        await driver.close()
        await resources.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())