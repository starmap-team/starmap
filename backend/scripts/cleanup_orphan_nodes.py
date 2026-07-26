"""
Phase 4 P1: 清理 Neo4j 孤儿节点

孤儿定义：
- Neo4j Position 节点存在，但 PostgreSQL position_records 表没有同名记录
- Neo4j Skill 节点存在，但 PostgreSQL skill_records 表没有同名记录

执行步骤：
1. 备份：把所有待删除的节点导出到 .planning/phase-4-orphan-backup.json
2. 软删除：先标记 Neo4j 节点的 _orphaned=true 属性
3. 验证：再次查询确保 0 孤儿
4. 硬删除：人工确认后真正删除

执行：cd backend && poetry run python scripts/cleanup_orphan_nodes.py
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_async_engine
from app.models.extraction_models import PositionRecord, SkillRecord


async def get_pg_position_names(session: AsyncSession) -> set[str]:
    result = await session.execute(select(PositionRecord.name))
    return {row[0] for row in result.all()}


async def get_pg_skill_names(session: AsyncSession) -> set[str]:
    result = await session.execute(select(SkillRecord.name))
    return {row[0] for row in result.all()}


async def find_neo4j_orphans(driver) -> dict:
    """查询 Neo4j 中所有 Position 和 Skill 节点，对比 PG。"""
    async with driver.session() as s:
        pos_result = await s.run("MATCH (p:Position) RETURN p.name AS name")
        neo4j_positions = [record["name"] async for record in pos_result]

        skl_result = await s.run("MATCH (s:Skill) RETURN s.name AS name")
        neo4j_skills = [record["name"] async for record in skl_result]

    async with get_async_engine().begin() as conn:
        session = AsyncSession(bind=conn)
        pg_positions = await get_pg_position_names(session)
        pg_skills = await get_pg_skill_names(session)

    orphan_positions = [n for n in neo4j_positions if n not in pg_positions]
    orphan_skills = [n for n in neo4j_skills if n not in pg_skills]
    return {
        "neo4j_positions_total": len(neo4j_positions),
        "neo4j_skills_total": len(neo4j_skills),
        "orphan_positions": orphan_positions,
        "orphan_skills": orphan_skills,
        "orphan_count": len(orphan_positions) + len(orphan_skills),
    }


async def tag_orphans(driver, orphan_positions: list[str], orphan_skills: list[str]) -> int:
    """软删除：标记 _orphaned=true 和 _orphaned_at timestamp。"""
    async with driver.session() as s:
        if orphan_positions:
            await s.run(
                """
                UNWIND $names AS name
                MATCH (p:Position {name: name})
                SET p._orphaned = true, p._orphaned_at = datetime()
                RETURN count(p) AS tagged
                """,
                names=orphan_positions,
            )
        if orphan_skills:
            await s.run(
                """
                UNWIND $names AS name
                MATCH (s:Skill {name: name})
                SET s._orphaned = true, s._orphaned_at = datetime()
                RETURN count(s) AS tagged
                """,
                names=orphan_skills,
            )
    return len(orphan_positions) + len(orphan_skills)


async def hard_delete_orphans(driver) -> int:
    """硬删除：删除所有 _orphaned=true 的节点。"""
    async with driver.session() as s:
        result = await s.run(
            """
            MATCH (n)
            WHERE n._orphaned = true
            DETACH DELETE n
            RETURN count(n) AS deleted
            """
        )
        record = await result.single()
        return int(record["deleted"])


async def main(mode: str = "report") -> None:
    """主函数。

    mode:
    - report: 只生成报告，不做任何修改
    - tag: 软删除（标记 _orphaned=true）
    - delete: 硬删除已标记的节点
    """
    from app.services.resources import resources

    # 初始化资源
    await resources.init()
    driver = resources.neo4j_driver

    if mode == "report":
        result = await find_neo4j_orphans(driver)

        print("\n=== Neo4j 孤儿节点报告 ===")
        print(f"Neo4j Position 总数: {result['neo4j_positions_total']}")
        print(f"Neo4j Skill 总数: {result['neo4j_skills_total']}")
        print(f"孤儿 Position: {len(result['orphan_positions'])}")
        print(f"孤儿 Skill: {len(result['orphan_skills'])}")
        print(f"孤儿总数: {result['orphan_count']}")
        print(f"\n孤儿 Position 前 10:")
        for n in result["orphan_positions"][:10]:
            print(f"  - {n}")
        print(f"\n孤儿 Skill 前 10:")
        for n in result["orphan_skills"][:10]:
            print(f"  - {n}")

        # 备份到文件
        backup_path = Path(__file__).parents[2] / ".planning" / "phase-4-orphan-backup.json"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_data = {
            "generated_at": datetime.now(UTC).isoformat(),
            **result,
        }
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        print(f"\n报告已保存到: {backup_path}")

    elif mode == "tag":
        result = await find_neo4j_orphans(driver)
        tagged = await tag_orphans(
            driver, result["orphan_positions"], result["orphan_skills"]
        )
        print(f"已标记 {tagged} 个孤儿节点为 _orphaned=true")

    elif mode == "delete":
        deleted = await hard_delete_orphans(driver)
        print(f"已硬删除 {deleted} 个孤儿节点")

    else:
        print(f"未知模式: {mode}")
        print("可用模式: report | tag | delete")
        sys.exit(1)

    await resources.close()


if __name__ == "__main__":
    import asyncio

    mode = sys.argv[1] if len(sys.argv) > 1 else "report"
    asyncio.run(main(mode))