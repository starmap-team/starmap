#!/bin/sh
# StarMap backend container entrypoint.
# Runs idempotent bootstrap (alembic upgrade + admin seed) once, then execs
# whatever command was supplied (e.g. uvicorn, celery).

set -e

echo "[entrypoint] Starting StarMap backend…"

# D5 fix (2026-08-12): 确保 crawler 同步 DB 驱动存在（crawl-source/管线 crawl 写
# jd_raw 依赖 psycopg）。镜像可能构建于 psycopg 加入 pyproject 之前；此处幂等兜底，
# 已装则跳过，未装则 pip 补装 —— 任意镜像 recreates 后两个按钮都可用。
if python -c "import psycopg" >/dev/null 2>&1; then
    echo "[entrypoint] psycopg already present"
else
    echo "[entrypoint] psycopg missing — installing (crawler sync driver)..."
    pip install --no-cache-dir 'psycopg[binary]>=3.0' >/dev/null 2>&1 && echo "[entrypoint] psycopg installed" || echo "[entrypoint] WARN: psycopg install failed — crawl 端点将不可用"
fi

# Honour BOOTSTRAP_SKIP_DB=true to skip migrate + seed (when DB is managed
# externally or you want a fast dev reload)
if [ "${BOOTSTRAP_SKIP_DB:-false}" = "true" ]; then
    echo "[entrypoint] BOOTSTRAP_SKIP_DB=true — skipping bootstrap.py"
else
    python -m scripts.bootstrap
fi

echo "[entrypoint] bootstrap complete, exec $*"
exec "$@"
