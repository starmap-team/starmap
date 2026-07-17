"""Use SQLAlchemy (as the app does) to confirm tables exist."""
import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from app.config import settings
from app.db.session import get_async_engine
from sqlalchemy import text


async def main():
    engine = get_async_engine()
    async with engine.begin() as conn:
        rows = await conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        ))
        tables = [r[0] for r in rows]
        print("Tables via SQLAlchemy:", tables)
        try:
            cnt = await conn.execute(text("SELECT COUNT(*) FROM users"))
            print("users count:", cnt.scalar())
        except Exception as e:
            print(f"users query failed: {type(e).__name__}: {e}")
    await engine.dispose()


asyncio.run(main())