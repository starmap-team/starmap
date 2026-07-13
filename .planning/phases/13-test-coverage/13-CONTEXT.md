# Phase 13: 测试覆盖率提升 - Context

**Gathered:** 2026-07-13
**Status:** Ready for planning
**Source:** /gsd:discuss-phase 13

<domain>
## Phase Boundary

将 StarMap 测试基础设施从"部分覆盖+已知失败"升级到"CI 可靠+核心业务链路深度覆盖"：

1. 修复 41 个测试失败背后的真实代码 bug（非修测试，而是修项目代码）
2. 后端核心业务链路深度测试（Pipeline 执行器、LLM 客户端、抽取 API、图谱 API）
3. 前端 5 个核心 Store + 3 个关键 composable 测试
4. CI 覆盖率门禁从 60% 提升到 70%

前置条件：Phase 12 安全加固完成（PyJWT/bcrypt/IDOR/FK/Settings guard 已验证）。

</domain>

<decisions>
## Implementation Decisions

### 策略原则 (TEST-STRATEGY)
- **DEC: 测试失败 = 项目 bug** — 测试失败时，从项目代码和架构入手修复，不为通过测试而修测试。保障项目质量来确保测试质量。
- **DEC: Bug-fix + fill gaps** — 先修 41 个失败测试背后的代码 bug，再补零测试模块。确保 CI 全绿后再写新测试。
- **DEC: 深度优先** — 后端集中火力给核心业务链路写深度测试（Pipeline/LLM/抽取/图谱），其他低覆盖模块只写基本 smoke 测试。
- **DEC: Store + 3 composable 全写** — 前端 5 个核心 Store（learning, loop, evolution, dashboard, pipeline）+ 3 个 composable（useSSE, useLearning*, useG6*）全部写测试。
- **DEC: CI 门禁 70%** — `--cov-fail-under=70`，比当前 78% 低 8% 留缓冲，比旧 60% 高 10% 防回退。

### 41 个失败测试的代码 Bug 分类 (BUG-CATEGORIES)

#### Category A: 项目代码 Bug（需修项目代码）
1. **UnboundLocalError** — `graph_overview.py:190,295` 中 `independent_pos` 在条件分支中未赋值就被使用。影响 4 个测试。
2. **Domain exception 未捕获** — `cancel_run()` 抛 `RunNotFoundError`/`RunAlreadyTerminalError`，但 API 层未 catch 映射为 HTTP。影响 3 个测试。
3. **Validation 缺失** — `loop_api` 接受空 target（应 422），`datasource` status 验证不完整。影响 3 个测试。
4. **Learning API 404** — `update_progress` 返回 404，可能是 IDOR guard 或 record 查询问题。影响 3 个测试。
5. **Health endpoint 变更** — `/health/detail` 不再返回 `demo_data` key（Phase 8 已删除 demo），但测试仍期望。影响 1 个测试。

#### Category B: 测试基础设施问题（需修测试辅助代码）
6. **Auth mock 不完整** — `_decode_token` 使用 `settings.jwt_leeway_seconds`，但测试 mock settings 为 MagicMock（属性返回 MagicMock 而非 int）。需 patch settings 属性而非整个对象。影响 12 个测试。
7. **Integration test session init** — `test_extraction_api.py` 使用 TestClient 但 PostgreSQL sessionmaker 未初始化。需添加 fixture 或 mock。影响 7 个测试。
8. **Stale test expectations** — `pipeline_orchestrator` 现有 6 个 stage（TIMESERIES 已添加），测试期望 5。影响 2 个测试。
9. **AB test fixture broken** — `test_ap07_fe02` DB session未初始化。影响 2 个测试。
10. **Evolution sub-api** — `test_industry_report_empty_timeseries_fallback` 返回 500（ValueError: too many values to unpack）。影响 1 个测试。

### 后端深度测试目标 (BACKEND-DEPTH)
- **Pipeline 执行器** (`executor.py`, 9%) — 核心业务链路，测试 advance_pipeline、stage 调度、错误恢复
- **LLM 客户端** (`llm_client.py`, 23%) — 降级链、fallback、超时处理
- **JD 抽取 API** (`extract.py`, 37%) — 端到端抽取流程、验证、错误处理
- **图谱 API** (`graph.py`, 44%) — overview、search、layer navigation
- **其他低覆盖模块** — smoke 测试（≥5 个基本测试），不追求深度

### 前端测试目标 (FRONTEND-SCOPE)
- **5 个核心 Store**: learning, loop, evolution, dashboard, pipeline
- **3 个 composable**: useSSE (SSE 鉴权+重连), useLearningActions (学习操作), useG6 (图谱渲染)
- **测试模式**: Pinia `setActivePinia(createPinia())` + `vi.mock('@/api/request')` + Vue 生命周期 mock

### CI 门禁 (CI-GATE)
- **DEC: `--cov-fail-under=70`** — 从 60% 提升到 70%
- 当前实际 78%，修 bug + 补测试后预计 85%+
- 70% 为 Phase 14/15 留 15% 缓冲（新文件初始 0% 覆盖）

</decisions>

<canonical_refs>
## Canonical References

### 项目规范
- `AGENTS.md` — 技术栈、代码风格、项目约定
- `.planning/ROADMAP-v2.2.md` — v2.2 全量路线图（Phase 13 定义）
- `.planning/STATE.md` — 当前项目状态
- `.planning/codebase/TESTING.md` — 测试基础设施、模式、缺口清单（MUST READ）

### 已有安全实现（Phase 12 产出，影响测试）
- `backend/app/api/v1/auth.py` — PyJWT encode/decode（旧测试需适配）
- `backend/app/dependencies.py` — _decode_token 使用 settings.jwt_leeway_seconds
- `backend/app/config.py` — JWT settings 字段、safe_update()
- `backend/app/exceptions.py` — 领域异常（RunNotFoundError, RunAlreadyTerminalError 等）

### 需修 Bug 的源文件
- `backend/app/services/graph_overview.py` — UnboundLocalError at line 190, 295
- `backend/app/core/pipeline/orchestrator.py` — cancel_run domain exceptions 未映射 HTTP
- `backend/app/api/v1/loop.py` — 空 target validation 缺失
- `backend/app/api/v1/datasource.py` — status validation 不完整
- `backend/app/api/v1/learning.py` — update_progress 404 问题
- `backend/app/api/v1/evolution_industry_report.py` — ValueError: too many values to unpack

### 需补测试的低覆盖模块
- `backend/app/core/pipeline/executor.py` — 9% 覆盖率
- `backend/app/core/extraction/llm_client.py` — 23% 覆盖率
- `backend/app/tasks/celery_app.py` — 27% 覆盖率
- `backend/app/core/extraction/resume_eval.py` — 30% 覆盖率
- `backend/app/api/v1/extract.py` — 37% 覆盖率
- `backend/app/pipeline/steps.py` — 41% 覆盖率
- `backend/app/api/v1/graph.py` — 44% 覆盖率

### 前端需补测试
- `frontend/src/stores/learning.ts` — 无测试
- `frontend/src/stores/loop.ts` — 无测试
- `frontend/src/stores/evolution.ts` — 无测试
- `frontend/src/stores/dashboard.ts` — 无测试
- `frontend/src/stores/pipeline.ts` — 无测试
- `frontend/src/composables/useSSE.ts` — 无测试
- `frontend/src/composables/useLearningActions.ts` — 无测试（或 useLearning*.ts）
- `frontend/src/composables/useG6.ts` — 无测试

### 已有测试模式参考
- `backend/tests/unit/test_auth_security.py` — Phase 12 新增，PyJWT 测试模式
- `backend/tests/unit/test_loop_idor.py` — Phase 12 新增，IDOR 测试模式
- `frontend/src/stores/__tests__/graph.test.ts` — Store 测试模式参考
- `frontend/src/stores/__tests__/match.test.ts` — Store 测试模式参考

</canonical_refs>

<specifics>
## Specific Ideas

1. Bug 修复顺序：先修 Category A（项目代码 bug），再修 Category B（测试基础设施），最后写新测试
2. `graph_overview.py` UnboundLocalError：在条件分支前初始化 `independent_pos = []`
3. Domain exception 映射：在 API 层添加 `except (RunNotFoundError, RunAlreadyTerminalError)` → HTTP 404/409
4. Auth mock 修复：使用 `patch.object(settings, 'jwt_leeway_seconds', 30)` 而非 mock 整个 settings
5. Integration test 修复：添加 `@pytest.fixture` 初始化 sessionmaker 或 mock `get_session_factory()`
6. Pipeline executor 测试：重点测试 `_check_stop_flag`, `_skip_optional_stages`, `_complete_run_if_done`（Phase 14 拆分后的子函数）
7. LLM client 测试：测试 fallback chain（MiMo → DeepSeek → Xunfei → Ollama）、超时、重试
8. useSSE 测试：mock EventSource，测试 token query-param、重连逻辑、事件解析
9. useG6 测试：mock G6 Graph 构造，测试 node/edge 数据映射、layer 切换

</specifics>

<codebase_context>
## Reusable Assets

### Backend Test Patterns
- **FakeNode/FakeRelationship** — Neo4j mock 模式（见 TESTING.md）
- **FakeSession/FakeResult** — SQLAlchemy mock 模式
- **`app.dependency_overrides`** — FastAPI 依赖注入替换
- **`autouse=True` conftest fixture** — 全局状态清理

### Frontend Test Patterns
- **Pinia reset** — `setActivePinia(createPinia())` in `beforeEach`
- **API mock** — `vi.mock('@/api/request', () => ({ default: { get: vi.fn(), post: vi.fn() } }))`
- **ECharts mock** — `vi.mock('vue-echarts', ...)` + `vi.mock('echarts/core', ...)`
- **Element Plus stubs** — `global.stubs` in `mount()` options

### Existing Test Infrastructure
- pytest 8.0+ with asyncio_mode = "auto"
- vitest 1.4+ with jsdom environment
- Coverage gate: `--cov-fail-under=60` (→ 70%)
- conftest.py: autouse fixture clears dependency_overrides + _rate_buckets

</codebase_context>

<deferred>
## Deferred Ideas

- 前端组件测试（33 个组件无测试）— Phase 14 拆分后再补
- E2E 测试增强（JD 抽取流程、Resume 上传、Match 诊断向导）— 独立 Phase
- 前端覆盖率门禁 — 当前无，需 vitest coverage 配置
- Mutation testing — 验证测试质量，长期目标
- Property-based testing (hypothesis) — 高级测试策略，长期目标
- 测试数据工厂共享 — 当前每文件内联，可提取为 conftest fixtures

</deferred>

---
*Phase: 13-test-coverage*
*Context gathered: 2026-07-13 via /gsd:discuss-phase*
