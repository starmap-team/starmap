# StarMap — 完整启动一致性修复 + 企业级 Auth/用户生命周期 改造计划

## 项目目标
1. **三类启动模式都能工作**且行为/数据/版本一致 — Docker 全栈、主机本地 + Docker DB、生产部署
2. **Auth 改为数据库 + bcrypt**，彻底废弃 `AUTH_USERS` 环境变量
3. **企业级用户生命周期**：access + refresh token、登录锁限、密码策略、admin 用户管理、审计可查
4. **三种模式实际跑通验证**

---

## A. 修复启动一致性（启动方式统一）

### A.1 自动初始化入口（一次性幂等脚本）
新建 `backend/scripts/bootstrap.py`，包含以下子任务，按依赖顺序执行：

| 步骤 | 内容 | 幂等性 | 错误处理 |
|------|------|--------|----------|
| 1 | `alembic upgrade head` (读写 `backend/alembic.ini`) | ✅ Alembic 天然幂等 | 失败抛错，容器重启即可 |
| 2 | 初始化 Neo4j 约束/索引（迁移 `scripts/init_neo4j_schema.py` 的核心逻辑到 backend） | ✅ CREATE … IF NOT EXISTS | 失败 warn 不阻断（Neo4j 业务暂未依赖） |
| 3 | seed admin 用户（若 `users` 表为空） | ✅ 检查后插入 | 失败抛错 |
| 4 | 检查 `app_admin` 默认角色存在 | ✅ | warn |

调用方式：`poetry run python -m scripts.bootstrap` 或容器内 `python -m scripts.bootstrap && uvicorn …`

### A.2 修改三个 Dockerfile + compose
**`backend/Dockerfile.dev` & `backend/Dockerfile`（生产）**：
- 全部使用统一的 `entrypoint.sh`，先 `bootstrap.py`，再 exec `uvicorn` / `celery`

**新增 `backend/entrypoint.sh`**：
```bash
#!/bin/sh
set -e
echo "[entrypoint] bootstrapping…"
python -m scripts.bootstrap
echo "[entrypoint] bootstrap done, exec $*"
exec "$@"
```

**`docker-compose.dev.yml`**：
- `backend.command` → `entrypoint.sh uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload …`
- `celery-worker.command` → `entrypoint.sh celery -A app.tasks…`
- `frontend.depends_on.backend` → 加 `condition: service_healthy`（修原报告 P0.2）
- 给 frontend 加 healthcheck：`wget http://localhost:5173`（dev compose 现没有）

**`docker-compose.prod.yml`**：
- backend/celery 同样切到 entrypoint
- 保留已有 healthcheck 与 depends_on

### A.3 Vite 代理修复（P0.1）
**`frontend/vite.config.ts`**：
```ts
target: process.env.VITE_API_BASE_URL || 'http://localhost:8000',  // 8002 → 8000
```
保留 env override；删除残留 "backend-dev" 注释

### A.4 `.env` 文件真相源梳理
| 文件 | 用途 | 处理 |
|------|------|------|
| `.env.example` | 已提交模板（仅文档） | 保留 |
| `.env` | Docker 全栈用（含 `POSTGRES_HOST=postgres` 等 docker 服务名） | 保留，新文档明确 |
| `backend/.env` | 主机本地后端用（含 `POSTGRES_PORT=5433`，HOST=localhost） | 保留，补 `AUTH_USERS` 注释 "已废弃，使用 DB" |
| `backend/.env.local` | 主机本地 DB 端口定制 | 保留 |
| `.env.local`、`backend/.env.local`（重复名冲突） | 删除 — 与上述重名会引起混淆 | 删除两个 `.env.local` |
| `.env.docker` | 老旧残留（已被 `.env` 替代） | 删除 |

**.gitignore** 已正确忽略所有本地文件。

### A.5 `config.py` 修复
- `POSTGRES_PORT` 默认值改为 `5433`（与 Windows 主机约定对齐）。Docker 模式下 `.env` 显式覆盖为 5432，行为不变
- 删除 `auth_users` 字段、删除 `parsed_users` 属性、删除 plaintext 校验逻辑（不再有 AUTH_USERS）
- `cors_origins` 默认加 `http://frontend`、`http://starmap-frontend`（dev compose 服务名）
- `redis_uri` 默认 `redis://localhost:6379/0` 不变

---

## B. Auth 迁移到数据库 + 企业级增强

### B.1 User 模型扩展
新建迁移 `014_extend_users_for_lifecycle.py`：

| 字段 | 类型 | 用途 |
|------|------|------|
| `email` | String(120) UNIQUE nullable | 找回密码 / 通知 |
| `failed_login_attempts` | Integer default 0 | 锁限触发 |
| `locked_until` | DateTime nullable | 锁定到期时间 |
| `last_login_at` | DateTime nullable | 审计 |
| `last_login_ip` | String(45) nullable | 审计 |
| `password_changed_at` | DateTime nullable | 强制改密 |
| `must_change_password` | Boolean default False | 首次登录强制 |
| `disabled_at` | DateTime nullable | 软删除 |
| `disabled_by` | UUID FK→users.id nullable | 操作者 |
| `disabled_reason` | String(255) nullable | 原因 |

修改 `backend/app/models/user.py` 加 `Enum("admin","user")` 或 `CheckConstraint`；并把 `User` 加入 `models/__init__.py` 的 `__all__`

### B.2 Auth Service 增强（`backend/app/services/auth_service.py`）
新函数（已有函数扩展 + 新增）：
- `authenticate(...)` → 失败时 `failed_login_attempts +=1`；达 5 次写 `locked_until=now+15min`
- `authenticate(...)` → 成功时重置计数 + 写 `last_login_at`/`last_login_ip`
- `authenticate(...)` → 锁限中：`raise LoginLockedError(until=…)`
- 新 `forgot_password_request(email)` → 写 Redis token，发送重置链接（占位：仅返回 token）
- 新 `reset_password_with_token(token, new_pwd)` → Redis token 校验后改密
- `change_password(...)` 同时更新 `password_changed_at`

### B.3 新增 HTTP 路由（拆分文件）
**`backend/app/api/v1/auth.py`** — 改写为薄路由：
```python
POST /auth/login           → 调用 auth_service.authenticate + create_tokens
POST /auth/refresh         → 调用 auth_service.refresh_access_token
POST /auth/logout          → 调用 auth_service.revoke_refresh_token
POST /auth/change-password → self-service，需 get_current_user
POST /auth/forgot-password → email-based，发送重置 token
POST /auth/reset-password  → token-based 改密
GET  /auth/me              → 返回当前用户（DB truth，非 JWT 解析）
```

**`backend/app/api/v1/admin_users.py`** 新文件：
```python
GET    /admin/users                  → list（分页/搜索/过滤）
POST   /admin/users                  → create
GET    /admin/users/{id}             → detail
PATCH  /admin/users/{id}             → role / is_active / must_change_password
DELETE /admin/users/{id}             → soft-delete
POST   /admin/users/{id}/unlock      → 解除锁限
POST   /admin/users/{id}/reset-password  → admin 重置
GET    /admin/audit-events           → 查询审计（分页/过滤 actor/event/time）
```
全部 `require_admin` 守护。审计查询使用 `audit_events` 表（已存在）。

注册到 `api_router`：`api_router.include_router(admin_users.router, prefix="/admin/users", tags=["用户管理"])`

### B.4 `dependencies.py` 改造
- 删除 `dev-token` 直通（仍保留 dev 环境无 token 默认 dev 用户，便于调试）
- 解码器统一调 `auth_service.decode_token`（保持 aud/iss 强制）
- `get_current_user_sse` 同样走统一解码

### B.5 审计增强
- `auth_service.authenticate` 失败 → `AuditEvent.AUTH_FAILURE`，detail 含 username/IP
- 锁限触发 → `AuditEvent.RATE_LIMITED`，detail "account locked"
- 密码改 → `AuditEvent.SENSITIVE_WRITE`
- 角色/状态改 → `AuditEvent.ADMIN_ACTION`

---

## C. 前端用户管理 UI

### C.1 Auth 状态增强
- `frontend/src/stores/user.ts` 增加 `access_token`/`refresh_token`/`expires_at` ref
- `logout()` 调用 `POST /auth/logout`
- 401 拦截器：尝试 `POST /auth/refresh` 一次后重试；过期则清除
- 新增 `initFromServer()`：app 启动调 `GET /auth/me` 同步服务端 truth，取代客户端 JWT 解析的 user 角色

### C.2 新增页面（最小可用）
**`frontend/src/pages/UserManagement.vue`** — admin tab 加到 `Admin.vue` 第 5 个 tab：
- `el-table` 展示用户列表（username、role、is_active、last_login_at）
- 搜索框（按 username） + 状态筛选（active/locked/disabled）
- 行操作：禁用/启用、改角色、解锁、重置密码
- 新建用户 dialog（用户名/email/密码/角色）

**`frontend/src/pages/AuditLog.vue`** — admin 第 6 个 tab：
- `el-table` 展示 `audit_events`
- 过滤：event type、actor、时间区间
- 仅 admin 可见

**`frontend/src/components/ProfileMenu.vue`** — 顶栏右上角下拉：
- 显示当前用户
- 「修改密码」→ dialog 调 `/auth/change-password`
- 「退出登录」→ 调 `/auth/logout`
- 接入 `MainLayout.vue`

### C.3 路由 + menu
- `frontend/src/router/index.ts` 注册 `/admin/users`、`/admin/audit-log`
- `Admin.vue` tabs 加这两个组件
- `MainLayout.vue` 顶栏接入 `<ProfileMenu />`

---

## D. 主机本地模式 B 文档化

`backend/README.md` 与根 `README.md` 新增 `## 启动模式` 段，详细列出 3 种模式：
- Mode A: `docker compose -f docker-compose.dev.yml up`
- Mode B: `docker compose -f docker-compose.dev.yml up neo4j postgres redis chroma -d` 然后主机 `poetry run uvicorn …`
- Mode C: `docker compose -f docker-compose.prod.yml up -d`

每个模式包含：端口映射 / 凭据来源 / 初始化方式 / 访问 URL / 注意事项。

---

## E. 验证（必须全部 3 种模式跑通）

每个模式执行以下 checklist（脚本化保存到 `tests/e2e/startup_smoke.py`）：

```
1. 所有容器/进程启动 → docker compose ps / pgrep uvicorn
2. /health 端点 200
3. 等待 /ready 端点（新增，见下）返回 ok（含 alembic head + admin seeded）
4. PostgreSQL: SELECT COUNT(*) FROM users >= 1
5. Neo4j 约束存在
6. POST /api/v1/auth/login admin/starmap2024 → 200 + JWT
7. GET /api/v1/auth/me → 返回 admin
8. 创建新 user → 登录新 user → 修改密码 → 登出/登入 OK
9. Admin 创建 user 后禁用 → 该 user 登录被拒
10. POST /admin/users/{id}/reset-password → 新密码可登录
11. 5 次错密码 → locked → /admin/users/{id}/unlock → 可登录
12. /admin/audit-events 显示上述事件
13. 前端 vite dev server 起来 → /login 页面 200 → 输入凭据 → 跳首页
14. curl 首页 healthcheck 200（docker 模式）
```

F. **新增 `/ready` 端点**（在 main.py）
检测项：
- `alembic_version` 行存在 + 当前 revision == head
- `SELECT 1 FROM users` 返回 ≥ 1
- Neo4j 至少 1 个约束存在

未通过返回 503 + 详细哪个检查失败。docker healthcheck 也可切换到 `/ready`（dev 暂用 `/health`，prod 用 `/ready`）。

---

## G. 修复清单（按文件）

### 新增文件
- `backend/scripts/bootstrap.py` — 启动引导
- `backend/entrypoint.sh` — 容器入口
- `backend/scripts/init_neo4j_schema_internal.py` — Neo4j 约束（搬到 backend）
- `backend/alembic/versions/014_extend_users_for_lifecycle.py` — DB migration
- `backend/app/api/v1/admin_users.py` — 用户管理路由
- `backend/app/exceptions_auth.py` — `LoginLockedError` 等业务异常
- `backend/tests/unit/test_auth_db_endpoints.py` — 新路由单测
- `frontend/src/pages/UserManagement.vue`
- `frontend/src/pages/AuditLog.vue`
- `frontend/src/components/ProfileMenu.vue`
- `frontend/src/composables/useAuthBootstrap.ts` — 启动时 /auth/me + 静默 refresh
- `tests/e2e/startup_smoke.py` — 三模式 smoke

### 修改文件
- `backend/Dockerfile.dev`、`backend/Dockerfile`、`backend/Dockerfile.celery` — 用 entrypoint.sh
- `docker-compose.dev.yml`、`docker-compose.prod.yml` — 切 command、加 frontend depends_on/健康检查
- `frontend/vite.config.ts` — 8002 → 8000
- `backend/app/config.py` — 删 auth_users，POSTGRES_PORT→5433，加 CORS
- `backend/app/api/v1/auth.py` — 改写为 thin router，调用 auth_service
- `backend/app/services/auth_service.py` — 加锁限/审计/用户生命周期
- `backend/app/models/user.py` — 加企业字段 + Enum
- `backend/app/models/__init__.py` — 导出 User
- `backend/app/dependencies.py` — 统一解码器
- `backend/app/main.py` — lifespan 调 bootstrap()（fallback 给非容器启动）；新增 `/ready`
- `backend/app/utils/audit.py` — 加 `AuditEvent.LOGIN_LOCKED`、`PASSWORD_RESET`、`USER_CREATED`
- `backend/app/api/v1/router.py` — 注册 admin_users
- `frontend/src/stores/user.ts` — refresh/logout/`/auth/me`
- `frontend/src/api/request.ts` — refresh interceptor
- `frontend/src/pages/Admin.vue` — 加两个 tab
- `frontend/src/layouts/MainLayout.vue` — 接入 ProfileMenu
- `frontend/src/router/index.ts` — 注册新路由
- `.env.example`、`backend/.env` — 注释清除 AUTH_USERS
- 删除：`.env.local`、`backend/.env.local`、`.env.docker`（与新增真相源冲突）
- `backend/README.md`、`README.md` — 文档化三种模式

---

## H. 验证 commit 节点
执行顺序（每完成一组跑对应测试）：
1. Phase 1 — DB auth 改造 + admin_users + auth.py + dependencies.py → `pytest tests/unit/test_auth* tests/unit/test_admin_users*.py -q`
2. Phase 2 — bootstrap.py + entrypoint + alembic 自动 + init_neo4j_internal + main.py `/ready` → Mode A 启动验证
3. Phase 3 — 前端 UserManagement + AuditLog + ProfileMenu + refresh → `npm run test` + Mode A E2E
4. Phase 4 — Mode B 主机本地后端验证
5. Phase 5 — Mode C 生产验证

每阶段结束要求 reachest risk test 为绿，否则不进入下阶段。

---

## I. 不在本轮范围（明确划线）
- 邮件实际发送（仅留 token 占位 + log）
- MFA / TOTP
- OAuth / SSO / SAML
- Audit 日志的导出（CSV/Excel）
- 用戶头像 / locale / timezone（结构加好字段即可）
- `pip install` 同步性（已经用 Poetry 锁）
- Crawler 业务（明确不接触用户）

---

## J. 风险与权衡
1. **异步 alembic upgrade 在 lifespan 中的稳定性**：fastapi lifespan 已经是 async，alembic 命令同步执行 — 用 `asyncio.to_thread(upgrade_head)` 包一层，避免阻塞事件循环
2. **dev-token 直通删除风险**：当前开发依赖此 token 跨服务调试，删除后开发者需确认数据库 seed 成功，否则 login 全挂 — `bootstrap.py` 失败时清晰告警
3. **生产环境首次启动种子**：首次 prod 启动会自动 seed admin/starmap2024，**安全风险** — 增加 `BOOTSTRAP_SEED_ADMIN` env，默认 `false`，仅 dev/内部环境开启
4. **`/ready` 与 docker healthcheck**：dev 端 compose 改用 `/ready` 会拖慢冷启动（首次需要等 migration） — 接受，文档化

---

## K. 完成标准
- 三种模式均能 `pytest tests/e2e/startup_smoke.py -m mode_a|mode_b|mode_c` 通过
- 完整 admin-user CRUD + lockout + reset password + audit 查询 UI 可用
- CI 现有 1697 测 + 新测试全绿
- ruff/mypy/vue-tsc/eslint 全绿
