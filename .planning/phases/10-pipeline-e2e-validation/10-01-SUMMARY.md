---
plan: 10-01
phase: 10-pipeline-e2e-validation
completed_at: 2026-07-10
status: complete
---

# 10-01 Summary: Playwright 官方镜像 + Celery Worker 容器化

## Goal
(D-01) 用 `mcr.microsoft.com/playwright/python:v1.49.0-jammy` 作为 celery-worker 容器 base image，替代当前 `python:3.11-slim` 自装 Chromium 的不可复现路径。

## Tasks Completed

### T1 — 新建 celery worker Dockerfile (基于 Playwright 官方镜像) ✅
- `backend/Dockerfile.celery` — FROM 官方 Playwright v1.49.0-jammy 镜像，apt-get install psycopg build deps，poetry install, COPY crawler/, CMD celery worker
- 不修改 `backend/Dockerfile.dev`（main API 仍用它）

### T2 — docker-compose.dev.yml 切换 celery-worker 服务 ✅
- `celery-worker.build.dockerfile: Dockerfile.dev` → `Dockerfile.celery`
- 保留 volumes / env_file / depends_on / command 字段不变

### T3 — .env.example 补全 PIPELINE_BOOTSTRAP ✅
- `PROXY_LIST=` 已有（Phase 8 D-07 留）
- 追加 `PIPELINE_BOOTSTRAP=false` + 解释性注释

### T4 — 验证 Docker 静态解析 ✅
- `python -c "import yaml; ..."` 静态校验 `docker-compose.dev.yml` 通过
- celery-worker.build → `{'context': './backend', 'dockerfile': 'Dockerfile.celery'}`

## Commit

- `187d0d7` — feat(10-01): switch celery-worker to Playwright official Python image

## Acceptance verification

- `cat backend/Dockerfile.celery | head -3` → FROM 官方 Playwright 镜像 ✅
- `grep -q "playwright/python:v1.49.0-jammy" backend/Dockerfile.celery` exit 0 ✅
- `grep -q "dockerfile: Dockerfile.celery" docker-compose.dev.yml` exit 0 ✅
- `grep -q "^PIPELINE_BOOTSTRAP=false" .env.example` exit 0 ✅
- `grep -q "^PROXY_LIST=" .env.example` exit 0 ✅

## must_haves verification

- ✅ celery-worker 容器使用 Playwright 官方镜像作为 base (D-01)
- ✅ 镜像构建期不联网下载 Chromium (Chromium 已在官方镜像内)
- ✅ docker-compose.dev.yml 正确指向 Dockerfile.celery
- ✅ PIPELINE_BOOTSTRAP 与 PROXY_LIST 字段均在 .env.example 可见

## Artifacts this phase produces

- `backend/Dockerfile.celery` (new)
- `docker-compose.dev.yml` (modified: celery-worker build context)
- `.env.example` (modified: PIPELINE_BOOTSTRAP field)
