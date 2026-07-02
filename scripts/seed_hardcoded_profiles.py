"""将 match_service 中的8个硬编码岗位画像写入 Neo4j。

运行后，PositionRepository 可以从图谱加载这些画像，
逐步替代硬编码 fallback。

用法：
    python scripts/seed_hardcoded_profiles.py [--neo4j-uri bolt://localhost:7687]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from neo4j import AsyncGraphDatabase

# 从 match_service 导入硬编码画像
from app.services.match_service import POSITION_SKILL_PROFILES


async def seed(uri: str, user: str, password: str) -> dict:
    """将硬编码画像写入 Neo4j。"""
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    stats = {"positions_created": 0, "skills_created": 0, "relationships_created": 0}

    async with driver.session() as session:
        for pos_name, profile in POSITION_SKILL_PROFILES.items():
            # MERGE Position 节点
            await session.run(
                "MERGE (p:Position {name: $name}) "
                "SET p.source = 'hardcoded_seed', p.seeded_at = datetime()",
                name=pos_name,
            )
            stats["positions_created"] += 1

            # 处理 required 和 bonus 技能
            for skill_info in profile.get("required", []):
                skill_name = skill_info["skill"]
                category = skill_info.get("category", "hard_skill")
                proficiency = skill_info.get("proficiency", "熟悉")

                # MERGE Skill 节点
                await session.run(
                    "MERGE (s:Skill {name: $name}) "
                    "ON CREATE SET s.category = $category, s.source_count = 1 "
                    "ON MATCH SET s.source_count = COALESCE(s.source_count, 0) + 1",
                    name=skill_name, category=category,
                )
                stats["skills_created"] += 1

                # MERGE REQUIRES 关系
                await session.run(
                    "MATCH (p:Position {name: $pos_name}) "
                    "MATCH (s:Skill {name: $skill_name}) "
                    "MERGE (p)-[r:REQUIRES]->(s) "
                    "SET r.level = $proficiency, r.required = true, r.source = 'hardcoded_seed'",
                    pos_name=pos_name, skill_name=skill_name, proficiency=proficiency,
                )
                stats["relationships_created"] += 1

            for skill_info in profile.get("bonus", []):
                skill_name = skill_info["skill"]
                category = skill_info.get("category", "hard_skill")
                proficiency = skill_info.get("proficiency", "了解")

                await session.run(
                    "MERGE (s:Skill {name: $name}) "
                    "ON CREATE SET s.category = $category, s.source_count = 1 "
                    "ON MATCH SET s.source_count = COALESCE(s.source_count, 0) + 1",
                    name=skill_name, category=category,
                )
                stats["skills_created"] += 1

                await session.run(
                    "MATCH (p:Position {name: $pos_name}) "
                    "MATCH (s:Skill {name: $skill_name}) "
                    "MERGE (p)-[r:REQUIRES]->(s) "
                    "SET r.level = $proficiency, r.required = false, r.source = 'hardcoded_seed'",
                    pos_name=pos_name, skill_name=skill_name, proficiency=proficiency,
                )
                stats["relationships_created"] += 1

    await driver.close()
    return stats


async def main() -> None:
    parser = argparse.ArgumentParser(description="将硬编码画像写入 Neo4j")
    parser.add_argument("--neo4j-uri", default="bolt://localhost:7687")
    parser.add_argument("--neo4j-user", default="neo4j")
    parser.add_argument("--neo4j-password", default="password")
    parser.add_argument("--dry-run", action="store_true", help="仅打印，不写入")
    args = parser.parse_args()

    print(f"📌 将写入 {len(POSITION_SKILL_PROFILES)} 个岗位画像:")
    for name, profile in POSITION_SKILL_PROFILES.items():
        req = len(profile.get("required", []))
        bon = len(profile.get("bonus", []))
        print(f"  {name}: {req} required + {bon} bonus")

    if args.dry_run:
        print("\n[dry-run] 未写入任何数据")
        return

    print(f"\n🔗 连接 Neo4j: {args.neo4j_uri}")
    stats = await seed(args.neo4j_uri, args.neo4j_user, args.neo4j_password)

    print(f"\n✅ 完成:")
    print(f"  岗位节点: {stats['positions_created']}")
    print(f"  技能节点: {stats['skills_created']}")
    print(f"  REQUIRES 关系: {stats['relationships_created']}")


if __name__ == "__main__":
    asyncio.run(main())
