# StarMap 启动方法指南

> **版本**: v1.1  
> **日期**: 2026-07-05  
> **适用项目**: 星图(StarMap) - 人才能力星云导航系统  
> **技术栈**: FastAPI + Vue 3 + PostgreSQL + Neo4j + Redis + ChromaDB + Ollama

---

## 目录

- [快速开始（推荐）](#快速开始推荐)
- [方式一：Docker Compose 全栈一键启动](#方式一docker-compose-全栈一键启动)
- [方式二：本地原生开发](#方式二本地原生开发)
- [方式三：纯 Docker 生产部署](#方式三纯-docker-生产部署)
- [方式四：轻量级服务器部署（无 Docker）](#方式四轻量级服务器部署无-docker)
- [常见问题排查](#常见问题排查)
- [服务健康检查](#服务健康检查)
- [环境变量说明](#环境变量说明)

---

## 快速开始（推荐）

如果你只想**最快看到效果**，执行以下命令：

```bash
cd starmap

# 1. 准备环境变量（Docker 模式）
cp .env.docker .env

# 2. 启动所有服务
docker compose -f docker-compose.dev.yml up -d

# 3. 等待服务就绪（约 30~60 秒）
docker compose -f docker-compose.dev.yml ps

# 4. 访问应用
# 前端: http://localhost:5173
# 后端 API: http://localhost:8000
# Neo4j 浏览器: http://localhost:7474
```

---

## 方式一：Docker Compose 全栈一键启动（**推荐，最完整**）

所有服务运行在 Docker 容器中，包含热重载、代码挂载、自动健康检查。

### 1.1 前置要求

| 软件 | 最低版本 | 说明 |
|------|----------|------|
| Docker Desktop | v24+ | 包含 Docker Compose v2 |
| Git | 任意 | 克隆代码 |
| 内存 | 8GB+ | Ollama 本地 LLM 需要约 4GB |
| 磁盘 | 20GB+ | Ollama 模型约 4.5GB |

### 1.2 启动步骤

```bash
cd starmap

# 1. 选择 Docker 模式环境变量
cp .env.docker .env

# 2. 启动所有服务（前台运行，查看日志）
docker compose -f docker-compose.dev.yml up

# 或后台运行
# docker compose -f docker-compose.dev.yml up -d

# 3. 查看服务状态
docker compose -f docker-compose.dev.yml ps

# 4. 查看日志（可选）
docker compose -f docker-compose.dev.yml logs -f backend
docker compose -f docker-compose.dev.yml logs -f frontend
```

### 1.3 服务清单

| 服务 | 容器名 | 端口 | 说明 |
|------|--------|------|------|
| backend | starmap-backend | 8000 | FastAPI + 热重载 |
| celery-worker | starmap-celery-worker | - | 异步任务队列 |
| frontend | starmap-frontend | 5173 | Vite HMR |
| neo4j | starmap-neo4j | 7474/7687 | 图数据库浏览器 |
| postgres | starmap-postgres | 5433 | PostgreSQL 16 |
| redis | starmap-redis | 6379 | 缓存+消息队列 |
| chroma | starmap-chroma | 8001 | 向量数据库 |
| ollama | starmap-ollama | 11434 | 本地 LLM (Qwen2.5-7B) |

### 1.4 停止服务

```bash
# 正确方式：停止容器（保留容器，下次启动更快）
docker compose -f docker-compose.dev.yml stop

# 启动已停止的容器
docker compose -f docker-compose.dev.yml start

# 完全删除容器（慎用，会丢失容器但保留数据卷）
docker compose -f docker-compose.dev.yml down

# 完全清理（删除数据卷）
docker compose -f docker-compose.dev.yml down -v
```

> **⚠️ 重要警告**: Docker Desktop 的 Stop 按钮会**删除容器**（执行 `docker compose down`），而非仅仅停止。请始终使用命令行 `docker compose stop` 来保留容器。详见 `DOCKER_DESKTOP_STOP_FIX.md`。
>
> **重要提示**：使用 `docker compose stop` 而非 `docker compose down`，前者保留容器，后者会删除容器。数据卷（数据库数据）始终保留，不受 `down` 影响。

### 1.5 代码热重载

- **后端**: 修改 `backend/app/` 下的代码，Uvicorn 自动重载
- **前端**: 修改 `frontend/src/` 下的代码，Vite 自动 HMR
- **爬虫**: 修改 `crawler/` 下的代码，Celery worker 自动重载

---

## 方式二：本地原生开发（**灵活性最高**）

基础设施用 Docker 运行，应用代码在本地直接运行，便于 IDE 调试。

### 2.1 前置要求

| 软件 | 最低版本 |
|------|----------|
| Docker Desktop | v24+ |
| Python | 3.11+ |
| Poetry | 2.4+ |
| Node.js | 20+ |
| npm | 10+ |

### 2.2 启动基础设施

```bash
cd starmap

# 启动数据库等基础设施（不含应用）
docker compose -f docker-compose.dev.yml up neo4j postgres redis chroma ollama -d
```

### 2.3 后端本地启动

```bash
cd starmap/backend

# 1. 安装依赖
poetry install

# 2. 数据库迁移
poetry run alembic upgrade head

# 3. 启动 FastAPI（热重载）
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2.4 Celery Worker（可选，异步任务需要）

```bash
cd starmap/backend
poetry run celery -A app.tasks.celery_app.celery_app worker --loglevel=info
```

### 2.5 前端本地启动

```bash
cd starmap/frontend

# 1. 安装依赖
npm install

# 2. 生成 API 类型定义
npm run gen:api

# 3. 启动开发服务器（自动代理 /api → localhost:8000）
npm run dev
```

### 2.6 爬虫本地启动

```bash
cd starmap/crawler

# 初始化数据库表
python run.py init

# 爬取各站点
python run.py lagou --max 10 --keyword python
python run.py bosszhipin --max 10
python run.py stealth_all --max 10
```

### 2.7 环境变量切换

本地开发需使用 `.env.local`（已预置 localhost 地址）：

```bash
cd starmap
cp .env.local .env
```

---

## 方式三：纯 Docker 生产部署

### 3.1 前置要求

- Docker Desktop v24+
- 内存 16GB+
- 磁盘 30GB+

### 3.2 启动步骤

```bash
cd starmap

# 1. 准备生产环境变量
cp .env.docker .env
# 编辑 .env，将 APP_ENV=production，并填入强密码

# 2. 启动生产环境
docker compose -f docker-compose.prod.yml up -d

# 3. 等待所有服务 healthy（约 60 秒）
docker compose -f docker-compose.prod.yml ps
```

### 3.3 生产环境特性

- **Backend**: 4 个 Uvicorn worker，资源限制 2 CPU / 2GB
- **Celery**: 4 并发 worker，多队列（default/extraction/matching/graph）
- **Frontend**: Nginx 静态服务，Gzip 压缩，SPA 路由回退
- **资源限制**: 所有服务都有 CPU/内存限制
- **健康检查**: 所有服务都有自动健康检查

---

## 方式四：轻量级服务器部署（**无 Docker**）

适合阿里云 ECS 等轻量服务器（内存 1.8GB+）。

### 4.1 一键部署

```bash
# 以 root 身份运行
sudo bash scripts/deploy-lightweight.sh
```

脚本自动执行：
1. 环境检测（内存、Python、Git）
2. 创建 starmap 用户
3. 克隆代码到 `/opt/starmap`
4. 安装 Poetry + 后端依赖
5. 配置每日 crontab（UTC 02:00）
6. 运行契约校验 + Lint 验证

### 4.2 手动启动

```bash
cd /opt/starmap/backend
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 常见问题排查

### Q1: 后端启动报错 "Connection refused" 到数据库

**原因**: `.env` 中的数据库地址与运行环境不匹配。

**解决**:
- Docker 模式: `cp .env.docker .env`
- 本地模式: `cp .env.local .env`

### Q2: Ollama 模型拉取失败

**现象**: `ollama-pull` 容器 exit code 1。

**解决**:
```bash
# 手动拉取模型
docker compose -f docker-compose.dev.yml exec ollama ollama pull qwen2.5:7b

# 或跳过 Ollama（不使用本地 LLM）
docker compose -f docker-compose.dev.yml up --scale ollama=0 --scale ollama-pull=0
```

### Q3: 前端连接不到后端 API

**原因**: MSW (Mock Service Worker) 默认启用。

**解决**: 确保 `VITE_USE_MSW=false` 已设置（`.env.docker` 和 `.env.local` 中已预置）。

### Q4: Celery worker 被 SIGKILL (exit 137)

**原因**: 内存不足或 Docker 资源限制。

**解决**:
```bash
# 增加 Docker 内存限制（Docker Desktop → Settings → Resources）
# 或单独启动 Celery（减少并发）
docker compose -f docker-compose.dev.yml up --scale celery-worker=0
```

### Q5: poetry.lock 缺失导致依赖不可复现

**解决**:
```bash
cd starmap/backend
poetry lock
```

### Q6: Docker Desktop 中容器停止后从列表消失

**现象**: 执行 `docker compose stop` 后，Docker Desktop 的 Containers 页面显示 "No containers are running"，容器似乎"消失"了。

**原因**: Docker Desktop 默认开启 **"Only show running containers"** 过滤开关，停止的容器被隐藏了。

**解决方案**:

1. **Docker Desktop 界面操作**（推荐）:
   - 打开 Docker Desktop → Containers 页面
   - 找到 **"Only show running containers"** 开关
   - **关闭它**（从蓝色变为灰色）
   - 停止的容器就会显示为 "Exited" 状态

2. **命令行验证容器仍在**:
   ```bash
   # 查看所有容器（包括停止的）
   docker ps -a
   
   # 查看 starmap 项目容器
   docker compose -f docker-compose.dev.yml ps -a
   ```

3. **重新启动容器**:
   ```bash
   # 启动已停止的容器（保留数据，快速启动）
   docker compose -f docker-compose.dev.yml start
   
   # 或重新创建（如果容器被删除）
   docker compose -f docker-compose.dev.yml up -d
   ```

**关键区别**:
| 命令 | 容器状态 | 数据卷 | 用途 |
|------|----------|--------|------|
| `docker compose stop` | 保留（Exited） | 保留 | ✅ 开发推荐，快速重启 |
| `docker compose start` | 恢复运行 | 保留 | 启动已停止的容器 |
| `docker compose down` | **删除** | 保留 | 清理容器，保留数据 |
| `docker compose down -v` | **删除** | **删除** | ⚠️ 完全清理，数据丢失 |

> **最佳实践**: 开发环境始终使用 `stop`/`start` 组合，避免使用 `down` 删除容器。

---

## 服务健康检查

```bash
# Backend
curl http://localhost:8000/health

# Neo4j
open http://localhost:7474

# PostgreSQL
docker compose -f docker-compose.dev.yml exec postgres pg_isready -U starmap

# Redis
docker compose -f docker-compose.dev.yml exec redis redis-cli ping

# ChromaDB
curl http://localhost:8001/api/v1/heartbeat

# Ollama
curl http://localhost:11434/api/tags
```

---

## 环境变量说明

| 文件 | 用途 | 数据库地址 |
|------|------|----------|
| `.env` | 当前生效配置 | 取决于复制来源 |
| `.env.docker` | Docker 全栈模式 | 服务名（neo4j, postgres） |
| `.env.local` | 本地开发模式 | 127.0.0.1 |
| `.env.example` | 模板（含占位符） | - |

### 切换命令

```bash
# 切换到 Docker 模式
cp .env.docker .env

# 切换到本地模式
cp .env.local .env
```

---

## 相关文档

- `DEPLOY_GUIDE.md` - 部署指南（含阿里云轻量部署）
- `DOCKER_DESKTOP_STOP_FIX.md` - Docker Desktop Stop 按钮问题解决方案
- `docker-compose.dev.yml` - 开发环境配置
- `docker-compose.prod.yml` - 生产环境配置
- `backend/pyproject.toml` - Python 依赖
- `frontend/package.json` - Node 依赖
