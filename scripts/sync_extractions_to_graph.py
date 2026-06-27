import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from neo4j import AsyncGraphDatabase

async def main():
    pg = create_async_engine("postgresql+asyncpg://starmap:starmap123456@postgres:5432/starmap", pool_pre_ping=True)
    sf = async_sessionmaker(pg, expire_on_commit=False)
    async with AsyncGraphDatabase.driver("bolt://neo4j:7687", auth=("neo4j", "starmap123456")) as driver:
        await driver.verify_connectivity()
        async with sf() as session:
            rows = (await session.execute(text("SELECT job_title, extracted_skills FROM jd_extraction_records"))).fetchall()
        written = 0
        async with driver.session() as ns:
            for row in rows:
                pos = row[0]
                skills = json.loads(row[1]) if isinstance(row[1], str) else row[1]
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
        print(f"Triples: {written}, Nodes: {counts}, Rels: {rels}")
    await pg.dispose()

if __name__ == "__main__":
    asyncio.run(main())