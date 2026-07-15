"""Seed the initial admin user into the users table.

Usage:
    python -m scripts.seed_admin --username admin --password <strong-password>
    python -m scripts.seed_admin                          # defaults: admin / starmap2024

This script is idempotent: if the username already exists, it skips insertion.
Run this once after deploying the database migration (011_add_users_table).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import bcrypt
import sqlalchemy as sa
from loguru import logger


def _build_db_url() -> str:
    """Build PostgreSQL async URL from app settings (loads .env via pydantic-settings)."""
    from app.config import settings

    uri = settings.postgres_uri
    if uri:
        return uri.replace("postgresql://", "postgresql+asyncpg://", 1)
    # Fallback: should not happen since Settings resolves postgres_uri in model_validator
    return (
        f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )


async def seed_admin(username: str, password: str) -> None:
    """Insert admin user if not already present."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    db_url = _build_db_url()
    engine = create_async_engine(db_url)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async with sessionmaker() as session:
        # Check if user already exists
        result = await session.execute(
            sa.text("SELECT id FROM users WHERE username = :username"),
            {"username": username},
        )
        if result.scalar_one_or_none() is not None:
            logger.info("User '{}' already exists — skipping seed", username)
            await engine.dispose()
            return

        # Hash password with bcrypt
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

        # Insert admin user (id uses PostgreSQL gen_random_uuid)
        await session.execute(
            sa.text(
                "INSERT INTO users (id, username, password_hash, role, is_active) "
                "VALUES (gen_random_uuid(), :username, :password_hash, 'admin', true)"
            ),
            {"username": username, "password_hash": password_hash},
        )
        await session.commit()
        logger.info("Admin user '{}' seeded successfully", username)

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed initial admin user")
    parser.add_argument("--username", default="admin", help="Admin username (default: admin)")
    parser.add_argument("--password", default="starmap2024", help="Admin password (default: starmap2024)")
    args = parser.parse_args()

    if len(args.password) < 8:
        logger.error("Password must be at least 8 characters")
        sys.exit(1)

    asyncio.run(seed_admin(args.username, args.password))


if __name__ == "__main__":
    main()
