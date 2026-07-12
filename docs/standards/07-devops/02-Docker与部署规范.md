# Docker 与部署规范文档

## 1. 模块概述

### 职责定位
Docker 与部署模块负责 StarMap 全栈服务的容器化封装、环境编排和生产部署。通过 Docker Compose 管理多服务依赖（后端/前端/Neo4j/PostgreSQL/Redis/Chroma/Ollama），实现开发-生产环境一致性。

### 核心目标
1. **环境一致性**：开发、测试、生产使用相同的容器镜像和编排配置
2. **一键启动**：`docker compose -f docker-compose.dev.yml up -d` 启动全栈
3. **热重载开发**：开发模式支持代码挂载和热重载
4. **生产优化**：多阶段构建、资源限制、健康检查
5. **本地 LLM**：Ollama 容器化提供离线 LLM 能力

### 在系统中的位置
```
┌─────────────────────────────────────────┐
│         Docker 与部署模块               │
├─────────────────────────────────────────┤
│  docker-compose.dev.yml    开发全栈编排 │
│  docker-compose.prod.yml   生产全栈编排 │
│  backend/Dockerfile        后端生产镜像 │
│  backend/Dockerfile.dev    后端开发镜像 │
│  backend/Dockerfile.celery Celery Worker│
│  frontend/Dockerfile       前端生产镜像 │
│  frontend/Dockerfile.dev   前端开发镜像 │
└─────────────────────────────────────────┘
```

## 2. 文件清单

### Docker Compose

| 文件路径 | 行数 | 职责 | 主要导出 |
|---------|------|------|---------|
| `docker-compose.dev.yml` | 234 | 开发环境全栈编排（8 个服务 + 1 个 init） | `starmap-dev` compose 项目 |
| `docker-compose.prod.yml` | 343 | 生产环境全栈编排（7 个服务 + 1 个 init） | `starmap-prod` compose 项目 |

### Dockerfile

| 文件路径 | 行数 | 职责 | 主要导出 |
|---------|------|------|---------|
| `backend/Dockerfile` | 54 | 后端生产镜像（多阶段构建） | `starmap-backend` 镜像 |
| `backend/Dockerfile.dev` | 31 | 后端开发镜像（热重载） | 开发模式 backend 服务 |
| `backend/Dockerfile.celery` | 26 | Celery Worker 镜像（Playwright） | `starmap-celery-worker` |
| `frontend/Dockerfile` | 53 | 前端生产镜像（Node 构建 + Nginx） | `starmap-frontend` 镜像 |
| `frontend/Dockerfile.dev` | 19 | 前端开发镜像（Vite HMR） | 开发模式 frontend 服务 |

## 3. 架构设计

### 开发环境架构（docker-compose.dev.yml）

```
┌─────────────────────────────────────────────────────────────┐
│  starmap-dev                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  backend    │  │  frontend   │  │  celery-worker      │ │
│  │  (8000)     │  │  (5173)     │  │  (无端口暴露)        │ │
│  │  uvicorn    │  │  vite dev   │  │  celery worker      │ │
│  │  --reload   │  │  --host     │  │  --loglevel=info    │ │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
│         │                │                    │            │
│  ┌──────┴──────┐  ┌──────┴──────┐  ┌──────────┴──────────┐ │
│  │   neo4j     │  │   postgres  │  │      redis          │ │
│  │  (7474/7687)│  │   (5433)    │  │     (6379)          │ │
│  │   APOC      │  │   starmap   │  │                     │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│  ┌─────────────┐  ┌─────────────────────────────────────┐  │
│  │   chroma    │  │   ollama (11434) + ollama-pull     │  │
│  │   (8001)    │  │   Qwen2.5-7B 模型自动拉取           │  │
│  └─────────────┘  └─────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 生产环境架构（docker-compose.prod.yml）

```
┌─────────────────────────────────────────────────────────────┐
│  starmap-prod                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  backend    │  │  frontend   │  │  celery-worker      │ │
│  │  (8000)     │  │  (80)       │  │  (无端口暴露)        │ │
│  │  4 workers  │  │  Nginx      │  │  4 concurrency      │ │
│  │  --access-log│ │  static     │  │  --max-tasks=200    │ │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
│         │                │                    │            │
│  ┌──────┴──────┐  ┌──────┴──────┐  ┌──────────┴──────────┐ │
│  │   neo4j     │  │   postgres  │  │      redis          │ │
│  │  (7474/7687)│  │   (5432)    │  │     (6379)          │ │
│  │   APOC      │  │   UTF-8     │  │   --requirepass     │ │
│  │   512m-1G   │  │   initdb    │  │   --maxmemory 256mb │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│  ┌─────────────┐  ┌─────────────────────────────────────┐  │
│  │   chroma    │  │   ollama (11434) + ollama-pull     │  │
│  │   (8000)    │  │   4 CPU / 8G RAM                    │  │
│  └─────────────┘  └─────────────────────────────────────┘  │
│                                                            │
│  Network: starmap-net (bridge, 172.28.0.0/16)             │
└─────────────────────────────────────────────────────────────┘
```

### 多阶段构建流程

```
backend/Dockerfile:
┌─────────────────┐    ┌─────────────────┐
│  Stage 1:       │───▶│  Stage 2:       │
│  builder        │    │  production     │
│  python:3.11    │    │  python:3.11    │
│  + build-ess    │    │  + libpq5       │
│  + poetry 2.4.1│    │  + non-root     │
│  + 安装依赖     │    │  + 4 workers    │
└─────────────────┘    └─────────────────┘

frontend/Dockerfile:
┌─────────────────┐    ┌─────────────────┐
│  Stage 1:       │───▶│  Stage 2:       │
│  builder        │    │  production     │
│  node:20-alpine│    │  nginx:alpine   │
│  + npm ci       │    │  + dist/        │
│  + npm build    │    │  + nginx.conf   │
│  + VITE_API_... │    │  + non-root     │
└─────────────────┘    └─────────────────┘
```

## 4. 接口规范

### 启动命令

| 环境 | 命令 | 说明 |
|------|------|------|
| 开发 | `docker compose -f docker-compose.dev.yml up -d` | 后台启动全栈 |
| 开发 | `docker compose -f docker-compose.dev.yml stop` | 停止（保留容器） |
| 生产 | `docker compose -f docker-compose.prod.yml up -d` | 后台启动全栈 |
| 生产 | `docker compose -f docker-compose.prod.yml down -v` | 停止并清理卷 |

### 服务端口映射

| 服务 | 开发端口 | 生产端口 | 说明 |
|------|---------|---------|------|
| backend | 8000 | 8000 | FastAPI |
| frontend | 5173 | 80 | Vite dev / Nginx |
| neo4j (HTTP) | 7474 | 7474 | Neo4j Browser |
| neo4j (Bolt) | 7687 | 7687 | Bolt 协议 |
| postgres | 5433 | 5432 | PostgreSQL |
| redis | 6379 | 6379 | Redis |
| chroma | 8001 | 8000 | ChromaDB |
| ollama | 11434 | 11434 | Ollama API |

### 健康检查端点

| 服务 | 检查方式 | 间隔 | 超时 | 重试 |
|------|---------|------|------|------|
| backend | `curl -sf http://localhost:8000/health` | 15s | 5s | 5 次 |
| neo4j | `wget -q -O - http://localhost:7474` | 10s | 5s | 10 次 |
| postgres | `pg_isready -U starmap` | 5s | 3s | 10 次 |
| redis | `redis-cli ping` | 10s | 3s | 5 次 |
| chroma | `curl -sf http://localhost:8000/api/v1/heartbeat` | 15s | 5s | 5 次 |
| ollama | `curl -sf http://localhost:11434/api/tags` | 30s | 10s | 5 次 |
| frontend | `curl -sf http://localhost:80/` | 15s | 5s | 3 次 |
| celery | `celery -A app.tasks.celery_app.celery_app inspect ping` | 30s | 10s | 3 次 |

## 5. 编码规范（本模块特有）

### 5.1 Dockerfile 规范
- **多阶段构建**：生产镜像使用 builder + production 两阶段
- **非 root 用户**：生产环境创建 `starmap` 或 `nginx` 用户
- **层缓存优化**：先 COPY 依赖文件，再 COPY 源码
- **清理 apt 缓存**：`rm -rf /var/lib/apt/lists/*`
- **UTF-8 编码**：`ENV LANG=C.UTF-8 LC_ALL=C.UTF-8`

### 5.2 Compose 规范
- **服务名作为 DNS**：服务间通信使用服务名（如 `neo4j`, `postgres`）
- **depends_on + condition**：使用 `condition: service_healthy` 而非简单 `depends_on`
- **命名卷**：使用 `neo4j_data`, `postgres_data` 等命名卷持久化数据
- **环境变量**：敏感信息通过 `.env` 文件注入，不硬编码
- **restart 策略**：`unless-stopped`（开发）/ `unless-stopped`（生产）

### 5.3 开发 vs 生产差异

| 项 | 开发 | 生产 |
|----|------|------|
| 后端命令 | `uvicorn --reload` | `uvicorn --workers 4` |
| 前端命令 | `npm run dev --host` | Nginx 静态服务 |
| Celery loglevel | `info` | `warning` |
| Celery concurrency | 默认 | 4 |
| 资源限制 | 无 | CPU/Memory limits |
| 网络 | 默认 | `starmap-net` (172.28.0.0/16) |
| 数据卷 | 不命名 | 命名 + `driver: local` |

### 5.4 反模式
- **不要在 Dockerfile 中 COPY 整个项目根目录**：仅 COPY 必要文件
- **不要在生产镜像中包含 dev 依赖**：使用 `--only main`
- **不要在 Compose 中暴露不必要的端口**：仅暴露需要外部访问的端口
- **不要使用 `latest` 标签**：锁定镜像版本（`neo4j:5-community`, `postgres:16`）
- **不要在 `.env` 中提交敏感信息**：使用 `.env.example` 模板

### 5.5 Celery Worker 特殊配置
```dockerfile
# Dockerfile.celery 使用 Playwright 官方镜像
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy
# 原因：免去 Chromium 重复安装，支持爬虫反检测
```

## 6. 测试规范

### 6.1 Docker 冒烟测试
- **触发**：CI 中 `workflow_dispatch` 或 `schedule`
- **验证项**：
  1. `docker compose -f docker-compose.dev.yml up -d` 成功
  2. 后端 `/health` 返回 200（30 轮 x 2s 轮询）
  3. 前端 `curl -sf http://localhost:5173` 成功
  4. `docker compose down -v` 清理成功

### 6.2 本地验证
```bash
# 构建所有镜像
docker compose -f docker-compose.dev.yml build

# 启动并查看日志
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml logs -f backend

# 健康检查
docker compose -f docker-compose.dev.yml ps
docker compose -f docker-compose.dev.yml exec backend curl -sf http://localhost:8000/health
```

### 6.3 覆盖率要求
- Docker 构建成功率：100%
- 健康检查通过率：100%
- 冒烟测试通过率：100%

## 7. 变更管理

### 修改 Docker 配置时的检查清单

- [ ] 新增服务是否添加 `healthcheck`？
- [ ] 新增服务是否声明 `depends_on` + `condition`？
- [ ] 修改端口映射是否同步更新文档？
- [ ] 修改 Dockerfile 是否验证多阶段构建仍然有效？
- [ ] 新增环境变量是否在 `.env.example` 中声明？
- [ ] 修改镜像版本是否测试兼容性？
- [ ] 新增卷是否声明在 `volumes:` 段？
- [ ] 修改网络配置是否影响服务间通信？
- [ ] 生产配置变更是否同步到 `docker-compose.prod.yml`？
- [ ] 开发配置变更是否同步到 `docker-compose.dev.yml`？

### 契约影响
- **修改 Dockerfile**：影响 CI 构建和部署流程
- **修改 docker-compose**：影响开发环境和生产部署
- **新增服务**：需要更新健康检查和依赖关系
- **修改端口**：需要更新前端 API 配置和文档

### 迁移要求
- Dockerfile 变更需重新构建镜像：`docker compose build <service>`
- Compose 变更需重启服务：`docker compose up -d --force-recreate`
- 新增命名卷需提前创建或让 compose 自动创建
- 镜像版本升级需测试兼容性（特别是 Neo4j 5 -> 6）
- 网络配置变更需确保所有服务能正常通信
