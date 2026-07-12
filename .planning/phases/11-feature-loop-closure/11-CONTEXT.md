---
phase: 11-feature-loop-closure
status: ready_for_planning
gathered: 2026-07-12
---

# Phase 11: 功能闭环补全 — Context

<domain>
## Phase Boundary

修复 3 个生产阻断问题 + 闭合 6 大核心功能循环，确保 StarMap 核心业务端到端可用。

**前置已经具备:**
- ✅ Phase 8 后端清理（auto-seed/reset-demo 删，`/health/detail` 配置校验，LLM 降级链打通）
- ✅ Phase 9 前端 MSW 关闭 + placeholder 删除 + Vite proxy 真实 API
- ✅ Phase 10 Pipeline 端到端验证（Playwright + 代理 + 触发 + E2E 冒烟）
- ✅ Code Review 全量修复（5 波：安全/内存/验证/质量/测试）
- ✅ Codebase Map 完成（7 文档：STACK/INTEGRATIONS/ARCHITECTURE/STRUCTURE/CONVENTIONS/TESTING/CONCERNS）

**本阶段 12 个需求（3 P0 + 4 P1 + 5 P2）:**

### P0 — 阻断生产部署
1. **LOOP-01** 认证登录端点 + 登录页面 — 后端无 `/auth/login`，前端无 `Login.vue`，生产环境全部 401
2. **LOOP-02** SSE 连接鉴权修复 — 3 处 fetch/EventSource 绕过 axios interceptor，生产 SSE 全部 401
3. **LOOP-03** 学习计划 createPlan 请求结构修复 — 前端发送 `Record<string, unknown>`，后端要求 `CreatePlanRequest`，422

### P1 — 核心功能闭环
4. **LOOP-04** 匹配诊断 Step4 → 学习中心贯通 — 无"创建学习计划"按钮，用户需手动导航
5. **LOOP-05** JD 抽取 → PositionRecord 自动创建 — 抽取只写 Neo4j，`/positions` 读 PG，抽取结果不可查
6. **LOOP-06** 演化告警前端消费 + 定时分析触发 — alerts 端点存在但前端不消费，分析需手动触发
7. **LOOP-11** Dashboard/Pipeline SSE 实时连接接通 — SSE 端点存在但前端未建立连接

### P2 — 数据一致性与 UX
8. **LOOP-07** 管理审核 approve/reject → Neo4j 同步 — 审核只更新 PG，Neo4j trust_score 不变
9. **LOOP-08** Pipeline 管理权限前端适配 — 非admin看到管理UI但操作403
10. **LOOP-09** LoopDemo target_position 可选/必填修复 — 前端允许空但后端要求必填
11. **LOOP-10** 学习进度 → 用户技能更新 + 重新匹配 — mastered skills 不反映到 parsedSkills
12. **LOOP-12** Evolution changelog 参数语义修复 — 前端传 skill name，后端期望 position name

</domain>

<decisions>
## Implementation Decisions

### LOOP-01 认证登录端点 + 登录页面
- **D-01:** 新增 `POST /auth/login` 端点，接受 `username` + `password`，验证后返回 JWT token
  - 初期使用配置文件中的固定用户列表（`AUTH_USERS` 环境变量，JSON 格式），不引入完整用户注册系统
  - JWT payload: `{sub, role, username, exp}` — 与现有 `get_current_user()` 解码逻辑兼容
  - Token 有效期 24h（可配置 `TOKEN_EXPIRE_HOURS`）
- **D-02:** 新增 `Login.vue` 页面，包含用户名/密码表单 + 登录按钮
  - 登录成功后存储 token 到 localStorage 并跳转首页
  - `/login` 路由从渲染 `Home.vue` 改为渲染 `Login.vue`
- **D-03:** 后端新增 `backend/app/api/v1/auth.py` 路由模块，注册到 `router.py`

### LOOP-02 SSE 连接鉴权修复
- **D-04:** `useSSE.ts` 中 `EventSource` 改为通过 query parameter 传递 token（`?token=xxx`）
  - 后端 SSE 端点新增 query parameter token 验证逻辑（与 header 验证并行）
- **D-05:** `jobseeker.ts` 中 `fetch('/api/v1/pipeline/analyze')` 改为使用 `request.ts` axios 实例
  - 如需 SSE streaming，使用 axios `responseType: 'stream'` 或保留 fetch 但手动注入 Authorization header
- **D-06:** `useSSE.ts` 中 `fetch(pollUrl)` 调用添加 Authorization header

### LOOP-03 学习计划 createPlan 请求结构修复
- **D-07:** 在 `learning.ts` store 中新增 `buildCreatePlanRequest(matchResult)` 映射函数
  - 从 `MatchResult` 提取 `position`、`match_score`、`skill_gap_detail` → `CreatePlanRequest`
  - `SkillGapInput` 映射: `skill` → skill name, `importance` → from gap detail, `gap_level` → from gap detail, `learning_path` → from gap detail or empty array
- **D-08:** `useLearningActions.ts` 中 `handleAddToPlan()` 使用 `buildCreatePlanRequest()` 构造请求

### LOOP-04 匹配诊断 Step4 → 学习中心贯通
- **D-09:** `LearningPathPlan.vue` 新增"创建学习计划"按钮
  - 点击后调用 `learningStore.createPlan(matchResult)` 并跳转 `/learning`
  - 使用 `buildCreatePlanRequest()` 构造请求体

### LOOP-05 JD 抽取 → PositionRecord 自动创建
- **D-10:** `POST /extract/jd` 成功后，在 `_write_extraction_to_graph()` 旁边新增 `_write_extraction_to_pg()`
  - 创建/更新 `PositionRecord`（name=position_name, source="extraction"）
  - 同步创建 `SkillRecord` 条目（如不存在）
  - 使用 `ON CONFLICT DO UPDATE` 避免重复

### LOOP-06 演化告警前端消费 + 定时分析触发
- **D-11:** `evolution.ts` store 新增 `fetchEmergingAlerts()` action，调用 `GET /evolution/emerging-alerts`
- **D-12:** `EvolutionDashboard.vue` 新增 alerts 展示区域（AlertList 组件复用或新组件）
- **D-13:** `celery_app.py` 新增 Celery beat schedule，每 6 小时触发一次 `evolution/analyze`

### LOOP-07 管理审核 approve/reject → Neo4j 同步
- **D-14:** `admin_audit_service.py` 的 `approve_audit_item()` / `reject_audit_item()` 新增 Neo4j 更新逻辑
  - approve: 设置 Neo4j 节点 `trust_score = 1.0`, `status = "approved"`
  - reject: 设置 Neo4j 节点 `status = "rejected"`
  - 使用 `get_neo4j_driver()` dependency

### LOOP-08 Pipeline 管理权限前端适配
- **D-15:** `PipelineMonitor.vue` 中 trigger/config/schedule 控件添加 `v-if="userStore.isAdmin"` 条件
  - 非admin用户显示只读视图

### LOOP-09 LoopDemo target_position 可选/必填修复
- **D-16:** 后端 `LoopRunRequest.target_position` 改为 `Optional[str] = None`（允许空值，loop 可不指定目标岗位）
  - 前端保持当前行为（空时传 undefined/不传）

### LOOP-10 学习进度 → 用户技能更新 + 重新匹配
- **D-17:** `useLearningActions.ts` 中 `handleUpdateStatus()` 当 status 变为 `mastered` 时：
  - 更新 `userStore.parsedSkills` 中对应 skill 的 proficiency
  - 可选：显示"重新匹配"提示按钮

### LOOP-11 Dashboard/Pipeline SSE 实时连接接通
- **D-18:** `dashboard.ts` store 在 `fetchAll()` 后建立 SSE 连接（调用 `useSSE` composable）
  - 连接 `GET /dashboard/realtime?token=xxx`
  - 事件分发到 `addRealtimeEvent()`
- **D-19:** `pipeline.ts` store 在 `fetchStatus()` 后建立 SSE 连接
  - 连接 `GET /pipeline/events?token=xxx`
  - 事件分发到 `handlePipelineEvent()`

### LOOP-12 Evolution changelog 参数语义修复
- **D-20:** `evolution.ts` store 中 `fetchChangelog()` 参数从 skill name 改为 position name
  - 或后端 `GET /evolution/changelog/{position}` 改为接受通用 identifier（同时支持 skill 和 position）

### Claude's Discretion
- Login.vue 的具体 UI 设计（Element Plus 表单组件）
- AUTH_USERS 环境变量的 JSON 格式细节
- SSE query-param token 验证在后端的具体实现位置（middleware vs endpoint 内联）
- Celery beat schedule 的精确间隔（6h 为建议值）
- alerts 展示组件的具体样式
- Neo4j 同步的 Cypher 语句细节
- `buildCreatePlanRequest()` 的默认值策略（缺失字段如何填充）

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 项目级决策（不重做）
- `.planning/PROJECT.md` — v2.1 真实数据切换、DEC-001~012
- `.planning/ROADMAP.md` §Phase 11 — 成功标准、关键文件
- `.planning/STATE.md` — 当前状态、已锁定决策

### Codebase Map（核心参考）
- `.planning/codebase/CONCERNS.md` — 3 阻断问题 + 6 功能闭环缺失 + API 不匹配 + 技术债
- `.planning/codebase/INTEGRATIONS.md` — 14 个未消费端点 + 7 个数据流断点 + SSE 状态
- `.planning/codebase/ARCHITECTURE.md` — 8 大功能闭环分析 + 反模式 + 认证流
- `.planning/codebase/STRUCTURE.md` — 文件结构
- `.planning/codebase/CONVENTIONS.md` — 代码约定

### 前序阶段决策（不重做）
- `.planning/phases/10-pipeline-e2e-validation/10-CONTEXT.md` — Phase 10 Pipeline 验证
- `.planning/phases/09-frontend-mock-off/09-CONTEXT.md` — Phase 9 前端关闭 Mock
- `.planning/phases/08-backend-cleanup/08-CONTEXT.md` — Phase 8 后端清理

### 认证相关
- `backend/app/dependencies.py` — `get_current_user()` JWT 验证逻辑
- `backend/app/config.py` — `SECRET_KEY` 配置
- `frontend/src/stores/user.ts` — token 解码 + 用户状态
- `frontend/src/api/request.ts` — axios interceptor + 401 处理
- `frontend/src/router/index.ts` — auth guard + /login 路由

### SSE 相关
- `frontend/src/composables/useSSE.ts` — SSE composable（exponential backoff + polling fallback）
- `backend/app/core/dashboard/sse_broadcaster.py` — Redis pub/sub → SSE
- `frontend/src/stores/jobseeker.ts` — 原生 fetch 调用（需修复）
- `frontend/src/stores/dashboard.ts` — SSE 连接未建立
- `frontend/src/stores/pipeline.ts` — SSE 连接未建立

### 学习计划相关
- `frontend/src/stores/learning.ts` — `createPlan()` + `buildCreatePlanRequest()`
- `frontend/src/composables/useLearningActions.ts` — `handleAddToPlan()` + `handleUpdateStatus()`
- `frontend/src/components/LearningPathPlan.vue` — Step 4 学习路径展示
- `backend/app/api/v1/learning.py` — `CreatePlanRequest` schema
- `frontend/src/stores/match.ts` — `MatchResult` 类型

### JD 抽取相关
- `backend/app/api/v1/extract.py` — `_write_extraction_to_graph()` + 新增 `_write_extraction_to_pg()`
- `backend/app/api/v1/position.py` — `/positions` 端点（读 PG）
- `backend/app/models/extraction_models.py` — `PositionRecord`, `SkillRecord`

### 演化相关
- `frontend/src/stores/evolution.ts` — trends/snapshots/changelog
- `backend/app/api/v1/evolution.py` — trends/snapshots/changelog/emerging-alerts
- `backend/app/api/v1/evolution_emerging_alerts.py` — alerts 子路由
- `backend/app/tasks/celery_app.py` — Celery beat schedule

### 管理审核相关
- `backend/app/services/admin_audit_service.py` — approve/reject 逻辑
- `backend/app/api/v1/admin.py` — admin 端点
- `frontend/src/stores/audit.ts` — audit store
- `frontend/src/stores/graphNode.ts` — graph node store

### Pipeline 权限相关
- `backend/app/api/v1/pipeline/routes.py` — `require_admin` 依赖
- `frontend/src/pages/PipelineMonitor.vue` — pipeline 管理页面
- `frontend/src/stores/pipeline.ts` — pipeline store

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **JWT 验证逻辑** — `backend/app/dependencies.py:get_current_user()` 已有完整 JWT 解码验证，新增 `/auth/login` 只需签发 token
- **axios interceptor** — `frontend/src/api/request.ts` 已有 Authorization header 注入 + 401 清理逻辑
- **SSE composable** — `frontend/src/composables/useSSE.ts` 已有 exponential backoff + polling fallback，只需接通
- **Element Plus 表单** — 项目已使用 Element Plus，Login.vue 可直接用 `el-form` + `el-input` + `el-button`
- **PositionRecord ORM** — `backend/app/models/extraction_models.py` 已有 `PositionRecord` 模型
- **Celery beat** — `backend/app/tasks/celery_app.py` 已有 Celery app 配置，新增 beat schedule 即可
- **Neo4j driver** — `backend/app/dependencies.py:get_neo4j_driver()` 已有 Neo4j 连接注入

### Established Patterns
- **API 路由注册**: 新路由在 `backend/app/api/v1/router.py` 中 `include_router`
- **Pydantic schema**: 请求/响应模型在路由文件内定义（与 Phase 8-10 一致）
- **Pinia store**: `defineStore` + `request.ts` axios 调用 + `ref`/`computed` 响应式
- **Domain exception → HTTP**: 服务层抛 domain exception，API 层 catch 映射（Phase 10 修复的模式）
- **环境变量**: `backend/app/config.py` Settings 类 + `.env.example` 补全

### Integration Points
- `backend/app/api/v1/auth.py` — new (LOOP-01)
- `frontend/src/pages/Login.vue` — new (LOOP-01)
- `frontend/src/composables/useSSE.ts` — modify (LOOP-02)
- `frontend/src/stores/jobseeker.ts` — modify (LOOP-02)
- `frontend/src/stores/learning.ts` — modify (LOOP-03)
- `frontend/src/composables/useLearningActions.ts` — modify (LOOP-03/04/10)
- `frontend/src/components/LearningPathPlan.vue` — modify (LOOP-04)
- `backend/app/api/v1/extract.py` — modify (LOOP-05)
- `frontend/src/stores/evolution.ts` — modify (LOOP-06/12)
- `backend/app/tasks/celery_app.py` — modify (LOOP-06)
- `backend/app/services/admin_audit_service.py` — modify (LOOP-07)
- `frontend/src/pages/PipelineMonitor.vue` — modify (LOOP-08)
- `backend/app/api/v1/loop.py` — modify (LOOP-09)
- `frontend/src/stores/dashboard.ts` — modify (LOOP-11)
- `frontend/src/stores/pipeline.ts` — modify (LOOP-11)

</code_context>

<specifics>
## Specific Ideas

- LOOP-01 AUTH_USERS 格式: `AUTH_USERS=[{"username":"admin","password":"starmap2024","role":"admin"},{"username":"demo","password":"demo123","role":"user"}]`
- LOOP-01 JWT 签发: `jwt.encode({"sub": username, "role": role, "username": username, "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)}, SECRET_KEY, algorithm="HS256")`
- LOOP-02 EventSource query-param: 后端 SSE 端点检查 `request.query_params.get("token")`，与 `Authorization` header 并行验证
- LOOP-05 `_write_extraction_to_pg()`: 使用 `INSERT INTO position_records (name, source, ...) VALUES (...) ON CONFLICT (name) DO UPDATE SET updated_at=NOW()`
- LOOP-06 Celery beat: `app.conf.beat_schedule["evolution-analyze"] = {"task": "app.tasks.celery_app.run_evolution_analysis", "schedule": crontab(hour="*/6", minute=0)}`
- LOOP-07 Neo4j sync: `MATCH (n) WHERE elementId(n) = $node_id SET n.trust_score = 1.0, n.status = "approved"`
- LOOP-11 SSE 接通: 在 `onMounted` 中调用 `useSSE(url, handlers)` 并在 `onUnmounted` 中 disconnect

</specifics>

<deferred>
## Deferred Ideas

- **完整用户注册系统** — Out of Scope（v2.1 使用配置文件用户列表，注册推 v2.2）
- **JWT 迁移到 httpOnly cookie** — Out of Scope（需后端 login endpoint 配合，当前无 /auth/login）
- **CSRF token 机制** — Out of Scope（需 cookie-based session，当前用 Bearer token）
- **Redis 共享代理熔断状态** — Out of Scope（Phase 10 单 worker 进程 module-level dict 足够）
- **N+1 查询优化** — Out of Scope（性能优化推 v2.2）
- **Quality dashboard Redis 缓存** — Out of Scope（性能优化推 v2.2）
- **Raw request.get/post 迁移到 typed api client** — Out of Scope（长期任务）
- **Pipeline config 持久化** — Out of Scope（推 v2.2）
- **Junction table 唯一约束** — Out of Scope（推 v2.2）
- **LoopDemo.vue 1674 行拆分** — Out of Scope（需设计新组件结构）
- **Graph3D.vue 1000 行拆分** — Out of Scope（同上）
- **update_trust() 调用接通** — Out of Scope（推 v2.2）
- **Graph depth 参数实现** — Out of Scope（推 v2.2）
- **Reverse match (/match/recommend) 前端消费** — Out of Scope（推 v2.2）
- **Quality evaluate/comprehensive-report 前端消费** — Out of Scope（推 v2.2）

</deferred>

---

*Phase: 11-feature-loop-closure*
*Context gathered: 2026-07-12*
*Next: `/gsd:plan-phase 11`*
