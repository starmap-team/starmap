#!/bin/sh
# StarMap backend container entrypoint.
# Runs idempotent bootstrap (alembic upgrade + admin seed) once, then execs
# whatever command was supplied (e.g. uvicorn, celery).

set -e

echo "[entrypoint] Starting StarMap backend…"

# Honour BOOTSTRAP_SKIP_DB=true to skip migrate + seed (when DB is managed
# externally or you want a fast dev reload)
if [ "${BOOTSTRAP_SKIP_DB:-false}" = "true" ]; then
    echo "[entrypoint] BOOTSTRAP_SKIP_DB=true — skipping bootstrap.py"
else
    python -m scripts.bootstrap
fi

echo "[entrypoint] bootstrap complete, exec $*"
exec "$@"
