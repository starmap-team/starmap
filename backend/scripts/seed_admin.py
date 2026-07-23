"""Seed initial admin user into the users table.

Referenced by scripts/bootstrap.py. Idempotent: does nothing if an admin already
exists with the configured username. Uses settings.bootstrap_admin_username
and settings.bootstrap_admin_password (read from .env via pydantic-settings).
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Make `app.*` importable when run as `python -m scripts.seed_admin`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import get_session_factory  # noqa: E402
from app.models.user import ROLE_ADMIN, User  # noqa: E402
from app.services.auth_service import create_user  # noqa: E402

log = logging.getLogger("seed_admin")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


async def seed_admin() -> None:
    """Create the initial admin if no admin with this username exists."""
    if not settings.bootstrap_seed_admin:
        log.info("bootstrap_seed_admin=false, skipping")
        return

    session_factory = get_session_factory()
    async with session_factory() as session:
        existing = await session.execute(
            select(User).where(User.username == settings.bootstrap_admin_username)
        )
        if existing.scalar_one_or_none() is not None:
            log.info("admin user '%s' already exists, skipping",
                     settings.bootstrap_admin_username)
            return

        log.info("creating admin user '%s'", settings.bootstrap_admin_username)
        try:
            user = await create_user(
                username=settings.bootstrap_admin_username,
                password=settings.bootstrap_admin_password,
                role=ROLE_ADMIN,
                session=session,
                actor="seed_admin",
            )
            user.must_change_password = True
            await session.commit()
            log.info("admin user '%s' created (id=%s, role=%s, must_change_password=true)",
                     user.username, user.id, user.role)
        except Exception as e:  # noqa: BLE001
            log.error("failed to create admin user: %s", e)
            raise


def main() -> int:
    try:
        asyncio.run(seed_admin())
    except Exception as e:  # noqa: BLE001
        log.error("seed_admin failed: %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
