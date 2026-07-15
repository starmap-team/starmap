"""One-shot, idempotent container bootstrap.

Runs in order:
1. `alembic upgrade head` — apply pending migrations (idempotent)
2. Idempotent Neo4j schema initialiser (constraints + indexes)
3. Seed initial admin user IF `BOOTSTRAP_SEED_ADMIN=true` (default: false)

Intended to run from `entrypoint.sh` before uvicorn/celery start, OR
manually with `python -m scripts.bootstrap`. Each step is safe to re-run.
"""
from __future__ import annotations

import asyncio
import sys
import traceback
from pathlib import Path

from loguru import logger

# Ensure `app.*` import works when run as `python -m scripts.bootstrap`
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _step_alembic() -> None:
    """Apply Alembic migrations to head (idempotent)."""
    from alembic.config import Config

    from alembic import command

    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    logger.info("[bootstrap] Running alembic upgrade head")
    command.upgrade(cfg, "head")
    logger.info("[bootstrap] ✓ alembic at head")


async def _step_neo4j_schema_async() -> None:
    """Async variant of _step_neo4j_schema — shares the same event loop
    as the seed step (so we don't double-bind loop-policy)."""
    try:
        try:
            from app.core.graph_engine.schema_bootstrap import ensure_constraints
        except ImportError:
            return

        from app.services.resources import init_resources, resources

        if resources.neo4j_driver is None:
            resources_new = await init_resources()
            if resources_new.neo4j_driver is None:
                logger.warning("[bootstrap] Neo4j driver unavailable after init — skipping")
                return

        driver = resources.neo4j_driver
        async with driver.session() as session:
            await ensure_constraints(session)
        logger.info("[bootstrap] ✓ Neo4j constraints ensured")
    except Exception as exc:
        logger.warning(f"[bootstrap] Neo4j schema bootstrap failed (non-fatal): {exc}")


async def _step_seed_admin() -> None:
    """If BOOTSTRAP_SEED_ADMIN=true, ensure an admin user exists.

    Idempotent: looks up by username; if present, does nothing.
    """
    from app.config import settings
    from app.services.auth_service import UsernameTakenError, create_user

    if not settings.bootstrap_seed_admin:
        logger.info(
            "[bootstrap] BOOTSTRAP_SEED_ADMIN is false — skipping admin seed"
        )
        return

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    db_url = settings.postgres_uri
    if db_url and not db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if not db_url:
        logger.error("[bootstrap] POSTGRES_URI not configured — cannot seed admin")
        return

    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            await create_user(
                username=settings.bootstrap_admin_username,
                password=settings.bootstrap_admin_password,
                role="admin",
                session=session,
                actor="bootstrap",
            )
        logger.info(
            "[bootstrap] ✓ admin user '{}' is present",
            settings.bootstrap_admin_username,
        )
    except UsernameTakenError:
        logger.info(
            "[bootstrap] admin user '{}' already exists — skipping",
            settings.bootstrap_admin_username,
        )
    except Exception as exc:
        logger.error(f"[bootstrap] admin seed failed: {exc}")
        traceback.print_exc()
        raise
    finally:
        await engine.dispose()


def main() -> int:
    """Run all bootstrap steps in order. Returns process exit code."""
    logger.info("=== StarMap bootstrap starting ===")
    try:
        _step_alembic()
    except Exception as exc:
        logger.error(f"[bootstrap] alembic step failed: {exc}")
        traceback.print_exc()
        return 1

    async def _post_alembic_steps():
        await _step_neo4j_schema_async()
        await _step_seed_admin()

    try:
        asyncio.run(_post_alembic_steps())
    except Exception as exc:
        logger.error(f"[bootstrap] post-alembic steps failed: {exc}")
        traceback.print_exc()
        return 1

    logger.info("=== StarMap bootstrap complete ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
