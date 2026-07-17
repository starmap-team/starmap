"""Run alembic with explicit URL, bypassing the buggy app.config URI builder."""
import os
import sys
from pathlib import Path

# Build URL manually (no sslmode / ssl - localhost dev)
HOST = os.environ.get("POSTGRES_HOST", "localhost")
PORT = os.environ.get("POSTGRES_PORT", "5433")
USER = os.environ.get("POSTGRES_USER", "starmap")
PASSWORD = os.environ.get("POSTGRES_PASSWORD", "starmap123456")
DB = os.environ.get("POSTGRES_DB", "starmap")
URL = f"postgresql+asyncpg://{USER}:{PASSWORD}@{HOST}:{PORT}/{DB}"

# Backend path setup
BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from alembic.config import Config

from alembic import command

cfg = Config(str(BACKEND / "alembic.ini"))
cfg.set_main_option("script_location", str(BACKEND / "alembic"))
cfg.set_main_option("sqlalchemy.url", URL)

print(f"[run_migration] URL={URL}")
try:
    command.upgrade(cfg, "head")
    print("[run_migration] DONE")
except Exception as e:
    print(f"[run_migration] FAILED: {type(e).__name__}: {e}")
    sys.exit(1)
