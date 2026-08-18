import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from loguru import logger
from neo4j import AsyncGraphDatabase
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


async def main():
    # SY-01 fix: use env vars instead of hardcoded credentials
    pg_uri = os.getenv("POSTGRES_URI", "postgresql+asyncpg://starmap:starmap123456@localhost:5433/starmap")
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "")

    pg = create_async_engine(pg_uri, pool_pre_ping=True)
    sf = async_sessionmaker(pg, expire_on_commit=False)
    async with AsyncGraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password)) as driver:
        await driver.verify_connectivity()
        async with sf() as session:
            rows = (await session.execute(text("SELECT job_title, extracted_skills FROM jd_extraction_records"))).fetchall()
        written = 0
        json_errors = 0
        async with driver.session() as ns:
            for row in rows:
                pos = row[0]
                # SY-02 fix: handle malformed JSON gracefully
                try:
                    skills = json.loads(row[1]) if isinstance(row[1], str) else (row[1] or [])
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Skipping bad JSON for position '{pos}': {e}")
                    json_errors += 1
                    continue
                await ns.run("MERGE (p:Position {name: $n}) SET p.source='seed'", n=pos)
                for sk in skills:
                    name = sk.get("skill", "")
                    typ = sk.get("type", "required")
                    prof = sk.get("proficiency", "熟悉")
                    await ns.run("MERGE (s:Skill {name: $n}) SET s.proficiency=$p", n=name, p=prof)
                    await ns.run("MATCH (p:Position {name:$pos}) MATCH (s:Skill {name:$sk}) MERGE (p)-[r:REQUIRES]->(s) SET r.required=$req, r.weight=$w", pos=pos, sk=name, req=(typ=="required"), w=1.0 if typ=="required" else 0.5)
                    written += 1
            res = await ns.run("MATCH (n) RETURN labels(n)[0] AS l, count(n) AS c")
            counts = {}
            async for r in res: counts[r["l"]] = r["c"]
            res = await ns.run("MATCH ()-[r]->() RETURN count(r) AS c")
            rels = (await res.single())["c"]
        print(f"Triples: {written}, Nodes: {counts}, Rels: {rels}, JSON errors: {json_errors}")
    await pg.dispose()

if __name__ == "__main__":
    asyncio.run(main())