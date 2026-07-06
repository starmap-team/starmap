"""Seed position profiles into Neo4j from the graph data pipeline.

This script was originally used to write 8 hardcoded position profiles
from match_service.POSITION_SKILL_PROFILES into Neo4j. Since the refactoring
to a fully graph-driven architecture, POSITION_SKILL_PROFILES has been removed.

This script now serves as a utility to verify that position profiles
exist in Neo4j and can be loaded by the match service.

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


async def verify(uri: str, user: str, password: str) -> dict:
    """Verify that position profiles exist in Neo4j and can be loaded."""
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    stats: dict[str, int | list[str]] = {
        "positions_found": 0,
        "positions_with_skills": 0,
        "total_skills": 0,
        "position_names": [],
    }

    async with driver.session() as session:
        # Count positions
        result = await session.run("MATCH (p:Position) RETURN p.name AS name")
        async for record in result:
            stats["positions_found"] += 1
            name = record["name"]
            if name:
                stats["position_names"].append(name)  # type: ignore[union-attr]

        # Count positions with at least one REQUIRES relationship
        skill_result = await session.run(
            "MATCH (p:Position)-[:REQUIRES]->(s:Skill) "
            "RETURN p.name AS pos_name, count(s) AS skill_count"
        )
        async for record in skill_result:
            if record["skill_count"] > 0:
                stats["positions_with_skills"] += 1
                stats["total_skills"] += record["skill_count"]  # type: ignore[union-attr]

    await driver.close()
    return stats


async def main() -> None:
    parser = argparse.ArgumentParser(description="Verify position profiles in Neo4j")
    parser.add_argument("--neo4j-uri", default="bolt://localhost:7687")
    parser.add_argument("--neo4j-user", default="neo4j")
    parser.add_argument("--neo4j-password", default="password")
    args = parser.parse_args()

    print(f"🔗 连接 Neo4j: {args.neo4j_uri}")
    stats = await verify(args.neo4j_uri, args.neo4j_user, args.neo4j_password)

    print("\n✅ Neo4j 图谱状态:")
    print(f"  岗位节点: {stats['positions_found']}")
    print(f"  有技能要求的岗位: {stats['positions_with_skills']}")
    print(f"  总技能关联: {stats['total_skills']}")
    if stats["position_names"]:
        print("\n📋 岗位列表:")
        for name in sorted(stats["position_names"]):  # type: ignore[union-attr]
            print(f"  - {name}")


if __name__ == "__main__":
    asyncio.run(main())
