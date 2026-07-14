# Roadmap: StarMap v3.0 — 前后端对齐与功能闭环

**Created:** 2026-07-14
**Milestone:** v3.0 — 前后端对齐与功能闭环
**Total phases:** 6
**Total requirements:** 42

## Phase Summary

| # | Phase | Goal | Requirements | Priority |
|---|-------|------|--------------|----------|
| 18 | P0 阻断修复 ✅ | 修复 2 个页面渲染崩溃 + SSE token key 不匹配 + Home 页鉴权 | 6 | P0 |
| 19 | 前后端 API 对齐 ✅ | 修复请求/响应结构不匹配 + 补全缺失的前端消费 + 参数语义修复 | 8 | P1 |
| 20 | 数据流闭环 ✅ | 闭合 7 大数据流断点：match→learning, JD→PG, evolution→graph, alerts→action 等 | 8 | P1 |
| 21 | SSE 实时连接接通 ✅ | Dashboard/Pipeline/Jobseeker SSE 端到端接通 + 事件消费 | 5 | P1 |
| 22 | 基础设施配置统一 ✅ | Docker dev 修复 + .env 统一 + 端口对齐 + CORS 修正 | 7 | P2 |
| 23 | UAT 全链路验证 ✅ | 手工测试所有页面功能 + 修复发现的运行时错误 | 8 | P1 |

**Coverage:** 100% (42/42 requirements mapped across 6 phases)

---

## Phase 18: P0 阻断修复

**Goal:** 修复导致页面崩溃和核心功能不可用的 P0 级问题，确保所有页面可正常渲染、SSE 连接可鉴权、首页有鉴权保护。

**Requirements:**
- FIX-01: EvolutionDashboard.vue 修复 `<div` 未闭合标签 (line 169) — 页面渲染崩溃
- FIX-02: Admin.vue 修复重复 `</el-tab-pane>` 标签 (line 486) — Tab 导航崩溃
- FIX-03: useSSE.ts token key 修复 — 读取 `starmap_access_token` 而非 `starmap_token`
- FIX-04: jobseeker.ts token key 修复 — 同 FIX-03，raw fetch 需要正确 token
- FIX-05: Home 页添加 `requiresAuth` meta — 未登录用户不应看到空白闪烁
- FIX-06: Login.vue 移除默认密码显示 — 生产安全风险

**Success criteria:**
1. EvolutionDashboard.vue 正常渲染，CII gauge 区域显示图表或空状态
2. Admin.vue 6 个 Tab 全部正常切换和渲染
3. SSE 连接携带正确 token，不再 401
4. Jobseeker pipeline analyze 携带正确 token
5. 未登录用户访问 `/` 自动跳转 `/login`
6. Login.vue 不显示默认密码

**Key files:**
- `frontend/src/pages/EvolutionDashboard.vue` — 修复 line 169 `<div` 标签
- `frontend/src/pages/Admin.vue` — 修复 line 486 重复标签
- `frontend/src/composables/useSSE.ts` — token key 修复
- `frontend/src/stores/jobseeker.ts` — token key 修复
- `frontend/src/router/index.ts` — Home 页 requiresAuth
- `frontend/src/pages/Login.vue` — 移除默认密码提示

---

## Phase 19: 前后端 API 对齐

**Goal:** 修复所有已知的前后端请求/响应结构不匹配，补全前端缺失的 API 消费，修复参数语义错误。

**Requirements:**
- API-01: learning/plan createPlan 请求结构修复 — 前端发送 `Record<string, unknown>`，后端要求 `CreatePlanRequest` 含 `match_score` + `SkillGapInput`
- API-02: evolution/changelog 参数语义修复 — 前端传 skill name，后端期望 position name
- API-03: loop/run target_position 可选/必填对齐 — 前端可选发送，后端必填
- API-04: dashboard overview 字段映射修复 — `today_matches` 始终为 0, `quality_score` vs `trust_score`
- API-05: match/batch 响应结构对齐 — 前端期望 `BatchMatchItem[]` 字段与后端不同
- API-06: positions 列表响应结构统一 — 前端防御性解析 `data.items ?? data ?? []` 说明后端响应不稳定
- API-07: datasource daily_crawl_volume 字段 — 前端使用但不在 schema 类型中
- API-08: learning plan overall_progress vs overall_pct 命名对齐

**Success criteria:**
1. 创建学习计划 POST 请求包含完整 `CreatePlanRequest` 字段，后端返回 200
2. Evolution changelog 使用 position 参数调用，返回正确数据
3. Loop run 在 target_position 为空时不报 422
4. Dashboard overview 所有 KPI 字段正确映射和显示
5. Match batch 响应字段与前端类型定义一致
6. Positions 列表响应结构稳定，无需防御性解析
7. 所有 API 调用使用正确的字段名，无类型断言绕过

**Key files:**
- `frontend/src/stores/learningPlan.ts` — createPlan 请求结构
- `frontend/src/stores/evolution.ts` — changelog 参数
- `frontend/src/stores/loop.ts` — target_position
- `frontend/src/stores/dashboard.ts` — overview 字段映射
- `frontend/src/stores/learningRecommendation.ts` — batch match 响应
- `frontend/src/stores/jd.ts` — positions 响应
- `frontend/src/stores/datasource.ts` — daily_crawl_volume
- `backend/app/api/v1/learning.py` — CreatePlanRequest schema
- `backend/app/api/v1/evolution.py` — changelog 参数语义
- `backend/app/api/v1/loop.py` — target_position Optional

---

## Phase 20: 数据流闭环

**Goal:** 闭合 7 大核心数据流断点，确保业务端到端贯通：用户操作 → 后端处理 → 前端展示 → 下游消费。

**Requirements:**
- FLOW-01: 匹配诊断 → 学习中心贯通 — MatchDiagnosis Step 4 "创建学习计划" 按钮自动跳转 `/learning` 并预填数据
- FLOW-02: JD 抽取 → PositionRecord 自动创建 — POST /extract/jd 成功后自动写入 PG position_records，/positions 可查到
- FLOW-03: 学习进度 → 用户技能更新 — skill 标记 mastered 后 userStore.parsedSkills 更新，重新匹配反映进步
- FLOW-04: 演化告警前端消费 — emerging-alerts 端点数据在 EvolutionDashboard 展示
- FLOW-05: 管理审核 → Neo4j 同步 — approve/reject 同步更新 Neo4j 节点 trust_score/status
- FLOW-06: Pipeline 权限前端适配 — 非 admin 用户隐藏 trigger/config/schedule 控件
- FLOW-07: 演化分析定时触发 — Celery beat 定时触发 evolution analysis（当前仅手动）
- FLOW-08: 简历技能 proficiency 保留 — 当前 resume skills 存为 plain string + fake skill_id，丢失 proficiency 数据

**Success criteria:**
1. MatchDiagnosis Step 4 点击"创建学习计划"→ 跳转 LearningCenter → 自动创建计划
2. ExtractJD 抽取后 PositionList 可查到新岗位
3. 学习计划中 skill 标记 mastered → 重新匹配分数提升
4. EvolutionDashboard 展示 emerging alerts 列表
5. Admin approve/reject → Neo4j 节点状态同步更新
6. Pipeline Monitor 非 admin 用户看不到 trigger/config/schedule
7. Celery beat 配置 evolution 定时分析 cron
8. Resume 解析保留 skill proficiency 数据

**Key files:**
- `frontend/src/pages/MatchDiagnosis.vue` — Step 4 创建计划按钮
- `frontend/src/composables/useLearningActions.ts` — 创建计划跳转
- `backend/app/api/v1/extract.py` — PositionRecord 创建
- `frontend/src/stores/user.ts` — parsedSkills 更新
- `frontend/src/stores/evolution.ts` — alerts 消费
- `backend/app/services/admin_audit_service.py` — Neo4j 同步
- `frontend/src/pages/PipelineMonitor.vue` — admin 权限适配
- `backend/app/tasks/celery_app.py` — evolution 定时任务
- `frontend/src/stores/resume.ts` — proficiency 保留

---

## Phase 21: SSE 实时连接接通

**Goal:** 将 3 个 SSE 端点端到端接通前端，确保实时数据推送正常工作。

**Requirements:**
- SSE-01: Dashboard realtime SSE 接通 — `/dashboard/realtime` EventSource 连接 + 事件消费
- SSE-02: Pipeline events SSE 接通 — `/pipeline/events` EventSource 连接 + 事件消费
- SSE-03: Jobseeker analyze SSE 鉴权修复 — `/pipeline/analyze` SSE 流携带正确 token
- SSE-04: SSE 事件类型前端消费 — skill_update, match_event, graph_update, pipeline_update, quality_alert, data_milestone, extraction_complete 全部有对应 store handler
- SSE-05: SSE URL 使用 VITE_API_BASE_URL — 当前 dashboard SSE 硬编码 `/api/v1/dashboard/realtime`

**Success criteria:**
1. DataDashboard 页面 SSE 连接建立，实时事件推送更新 KPI 和图表
2. PipelineMonitor 页面 SSE 连接建立，pipeline 状态实时更新
3. PipelineAnalysis 页面 SSE 流正常接收 progress/result 事件
4. 所有 7 种 SSE 事件类型有对应 store handler 处理
5. SSE URL 使用环境变量，Docker 和本地开发均可工作

**Key files:**
- `frontend/src/composables/useDashboardRealtimeSync.ts` — dashboard SSE
- `frontend/src/composables/usePipelineMonitor.ts` — pipeline SSE
- `frontend/src/stores/jobseeker.ts` — analyze SSE
- `frontend/src/composables/useSSE.ts` — 通用 SSE composable
- `frontend/src/stores/dashboard.ts` — SSE 事件消费
- `frontend/src/stores/pipeline.ts` — SSE 事件消费
- `backend/app/api/v1/dashboard.py` — SSE 端点
- `backend/app/api/v1/pipeline/routes.py` — SSE 端点

---

## Phase 22: 基础设施配置统一

**Goal:** 修复 Docker 开发模式、统一 .env 配置、对齐端口、修正 CORS，确保全栈可一键启动。

**Requirements:**
- INFRA-01: Docker dev VITE_API_BASE_URL 修复 — 当前指向容器 hostname，浏览器不可达
- INFRA-02: Vite proxy port 对齐 — 默认 8002 vs 后端实际 8000
- INFRA-03: .env 文件统一 — 4 个冲突 .env 文件合并为 2 个（.env + .env.docker）
- INFRA-04: backend/.env 缺少 AUTH_USERS — 本地启动登录返回 "user not found"
- INFRA-05: CORS 配置覆盖 Docker 内部网络 — 服务间通信被 CORS 阻断
- INFRA-06: Frontend container healthcheck — Docker Compose 无前端健康检查
- INFRA-07: docker-compose.dev.yml depends_on condition — 缺少 service_healthy 条件

**Success criteria:**
1. `docker compose -f docker-compose.dev.yml up` 一键启动，前端可访问后端 API
2. 本地 `npm run dev` + `poetry run uvicorn` 可正常工作
3. .env 文件有且仅有 2 个：根目录 `.env`（本地开发）+ `.env.docker`（Docker）
4. 登录功能在 Docker 和本地模式均可工作
5. CORS 不阻断任何前端→后端请求
6. Docker Compose 所有服务有 healthcheck
7. Frontend 容器等待 backend healthy 后再启动

**Key files:**
- `docker-compose.dev.yml` — VITE_API_BASE_URL + depends_on
- `frontend/vite.config.ts` — proxy port
- `.env.example` — 统一模板
- `backend/.env.example` — AUTH_USERS 说明
- `backend/app/main.py` — CORS 配置
- `frontend/Dockerfile.dev` — healthcheck

---

## Phase 23: UAT 全链路验证

**Goal:** 对所有页面进行手工级别的端到端验证，修复发现的运行时错误，确保业务准确无报错。

**Requirements:**
- UAT-01: 登录流程验证 — 登录/登出/刷新 token/修改密码/强制改密 全流程
-流程
- UAT-02: 图谱浏览验证 — Home 页 2D/3D 图谱加载、节点点击、搜索、演化抽屉
- UAT-03: 匹配诊断验证 — 5 步向导完整走通：上传简历→选岗位→雷达→差距→学习计划
- UAT-04: 学习中心验证 — 创建计划、更新进度、推荐、技能掌握→重新匹配
- UAT-05: 演化看板验证 — 趋势图、快照、告警、changelog、职业路径
- UAT-06: 管理后台验证 — 审核队列、图谱节点管理、数据源、Prompt、用户管理、审计日志
- UAT-07: Pipeline 验证 — 状态查看、触发、取消、重试、调度、配置
- UAT-08: 数据大屏验证 — KPI、图表、SSE 实时更新

**Success criteria:**
1. 所有 17 个页面无 JS 报错、无 API 500、无白屏
2. 核心业务流（登录→图谱→匹配→学习→演化→管理）端到端贯通
3. SSE 实时连接在 Dashboard 和 Pipeline 页面正常工作
4. Admin 功能（审核、用户管理、Prompt 管理）全部可用
5. 所有表单提交有正确的成功/错误反馈
6. 空数据状态有 EmptyState 展示，无空白区域
7. 分页、搜索、筛选功能正常
8. 响应式布局在 1280px+ 宽度正常

**Key files:**
- All frontend pages
- All backend API endpoints
- Docker Compose configuration
