"""
Phase 5 补遗: 重建 PositionSkillRelation 关系到 Neo4j。

问题：Phase 5 Step 1 重建 Neo4j 时只创建了 Position/Skill 节点，
没创建 Position -[REQUIRES]-> Skill 关系。
后果：/graph/overview?group_by=domain 返回 0 domains，
    因为 fallback 查询 MATCH (p:Position)-[:REQUIRES]->(s:Skill) 找不到关系。

修复：从 PG position_skill_relations 表读 582 条关系，
    用 canonical_id 在 Neo4j 中创建 MATCH 关系。
"""
from __future__ import annotations

import asyncio

from neo4j import AsyncGraphDatabase
from sqlalchemy import select

from app.db.session import get_async_engine
from app.models.extraction_models import PositionSkillRelation

NEO4J_URI = "bolt://neo4j:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "starmap123456"


async def build_relationships(driver) -> int:
    """从 PG position_skill_relations 读关系，在 Neo4j 中创建 REQUIRES 边。"""
    engine = get_async_engine()
    async with engine.begin() as conn:
        from sqlalchemy.ext.asyncio import AsyncSession
        session = AsyncSession(bind=conn)
        # 取所有关系：position_id 和 skill_id
        result = await session.execute(
            select(
                PositionSkillRelation.position_id,
                PositionSkillRelation.skill_id,
                PositionSkillRelation.requirement_type,
                PositionSkillRelation.confidence,
            )
        )
        relations = result.all()

    if not relations:
        print("PG position_skill_relations 为空")
        return 0

    print(f"PG 中有 {len(relations)} 条 Position-Skill 关系")

    # 验证两端节点都存在
    position_cids = {str(r[0]) for r in relations}
    skill_cids = {str(r[1]) for r in relations}

    async with driver.session() as s:
        result = await s.run(
            "MATCH (p:Position) WHERE p.canonical_id IN $cids RETURN p.canonical_id AS cid",
            cids=list(position_cids),
        )
        existing_pos = {record["cid"] async for record in result}

        result = await s.run(
            "MATCH (s:Skill) WHERE s.canonical_id IN $cids RETURN s.canonical_id AS cid",
            cids=list(skill_cids),
        )
        existing_skl = {record["cid"] async for record in result}

    print(f"  Neo4j 中 Position 节点: {len(existing_pos)}/{len(position_cids)}")
    print(f"  Neo4j 中 Skill 节点: {len(existing_skl)}/{len(skill_cids)}")

    # 批量创建关系（只创建两端都存在的关系）
    valid_relations = [
        {"p_cid": str(p[0]), "s_cid": str(p[1]), "rtype": p[2], "conf": float(p[3])}
        for p in relations
        if str(p[0]) in existing_pos and str(p[1]) in existing_skl
    ]

    skipped = len(relations) - len(valid_relations)
    if skipped > 0:
        print(f"  跳过 {skipped} 条（节点缺失）")

    # 分批 MERGE
    batch_size = 200
    total_created = 0
    async with driver.session() as s:
        for i in range(0, len(valid_relations), batch_size):
            batch = valid_relations[i:i + batch_size]
            await s.run(
                """
                UNWIND $rels AS r
                MATCH (p:Position {canonical_id: r.p_cid})
                MATCH (s:Skill {canonical_id: r.s_cid})
                MERGE (p)-[rel:REQUIRES]->(s)
                SET rel.requirement_type = r.rtype,
                    rel.confidence = r.conf,
                    rel.synced_at = datetime()
                RETURN count(rel) AS created
                """,
                rels=batch,
            )
            total_created += len(batch)

    print(f"  Neo4j REQUIRES 关系创建完成: {total_created} 条")
    return total_created


async def main() -> None:
    from app.services.resources import init_resources

    resources = await init_resources()
    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        async with driver.session() as s:
            result = await s.run("RETURN 1 AS ok")
            await result.single()
            print("Neo4j 连接成功\n")

        created = await build_relationships(driver)
        print("\n=== 完成 ===")
        print(f"创建 REQUIRES 关系: {created} 条")

        # 验证
        async with driver.session() as s:
            result = await s.run("MATCH ()-[r:REQUIRES]->() RETURN count(r) AS c")
            total = int((await result.single())["c"])
            print(f"Neo4j 中 REQUIRES 关系总数: {total}")
    finally:
        await driver.close()
        await resources.close()


if __name__ == "__main__":
    asyncio.run(main())
