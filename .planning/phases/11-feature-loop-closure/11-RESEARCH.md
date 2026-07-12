# Phase 11: 功能闭环补全 — Research

**Gathered:** 2026-07-12
**Status:** Complete

---

## LOOP-01: 认证登录端点 + 登录页面

### Current State
- **Backend**: `backend/app/dependencies.py` 有完整的 JWT 验证逻辑（`_decode_token()` + `get_current_user()`），使用 HMAC-SHA256 + `settings.secret_key` 签名
- **Backend**: 无 `/auth/login` 端点，无用户注册/登录路由
- **Frontend**: `frontend/src/stores/user.ts` 有 `decodeToken()` + `initUser()` + `logout()` + `clearUser()`
- **Frontend**: `frontend/src/api/request.ts` 有 Authorization header 注入 + 401 清理
- **Frontend**: `frontend/src/router/index.ts` 有 `/login` 路由但渲染 `Home.vue`，非登录表单
- **Config**: `backend/app/config.py` 有 `SECRET_KEY`，无 `AUTH_USERS` 或 `TOKEN_EXPIRE_HOURS`

### Proposed Approach
1. 新增 `backend/app/api/v1/auth.py`，包含 `POST /auth/login` 端点
2. `config.py` 新增 `AUTH_USERS: str` 环境变量（JSON 数组格式）+ `TOKEN_EXPIRE_HOURS: int = 24`
3. 登录端点验证 username/password，签发 JWT（复用 `_decode_token` 的签名逻辑）
4. 新增 `frontend/src/pages/Login.vue`（Element Plus `el-form` + `el-input` + `el-button`）
5. 修改 `router/index.ts` 的 `/login` 路由指向 `Login.vue`
6. `user.ts` 新增 `login(username, password)` action

### Risks
- AUTH_USERS JSON 格式在环境变量中可能需要转义，建议提供 `.env.example` 示例
- JWT 签发需使用 `jwt` 库或手动构造（当前 `_decode_token` 是手动实现，签发也应手动实现保持一致）

### Key Files
- `backend/app/dependencies.py:52-88` — `_decode_token()` 签名验证逻辑
- `backend/app/config.py` — Settings 类
- `frontend/src/stores/user.ts` — user store
- `frontend/src/router/index.ts` — /login 路由

---

## LOOP-02: SSE 连接鉴权修复

### Current State
- **`frontend/src/stores/jobseeker.ts:82`**: `fetch('/api/v1/pipeline/analyze', ...)` — 无 Authorization header，硬编码 `/api/v1` 前缀
- **`frontend/src/composables/useSSE.ts:72`**: `new EventSource(url)` — EventSource API 不支持自定义 headers
- **`frontend/src/composables/useSSE.ts:170`**: `fetch(pollUrl, ...)` — 无 Authorization header
- **Backend SSE 端点**: `GET /dashboard/realtime`, `GET /pipeline/events`, `POST /pipeline/analyze` — 均依赖 `get_current_user` header 验证

### Proposed Approach
1. **EventSource**: 在 URL 中添加 `?token=xxx` query parameter
   - `useSSE.ts` 修改 `connectSSE()` 在 URL 后追加 token
   - 后端 SSE 端点新增 query-param token 验证（与 header 验证并行）
2. **jobseeker.ts fetch**: 改用 `request.ts` axios 实例（自动注入 Authorization header）
   - SSE streaming 部分保留 fetch 但手动注入 header: `headers: { Authorization: 'Bearer ' + token }`
   - 修改硬编码 `/api/v1` 为 `import.meta.env.VITE_API_BASE_URL || '/api/v1'`
3. **useSSE.ts pollOnce()**: 在 fetch 调用中添加 Authorization header

### Risks
- Token 在 URL query parameter 中可能被日志记录，建议后端日志脱敏
- EventSource 不支持自定义 headers 是浏览器 API 限制，query-param 是标准解决方案

### Key Files
- `frontend/src/composables/useSSE.ts:62-163` — connectSSE + EventSource
- `frontend/src/composables/useSSE.ts:167-200` — pollOnce + fetch
- `frontend/src/stores/jobseeker.ts:69-128` — analyzeResume + fetch
- `backend/app/core/dashboard/sse_broadcaster.py` — SSE event stream

---

## LOOP-03: 学习计划 createPlan 请求结构修复

### Current State
- **Backend `CreatePlanRequest`** (`backend/app/api/v1/learning.py:47-53`):
  - `position: str` (required, min_length=1)
  - `match_score: float` (default=0.0, ge=0.0, le=1.0)
  - `skills: list[SkillGapInput]` (required, min_length=1)
  - `available_hours_per_week: float` (default=10.0)
- **Backend `SkillGapInput`** (`learning.py:37-44`):
  - `skill: str` (required)
  - `importance: str` (default="required")
  - `gap_level: str` (default="完全缺失")
  - `learning_path: list[str]` (default=[])
  - `target_proficiency: str` (default="熟悉")
- **Frontend `useLearningActions.ts:47-53`**: 发送 `{ position, skills: [{ skill, importance, gap_level }] }` — 缺少 `match_score`
- **Frontend `learning.ts:createPlan()`**: 接受 `matchResult: Record<string, unknown>` — 无类型安全

### Proposed Approach
1. 在 `learning.ts` 中新增 `buildCreatePlanRequest(matchResult: MatchResult): CreatePlanRequest` 映射函数
2. 映射逻辑:
   - `position` ← `matchResult.position_name`
   - `match_score` ← `matchResult.match_score`
   - `skills` ← `matchResult.skill_gap_detail.map(gap => ({ skill: gap.skill, importance: gap.importance || "required", gap_level: gap.gap_level || "完全缺失", learning_path: gap.learning_path || [] }))`
3. `createPlan()` 使用 `buildCreatePlanRequest()` 构造请求体
4. `useLearningActions.ts` 的 `handleAddToPlan()` 同步使用映射函数

### Risks
- `MatchResult.skill_gap_detail` 的字段名可能与 `SkillGapInput` 不完全对应，需运行时验证
- `match_score` 默认 0.0 不会导致 422，但数据不准确

### Key Files
- `backend/app/api/v1/learning.py:37-53` — CreatePlanRequest + SkillGapInput
- `frontend/src/stores/learning.ts` — createPlan
- `frontend/src/composables/useLearningActions.ts` — handleAddToPlan
- `frontend/src/stores/match.ts` — MatchResult type

---

## LOOP-04: 匹配诊断 Step4 → 学习中心贯通

### Current State
- **`LearningPathPlan.vue`**: 接收 `gapSkills: SkillGap[]` props，展示学习路径时间线
  - 仅有 `goBack` 和 `resetAll` emit，无"创建学习计划"按钮
- **`MatchDiagnosis.vue`**: Step 4 使用 `<LearningPathPlan :gap-skills="gapSkills" />`
- **`useLearningStore.createPlan()`**: 存在但未被 MatchDiagnosis 页面调用

### Proposed Approach
1. `LearningPathPlan.vue` 新增"创建学习计划"按钮（`el-button type="primary"`）
2. 新增 emit: `createPlan: []`
3. `MatchDiagnosis.vue` 监听 `@create-plan` 事件，调用 `learningStore.createPlan(matchResult)` + `router.push('/learning')`
4. 使用 `buildCreatePlanRequest()` 构造请求体（依赖 LOOP-03）

### Risks
- 需要确保 matchResult 在 Step 4 仍然可访问（当前 store 中 `matchStore.result` 应该可用）

### Key Files
- `frontend/src/components/LearningPathPlan.vue` — 学习路径展示组件
- `frontend/src/pages/MatchDiagnosis.vue` — 匹配诊断页面
- `frontend/src/stores/learning.ts` — learning store

---

## LOOP-05: JD 抽取 → PositionRecord 自动创建

### Current State
- **`extract.py:94-119`**: `_write_extraction_to_graph()` 将抽取结果写入 Neo4j（非阻塞）
- **`extract.py:122-158`**: `extract_jd()` 调用 `_write_extraction_to_graph()` 后返回结果
- **`position.py`**: `/positions` 端点从 PostgreSQL `PositionRecord` 读取
- **`extraction_models.py`**: `PositionRecord` 模型存在（name, source, etc.）
- **Gap**: 抽取只写 Neo4j，不写 PG，导致 `/positions` 查不到抽取的岗位

### Proposed Approach
1. 新增 `_write_extraction_to_pg()` 函数，在 `_write_extraction_to_graph()` 旁边调用
2. 使用 `INSERT ... ON CONFLICT (name) DO UPDATE SET updated_at=NOW(), source='extraction'`
3. 同时创建 `SkillRecord` 条目（如不存在）
4. 需要注入 `AsyncSession` 依赖（当前 `extract_jd` 只注入 `neo4j_driver`）

### Risks
- 需要修改 `extract_jd()` 函数签名添加 `session: AsyncSession = Depends(get_db_session)`
- PG 写入应同样非阻塞（try/except + logger.warning）

### Key Files
- `backend/app/api/v1/extract.py:94-158` — _write_extraction_to_graph + extract_jd
- `backend/app/models/extraction_models.py` — PositionRecord, SkillRecord
- `backend/app/api/v1/position.py` — /positions 端点

---

## LOOP-06: 演化告警前端消费 + 定时分析触发

### Current State
- **Backend**: `GET /evolution/emerging-alerts` 端点存在（`evolution_emerging_alerts.py`），返回 `EmergingAlertsResponse`
- **Frontend**: `evolution.ts` store 不调用此端点
- **Backend**: `POST /evolution/analyze` 存在但无定时触发
- **Celery**: `celery_app.py` 有 Celery app 配置，无 evolution analysis beat schedule

### Proposed Approach
1. `evolution.ts` 新增 `fetchEmergingAlerts()` action，调用 `GET /evolution/emerging-alerts`
2. `EvolutionDashboard.vue` 新增 alerts 展示区域（可复用 `AlertList.vue` 组件或新建简化版）
3. `celery_app.py` 新增 beat schedule:
   ```python
   app.conf.beat_schedule["evolution-analyze"] = {
       "task": "app.tasks.celery_app.run_evolution_analysis",
       "schedule": crontab(hour="*/6", minute=0),
   }
   ```
4. 需确认 `run_evolution_analysis` task 是否已存在，如不存在需创建

### Risks
- Celery beat 需要单独的 beat worker 进程（`celery -A app.tasks.celery_app beat`）
- alerts 数据可能为空（依赖 timeseries 数据积累）

### Key Files
- `backend/app/api/v1/evolution_emerging_alerts.py` — alerts 端点
- `frontend/src/stores/evolution.ts` — evolution store
- `frontend/src/pages/EvolutionDashboard.vue` — 演化看板页面
- `backend/app/tasks/celery_app.py` — Celery 配置

---

## LOOP-07: 管理审核 approve/reject → Neo4j 同步

### Current State
- **`admin_audit_service.py`**: `approve_audit_item()` / `reject_audit_item()` 只更新 PG `review_queue` 表
- **Backend AuditItem**: `{id, type, name, trust, status}` — type 为 "position" 或 "skill"
- **Gap**: approve/reject 不更新 Neo4j 节点的 trust_score/status

### Proposed Approach
1. `admin_audit_service.py` 的 approve/reject 方法新增 Neo4j 更新逻辑
2. 需要注入 `neo4j_driver` 到 service 方法
3. Cypher 语句:
   - approve: `MATCH (n:{type}) WHERE n.name = $name SET n.trust_score = 1.0, n.status = 'approved'`
   - reject: `MATCH (n:{type}) WHERE n.name = $name SET n.status = 'rejected'`
4. Neo4j 更新应非阻塞（try/except + logger.warning）

### Risks
- Neo4j 节点可能没有 `trust_score` 或 `status` 属性（需确认 schema）
- `type` 参数需映射到 Neo4j 标签名（"position" → Position, "skill" → Skill）
- Cypher 注入风险：使用参数化查询，不拼接 type 到标签

### Key Files
- `backend/app/services/admin_audit_service.py` — audit service
- `backend/app/api/v1/admin.py` — admin 端点
- `backend/app/dependencies.py:get_neo4j_driver()` — Neo4j driver 注入

---

## LOOP-08: Pipeline 管理权限前端适配

### Current State
- **Backend**: `pipeline/routes.py` 的 trigger/retry/resume/schedule 端点有 `dependencies=[Depends(require_admin)]`
- **Frontend**: `PipelineMonitor.vue` 对所有用户展示管理 UI
- **`user.ts`**: `isAdmin` computed 已存在（`user.value?.role === 'admin'`）
- **`MainLayout.vue`**: 已用 `userStore.isAdmin` 条件渲染 admin 导航项

### Proposed Approach
1. `PipelineMonitor.vue` 中 trigger/config/schedule 控件添加 `v-if="userStore.isAdmin"`
2. 非admin用户显示只读状态 + 提示文字"仅管理员可执行此操作"

### Risks
- 低风险，纯前端条件渲染

### Key Files
- `frontend/src/pages/PipelineMonitor.vue` — pipeline 管理页面
- `frontend/src/stores/user.ts:15` — isAdmin computed

---

## LOOP-09: LoopDemo target_position 可选/必填修复

### Current State
- **Backend `LoopRunRequest`** (`loop.py:30-35`):
  - `jd_text: str` (required, min_length=1)
  - `target_position: str` (required, min_length=1) — **必填**
- **Frontend `loop.ts:165`**: `targetPosition.value || undefined` — 允许空值
- **Test**: `test_empty_target_fails_validation` 断言空 target_position 验证失败

### Proposed Approach
1. 后端 `LoopRunRequest.target_position` 改为 `Optional[str] = None`
2. `LoopOrchestrator.run_loop()` 中 target_position 为 None 时跳过 match 步骤（降级为4步）
3. 更新测试用例

### Risks
- 需确认 `LoopOrchestrator` 在 target_position=None 时的行为
- 现有测试 `test_empty_target_fails_validation` 需要修改

### Key Files
- `backend/app/api/v1/loop.py:30-35` — LoopRunRequest
- `backend/app/core/pipeline/loop_orchestrator.py` — LoopOrchestrator
- `frontend/src/stores/loop.ts` — loop store

---

## LOOP-10: 学习进度 → 用户技能更新 + 重新匹配

### Current State
- **`useLearningActions.ts`**: `handleUpdateStatus()` 只调用 `updateProgress()`，不更新 `userStore.parsedSkills`
- **`user.ts:62`**: `parsedSkills` 是 `ref<string[]>`，只在 `setResume()` 中设置
- **Gap**: mastered skills 不反映到 parsedSkills，重新匹配使用旧数据

### Proposed Approach
1. `handleUpdateStatus()` 当 status 变为 `mastered` 时:
   - 将 skill name 添加到 `userStore.parsedSkills`（如不存在）
2. 可选：显示"重新匹配"提示，引导用户回到 MatchDiagnosis
3. `user.ts` 新增 `addParsedSkill(skill: string)` action

### Risks
- `parsedSkills` 是简单 string 数组，无 proficiency 信息
- 重新匹配仍需用户手动触发（自动触发可能过于激进）

### Key Files
- `frontend/src/composables/useLearningActions.ts` — handleUpdateStatus
- `frontend/src/stores/user.ts:62` — parsedSkills

---

## LOOP-11: Dashboard/Pipeline SSE 实时连接接通

### Current State
- **Backend**: `GET /dashboard/realtime` (SSE) + `GET /dashboard/realtime-poll` (fallback) 存在
- **Backend**: `GET /pipeline/events` (SSE) + `GET /pipeline/events-poll` (fallback) 存在
- **Frontend `dashboard.ts`**: 有 `addRealtimeEvent()` + `sseConnected` ref，但无 SSE 连接代码
- **Frontend `pipeline.ts`**: 有 `handlePipelineEvent()` + handlers，但无 SSE 连接代码
- **`useSSE.ts`**: 完整的 SSE composable（exponential backoff + polling fallback + storeHandlers）

### Proposed Approach
1. `DataDashboard.vue` 在 `onMounted` 中调用 `useSSE('/api/v1/dashboard/realtime', { onMessage, storeHandlers })`
2. `PipelineMonitor.vue` 在 `onMounted` 中调用 `useSSE('/api/v1/pipeline/events', { onMessage, storeHandlers })`
3. storeHandlers 映射:
   - dashboard: `{ pipeline_update: addRealtimeEvent, quality_alert: addRealtimeEvent, data_milestone: addRealtimeEvent }`
   - pipeline: `{ pipeline_update: handlePipelineEvent }`
4. `onUnmounted` 中调用 `disconnect()`
5. 依赖 LOOP-02（SSE 鉴权修复）— URL 需包含 `?token=xxx`

### Risks
- SSE 连接可能增加服务器负载（需确认 MAX_SSE_CLIENTS 限制）
- 需确保 Redis pub/sub 正常运行

### Key Files
- `frontend/src/composables/useSSE.ts` — SSE composable
- `frontend/src/stores/dashboard.ts` — dashboard store
- `frontend/src/stores/pipeline.ts` — pipeline store
- `frontend/src/pages/DataDashboard.vue` — 数据大屏
- `frontend/src/pages/PipelineMonitor.vue` — pipeline 管理页面
- `backend/app/core/dashboard/sse_broadcaster.py` — SSE broadcaster

---

## LOOP-12: Evolution changelog 参数语义修复

### Current State
- **Frontend `useEvolutionActions.ts:62`**: `fetchChangelog(skillName: string)` — 传 skill name
- **Backend `evolution.py`**: `GET /evolution/changelog/{position}` — param 描述为"岗位名称"
- **OpenAPI contract**: param 名为 `position`，描述为"岗位名称"

### Proposed Approach
1. 方案A（推荐）: 后端 `changelog` 端点参数改为通用 `identifier`，同时支持 skill 和 position 查询
2. 方案B: 前端改为传 position name（但用户在演化看板选择的是 skill，不是 position）
3. 选择方案A: 修改后端参数名为 `identifier`，Cypher 查询同时匹配 Position 和 Skill 节点

### Risks
- 修改 OpenAPI contract 参数名可能影响生成的 API client
- 需确认后端 Cypher 查询是否支持按 skill name 查询

### Key Files
- `frontend/src/composables/useEvolutionActions.ts:62` — fetchChangelog
- `frontend/src/stores/evolution.ts` — evolution store
- `backend/app/api/v1/evolution.py` — changelog 端点

---

## Dependency Map

```
LOOP-01 (Auth) ──────┐
                      ├──→ LOOP-02 (SSE auth) ──→ LOOP-11 (SSE wiring)
                      │
LOOP-03 (createPlan) ─┼──→ LOOP-04 (Match→Learning)
                      │
LOOP-05 (JD→PG)       │    (independent)
LOOP-06 (Evolution)   │    (independent)
LOOP-07 (Audit→Neo4j) │    (independent)
LOOP-08 (Pipeline UX) │    (independent)
LOOP-09 (LoopDemo)    │    (independent)
LOOP-10 (Skills sync) │    (independent)
LOOP-12 (Changelog)   │    (independent)
```

**Critical path**: LOOP-01 → LOOP-02 → LOOP-11 (auth must work before SSE can connect)
**Secondary path**: LOOP-03 → LOOP-04 (createPlan fix enables Match→Learning bridge)

---

## Recommended Wave Ordering

### Wave 1: P0 Production Blockers (no deps)
- **11-01**: LOOP-01 Auth login endpoint + Login page
- **11-02**: LOOP-03 createPlan request shape fix
- **11-03**: LOOP-05 JD extraction → PositionRecord

### Wave 2: P0 + P1 (depends on Wave 1)
- **11-04**: LOOP-02 SSE auth fix (depends on LOOP-01 for token flow)
- **11-05**: LOOP-04 Match→Learning bridge (depends on LOOP-03)
- **11-06**: LOOP-06 Evolution alerts + scheduled analysis

### Wave 3: P1 + P2 (depends on Wave 2)
- **11-07**: LOOP-11 Dashboard/Pipeline SSE wiring (depends on LOOP-02)
- **11-08**: LOOP-07 Audit→Neo4j sync + LOOP-08 Pipeline UX + LOOP-09 LoopDemo fix
- **11-09**: LOOP-10 Skills sync + LOOP-12 Changelog fix

---

## Open Questions

1. **AUTH_USERS 格式**: 建议使用 JSON 数组 `[{"username":"admin","password":"xxx","role":"admin"}]`，但环境变量中 JSON 转义可能复杂。替代方案：使用 `AUTH_USERS=admin:password:admin,demo:demo123:user` 格式（更简单）
2. **Evolution analysis Celery task**: 需确认 `run_evolution_analysis` task 是否已存在于 `celery_app.py`
3. **Neo4j 节点属性**: 需确认 Position/Skill 节点是否有 `trust_score` 和 `status` 属性
4. **LoopOrchestrator target_position=None**: 需确认降级行为是否合理

---

*Phase: 11-feature-loop-closure*
*Research gathered: 2026-07-12*
