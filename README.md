# 星图 StarMap —— 人才能力星云导航系统

## 这是什么

构建新一代信息技术领域岗位能力知识图谱，支持新岗位发现、既有岗位能力动态更新、全景图谱可视化、人岗匹配诊断。详见《星图-项目设计文档.docx》。

## 快速开始

### 启动模式

StarMap 支持三种互斥的启动方式。**所有三种模式连同一个 PostgreSQL `users` 表**，密码使用 bcrypt 哈希存储，登录后签发 access + refresh 双 JWT。

#### Mode A — Docker 全栈（推荐新手）

```bash
# 1. 配置环境
cp .env.example .env             # 默认 .env 已可工作；按需修改 SECRET_KEY / MIMO_API_KEY
# 2. 一键启动全栈
docker compose -f docker-compose.dev.yml up
```

容器启动时 `entrypoint.sh` 会自动运行 `bootstrap.py`：
1. `alembic upgrade head` 应用所有迁移
2. 如果 `BOOTSTRAP_SEED_ADMIN=true`（dev 默认），保证 `admin / starmap2024` 存在
3. 启动 uvicorn

服务地址：
- 前端：http://localhost:5173
- 后端 API 文档：http://localhost:8000/docs
- Neo4j 浏览器：http://localhost:7474 （neo4j / starmap123456）
- 就绪探针：http://localhost:8000/ready （返回所有依赖的检查结果）

#### Mode B — 主机本地后端 + Docker 数据栈

适合调试后端代码（热重载快、断点方便）：

```bash
# 1. 仅启动数据栈（PostgreSQL/Neo4j/Redis/Chroma/Ollama）
docker compose -f docker-compose.dev.yml up -d neo4j postgres redis chroma

# 2. 主机运行后端
cd backend
poetry install                   # 首次需要
python -m scripts.bootstrap      # 应用迁移 + 种子 admin（幂等）
poetry run uvicorn app.main:app --reload --port 8000

# 3. 主机运行前端
cd frontend
npm install                      # 首次需要
npm run dev                      # http://localhost:5173
```

数据栈端口映射（与 Mode A 相同，浏览器/vite 都能连）：
- PostgreSQL: `localhost:5433` (主机) → `5432` (容器)
- Neo4j Bolt: `localhost:7687`
- Redis: `localhost:6379`
- Chroma: `localhost:8001`

#### Mode C — 生产部署

```bash
# 在生产服务器，先生成强密钥
export POSTGRES_PASSWORD=$(openssl rand -hex 16)
export NEO4J_PASSWORD=$(openssl rand -hex 16)
export REDIS_PASSWORD=$(openssl rand -hex 16)
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# .env 必须 APP_ENV=production, APP_DEBUG=false
# BOOTSTRAP_SEED_ADMIN=false （生产环境用 admin API 创建用户，不自动 seed）
docker compose -f docker-compose.prod.yml up -d
```

生产模式启动时强校验：
- `SECRET_KEY` ≥ 32 字符
- `APP_DEBUG=false`
- Redis URI 必须含密码（`redis://:pwd@host:port/db`）
- 任何上述条件不满足 → 启动失败 fail-fast

## 认证 & 用户管理

- **登录**：`POST /api/v1/auth/login` → `{ access_token (15min), refresh_token (7d), user }`
- **刷新**：`POST /api/v1/auth/refresh` → 新 access_token
- **登出**：`POST /api/v1/auth/logout` → 吊销 refresh_token (Redis jti 黑名单)
- **当前用户**：`GET /api/v1/auth/me` → DB 真相（含 `must_change_password` 等生命周期字段）
- **改密自助**：`POST /api/v1/auth/change-password`
- **找回密码**：`POST /api/v1/auth/forgot-password` + `POST /api/v1/auth/reset-password`

### 企业级安全特性

- 5 次错密码 → 账号锁 15 分钟 (HTTP 423)
- admin 可在「用户管理」页一键解锁 / 重置密码 / 禁用
- 所有认证事件（登录成功 / 失败 / 锁定 / 解锁 / 改密）自动写入 `audit_events` 表
- admin 可在「审计日志」页按 `事件类型 / 操作人 / 时间区间` 过滤查询
- JWT 强制 `iss + aud + exp + iat + sub` claims；缺失任意一个 → 拒绝
- refresh_token 存 Redis (`refresh:{jti}`)；登出即从 Redis 删除

### 用户生命周期字段

PostgreSQL `users` 表字段（迁移 `014_extend_users_for_lifecycle.py`）：

| 字段 | 用途 |
|------|------|
| `email` | 找回密码目标 |
| `failed_login_attempts` | 暴力破解计数 |
| `locked_until` | 锁定到期时间 |
| `last_login_at` / `last_login_ip` | 审计 |
| `password_changed_at` | 密码轮换跟踪 |
| `must_change_password` | 首次登录强制改密 |
| `disabled_at` / `disabled_by` / `disabled_reason` | 软删除 + 操作溯源 |

## 项目结构

```
starmap/
├── backend/                # FastAPI 后端（流A/流B）
│   ├── app/
│   │   ├── api/v1/         # 路由（含 auth.py / admin_users.py）
│   │   ├── services/       # 服务层（auth_service.py 含完整认证业务）
│   │   ├── models/         # ORM（user.py 含企业字段）
│   │   ├── core/           # 业务核心
│   │   ├── dependencies.py # 认证依赖
│   │   ├── config.py       # Pydantic Settings
│   │   └── main.py         # FastAPI 入口（/health /ready）
│   ├── alembic/versions/   # 数据库迁移（最新 014）
│   ├── scripts/bootstrap.py # 容器启动幂等脚本
│   ├── entrypoint.sh       # 容器入口（先 bootstrap 再 exec CMD）
│   ├── Dockerfile          # 生产镜像
│   ├── Dockerfile.dev      # 开发镜像（热重载）
│   └── Dockerfile.celery   # Celery worker（Playwright + 反检测）
├── frontend/               # Vue 3 前端（流C）
│   ├── src/pages/          # UserManagement.vue, AuditLog.vue, Login.vue ...
│   ├── src/components/     # ProfileMenu.vue（顶栏下拉）
│   ├── src/stores/user.ts  # 双 token + /auth/me 同步
│   ├── src/composables/useAuthBootstrap.ts # 启动时静默 refresh
│   └── vite.config.ts      # 代理默认 → http://localhost:8000
├── crawler/                # 爬虫模块（流A）
├── evaluation/             # 评估脚本 + Golden Set（流D）
├── starmap-contracts/      # 接口契约（单一事实源，规范1）
├── docker-compose.dev.yml  # 开发环境编排（Mode A）
├── docker-compose.prod.yml # 生产部署（Mode C）
├── .env                    # Docker 模式环境变量（dev 默认值已就绪）
├── .env.example            # 三种模式的环境变量文档化
└── backend/.env            # Mode B 主机本地后端环境变量
```

## 工作流

| 流 | 组 | 范围 |
|----|----|------|
| A | 后端组 | 数据采集→图谱服务→API→部署 |
| B | 算法组 | 抽取→归一化→演化→匹配 |
| C | 前端组 | 组件库→图谱页→匹配页→看板 |
| D | QA | 评估方法学→Golden标注→评分→达标 |

优先级：**D > B > A > C**

## 强制协作纪律

1. **契约优先**：先改 `starmap-contracts/`，签字后再写代码
2. **模型变更管制**：走 Alembic 迁移，权限收归技术负责人+算法负责人
3. **Docker 开发**：依赖锁死版本（poetry.lock / package-lock.json）
4. **Mock 优先**：流C 用 MSW 独立开发，不依赖流B
5. **Trunk-based**：main 始终可运行，分支 ≤3天，PR 需 CI全绿+1人review
6. **进度可视**：任务进 GitHub Projects 看板，决策落文档附录D
7. **每日集成**：远程服务器每日拉main跑冒烟，当天问题当天修

**3 条永不可松绑的铁律**：① 契约优先 ② main 可运行 ③ 每日集成

## 测试 & 质量

```bash
# 后端
cd backend && poetry run pytest          # 1726 passed, 5 skipped
cd backend && poetry run ruff check .    # 全绿
cd backend && poetry run mypy app        # 全绿

# 前端
cd frontend && npm run test              # 226 passed
cd frontend && npm run typecheck         # 0 errors in 新文件
cd frontend && npm run lint              # 仅遗留 warning
```

## 文档

本项目采用「活文档 + 归档」治理，详见 [DOCUMENT_POLICY.md](DOCUMENT_POLICY.md)。

**活文档（当前真相，决策依据）**：
- [ONBOARDING.md](ONBOARDING.md) —— 项目认知入门（架构/数据流/成熟度/头号风险）
- [docs/standards/](docs/standards/) —— 全栈规范（顶部带 2026-07-16 硬数字核对表）
- [starmap-contracts/](starmap-contracts/) —— API 契约（单一事实源）
- [.planning/STATE.md](.planning/STATE.md) —— 进度真相
- [docs/星图-项目设计文档v2.0.md](docs/) —— 总纲设计

**归档区**（历史快照 / 过程产物，**不作当前依据**）：[docs/archive/](docs/archive/README.md)
