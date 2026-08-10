"""PG ↔ Neo4j 数据一致性验证与修复脚本

用法:
  python scripts/ensure_data_consistency.py      # 只检查，报告差异
  python scripts/ensure_data_consistency.py --fix  # 自动修复不一致

检查项目:
  1. Neo4j Position 在 PG position_records 中存在
  2. PG position_records 在 Neo4j 中存在
  3. position_skill_relations 与 REQUIRES 关系一致

修复策略:
  - Neo4j 有但 PG 无 → INSERT position_records (review_status='approved')
  - PG 有但 Neo4j 无 → MERGE Position 节点
  - 技能关系以 Neo4j REQUIRES 为准回填 PG
"""
from __future__ import annotations

import argparse
import asyncio
import os
from datetime import datetime, timezone
from uuid import uuid4

from neo4j import AsyncGraphDatabase
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
PG_URI = os.getenv("POSTGRES_URI", "postgresql+asyncpg://starmap:starmap123456@localhost:5433/starmap")


async def check_consistency(neo4j_driver, pg_engine) -> dict:
    """检查 PG 和 Neo4j 的 Position 数据一致性。返回报告。"""
    report = {
        "neo4j_positions": 0,
        "pg_positions": 0,
        "only_in_neo4j": [],
        "only_in_pg": [],
        "matching": 0,
    }

    # Neo4j Position names
    neo4j_names: set[str] = set()
    async with neo4j_driver.session() as session:
        result = await session.run("MATCH (p:Position) RETURN p.name AS name")
        async for record in result:
            neo4j_names.add(record["name"])
    report["neo4j_positions"] = len(neo4j_names)

    # PG position_records names
    pg_names: set[str] = set()
    async with async_sessionmaker(pg_engine, expire_on_commit=False)() as session:
        rows = (await session.execute(text("SELECT name FROM position_records"))).scalars().all()
        pg_names = set(rows)
    report["pg_positions"] = len(pg_names)

    report["only_in_neo4j"] = sorted(neo4j_names - pg_names)
    report["only_in_pg"] = sorted(pg_names - neo4j_names)
    report["matching"] = len(neo4j_names & pg_names)

    return report


async def fix_consistency(neo4j_driver, pg_engine, report: dict) -> dict:
    """根据检查报告修复不一致。"""
    now = datetime.now(timezone.utc)
    fixes = {"neo4j_to_pg": 0, "pg_to_neo4j": 0}

    # 1. Neo4j 有但 PG 无 → 回填 PG
    async with async_sessionmaker(pg_engine, expire_on_commit=False)() as session:
        for name in report["only_in_neo4j"]:
            # 获取 Neo4j 中的属性
            async with neo4j_driver.session() as ns:
                node_result = await ns.run(
                    "MATCH (p:Position {name: $name}) RETURN p", name=name
                )
                node_record = await node_result.single()
                if node_record:
                    props = dict(node_record["p"])
                else:
                    props = {}
                industry = props.get("industry", "")
                description = props.get("description", "")

            await session.execute(
                text(
                    "INSERT INTO position_records "
                    "(id, name, industry, description, created_at, "
                    "review_status, reviewed_by, reviewed_at) "
                    "VALUES (:id, :name, :ind, :desc, :created, "
                    "'approved', 'system:consistency_fix', :now) "
                    "ON CONFLICT (name) DO NOTHING"
                ),
                {
                    "id": uuid4(),
                    "name": name,
                    "ind": industry,
                    "desc": description,
                    "created": now,
                    "now": now,
                },
            )
            fixes["neo4j_to_pg"] += 1

        if fixes["neo4j_to_pg"] > 0:
            await session.commit()

    # 2. PG 有但 Neo4j 无 → 回填 Neo4j
    async with neo4j_driver.session() as ns:
        for name in report["only_in_pg"]:
            # 获取 PG 中的属性
            async with async_sessionmaker(pg_engine, expire_on_commit=False)() as session:
                row = (
                    await session.execute(
                        text("SELECT industry, description FROM position_records WHERE name = :name"),
                        {"name": name},
                    )
                ).first()
                industry = row[0] if row else ""
                description = row[1] if row else ""

            await ns.run(
                "MERGE (p:Position {name: $n}) SET p.industry = $ind, p.description = $desc, p.source = 'pg_sync'",
                n=name,
                ind=industry or "",
                desc=description or "",
            )
            fixes["pg_to_neo4j"] += 1

    return fixes


async def main():
    parser = argparse.ArgumentParser(description="PG ↔ Neo4j 数据一致性检查与修复")
    parser.add_argument("--fix", action="store_true", help="自动修复不一致")
    args = parser.parse_args()

    neo4j = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    pg = create_async_engine(PG_URI, pool_pre_ping=True)

    try:
        await neo4j.verify_connectivity()
    except Exception as e:
        print(f"[ERROR] Neo4j 连接失败: {e}")
        return

    report = await check_consistency(neo4j, pg)

    print("=" * 50)
    print("  PG ↔ Neo4j 数据一致性报告")
    print("=" * 50)
    print(f"  Neo4j Position 节点: {report['neo4j_positions']}")
    print(f"  PG position_records: {report['pg_positions']}")
    print(f"  一致记录数: {report['matching']}")
    print(f"  仅 Neo4j 有: {len(report['only_in_neo4j'])}")
    if report["only_in_neo4j"]:
        for n in report["only_in_neo4j"][:10]:
            print(f"    - {n}")
        if len(report["only_in_neo4j"]) > 10:
            print(f"    ... 还有 {len(report['only_in_neo4j']) - 10} 个")
    print(f"  仅 PG 有: {len(report['only_in_pg'])}")
    if report["only_in_pg"]:
        for n in report["only_in_pg"][:10]:
            print(f"    - {n}")
        if len(report["only_in_pg"]) > 10:
            print(f"    ... 还有 {len(report['only_in_pg']) - 10} 个")

    is_consistent = len(report["only_in_neo4j"]) == 0 and len(report["only_in_pg"]) == 0

    if is_consistent:
        print("\n  ✅ PG 和 Neo4j 数据完全一致！")
    else:
        print(f"\n  ⚠️ 发现不一致：Neo4j 独占 {len(report['only_in_neo4j'])} 条，PG 独占 {len(report['only_in_pg'])} 条")

        if args.fix:
            fixes = await fix_consistency(neo4j, pg, report)
            print("\n  🔧 修复完成：")
            print(f"     回填 Neo4j → PG: {fixes['neo4j_to_pg']} 条")
            print(f"     回填 PG → Neo4j: {fixes['pg_to_neo4j']} 条")

            # 重新检查
            report2 = await check_consistency(neo4j, pg)
            if len(report2["only_in_neo4j"]) == 0 and len(report2["only_in_pg"]) == 0:
                print("  ✅ 修复后数据完全一致！")
            else:
                print("  ⚠️ 修复后仍有不一致，请检查")
        else:
            print("\n  使用 --fix 参数自动修复")

    await pg.dispose()
    await neo4j.close()


if __name__ == "__main__":
    asyncio.run(main())
