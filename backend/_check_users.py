"""Check existing users."""
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
    rows = await conn.fetch(
        "SELECT username, role, is_active, email, password_changed_at FROM users ORDER BY created_at"
    )
    for r in rows:
        print(dict(r))
    await conn.close()


asyncio.run(main())
