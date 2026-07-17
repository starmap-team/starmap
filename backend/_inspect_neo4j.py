"""Check both Neo4j containers and identify which one the backend connects to."""
import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from app.config import settings
from neo4j import AsyncGraphDatabase


async def count_in(driver, label: str) -> int:
    async with driver.session() as s:
        result = await s.run(f"MATCH (n:{label}) RETURN count(n) AS cnt")
        rec = await result.single()
        return rec["cnt"]


async def main():
    print(f"settings.neo4j_uri = {settings.neo4j_uri}")
    print(f"settings.neo4j_user = {settings.neo4j_user}")
    print(f"settings.neo4j_password length = {len(settings.neo4j_password or '')}")

    # 1) Backend's neo4j driver
    print("\n--- via settings (what backend uses) ---")
    drv = AsyncGraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )
    try:
        for label in ["Position", "Skill", "Tool", "KnowledgeArea", "Industry"]:
            cnt = await count_in(drv, label)
            print(f"  {label}: {cnt}")
        async with drv.session() as s:
            rel = await s.run("MATCH ()-[r]-() RETURN count(r) AS cnt")
            rec = await rel.single()
            print(f"  Relationships: {rec['cnt']}")
    finally:
        await drv.close()

    # 2) Direct probe of host-port 7687
    print("\n--- direct probe bolt://localhost:7687 ---")
    drv2 = AsyncGraphDatabase.driver(
        "bolt://localhost:7687", auth=(settings.neo4j_user, settings.neo4j_password)
    )
    try:
        for label in ["Position", "Skill"]:
            cnt = await count_in(drv2, label)
            print(f"  {label}: {cnt}")
    except Exception as e:
        print(f"  FAIL: {e}")
    finally:
        await drv2.close()


asyncio.run(main())