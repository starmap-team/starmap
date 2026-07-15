# 登录模块完整闭环设计

**日期**: 2026-07-13
**状态**: 已批准，待实现
**作用域**: 登录、令牌管理、用户管理、首次部署 seed、前端 UI 设计

---

## 1. 背景与目标

### 现状问题（6 个）

| # | 问题 | 业务影响 |
|---|------|---------|
| 1 | 用户名密码硬编码在 `.env` 的 `AUTH_USERS` 中 | 改密码需重启服务；密钥泄漏到 git 历史 |
| 2 | `auth.py` 用 PyJWT 签发，`dependencies.py` 用手动 HMAC 验签 | 签发/验签实现不一致，生产可能验签失败 |
| 3 | dev-token 是万能钥匙，传任何接口都返回 admin | 开发便利但易泄漏到生产 |
| 4 | JWT 过期只能重新登录 | 用户体验差，会话中断 |
| 5 | 没有"修改密码"功能 | 用户管理残缺 |
| 6 | 没有用户管理界面 | 加用户需改数据库 |

### 设计目标

- 用户存储迁移到 PostgreSQL，支持运行时增删改
- JWT 签发/验签统一用 PyJWT
- 引入 access/refresh 双令牌机制，支持自动续期和吊销
- 提供完整的用户管理前端界面
- 彻底移除 `AUTH_USERS` 环境变量
- 保留 dev-token 开发便利，生产环境严格隔离

---

## 2. 业务架构

### 用户生命周期

```
首次部署 → scripts/seed_admin.py → PG users 表写入初始 admin
                                            ↓
                                         admin 登录
                                            ↓
                                  Admin 页管理其他用户
                                            ↓
                          ┌─ 新增用户（bcrypt 加密入库）
                          ├─ 修改角色/禁用
                          ├─ 重置密码
                          └─ 修改自己的密码
```

### 登录与会话

```
用户登录 → 后端 PG 查用户 → bcrypt 比对密码
                                ↓
                            通过？
                                ↓ 是
                ┌─ 签发 access_token (15min)
                └─ 签发 refresh_token (7d)，jti 存 Redis
                                ↓
                    返回给前端 → localStorage 存
                                ↓
                          跳转首页
```

### Token 自动续期

```
前端请求接口 → 后端验证 access_token
                                    ↓
                                已过期？
                                    ↓ 是
                ┌─ 前端拦截 401 → 自动用 refresh 换新 access
                ├─ 后端检查 Redis 中 refresh jti 是否被吊销
                ├─ 未吊销 → 签发新 access
                └─ 前端用新 access 重试原请求，用户无感知
```

### 登出

```
用户点登出 → POST /auth/logout (传 refresh)
                                  ↓
                          后端删除 Redis 中 refresh jti
                                  ↓
                          前端清 localStorage → 跳登录页
```

---

## 3. 数据模型

### `users` 表

```sql
CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(128) NOT NULL,
    role          VARCHAR(16) NOT NULL DEFAULT 'user',  -- admin | user
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### Redis refresh token 存储

```
Key:   refresh:{jti}
Value: user_id
TTL:   7 天（与 refresh_token 过期时间一致）
```

---

## 4. API 设计

| 方法 | 路径 | 用途 | 认证要求 |
|------|------|------|---------|
| POST | `/auth/login` | 用户名密码登录，返回 access + refresh | 无 |
| POST | `/auth/refresh` | 用 refresh 换新 access | refresh_token |
| POST | `/auth/logout` | 吊销 refresh | access_token |
| POST | `/auth/change-password` | 修改当前用户密码 | access_token |
| POST | `/admin/users` | 新增用户 | access_token + admin |
| GET | `/admin/users` | 用户列表 | access_token + admin |
| PATCH | `/admin/users/{id}` | 修改角色/状态 | access_token + admin |
| DELETE | `/admin/users/{id}` | 删除用户 | access_token + admin |
| POST | `/admin/users/{id}/reset-password` | 重置密码 | access_token + admin |

### 请求/响应体

```typescript
// POST /auth/login
Request:  { username: string, password: string }
Response: { access_token: string, refresh_token: string, expires_in: number, user: { username, role } }

// POST /auth/refresh
Request:  { refresh_token: string }
Response: { access_token: string, expires_in: number }

// POST /auth/logout
Request:  { refresh_token: string }
Response: 204

// POST /auth/change-password
Request:  { old_password: string, new_password: string }
Response: 204
```

---

## 5. 后端实现

### 5.1 模块职责

| 模块 | 文件 | 职责 |
|------|------|------|
| ORM 模型 | `backend/app/models/user.py` (新建) | User 表映射 |
| 服务层 | `backend/app/services/auth_service.py` (新建) | 认证业务逻辑 |
| 路由层 | `backend/app/api/v1/auth.py` (重构) | HTTP 接口 |
| 路由层 | `backend/app/api/v1/admin.py` (扩展) | 用户管理接口 |
| 依赖注入 | `backend/app/dependencies.py` (重构) | 统一 PyJWT 验签 |
| 配置 | `backend/app/config.py` (删除字段) | 移除 `auth_users`/`parsed_users` |
| 迁移 | `alembic/versions/xxxx_add_users_table.py` (新建) | 建表 |
| Seed | `scripts/seed_admin.py` (新建) | 首次部署创建 admin |

### 5.2 服务层核心函数

```
auth_service
├── authenticate(username, password, db) -> User | None
│     PG users 表查询 + bcrypt 验证
├── create_tokens(user, redis) -> {access_token, refresh_token, expires_in}
│     PyJWT 签发 access(15min) + refresh(7d)
│     refresh 的 jti 存 Redis: refresh:{jti} = user_id, TTL=7d
├── refresh_access_token(refresh_jwt, redis) -> {access_token, expires_in} | None
│     验证 refresh 未过期 + Redis 中 jti 存在
│     签发新 access_token（不轮换 refresh）
├── revoke_refresh_token(refresh_jwt, redis) -> None
│     从 Redis 删除 refresh:{jti}
├── change_password(user, old_pwd, new_pwd, db) -> bool
│     验证旧密码 + bcrypt 加密新密码 + 更新 PG
├── list_users(db) -> list[User]
├── create_user(username, password, role, db) -> User
├── update_user(id, role, is_active, db) -> User
├── delete_user(id, db) -> None
└── reset_password(id, new_password, db) -> None
```

### 5.3 依赖注入层

```python
# 统一用 PyJWT.decode() 验签
def get_current_user(credentials) -> dict:
    if credentials is None:
        if settings.app_env != "production":
            return {"sub": "dev", "role": "admin", "username": "developer"}
        raise 401

    token = credentials.credentials
    if settings.app_env != "production" and token == "dev-token":
        return {"sub": "dev", "role": "admin", "username": "developer"}

    return auth_service.decode_and_validate(token)  # 抛异常由上层处理
```

### 5.4 安全策略

| 项目 | 措施 |
|------|------|
| 密码存储 | 纯 bcrypt hash，cost factor=12 |
| access TTL | 15 分钟 |
| refresh TTL | 7 天 |
| JWT 签发 | PyJWT encode/decode，HS256 |
| JWT claims | `sub, role, username, exp, iat, nbf, iss, aud, jti` |
| dev-token | 仅 `app_env != "production"` 生效 |
| 密码强度 | 最少 8 位，注册/重置时校验 |
| refresh 吊销 | Redis key 删除即失效 |

---

## 6. 前端实现

### 6.1 Login.vue 修改

登录成功后存储：
```typescript
localStorage.setItem('starmap_token', accessToken)
localStorage.setItem('starmap_refresh', refreshToken)
localStorage.setItem('starmap_token_expires', Date.now() + expiresIn * 1000)
```

### 6.2 request.ts 拦截器改造

401 自动 refresh + 防并发刷新：

```typescript
// 核心状态机
let isRefreshing = false
let refreshSubscribers: Array<(token: string) => void> = []

function subscribeTokenRefresh(cb: (token: string) => void) {
  refreshSubscribers.push(cb)
}
function onTokenRefreshed(newToken: string) {
  refreshSubscribers.forEach(cb => cb(newToken))
  refreshSubscribers = []
}

response.use(
  (resp) => resp.data,
  async (error) => {
    if (error.response?.status === 401) {
      if (isLoginEndpoint) {
        return Promise.reject(error)
      }
      const refreshToken = localStorage.getItem('starmap_refresh')
      if (!refreshToken) {
        clearAuth(); router.push('/login')
        return Promise.reject(error)
      }
      if (!isRefreshing) {
        isRefreshing = true
        try {
          const { access_token } = await axios.post('/auth/refresh', { refresh_token: refreshToken })
          localStorage.setItem('starmap_token', access_token)
          onTokenRefreshed(access_token)
        } catch {
          clearAuth(); router.push('/login')
          return Promise.reject(error)
        } finally { isRefreshing = false }
      }
      // 排队等待 refresh 完成
      return new Promise(resolve => {
        subscribeTokenRefresh((newToken: string) => {
          error.config.headers.Authorization = `Bearer ${newToken}`
          resolve(request(error.config))
        })
      })
    }
    return Promise.reject(error)
  }
)
```

### 6.3 Admin.vue — 用户管理 Tab

新增第 5 个 Tab "用户管理"（与现有"图谱节点管理"Tab 结构对称）：
- el-table 列：username | role (el-tag) | is_active (el-switch) | created_at | 操作
- "新增用户"按钮 → el-dialog 表单 (username + password + role select)
- 行内操作：编辑（角色/状态）、重置密码、删除
- 所有操作调用 `/admin/users/*` 接口

### 6.4 右上角用户菜单

MainLayout.vue sidebar-footer 区域新增 el-dropdown：
```
┌─ [用户名] admin ▾
│   ├─ 修改密码        → ChangePasswordDialog.vue
│   ├─ ─────────
│   └─ 退出登录        → POST /auth/logout + clearAuth()
└─ [🌙 深色模式]
```

### 6.5 user store 扩展

```typescript
userStore = {
  // 已有
  user, isAdmin, isLoggedIn,
  initUser, clearUser, logout,

  // 新增
  accessToken: ref<string>(''),
  refreshToken: ref<string>(''),
  expiresAt: ref<number>(0),

  setTokens(access, refresh, expiresIn),
  refreshAccessToken(),
  isTokenExpired(),
  changePassword(oldPwd, newPwd),
}
```

---

## 6A. 前端 UI 设计规范

> 参考 Marble (withmarble.com) 的视觉语言，统一 StarMap 登录页与全景图谱的设计风格。
> Marble 的 3D 知识图谱可视化是其核心交互：每个点是一个 micro-topic，按学科着色，
> 高度=年龄，每条线是前置依赖。StarMap 的全景图谱与之同构（节点=技能/岗位/领域，
> 边=依赖/包含关系），因此视觉语言可直接复用。

### 6A.1 设计原则（源自 Marble）

| 原则 | Marble 体现 | StarMap 对应 |
|------|-----------|-------------|
| **数据即界面** | 3D 图即全部 UI，无管理壳 | 全景图谱 Home 页以 Graph3D 为视觉中心，KPI 条带仅作辅助 |
| **沉浸式交互** | Drag 旋转 / Right-drag 平移 / Scroll 缩放 / Tap 详情 | Graph3D 已支持：auto-rotate / camera-presets / node-click → DetailPanel |
| **语义着色** | 节点按学科着色（Science=绿, Math=蓝, English=橙...） | 节点按类型着色（Domain=青色大球, Position=蓝色中球, Skill=白色小球） |
| **极简入口** | 课程页只有一段话 + 交互提示 | 登录页：品牌视觉锚点 + 极简表单，无多余链接 |
| **深色优先** | 深色背景突出发光节点 | StarMap 已有 dark mode + `--dash-surface` 沉浸式 token |

### 6A.2 登录页 UI 设计

**布局：左右分栏（大屏）/ 单栏居中（移动端）**

```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│   ┌──────────────────────┐   ┌────────────────────────┐  │
│   │                      │   │                        │  │
│   │   ○ · ·  ·          │   │  登录                  │  │
│   │   3D 粒子背景        │   │                        │  │
│   │   (复用 Graph3D      │   │  ┌──────────────────┐  │  │
│   │    的场景渲染引擎,   │   │  │ 👤 用户名        │  │  │
│   │    预加载全景图谱    │   │  └──────────────────┘  │  │
│   │    数据, 登录后     │   │  ┌──────────────────┐  │  │
│   │    无感切换)        │   │  │ 🔒 密码     👁   │  │  │
│   │                      │   │  └──────────────────┘  │  │
│   │   ⭐ StarMap 星图    │   │  ┌──────────────────┐  │  │
│   │   "导航你的能力宇宙" │   │  │     登 录        │  │  │
│   │                      │   │  └──────────────────┘  │  │
│   └──────────────────────┘   │                        │  │
│                               │  深色模式 · v1.0       │  │
│                               └────────────────────────┘  │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

**关键设计细节**：

| 元素 | 规格 | 复用来源 |
|------|------|---------|
| 左侧 3D 背景 | 复用 `Graph3D.vue`，auto-rotate=true，节点数限制=200，opacity=0.3 | 已有组件 |
| 品牌标题 | `--text-display-xl` (36px) / `--weight-extrabold` / `--foreground` | design-tokens.css |
| 副标题 | `--text-body` (14px) / `--weight-medium` / `--muted-foreground` | design-tokens.css |
| 登录卡片 | `background: --surface-1` / `border-radius: --radius-panel` / `box-shadow: --shadow-float` | design-tokens.css |
| 输入框 | Element Plus `el-input` size=large / `--radius-button` | 已有组件 |
| 登录按钮 | `type=primary` / `width=100%` / 渐变背景 `--chart-1 → --chart-2` | chartColors |
| 深色切换 | 右下角小字链接，复用 MainLayout 的 `toggleDarkMode()` | 已有逻辑 |

**交互细节**：
- 登录失败：保留用户名输入，仅清空密码（减少重试摩擦）
- 登录成功：左侧 3D 背景渐变为全景图谱（opacity 0.3→1.0），右侧卡片 fade-out，实现"登录即进入图谱"的无感过渡
- 键盘：Enter 键提交；Tab 键在用户名↔密码↔按钮间切换

### 6A.3 全景图谱 Home 页 UI（与 Marble 对齐）

StarMap 的 Home.vue 已有 Graph3D + KPI Strip + DetailPanel + SearchBar 的布局，
与 Marble 的 curriculum 页面高度同构。以下是对齐点：

| Marble 交互 | StarMap 现状 | 对齐动作 |
|------------|-------------|---------|
| Drag 旋转 | Graph3D auto-rotate + OrbitControls | ✅ 已有 |
| Tap 节点看前置依赖 | node-click → DetailPanel | ✅ 已有 |
| 按学科着色 | `nodeColor()` 按 type 着色 | ✅ 已有 |
| 高度=年龄 | 无（3D 布局用 force-directed） | 可选：z 轴映射 proficiency |
| "0 concepts and 0 prerequisite links" 统计 | HomeKpiStrip (totalDomains/Positions/Skills/Relations) | ✅ 已有 |
| "Drag to spin · Right-drag to pan" 交互提示 | GraphToolbar 已有 | ✅ 已有 |
| 深色背景 + 发光节点 | dark mode + `--dash-accent-*` glow tokens | ✅ 已有 |

**唯一差距**：Marble 的节点按年龄分层（z 轴），StarMap 当前是纯 force-directed。
可选增强：将 `proficiency` 映射到 z 轴（初级在下/高级在上），形成"能力阶梯"视觉效果。

### 6A.4 Admin 用户管理 Tab UI

完全复用 Admin.vue 现有 CRUD 模式，与"图谱节点管理"Tab 对称：

```
┌─────────────────────────────────────────────────────────┐
│ 审核队列 │ 图谱节点管理 │ 数据源配置 │ Prompt管理 │ 用户管理 │
└─────────────────────────────────────────────────────────┘

Tab 5: 用户管理
┌───────────────────────────────────────────────────────┐
│  [新增用户]                                            │
│  ┌──────┬────────┬──────┬─────────┬────────────────┐ │
│  │ 用户名 │  角色   │ 状态  │ 创建时间  │    操作       │ │
│  ├──────┼────────┼──────┼─────────┼────────────────┤ │
│  │ admin │ [admin] │ [●]  │ 2026-07 │ 编辑 重置 删除 │ │
│  │ demo  │ [user]  │ [●]  │ 2026-07 │ 编辑 重置 删除 │ │
│  └──────┴────────┴──────┴─────────┴────────────────┘ │
│                                                       │
│  角色 el-tag: admin=danger / user=info                │
│  状态 el-switch: on=active / off=disabled             │
└───────────────────────────────────────────────────────┘
```

### 6A.5 ChangePasswordDialog.vue UI

```typescript
// 独立组件，由右上角用户菜单触发
<el-dialog title="修改密码" width="420px">
  <el-form label-width="80px">
    <el-form-item label="旧密码">
      <el-input type="password" show-password />
    </el-form-item>
    <el-form-item label="新密码">
      <el-input type="password" show-password />
      <el-progress :percentage="pwdStrength" />  // 密码强度条
    </el-form-item>
    <el-form-item label="确认密码">
      <el-input type="password" show-password />
    </el-form-item>
  </el-form>
</el-dialog>
```

密码强度条规则：
- 0-33% 弱（红色）：< 8 位
- 34-66% 中（橙色）：≥ 8 位 + 含数字或特殊字符
- 67-100% 强（绿色）：≥ 8 位 + 含大小写 + 数字 + 特殊字符

### 6A.6 设计 Token 复用清单

所有新增 UI 均使用现有 design-tokens.css，不引入新 token：

| Token | 用途 | 使用位置 |
|-------|------|---------|
| `--surface-1` | 登录卡片背景 | Login.vue |
| `--shadow-float` | 登录卡片阴影 | Login.vue |
| `--radius-panel` | 卡片圆角 | Login.vue, ChangePasswordDialog |
| `--text-display-xl` | 品牌标题 | Login.vue |
| `--chart-1`, `--chart-2` | 登录按钮渐变 | Login.vue |
| `--dash-accent-*` | 3D 节点发光 | Graph3D (已有) |
| `--status-success/warning/error` | 角色/状态标签 | UserManagementPanel |

---

## 7. 首次部署流程

```
1. 部署后端 + 数据库（Docker compose up）
2. 运维执行：python scripts/seed_admin.py --username admin --password <强密码>
   ├─ bcrypt 哈希密码
   ├─ INSERT INTO users (username, password_hash, role) VALUES ('admin', '<hash>', 'admin')
3. 访问前端 /login
4. 用初始 admin 登录
5. 进入 Admin 页 → 用户管理 → 添加其他用户
```

`.env` 中**不出现任何密码**，避免密钥泄漏到 git。

---

## 8. 测试覆盖

### 后端单元测试

| 测试文件 | 测试内容 |
|---------|---------|
| `test_auth_service.py` (新建) | authenticate 成功/失败、create_tokens 签发格式、refresh 成功/refresh 吊销失败、revoke 成功、change_password 旧密码错误/新密码过短 |
| `test_auth_endpoints.py` (新建) | POST /auth/login 200/401、POST /auth/refresh 200/401、POST /auth/logout 204、POST /auth/change-password 200/401/422 |
| `test_admin_user_endpoints.py` (新建) | 列表/创建/编辑/删除/重置密码，admin 权限校验 |
| `test_dependencies.py` (扩展) | get_current_user 各种场景：有效 JWT、过期 JWT、签名错误 JWT、dev-token、无 token |

### 前端单元测试

| 测试文件 | 测试内容 |
|---------|---------|
| `Login.spec.ts` | 登录成功跳转、401 错误提示、空输入校验 |
| `user.test.ts` (扩展) | setTokens、refreshAccessToken 成功/失败、isTokenExpired |
| `request.test.ts` (新建) | 401 拦截器自动 refresh 重试、refresh 失败跳登录 |

### E2E 测试

| 测试文件 | 测试内容 |
|---------|---------|
| `e2e/auth-flow.spec.ts` | 完整登录→首页→修改密码→登出→重新登录 |
| `e2e/user-management.spec.ts` | Admin 用户管理 CRUD |

---

## 9. 配置变更

### 删除项

- `backend/.env` / `.env.development` 中的 `AUTH_USERS` 行
- `backend/app/config.py` 的 `auth_users` 字段和 `parsed_users` 属性

### 新增项

- `backend/.env` 增加 `JWT_ISSUER=starmap`、`JWT_AUDIENCE=starmap-web`
- `backend/.env` 增加 `ACCESS_TOKEN_EXPIRE_MINUTES=15`、`REFRESH_TOKEN_EXPIRE_DAYS=7`
- `backend/scripts/seed_admin.py` — 首次部署脚本

### 配置项总览

```ini
# JWT 配置（已存在，保留）
SECRET_KEY=<从环境注入>
JWT_ISSUER=starmap
JWT_AUDIENCE=starmap-web
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# 删除项
# AUTH_USERS=admin:starmap2024:admin,demo:demo123:user  ← 移除
```

---

## 10. 文件清单

### 新建

| 文件 | 用途 |
|------|------|
| `backend/app/models/user.py` | User ORM 模型 |
| `backend/app/services/auth_service.py` | 认证服务层 |
| `backend/alembic/versions/xxxx_add_users_table.py` | Alembic 迁移 |
| `backend/scripts/seed_admin.py` | 首次部署 seed |
| `backend/tests/unit/test_auth_service.py` | 服务层单测 |
| `backend/tests/unit/test_auth_endpoints.py` | 路由单测 |
| `backend/tests/unit/test_admin_user_endpoints.py` | 用户管理单测 |
| `frontend/src/components/ChangePasswordDialog.vue` | 修改密码组件 |
| `frontend/src/components/UserManagementPanel.vue` | 用户管理面板 |
| `frontend/e2e/auth-flow.spec.ts` | 端到端登录流程 |
| `frontend/e2e/user-management.spec.ts` | 端到端用户管理 |

### 修改

| 文件 | 变更 |
|------|------|
| `backend/app/api/v1/auth.py` | 重构：调用 auth_service、新增 refresh/logout/change-password |
| `backend/app/api/v1/admin.py` | 扩展：用户管理路由 |
| `backend/app/dependencies.py` | 重构：统一用 PyJWT |
| `backend/app/config.py` | 删除 `auth_users`/`parsed_users` |
| `backend/.env` | 删除 `AUTH_USERS`，新增 JWT 配置 |
| `frontend/src/pages/Login.vue` | 双 token 存储 + 3D 背景布局 + 登录失败保留用户名 |
| `frontend/src/pages/Admin.vue` | 新增用户管理 Tab（第 5 个） |
| `frontend/src/api/request.ts` | 401 自动 refresh + 防并发刷新 |
| `frontend/src/stores/user.ts` | 扩展 token 管理 + changePassword |
| `frontend/src/layouts/MainLayout.vue` | 右上角用户菜单 dropdown（修改密码/登出） |
| `starmap-contracts/openapi.yaml` | 更新登录/用户管理 API 契约 |
| `frontend/src/router/index.ts` | admin 路由 requiresAdmin + 公共路径 |

---

## 11. 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| 现有 dev 环境用户被踢出 | 迁移脚本：把 `AUTH_USERS` 中的 admin 用户同步到 users 表（仅首次迁移） |
| Alembic 迁移失败 | 迁移脚本幂等（`IF NOT EXISTS`），提供回滚命令 |
| Redis 不可用 | refresh 功能降级：access 过期即重登录，登录流程不受影响 |
| 前端 localStorage 被 XSS | access 短 TTL(15min) 缩小窗口；后续可考虑 httpOnly cookie 升级 |
| 现有 SSE 连接 token 传递 | 保留 query param 方式，refresh 后重连 |

---

## 12. 验收标准

| 标准 | 验证方式 |
|------|---------|
| 用 admin 账号 + 正确密码登录成功 | 集成测试 + 手动 |
| 用错误密码登录返回 401 + 中文提示 | 集成测试 |
| access 过期后自动 refresh，无需重登 | E2E 测试 + 手动 |
| 登出后 refresh 立即失效 | 集成测试：登出后用同一 refresh 换 access 应失败 |
| Admin 用户管理 CRUD 全部工作 | E2E 测试 |
| 用户可修改自己的密码 | E2E 测试 |
| 生产环境 dev-token 完全失效 | 集成测试：APP_ENV=production + dev-token → 401 |
| `AUTH_USERS` env var 完全移除 | grep 整个项目确认无引用 |
| 现有 163 个单测全部仍通过 | pytest 全跑 |
| 现有 16 个 Playwright 数据校验测试仍通过 | playwright 全跑 |
| 登录页 3D 背景正常渲染，登录后无感过渡到全景图谱 | 手动验证 |
| 登录页深色/浅色模式切换正常 | 手动验证 |
| Admin 用户管理 Tab CRUD 与"图谱节点管理"Tab 交互一致 | E2E 测试 |
| 右上角用户菜单：修改密码/登出功能正常 | E2E 测试 |

---

## 13. 实施顺序

```
Phase 1: 数据库
  1. 建 User ORM 模型
  2. Alembic 迁移
  3. 首次 seed_admin 脚本

Phase 2: 后端
  4. auth_service 实现
  5. 重构 auth.py
  6. 重构 dependencies.py
  7. 扩展 admin.py 用户管理路由
  8. 删除 AUTH_USERS env

Phase 3: 前端
  9.  user store 扩展
  10. request.ts 401 自动 refresh
  11. Login.vue 存双 token
  12. Admin.vue 用户管理 Tab
  13. 修改密码组件

Phase 4: 测试
  14. 后端单测
  15. 前端单测
  16. E2E 测试
  17. 全量回归

Phase 5: 验证
  18. 浏览器手动验证
  19. 全部测试通过
```