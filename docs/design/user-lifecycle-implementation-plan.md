# StarMap 用户闭环实施计划

**日期**: 2026-07-14
**状态**: 审计完成，待实施
**依据**: `login-module-redesign.md` (已批准) + 全栈代码审计

---

## 0. 审计摘要

### 现状 vs 设计目标

| 维度 | 设计目标 | 实际状态 | 差距 |
|------|---------|---------|------|
| 用户存储 | PostgreSQL `users` 表 | `AUTH_USERS` 环境变量 | 🔲 全部缺失 |
| JWT 机制 | Access(15min) + Refresh(7d) 双 Token | 单 JWT 24h TTL | 🔲 全部缺失 |
| 签发/验签 | 统一 PyJWT | ✅ 已统一 | 无 |
| Token 续期 | 401 自动 refresh + 防并发 | 401 直接跳登录 | 🔲 全部缺失 |
| 用户管理 | Admin Tab 5 (CRUD) | 无 | 🔲 全部缺失 |
| 修改密码 | ChangePasswordDialog + API | 无 | 🔲 全部缺失 |
| 登出 | POST /auth/logout + Redis 吊销 | 无 | 🔲 全部缺失 |
| dev-token | 仅 dev 环境 | ✅ 已隔离 | 无 |
| 前端登录 UI | Marble 风格左右分栏 | ✅ 已实现 | 无 |

### 设计文档 11 个新文件 — 全部未创建

| # | 文件 | 状态 |
|---|------|------|
| 1 | `backend/app/models/user.py` | 🔲 |
| 2 | `backend/app/services/auth_service.py` | 🔲 |
| 3 | `backend/alembic/versions/xxxx_add_users_table.py` | 🔲 |
| 4 | `backend/scripts/seed_admin.py` | 🔲 |
| 5 | `backend/tests/unit/test_auth_service.py` | 🔲 |
| 6 | `backend/tests/unit/test_auth_endpoints.py` | 🔲 |
| 7 | `backend/tests/unit/test_admin_user_endpoints.py` | 🔲 |
| 8 | `frontend/src/components/ChangePasswordDialog.vue` | 🔲 |
| 9 | `frontend/src/components/UserManagementPanel.vue` | 🔲 |
| 10 | `frontend/e2e/auth-flow.spec.ts` | 🔲 |
| 11 | `frontend/e2e/user-management.spec.ts` | 🔲 |

### 设计文档 12 个修改文件 — 3 个部分完成，9 个未动

| # | 文件 | 状态 | 缺失内容 |
|---|------|------|---------|
| 1 | `backend/app/api/v1/auth.py` | ⚠️ 部分 | 缺 refresh/logout/change-password，仍用 parsed_users |
| 2 | `backend/app/api/v1/admin.py` | 🔲 | 缺用户管理路由 |
| 3 | `backend/app/dependencies.py` | ⚠️ 部分 | 仍用 parsed_users，缺 auth_service 集成 |
| 4 | `backend/app/config.py` | 🔲 | 仍含 auth_users/parsed_users |
| 5 | `backend/.env` | 🔲 | 仍含 AUTH_USERS，缺 JWT 配置 |
| 6 | `frontend/src/pages/Login.vue` | ✅ UI 完成 | 缺双 token 存储 |
| 7 | `frontend/src/pages/Admin.vue` | 🔲 | 缺用户管理 Tab |
| 8 | `frontend/src/api/request.ts` | 🔲 | 缺 401 自动 refresh |
| 9 | `frontend/src/stores/user.ts` | 🔲 | 缺 token 管理扩展 |
| 10 | `frontend/src/layouts/MainLayout.vue` | 🔲 | 缺用户菜单下拉 |
| 11 | `starmap-contracts/openapi.yaml` | 🔲 | 缺新 API 契约 |
| 12 | `frontend/src/router/index.ts` | ⚠️ 部分 | isAuthed() 不检查过期 |

---

## 1. Bug 清单

| # | Bug | 严重性 | 位置 | 说明 |
|---|-----|--------|------|------|
| B1 | `AUTH_USERS` 环境变量仍在使用 | 🐛 高 | `.env:56`, `config.py`, `auth.py:55` | 密码泄漏到 git 历史，改密码需重启 |
| B2 | 单 JWT 24h TTL 无续期 | 🐛 高 | `auth.py` | 用户体验差，无法吊销 |
| B3 | 401 直接跳登录丢失用户工作 | 🐛 中 | `request.ts` | 无静默续期 |
| B4 | 无登出功能 | 🐛 中 | 前端无按钮，后端无接口 | 用户无法主动结束会话 |
| B5 | 无修改密码功能 | 🐛 中 | 前后端均无 | 用户管理残缺 |
| B6 | `verify_aud: False` | ⚠️ 低 | `dependencies.py:62` | JWT aud 不验证，降低安全性 |
| B7 | `isAuthed()` 不检查过期 | ⚠️ 低 | `router/index.ts` | 过期 token 通过路由守卫 |
| B8 | E2E 测试硬编码 dev-token | ⚠️ 低 | `data-integrity.spec.ts:37-38` | 测试与 dev-token 耦合 |

---

## 2. 未开放功能项

| # | 功能 | 说明 | 阻塞原因 |
|---|------|------|---------|
| F1 | 用户管理 CRUD | 新增/编辑/删除/重置密码 | 缺 users 表 + admin API |
| F2 | Token 自动续期 | 401 静默刷新 | 缺 refresh API + 前端拦截器 |
| F3 | 修改密码 | ChangePasswordDialog + API | 缺 change-password API |
| F4 | 登出 | POST /auth/logout + Redis 吊销 | 缺 API + 前端菜单 |
| F5 | 首次部署 seed | scripts/seed_admin.py | 缺脚本 |
| F6 | 用户菜单下拉 | MainLayout 右上角 | 缺 MainLayout 修改 |
| F7 | Admin 用户管理 Tab | Admin.vue 第 5 个 Tab | 缺 UserManagementPanel |
| F8 | 密码强度校验 | 前端强度条 + 后端最少 8 字符 | 缺 ChangePasswordDialog |
| F9 | Refresh Token 吊销 | Redis key 删除 | 缺 logout API |
| F10 | 生产环境 dev-token 隔离 | APP_ENV=production 时拒绝 | 已隔离但需验证 |

---

## 3. 实施路线图

严格按 `login-module-redesign.md` 的 Phase 1-5 顺序执行，每个 Phase 有明确的验收标准。

### Phase 1: 数据库层 (预计 2h)

**目标**: 创建 `users` 表 + Alembic 迁移 + seed 脚本

| 步骤 | 任务 | 文件 | 验收标准 |
|------|------|------|---------|
| 1.1 | 创建 User ORM 模型 | `backend/app/models/user.py` (新建) | 模型含 id/username/password_hash/role/is_active/created_at/updated_at |
| 1.2 | 注册到 `__init__.py` | `backend/app/models/__init__.py` | `__all__` 包含 User |
| 1.3 | Alembic 迁移 | `alembic/versions/xxxx_add_users_table.py` (新建) | `alembic upgrade head` 成功 |
| 1.4 | seed_admin 脚本 | `scripts/seed_admin.py` (新建) | `python scripts/seed_admin.py --username admin --password xxx` 成功插入 |

**验收**: `alembic upgrade head` + `seed_admin.py` 成功，`users` 表存在且有 admin 行

### Phase 2: 后端 Auth 服务层 (预计 4h)

**目标**: auth_service + 重构 auth.py + 扩展 admin.py + 清理 config

| 步骤 | 任务 | 文件 |
|------|------|------|
| 2.1 | 创建 auth_service | `backend/app/services/auth_service.py` (新建) |
| 2.2 | 重构 auth.py | `backend/app/api/v1/auth.py` |
| 2.3 | 扩展 admin.py | `backend/app/api/v1/admin.py` |
| 2.4 | 重构 dependencies.py | `backend/app/dependencies.py` |
| 2.5 | 删除 AUTH_USERS | `backend/app/config.py` + `.env` |
| 2.6 | 更新契约 | `starmap-contracts/openapi.yaml` |

**auth_service 函数清单**:
```
authenticate(username, password, db)
create_tokens(user, redis)
refresh_access_token(refresh_jwt, redis)
revoke_refresh_token(refresh_jwt, redis)
change_password(user, old_pwd, new_pwd, db)
list_users(db) / create_user() / update_user() / delete_user() / reset_password()
```

**验收**: pytest 全通过 (新 test_auth_service.py + test_auth_endpoints.py + test_admin_user_endpoints.py)

### Phase 3: 前端闭环 (预计 3h)

**目标**: 双 Token 存储 + 401 自动 refresh + 用户菜单 + Admin Tab

| 步骤 | 任务 | 文件 |
|------|------|------|
| 3.1 | user store 扩展 | `frontend/src/stores/user.ts` |
| 3.2 | request.ts 401 拦截器 | `frontend/src/api/request.ts` |
| 3.3 | Login.vue 双 Token | `frontend/src/pages/Login.vue` |
| 3.4 | Admin.vue 用户管理 Tab | `frontend/src/pages/Admin.vue` |
| 3.5 | ChangePasswordDialog | `frontend/src/components/ChangePasswordDialog.vue` (新建) |
| 3.6 | UserManagementPanel | `frontend/src/components/UserManagementPanel.vue` (新建) |
| 3.7 | MainLayout 用户菜单 | `frontend/src/layouts/MainLayout.vue` |
| 3.8 | router isAuthed 增强 | `frontend/src/router/index.ts` |

**验收**: 登录→使用→401自动续期→登出 完整闭环

### Phase 4: 测试 (预计 2h)

| 步骤 | 任务 | 文件 |
|------|------|------|
| 4.1 | 后端单测 | test_auth_service.py, test_auth_endpoints.py, test_admin_user_endpoints.py |
| 4.2 | 前端单测 | Login.spec.ts, user.test.ts 扩展, request.test.ts |
| 4.3 | E2E 测试 | auth-flow.spec.ts, user-management.spec.ts |
| 4.4 | 全量回归 | pytest + vitest + Playwright |

**验收**: 所有测试通过，163 后端 + 31 前端 + E2E 无回归

### Phase 5: 验证 & 清理 (预计 1h)

| 步骤 | 任务 |
|------|------|
| 5.1 | 浏览器手动验证完整闭环 |
| 5.2 | grep 确认 AUTH_USERS 完全移除 |
| 5.3 | 生产环境 dev-token 拒绝验证 |
| 5.4 | Docker 全栈 smoke test |

---

## 4. 工时估算

| Phase | 内容 | 预计工时 |
|-------|------|---------|
| Phase 1 | 数据库层 | 2h |
| Phase 2 | 后端 Auth | 4h |
| Phase 3 | 前端闭环 | 3h |
| Phase 4 | 测试 | 2h |
| Phase 5 | 验证清理 | 1h |
| **总计** | | **12h** |

---

## 5. 风险项

| 风险 | 缓解 |
|------|------|
| Alembic 迁移与现有数据冲突 | 迁移脚本幂等 (IF NOT EXISTS) |
| Redis 不可用时 refresh 失效 | 降级：access 过期即重登录，登录流程不受影响 |
| 前端 localStorage XSS | access 短 TTL(15min) 缩小窗口 |
| E2E 测试 dev-token 硬编码 | 保留 dev-token 用于测试环境，生产隔离 |
| 现有用户被踢出 | seed 脚本支持从 AUTH_USERS 导入 |