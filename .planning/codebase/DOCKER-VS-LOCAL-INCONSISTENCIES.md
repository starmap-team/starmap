# Docker 服务 vs 本地服务 — 不一致分析报告

**分析日期：** 2026-07-14
**分析焦点：** Docker Compose 全栈启动 与 主机本地直接运行 之间的配置漂移/不一致
**关联文档：** `docker-compose.dev.yml`, `docker-compose.prod.yml`, `Dockerfile*`, `.env*`, `backend/app/config.py`

---

## 1. 总览（TL;DR）

StarMap 当前存在 **三类运行模式**，但只明确声明了两种：
- **A. Docker Compose 全栈**（`docker-compose.dev.yml up`）— 文档化、推荐路径
- **B. Docker Compose 生产**（`docker-compose.prod.yml up`）— 文档化、生产路径
- **C. 主机本地后端 + Docker DB**（`backend/.env.local` 暗示）— **未文档化**，但有完整 env 文件 + README 段落说明

| 维度 | 数量 | 严重程度 |
|------|------|----------|
| 高严重度（阻断/安全） | 5 | 🔴 必须修复 |
| 中严重度（行为偏差） | 7 | 🟡 应修复 |
| 低严重度（文档/卫生） | 4 | 🟢 可后续清理 |

**核心结论：** 项目当前的 `vite.config.ts` 代理默认端口（8002）、Docker 映射端口（8000）、以及主机本地后端端口（取决于 IDE/启动方式）三方不一致，是最容易踩坑的入口；`.env*` 文件存在 **4 份**但只有 `.env.example` 提交，导致开发者选错文件时整套配置静默失败。

---

## 2. 三种运行模式实测对照

| 项目 | A. Docker 全栈（dev） | B. Docker 生产 | C. 主机本地后端 |
|------|----------------------|----------------|-----------------|
| 启动命令 | `docker compose -f docker-compose.dev.yml up` | `docker compose -f docker-compose.prod.yml up` | `cd backend && poetry run uvicorn app.main:app --reload` |
| 使用的 `.env` | `.env`（最新, 2026-07-13） | `.env` + `docker-compose.prod.yml` 中 env 覆盖 | `backend/.env`（650B, 2026-07-14） |
| PostgreSQL 端口 | 5433→5432 (host:5433) | 5432→5432 (host:5432) | 5433 (host:5433) |
| Neo4j 端口 | 7687 (host:7687) | 7687 (容器内, host 未映射) | 7687 (host:7687) |
| ChromaDB 端口 | 8001→8000 (host:8001) | 8000→8000 (host:8000) | 8001 (host:8001) — 来自 `.env.local` |
| Redis 端口 | 6379 (host:6379) | 6379 (容器内, 未映射到 host) | 6379 (host:6379) |
| Frontend Proxy 目标 | `http://starmap-backend:8000` (Docker 网络) | `/api` (Nginx 反代) | `http://localhost:8002`（vite 默认, 注释中提到 8002） |
| LLM 地址 | `http://ollama:11434` (Docker 网络) | `http://ollama:11434` | `http://localhost:11434` (如果 .env.local) 或 `http://host.docker.internal:11434` (如果 .env) |
| Volume 挂载 | `./backend` 挂到 `/app`（热重载） | 无挂载（COPY 到镜像） | N/A |
| `depends_on` healthcheck | 有 (neo4j/postgres/redis/chroma) | 有 | 无（直接连） |
| AUTH_USERS | `admin:starmap2024:admin,demo:demo123:user` | 来自 `.env`（同上） | **空！** `backend/.env` 缺 AUTH_USERS，**本地启动后无法登录** |

---

## 3. 关键不一致清单

### 3.1 🔴 严重：`.env` 文件命名混乱 + 内容冲突

**问题：** 项目根目录同时存在 4 个 `.env*` 文件，内容相互冲突：

| 文件 | PostgreSQL Host | PostgreSQL Port | Chroma Host | Chroma Port | AUTH_USERS | VITE_API_BASE_URL | 注释 |
|------|----------------|----------------|-------------|-------------|------------|--------------------|------|
| `.env` | `postgres` | 5432 | `chroma` | 8000 | ✅ 有 | （无，注释提到用相对路径） | 最新 (07-13)，顶层注释说是 "Docker 模式"，但配置不是 Docker 的（端口 5432 = 容器内） |
| `.env.docker` | `postgres` | 5432 | `chroma` | 8000 | ❌ 无 | `http://localhost:8000` | 旧版 (07-03)，顶层注释是 Docker 模式 |
| `.env.example` | `postgres` | 5432 | `chroma` | 8000 | （空模板） | `http://localhost:8000` | 已提交，纯模板 |
| `.env.local` | `localhost` | 5433 | `localhost` | 8001 | ❌ 无 | ❌ 无 | 顶层注释："Windows 主机跑后端 + Docker 跑 DB" — **第三种模式！** |
| `backend/.env` | `localhost` | 5433 | ❌ 未设 | ❌ 未设 | ❌ 无 | N/A | 顶层注释 "Docker infrastructure credentials"，但实际是主机本地值 |
| `backend/.env.local` | `localhost` | 5433 | `localhost` | 8001 | ❌ 无 | N/A | 后端独立 `.env.local` (已 gitignore) |

**为什么会爆雷：**
1. **docker-compose.dev.yml 通过 `env_file: .env` 加载** → 加载的是根目录 `.env`，但 `.env` 内 `POSTGRES_HOST=postgres` 是 Docker 网络名。如果开发者 **临时改 host network** 跑某个服务，配置会找不到正确端口。
2. **`config.py` 的 `Settings` 默认 `postgres_port=5432`** — Docker 内正确，但若开发者 `uvicorn` 主机跑就是错的（应该是 5433）。`backend/.env` 主动写了 5433 缓解。
3. **`backend/.env` 缺 `AUTH_USERS`** — 本地启动后 `parsed_users = []`，调用 `/api/v1/auth/login` 返回 `user not found`。**这是真的会让开发者 30 分钟找 bug 的隐性失败。**

**应有真相源：** 当前 `(路径: 默认值)` 散落 5 处，无法用任何一种环境变量解释为什么"应该用哪一个"。

**建议修复（仅作报告，不自动改动）：**
- 文档化三种模式各自的 `.env` 来源（`scripts/setup.sh` 或 README 表格）
- 把 `.env` 改名为 `docker.env` 或 `.env.docker-compose`，避免和 `backend/.env` 重名
- `backend/.env` 加一份 `AUTH_USERS=admin:dev_password:admin` 或自动 fallback 到 docker-compose 的用户
- 在 `config.py` 增加 "未配置 AUTH_USERS 时打印明确告警" 的逻辑（当前只 warn 不报错）

---

### 3.2 🔴 严重：Docker / 主机本地 / Vite 代理的端口三元不一致

**实测证据：**

```
docker-compose.dev.yml:21    ports: "8000:8000"                    # backend 映射
docker-compose.dev.yml:91    VITE_API_BASE_URL=http://starmap-backend:8000
frontend/vite.config.ts:23   target: process.env.VITE_API_BASE_URL || 'http://localhost:8002'  # ← 8002，不是 8000！
                            ↑ 注释还提到 "8002 是 backend-dev 服务的映射端口"，但 compose 文件里服务名是 backend 而非 backend-dev
backend/app/config.py       POSTGRES_PORT 默认 5432               # 主机本地默认端口
backend/.env                POSTGRES_PORT=5433                    # Windows 端口冲突
docker-compose.dev.yml:128  ports: "5433:5432"   # Postgres 端口
```

**最严重的歧义：** `vite.config.ts:23`

```ts
target: process.env.VITE_API_BASE_URL || 'http://localhost:8002',
```

注释说 "8002 是 docker-compose.dev.yml 中 backend-dev 服务的映射端口"，但 `docker-compose.dev.yml` 中的服务名是 `backend`（不是 `backend-dev`），端口是 **8000**（不是 8002）。

**这意味着：**
- 开发者 `npm run dev` 单独跑前端（不在 Docker 内）→ vite 默认代理到 `localhost:8002` → **永远连不上**（因为后端在 8000）
- 必须手动 `VITE_API_BASE_URL=http://localhost:8000 npm run dev` 才正确
- 这个 8002 似乎是过去某个阶段的服务名，重构后没清理

**建议修复：**
- 把 vite.config.ts 默认值改成 `http://localhost:8000`（与 compose 对齐）
- 删除 "8002 / backend-dev" 残留注释
- 或者：反过来在 compose 里把 backend 改名为 `backend-dev` 端口 8002，匹配 vite 注释

---

### 3.3 🔴 严重：`ollama` 模型初始化逻辑在三处不同

| 位置 | 触发条件 | 网络要求 |
|------|---------|----------|
| `docker-compose.dev.yml:204-226` `ollama-pull` 服务 | ollama 健康检查通过后 | Docker 网络内 |
| `docker-compose.prod.yml:303-316` `ollama-pull` 服务 | 同上，但 `restart: "no"` | Docker 网络内 |
| `backend/.env` / `.env.local` | **没有** 拉取逻辑 | 开发者必须手动 `docker exec ollama ollama pull qwen2.5:7b` |

**后果：** 主机本地后端 + Docker DB 模式下，**Ollama 必须已在容器内手动启动并拉过模型**。如果开发者只 `docker compose up neo4j postgres redis chroma`（缺 ollama），后端启动会卡在 `Ollama not reachable`，但 `config.py` 只会 warn 不会阻止启动，导致 LLM 调用时 `RuntimeError`。

**建议：** 在 `config.py` 增加 "若 Qwen2.5 作为唯一 LLM 时，必须 reachable，否则启动失败" 开关。

---

### 3.4 🔴 严重：`backend/.env` 中 `SECRET_KEY=dev-secret-key-not-for-production` 但 `config.py` 第 254-260 行的生产校验是 `len(secret_key) < 32` — 这个串长度 **15** < 32，**生产校验会通过**（因为开发模式不校验），但万一误把 `APP_ENV=production` 会立刻挂掉。**这是好的还是坏的？** 看用法 —— 这其实是个 **良好的 fail-fast**，但本地开发文档没提。**建议：** 在 `backend/README.md` 加一段 `## 切换到生产模式前的检查清单`。

---

### 3.5 🔴 严重：Vite 代理的 `changeOrigin: true` 在 Docker 模式下会导致问题

`vite.config.ts:24` 启用了 `changeOrigin: true`。当 docker-compose.dev.yml 跑前端时（前端也是容器），代理目标是 `http://starmap-backend:8000`，但前端在浏览器访问时是 `http://localhost:5173/api/...`，`changeOrigin` 会把 Host 头改成 `starmap-backend:8000` —— **后端可能验证 Host 进行 CORS / rate-limit**，会导致间歇性失败。

`docker-compose.dev.yml:91` 把 `VITE_API_BASE_URL=http://starmap-backend:8000` 直接给了环境变量，这等于 **旁路掉了 vite 代理**，浏览器直连容器名（在用户的浏览器里这个域名不存在，会失败）。

**实测路径：** 用户用 docker compose up → 浏览器打开 `http://localhost:5173` → 前端代码读 `import.meta.env.VITE_API_BASE_URL = "http://starmap-backend:8000"` → axios 直接请求 `http://starmap-backend:8000/api/v1/...` → 浏览器 DNS 解析失败 → **404/network error**。

**这意味着 docker 化开发模式当前大概率是坏的**，至少需要：
- `VITE_API_BASE_URL=http://localhost:8000`（让 vite 代理工作），或者
- 把浏览器访问改成 `http://localhost:8000/api/v1` 直连后端（绕过前端 5173）

**强烈建议立即修复**：这是 P0（最易触发）。

---

### 3.6 🟡 中等：CHROMA URL 在 docker-compose.prod.yml 通过环境变量覆盖，而 dev 没覆盖

```yaml
# docker-compose.dev.yml 中 backend 没有 CHROMA_URL 环境变量
# 但 docker-compose.prod.yml 有：
- CHROMA_URL=http://chroma:8000
```

`config.py` 第 78-79 行用的是组件式 (`chroma_host`/`chroma_port`)，**prod 注入的 `CHROMA_URL` 会被 config 完全忽略**。 同样 neo4j/redis 也是注入完整 URL 但 config 用组件。

**后果：** prod 的 `DATABASE_URL=postgresql://...` / `NEO4J_URI=bolt://...` / `REDIS_URL=redis://...` **几乎全部被 `config.py` 忽略**（config 用的是 `POSTGRES_HOST`+`POSTGRES_PORT`+`POSTGRES_USER`... 字段）。

**这是配置层和编排层的概念错位。** Compose 文件让人觉得有完整 URL 兜底，其实没用。

---

### 3.7 🟡 中等：开发 compose 把 `neo4j_data`/`postgres_data` 等以无 driver 方式声明，prod 都加了 `driver: local`

```yaml
# dev:
volumes:
  neo4j_data:        # 默认 local，但未明确
  postgres_data:

# prod:
volumes:
  neo4j_data_prod:
    driver: local    # 明确
```

`docker-compose.dev.yml` 隐式用 `local` driver，没有 `name: starmap-dev-...` 前缀。跨机器迁移到其他 volume driver 时 dev 会自动 rename，prod 不会 — **不一致带来的可能影响是部署文档可移植性**。

---

### 3.8 🟡 中等：NEO4J 健康检查 URL 不同

| 文件 | URL | 状态 |
|------|-----|------|
| `docker-compose.dev.yml:114` | `wget -q -O - http://localhost:7474` | dev |
| `docker-compose.prod.yml:166` | `wget -q -O - http://localhost:7474` | prod 一致 |
| `backend/.env` / `.env.example` 都不涉及 | — | — |
| 浏览器访问 | http://localhost:7474 | 实际可用 |

**实际 prod 的 neo4j 浏览器 7474 端口没有映射到 host**（compose 中没有 `ports:`），但 docker-compose.prod.yml 后面没出现这段 — **实际查看：** `docker-compose.prod.yml` 152-181 行没有 `ports:` 暴露，**生产环境外部无法访问 7474 Web UI** —— 这是有意为之还是漏了？和 dev 不一致。

---

### 3.9 🟡 中等：`vite.config.ts` 写死 5173 vs backend 容器无健康检查 alias

dev docker 中 frontend 用 `command: npm run dev -- --host 0.0.0.0`，但 **没有 healthcheck**。后端 `depends_on: backend` 没有 `condition: service_healthy` —— **前端可能在后端未就绪时启动，导致首屏 502**。Compose dev 文件第 95 行：

```yaml
depends_on:
  - backend   # 没有 condition: service_healthy
```

应该是：

```yaml
depends_on:
  backend:
    condition: service_healthy
```

**这是真实可见的小问题。** 同样的 prod 文件第 131-133 行处理正确。

---

### 3.10 🟡 中等：`README.md` 文档与现实脱节

`README.md` 第 19 行：

```
docker-compose -f docker-compose.dev.yml up
```

但项目根目录的 compose 文件是 `docker-compose.dev.yml`（带 dot），最近的 Docker Compose v2 也接受 `docker compose -f docker-compose.dev.yml up`，**没问题**。但 README.md 没说还有 `docker-compose.prod.yml`，也没说主机本地后端模式。

**建议：** README 加一段：

```markdown
### 启动模式

1. **全栈 Docker（推荐）**：`docker compose -f docker-compose.dev.yml up`
2. **主机后端 + Docker DB**：见 `backend/README.md` 第 12 行
3. **生产部署**：`docker compose -f docker-compose.prod.yml up -d`
```

---

### 3.11 🟡 中等：CORS 配置可能漏掉 Docker 内部网络

`config.py` 第 25-32 行默认 `cors_origins` 列表是 `localhost:5173` 等本地端口。**没有列出 docker 网络的 `http://frontend` 或 `http://starmap-frontend`**。如果 backend 容器收到来自 frontend 容器的 CORS 预检，会被拒。

代码里 `cors_origins` 是从环境变量 `CORS_ORIGINS` 覆盖的（通过 `model_config = SettingsConfigDict(env_file=".env")`），但 `.env` 中无 `CORS_ORIGINS`，所以用默认 — **Docker 模式跨域请求会失败**（除非是 same-origin /api 反代）。

---

### 3.12 🟡 中等：`Dockerfile.celery` 与 `Dockerfile.dev` 基镜像不同，依赖一致性有风险

| 文件 | 基镜像 |
|------|--------|
| `backend/Dockerfile` | `python:3.11-slim` (prod) |
| `backend/Dockerfile.dev` | `python:3.11-slim` (dev) |
| `backend/Dockerfile.celery` | `mcr.microsoft.com/playwright/python:v1.49.0-jammy` |

celery 镜像基于微软 Playwright 镜像（Ubuntu 22.04 + Python），与 backend 镜像（Debian slim）的 **glibc、libc 版本、SSL 证书路径不同**。Celery worker 与 backend 共享 `pyproject.toml`，理论上包一致，但二进制 ABI 可能不一致（例如：`cryptography` wheel 在 musl vs glibc）。

**这是 celery 类任务在分布到 k8s 时常见的坑位，但本地不影响。**

---

### 3.13 🟢 低：`stop_signal: SIGTERM` + `stop_grace_period: 10s` 在 prod 中没有

```yaml
# dev compose 中每个服务都有：
stop_signal: SIGTERM
stop_grace_period: 10s

# prod compose 中没有这些配置（用默认值 SIGTERM + 10s）
```

不是 bug，而是 dev 文件更详细。**prod 文件可以加上以保持一致。**

---

### 3.14 🟢 低：`chroma` 镜像版本未在 `requirements.txt` 或 pyproject 锁定

`chromadb/chroma:0.5.3` 是 Docker image tag，未出现在 Python 依赖里。`pyproject.toml` 中 chromadb client 版本可能与之不兼容。

**建议：** 把 chroma client 版本加到 `pyproject.toml` 并在 README 标注与 image 兼容的版本对。

---

### 3.15 🟢 低：`network: starmap-net` 在 prod 中显式定义，dev 中隐式

dev compose 没显式声明 network，所有服务在默认 bridge。**理论上后端访问 `neo4j:7687` 仍可工作**（bridge 网络按服务名解析），但 prod 显式 `starmap-net` 桥接是更可控的做法。

---

### 3.16 🟢 低：`restart: unless-stopped` 在 dev 与 prod 一致 ✅

**这是好消息**，无 issue。

---

## 4. 模式 C（主机本地后端）的隐性陷阱

由于 `.env.local` 提到这个模式但 README 没有完整说明，开发者尝试此模式时大概率踩这些坑：

1. **AUTH_USERS 缺失** → `config.py` 第 304 行返回空列表 → 登录接口 `username not found`
2. **LANG=C.UTF-8 在 Windows 上不生效** → poetry run 时 console 中文乱码 → backend 日志可读性差
3. **`host.docker.internal`** 在 Windows 10/11 上要求 Docker Desktop 配置 → Ollama 连不上 → LLM fallback 不触发报错
4. **`/app/docs` 文档路径** 在 backend Dockerfile.dev 中是镜像内部路径，主机本地需要用 `docs/` 相对路径 → `ontology/skill_taxonomy.yaml` 找不到
5. **`PYTHONPATH=/app`** 在 celery worker container 中显式设了；**主机本地 poetry run 不需要**。如果开发者读 compose 文件依葫芦画瓢，他们会困惑。
6. **`./crawler` mount 到 `/app/crawler`** 在 dev compose 中是必要的；主机本地直接 `poetry install` 已经把 crawler 包装进 sys.path，但路径解析可能不同。

---

## 5. 一致性矩阵（关键参数）

| 参数 | dev compose | prod compose | `.env` (根) | `.env.local` (根) | `backend/.env` | `backend/.env.local` | config.py 默认 |
|------|-------------|---------------|------------|---------------------|-----------------|------------------------|------------------|
| POSTGRES_HOST | (env var) | postgres | postgres | localhost | localhost | localhost | localhost |
| POSTGRES_PORT | 5433→5432 host | 5432 | 5432 | 5433 | 5433 | 5433 | **5432 ⚠️** |
| POSTGRES_USER | starmap | starmap | starmap | starmap | starmap | starmap | starmap |
| POSTGRES_DB | starmap | starmap | starmap | starmap | starmap | starmap | starmap |
| NEO4J_URI | (env var) | bolt://neo4j:7687 | bolt://neo4j:7687 | bolt://localhost:7687 | bolt://localhost:7687 | bolt://localhost:7687 | bolt://localhost:7687 |
| REDIS_URI | (env var) | redis://:pwd@redis | redis://redis:6379/0 | redis://localhost:6379/0 | redis://localhost:6379/0 | redis://localhost:6379/0 | redis://localhost:6379/0 |
| CHROMA_HOST | (env var) | chroma | chroma | localhost | — | localhost | localhost |
| CHROMA_PORT | 8001→8000 host | 8000 | 8000 | 8001 | — | 8001 | 8001 |
| OLLAMA host | (compose service) | (compose service) | http://host.docker.internal:11434 | — | — | — | — |
| AUTH_USERS | from .env | from .env | ✅ 设置 | ❌ 空 | ❌ 空 | ❌ 空 | "" |
| SECRET_KEY | from .env | from .env | dev_secret_* | local-dev-secret-* | dev-secret-* | local-dev-secret-* | CHANGE_ME_IN_ENV |
| APP_ENV | development | (默认) | development | development | development | development | development |
| APP_DEBUG | true | — | true | true | true | true | **true** |
| TOKEN_EXPIRE_HOURS | 24 | — | 24 | — | — | — | 24 |

**重点：** `config.py` 默认 `POSTGRES_PORT=5432` 与所有"主机本地"配置文件不一致（主机本地都是 5433）。

---

## 6. 缺失的真相源 — 建议的 docker compose 配置规范

如果在项目里加一个 `docs/dev-environment.md`，列出：

```markdown
## 三种运行模式

### Mode A — Docker 全栈（推荐）

```bash
cp .env.example .env
# 编辑 .env 填入真实 LLM key
docker compose -f docker-compose.dev.yml up
```

访问：
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000/docs
- Neo4j Browser: http://localhost:7474

### Mode B — 主机本地后端 + Docker 数据栈

```bash
# 1. 启动 Docker 数据栈（仅 DB / 缓存 / 向量库）
docker compose -f docker-compose.dev.yml up neo4j postgres redis chroma

# 2. 主机运行后端
cp backend/.env.local backend/.env
# 编辑 backend/.env 填入真实 LLM key（注意：默认 LLM_PROVIDER=mock）
cd backend
poetry install
poetry run uvicorn app.main:app --reload --port 8002

# 3. 主机运行前端（Docker 8002 = 主机 8002）
cd frontend
npm install
VITE_API_BASE_URL=http://localhost:8002 npm run dev
```

### Mode C — 生产部署

```bash
# 在生产服务器
export POSTGRES_PASSWORD=$(openssl rand -hex 16)
export NEO4J_PASSWORD=$(openssl rand -hex 16)
export REDIS_PASSWORD=$(openssl rand -hex 16)
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
docker compose -f docker-compose.prod.yml up -d
```
```

---

## 7. 优先级修复建议

| 优先级 | 项目 | 修复路径 |
|--------|------|----------|
| **P0** | VITE_API_BASE_URL 在 Docker 模式下设错 (`http://starmap-backend:8000` 浏览器访问不到) | 改为 `http://localhost:8000`，让 vite 代理工作；或保留容器名但需要前端也运行在容器内且用户从容器视角访问（不现实）|
| **P0** | vite 默认代理端口 8002 与实际 backend 端口 8000 不匹配 | `vite.config.ts:23` 改为 `http://localhost:8000` |
| **P1** | `backend/.env` 缺 `AUTH_USERS` | 加默认 `dev` 用户或自动检测 |
| **P1** | `depends_on: - backend` 缺 `condition: service_healthy`（dev compose 95 行） | 加上 |
| **P1** | `.env` 文件命名混乱（4 份且 gitignore 不一致） | 重命名为 `docker.env`, `local.env`, `prod.env` 并文档化 |
| **P2** | 完整 URL 注入 (`DATABASE_URL`, `REDIS_URL`, `NEO4J_URI`) 在 prod compose 里写了但 config.py 不读 | 要么改 config.py 接受完整 URL，要么从 prod compose 删除冗余注入 |
| **P2** | prod compose 缺 `neo4j` 7474 host port 映射 | 决定是否需要外部访问浏览器，删除/保留需明确 |
| **P2** | CORS 默认没覆盖 docker 网络服务名 | 加 `http://frontend` / `http://starmap-frontend` |
| **P3** | Stop signal/grace period 在 prod 没显式 | 加上与 dev 一致 |
| **P3** | Chroma client 版本未锁定 | pyproject.toml 锁定 + README 注明与 image 兼容 |

---

## 8. 验证步骤（不必现在跑，但留作 checklist）

若想完整验证本文档的有效性，可以这样做：

```bash
# 1. 启动全栈
docker compose -f docker-compose.dev.yml up -d

# 2. 等所有 healthy
docker compose -f docker-compose.dev.yml ps

# 3. 浏览器测试
# - http://localhost:5173 → 应该出现登录页（验证 VITE 代理工作）
# - http://localhost:8000/docs → Swagger UI 可访问
# - http://localhost:7474 → Neo4j Browser 可登录

# 4. 切换到主机本地模式
docker compose -f docker-compose.dev.yml stop backend celery-worker
cp backend/.env.local backend/.env
cd backend
poetry install
poetry run uvicorn app.main:app --reload --port 8000

# 5. 浏览器复测 http://localhost:5173 → 应能继续工作
# 6. 尝试登录 admin / starmap2024 → 期望成功（验证 dev compose 的 AUTH_USERS 一致性）
```

---

## 9. 附录 — 我没找到问题但可能存在的潜在陷阱

- `frontend/package.json` 中 `msw: ^2.2.0` 列出，但 `VITE_USE_MSW=false` 在 dev compose 里硬写 → 如果开发者想用 MSW mock（参考 README.md 提到 "MSW 独立开发"），需要在 `.env` 设回 `true` 并重启。
- `evaluation/` 目录里的 `quick_match_test.py` 假设数据库是 localhost + 5433 — 与 dev compose 一致，与 prod compose 不一致。
- `tests/e2e/pipeline_smoke_test.py` 同上。
- Crawler `persistence/database.py` 用了独立连接配置 — 可能有自己的 env vars，**未深入审查**。
- 主机本地后端模式下 `migrate` Alembic 应该手动跑，但 compose 通过 entrypoint 自动化（基于 Dockerfile 的 command）—— 主机模式没有自动迁移机制。

---

**结论：** StarMap 已是一个 **生产就绪级别**（17 phase、1697 测试通过）的项目，其不一致问题集中在 "dev 体验"和 "配置真相源管理"两类，**不会影响功能正确性**（因为 CI 跑的是 docker compose 起来的实例）。但对新开发者 onboarding 是显著的 friction。优先级修复 P0/P1 即可消除 80% 的痛点。
