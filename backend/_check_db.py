"""Check tables and users count."""
import asyncio

import asyncpg


async def main():
    conn = await asyncpg.connect(
        host="localhost",
        port=5433,
        user="starmap",
        password="starmap123456",
        database="starmap",
    )
    tables = [
        r["tablename"]
        for r in await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        )
    ]
    print("Tables:", tables)
    try:
        users_count = await conn.fetchval("SELECT COUNT(*) FROM users")
        print("users count:", users_count)
    except Exception as e:
        print(f"users query failed: {e}")
    await conn.close()


asyncio.run(main())
