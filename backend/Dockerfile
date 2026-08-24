# =============================================================================
# 星图(StarMap) 后端 生产镜像 — 2c4G 适配版（单容器跑 uvicorn + celery）
# 多阶段构建：依赖安装 → 应用打包
#
# NOTE (2c4G-2026-08-21):
#   2c4G 阿里云适配：取消独立 celery-worker 容器，
#   在同一镜像内用 supervisord 拉起 uvicorn (1 worker) + celery worker (1 concurrency)。
#   节省一个容器的运行时开销（~150-250 MB）。
#
# NOTE (NEW-P0 fix, AUDIT_VERIFICATION §1.4 C7):
#   The previous build had `ARG ENVIRONMENT=production` (passed by
#   docker-compose.prod.yml) but never set `ENV APP_ENV=$ENVIRONMENT`,
#   so the runtime always fell back to config.py's default
#   `app_env: str = "development"`. We removed that dead ARG in favour of
#   loading the production env via `env_file: .env.production` in compose.
#   This keeps the single source of truth in Pydantic Settings.
# =============================================================================

# ── 阶段 1：依赖安装 ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Poetry（版本锁定）
RUN pip install --no-cache-dir poetry==2.4.1

# 配置 Poetry：不创建虚拟环境，缓存到临时目录
ENV POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

# 先拷依赖文件，利用 Docker 层缓存
COPY backend/pyproject.toml backend/poetry.lock* ./
RUN poetry install --no-root --only main && rm -rf $POETRY_CACHE_DIR

# ── 阶段 2：生产镜像 ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS production

# 2c4G 适配：装 supervisord 让单容器同时跑 uvicorn + celery
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl supervisor \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 从 builder 复制已安装的 Python 包
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用源码 (context=仓库根)
COPY backend/app/ ./app/
COPY backend/alembic/ ./alembic/
COPY backend/alembic.ini ./
COPY backend/scripts/ ./scripts/
COPY backend/entrypoint.sh ./
# Phase 15-02: CSV 导入端点需要 crawler.persistence.dao.upsert_jd
COPY crawler/ ./crawler/

# 2c4G 适配：supervisord 配置（uvicorn + celery worker）
COPY backend/deploy/supervisord.conf /etc/supervisor/conf.d/starmap.conf

# 创建非 root 用户运行应用
RUN useradd -m -s /bin/bash starmap && \
    mkdir -p /var/log/supervisor && \
    chown -R starmap:starmap /app /var/log/supervisor && \
    chmod +x entrypoint.sh
USER starmap

EXPOSE 8000

# Bootstrap runs alembic upgrade + admin seed; docker-compose overrides CMD.
ENTRYPOINT ["./entrypoint.sh"]
# 2c4G 默认：supervisord 拉起 uvicorn + celery（可被 docker-compose 覆盖）
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/starmap.conf"]
