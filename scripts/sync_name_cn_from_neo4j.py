"""Sync name_cn from Neo4j Position nodes to PostgreSQL position_records.

Run: cd starmap && python scripts/sync_name_cn_from_neo4j.py
"""
from __future__ import annotations

import asyncio
import os

from neo4j import AsyncGraphDatabase
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

PG_URI = os.getenv("POSTGRES_URI", "postgresql+asyncpg://starmap:starmap123456@localhost:5433/starmap")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")


async def main() -> None:
    pg = create_async_engine(PG_URI, pool_pre_ping=True)
    sf = async_sessionmaker(pg, expire_on_commit=False)

    async with AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        await driver.verify_connectivity()

        # Fetch name_cn map from Neo4j
        name_cn_map: dict[str, str] = {}
        async with driver.session() as session:
            result = await session.run("MATCH (p:Position) RETURN p.name AS name, p.name_cn AS name_cn")
            async for record in result:
                name = record["name"]
                name_cn = record["name_cn"]
                if name and name_cn:
                    name_cn_map[name] = name_cn

        print(f"Found {len(name_cn_map)} Position nodes with name_cn in Neo4j")

        # Update PostgreSQL
        updated = 0
        async with sf() as db_session:
            for name, name_cn in name_cn_map.items():
                res = await db_session.execute(
                    text("UPDATE position_records SET name_cn = :name_cn WHERE name = :name AND (name_cn IS NULL OR name_cn = '')"),
                    {"name": name, "name_cn": name_cn},
                )
                if res.rowcount:
                    updated += res.rowcount
            await db_session.commit()

        print(f"Updated {updated} position_records with name_cn")

    await pg.dispose()


if __name__ == "__main__":
    asyncio.run(main())