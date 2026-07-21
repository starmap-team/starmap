"""回填 PostgreSQL position_records / skill_records / position_skill_relations

从 Neo4j 读取所有 Position 节点及关联 Skill，对 PG 中不存在的记录以
review_status='approved' 回填，确保双存储数据一致性。

用法:
  cd starmap
  python scripts/backfill_pg_from_neo4j.py [--dry-run] [--include-skills]

设计意图（Phase 23 审核工作流）:
- Neo4j 中已公开可见的 Position 默认推定为 approved
- 回填记录的 reviewed_by 标记为 'system:backfill' 以便审计
- skill_records 按 name 去重，source_count 取 Neo4j 中出现的次数
"""
from __future__ import annotations

import asyncio
import argparse
import os
from datetime import datetime, timezone
from uuid import uuid4

from loguru import logger
from neo4j import AsyncGraphDatabase
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# ── 数据库连接配置 ──
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "starmap123456")
PG_URI = os.getenv("POSTGRES_URI", "postgresql+asyncpg://starmap:starmap123456@localhost:5433/starmap")


async def fetch_neo4j_positions(driver) -> list[dict]:
    """从 Neo4j 拉取所有 Position 节点及其关联 Skill。"""
    query = """
        MATCH (p:Position)
        OPTIONAL MATCH (p)-[r:REQUIRES]->(s:Skill)
        RETURN p, collect(DISTINCT s) AS skills
    """
    results: list[dict] = []
    async with driver.session() as session:
        async for record in await session.run(query):
            p_node = record["p"]
            if p_node is None:
                continue
            p_props = dict(p_node)
            skills_raw = record["skills"] or []
            skills = []
            for s in skills_raw:
                if s is None:
                    continue
                s_props = dict(s)
                skills.append({
                    "name": s_props.get("name", ""),
                    "category": s_props.get("category", "hard_skill"),
                })
            results.append({
                "name": p_props.get("name", ""),
                "name_cn": p_props.get("name_cn", ""),
                "industry": p_props.get("industry", ""),
                "description": p_props.get("description", ""),
                "skills": skills,
            })
    return results


async def backfill(
    neo4j_driver,
    pg_engine,
    *,
    dry_run: bool = False,
    include_skills: bool = False,
) -> dict:
    """主回填逻辑。返回统计摘要。"""
    now = datetime.now(timezone.utc)
    stats = {
        "neo4j_positions": 0,
        "pg_existing": 0,
        "positions_inserted": 0,
        "skills_inserted": 0,
        "relations_inserted": 0,
    }

    # 1. 从 Neo4j 拉取数据
    neo4j_data = await fetch_neo4j_positions(neo4j_driver)
    stats["neo4j_positions"] = len(neo4j_data)
    logger.info(f"从 Neo4j 读取到 {len(neo4j_data)} 个 Position 节点")

    neo4j_names = {p["name"] for p in neo4j_data}

    # 2. 查询 PG 中已有的 position
    async with async_sessionmaker(pg_engine, expire_on_commit=False)() as session:
        existing_rows = (
            await session.execute(
                text("SELECT name FROM position_records WHERE name = ANY(:names)"),
                {"names": list(neo4j_names)},
            )
        ).scalars().all()
        existing_names = set(existing_rows)
        stats["pg_existing"] = len(existing_names)
        logger.info(f"PG 中已有 {len(existing_names)} 条匹配的 position_records")

        # 3. 回填缺失的 position_records
        to_insert = [p for p in neo4j_data if p["name"] not in existing_names]
        if to_insert:
            for p in to_insert:
                pid = uuid4()
                await session.execute(
                    text(
                        "INSERT INTO position_records "
                        "(id, name, industry, description, created_at, "
                        "review_status, reviewed_by, reviewed_at) "
                        "VALUES (:id, :name, :ind, :desc, :created, "
                        ":status, :reviewed_by, :reviewed_at) "
                        "ON CONFLICT (name) DO NOTHING"
                    ),
                    {
                        "id": pid,
                        "name": p["name"],
                        "ind": p["industry"] or "",
                        "desc": p["description"] or "",
                        "created": now,
                        "status": "approved",
                        "reviewed_by": "system:backfill",
                        "reviewed_at": now,
                    },
                )
                p["_pg_id"] = pid
            stats["positions_inserted"] = len(to_insert)
            logger.info(f"回填 {len(to_insert)} 条 position_records")

            if not dry_run:
                await session.commit()
        else:
            logger.info("position_records 已完全一致，无需回填")

        # 4. 回填技能关系（可选）
        if include_skills:
            stats.update(await _backfill_skills(session, neo4j_data, existing_names, now, dry_run))

    return stats


async def _backfill_skills(session, neo4j_data, existing_names, now, dry_run) -> dict:
    """回填 skill_records 和 position_skill_relations。"""
    stats = {"skills_inserted": 0, "relations_inserted": 0}

    # 收集所有技能名 → 去重
    all_skills: dict[str, dict] = {}
    for p in neo4j_data:
        for sk in p.get("skills", []):
            name = sk["name"]
            if name:
                all_skills[name] = sk

    # 查询已存在的技能
    if all_skills:
        existing_skill_rows = (
            await session.execute(
                text("SELECT name FROM skill_records WHERE name = ANY(:names)"),
                {"names": list(all_skills.keys())},
            )
        ).scalars().all()
        existing_skill_names = set(existing_skill_rows)
    else:
        existing_skill_names = set()

    # 插入新技能
    new_skills = {n: s for n, s in all_skills.items() if n not in existing_skill_names}
    for name, sk in new_skills.items():
        await session.execute(
            text(
                "INSERT INTO skill_records (id, name, category, review_status, reviewed_by, reviewed_at) "
                "VALUES (:id, :name, :cat, 'approved', 'system:backfill', :now) "
                "ON CONFLICT (name) DO NOTHING"
            ),
            {"id": uuid4(), "name": name, "cat": sk["category"], "now": now},
        )
    stats["skills_inserted"] = len(new_skills)
    logger.info(f"回填 {len(new_skills)} 条 skill_records")

    # 获取所有 position_id（包括已存在的）
    pos_name_to_id = {}
    rows = (await session.execute(text("SELECT id, name FROM position_records"))).fetchall()
    for row in rows:
        pos_name_to_id[row[1]] = row[0]

    # 获取所有 skill_id
    skill_name_to_id = {}
    rows = (await session.execute(text("SELECT id, name FROM skill_records"))).fetchall()
    for row in rows:
        skill_name_to_id[row[1]] = row[0]

    # 查询已有关系
    existing_rels = set()
    rel_rows = (
        await session.execute(
            text(
                "SELECT pr.name, sr.name FROM position_skill_relations psr "
                "JOIN position_records pr ON pr.id = psr.position_id "
                "JOIN skill_records sr ON sr.id = psr.skill_id"
            )
        )
    ).fetchall()
    for row in rel_rows:
        existing_rels.add((row[0], row[1]))

    # 插入缺失的关系
    rels_to_insert = 0
    for p in neo4j_data:
        pos_id = pos_name_to_id.get(p["name"])
        if not pos_id:
            continue
        for sk in p.get("skills", []):
            sk_name = sk["name"]
            sk_id = skill_name_to_id.get(sk_name)
            if not sk_id:
                continue
            if (p["name"], sk_name) in existing_rels:
                continue
            await session.execute(
                text(
                    "INSERT INTO position_skill_relations "
                    "(id, position_id, skill_id, requirement_type, confidence) "
                    "VALUES (:id, :pid, :sid, 'required', 1.0) "
                    "ON CONFLICT DO NOTHING"
                ),
                {"id": uuid4(), "pid": pos_id, "sid": sk_id},
            )
            rels_to_insert += 1
            existing_rels.add((p["name"], sk_name))
    stats["relations_inserted"] = rels_to_insert
    logger.info(f"回填 {rels_to_insert} 条 position_skill_relations")

    if not dry_run:
        await session.commit()

    return stats


async def main():
    parser = argparse.ArgumentParser(description="回填 Neo4j Position → PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", help="只检查，不实际写入")
    parser.add_argument("--include-skills", action="store_true", help="同时回填技能和关系")
    args = parser.parse_args()

    neo4j = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    pg = create_async_engine(PG_URI, pool_pre_ping=True)

    try:
        await neo4j.verify_connectivity()
        logger.info("Neo4j 连接成功")
    except Exception as e:
        logger.error(f"Neo4j 连接失败: {e}")
        return

    try:
        stats = await backfill(neo4j, pg, dry_run=args.dry_run, include_skills=args.include_skills)
        print("\n=== 回填摘要 ===")
        for k, v in stats.items():
            print(f"  {k}: {v}")

        if args.dry_run:
            print("\n[Dry run] 未实际写入，去掉 --dry-run 以执行写入。")
        else:
            print("\n回填完成。")

        # 验证最终状态
        async with async_sessionmaker(pg, expire_on_commit=False)() as session:
            total_pg = (await session.execute(text("SELECT count(*) FROM position_records"))).scalar()
            approved = (
                await session.execute(
                    text("SELECT count(*) FROM position_records WHERE review_status = 'approved'")
                )
            ).scalar()
            print(f"\n=== PG 最终状态 ===")
            print(f"  position_records 总数: {total_pg}")
            print(f"  其中 approved: {approved}")

    finally:
        await pg.dispose()
        await neo4j.close()


if __name__ == "__main__":
    asyncio.run(main())
