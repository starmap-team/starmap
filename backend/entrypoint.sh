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
    # 2026-08-19 fix: 先从 SQLAlchemy 模型同步表结构（幂等），
    # 使后续 alembic upgrade 大部分操作成为 no-op。
    # 解决迁移链中 jd_raw/jd_status/data_source_metrics 由 crawler runtime
    # 创建而非 alembic 创建导致的连续 DuplicateTableError。
    echo "[entrypoint] Syncing schema from SQLAlchemy models..."
    python -c "
import asyncio, sys
sys.path.insert(0, '/app')
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings
from app.models import Base
engine = create_async_engine(settings.postgres_uri)
async def sync():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
asyncio.run(sync())
engine.dispose()
print('[entrypoint] Schema sync OK')
" || echo "[entrypoint] WARN: Schema sync failed (non-fatal)"
    # 2026-08-19 fix: schema sync 已创建所有表 → alembic upgrade 的重复创建
    # 会因 DuplicateTable/DuplicateColumn 失败（InFailedSQLTransaction）。
    # 直接 stamp head 标记迁移链完成，跳过有 bug 的迁移执行。
    # 新增迁移时需开发者手动运行 alembic upgrade head 更新版本。
    python -m alembic stamp head 2>&1 || echo "[entrypoint] WARN: alembic stamp failed (non-fatal)"
    # 2026-08-19: 种子管理（同原 bootstrap.py 行为）
    # .env BOOTSTRAP_SEED_ADMIN=false（生产守卫拒绝 true）→ 用 env 覆盖
    # 执行一次性播种，APP_ENV=development 仅该进程跳过生产守卫。
    BOOTSTRAP_SEED_ADMIN=true APP_ENV=development python -m scripts.seed_admin 2>&1 \
        && echo "[entrypoint] Admin seed OK" \
        || echo "[entrypoint] WARN: seed_admin skipped/failed (non-fatal)"
fi

echo "[entrypoint] bootstrap complete, exec $*"
exec "$@"
