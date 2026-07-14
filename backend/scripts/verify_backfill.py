"""Verify migration 015 backfill."""
import asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine


async def main():
    engine = create_async_engine("postgresql+asyncpg://starmap:starmap123456@localhost:5433/starmap")
    async with engine.begin() as conn:
        r = await conn.execute(sa.text("SELECT review_status, COUNT(*) FROM position_records GROUP BY review_status"))
        print("position_records:", list(r))
        r = await conn.execute(sa.text("SELECT review_status, COUNT(*) FROM skill_records GROUP BY review_status"))
        print("skill_records:", list(r))
        r = await conn.execute(sa.text("SELECT action, COUNT(*) FROM review_audit_log GROUP BY action"))
        print("audit_log:", list(r))
    await engine.dispose()


asyncio.run(main())
