"""Quick script to test backend service connectivity."""
import asyncio

from neo4j import AsyncGraphDatabase


async def test_neo4j():
    try:
        d = AsyncGraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "starmap123456"))
        async with d.session() as s:
            result = await s.run("RETURN 1 AS ok")
            rec = await result.single()
            print("Neo4j OK:", dict(rec))
        await d.close()
    except Exception as e:
        print(f"Neo4j FAILED: {type(e).__name__}: {e}")

async def test_redis():
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url("redis://localhost:6379/0", decode_responses=True)
        await r.ping()
        print("Redis OK")
        await r.aclose()
    except Exception as e:
        print(f"Redis FAILED: {type(e).__name__}: {e}")

async def test_postgres():
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        engine = create_async_engine("postgresql+asyncpg://starmap:starmap123456@localhost:5433/starmap")
        async with engine.begin() as conn:
            await conn.exec_driver_sql("SELECT 1")
        print("Postgres OK")
        await engine.dispose()
    except Exception as e:
        print(f"Postgres FAILED: {type(e).__name__}: {e}")

async def main():
    await test_neo4j()
    await test_redis()
    await test_postgres()

asyncio.run(main())
