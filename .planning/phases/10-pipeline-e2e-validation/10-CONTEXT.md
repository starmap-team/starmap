---
phase: 10-pipeline-e2e-validation
status: ready_for_planning
gathered: 2026-07-10
---

# Phase 10: Pipeline 端到端验证 — Context

<domain>
## Phase Boundary

确保 v2.1 真实数据链路全通：Playwright 浏览器依赖 + 代理支持 + 一次启动触发 + 端到端冒烟验证 (crawl → dedup → clean → extract → graph_sync → 前端展示真实数据)。
这是 v2.1"真实数据切换"的最后一层：从前端 UI 下行到爬虫采集的真实数据采集闭环。

**前置已经具备:**
- ✅ Phase 8 后端清理（auto-seed/reset-demo 删，`/health/detail` 配置校验，LLM 降级链打通）
- ✅ Phase 9 前端 MSW 关闭 + placeholder 删除 + Vite proxy 真实 API
- ✅ Pipeline 框架（`backend/app/core/pipeline/`：orchestrator/executor/cron_scheduler/loop_orchestrator/quality_monitor/source_authority）
- ✅ Celery worker + SSE 事件广播 + Redis pub/sub
- ✅ 5 阶段 DAG（crawl → dedup ∥ clean → import → graph_sync）
- ✅ Neo4j/PG/Redis/Ollama Docker 编排，`/health/detail` 4 服务 ping

**本阶段 4 个灰色地带（仅实现决策）:**
1. **G1** Playwright 安装方式（镜像 vs pip install）
2. **G2** PROXY_LIST 加载策略（解析 + fallback + 熔断）
3. **G3** Pipeline 触发方式（启动 bootstrap + API + CLI 组合）
4. **G4** E2E 冒烟验证谱宽度（happy-path / 核心覆盖 / 边界+负向）

</domain>

<decisions>
## Implementation Decisions

### G1 Playwright 安装方式 (PIPE-01) — 官方镜像锁定
- **D-01 (User-selected):** **使用 `mcr.microsoft.com/playwright/python:v1.49.0-jammy` 作为 celery-worker 容器 base image**。不再使用 `RUN pip install playwright && playwright install --with-deps` 两步，改为直接继承 Playwright 官方镜像（已含 Chromium + 系统依赖 + Node）。理由：可复现性强、构建期不联网、体积虽大但已压缩、Phase 10 不再需要重新解决 Chromium 安装的边缘 case
  - 影响文件: `backend/Dockerfile.dev`（celery-worker 服务重写 FROM 指令）
  - 锁定版本 v1.49.0（与 `playwright` Python 包当前 pin 兼容；如果项目未固定 playwright 版本则优先查看当前 `requirements.txt` 的 playwright 行）
  - 保留 `playwright install-deps` 步骤不再需要（官方镜像已含）

### G2 PROXY_LIST 加载策略 (PIPE-02) — 逐项试用 + 失败熔断 + 熔断窗口
- **D-02 (User-selected):** **逗号分隔 `PROXY_LIST=http://1.2.3.4:8080,http://5.6.7.8:8080`，**scrapy 中间件逐项试用**，最近 5 分钟内 ≥3 次连接失败的代理进入 5 分钟冷却期**。理由：高失败率代理池下不浪费新请求，熔断比 round-robin 更现实；与 Phase 8 D-07 补全的 PROXY_LIST 字段兼容
  - 实现位置: `crawler/spiders/boss.py` 或新的 `crawler/middleware/proxy_middleware.py`
  - 配置读取: `crawler/config.py` 新增 `PROXY_LIST` 解析，返回 `list[ProxyEntry]`
  - 熔断状态: 模块级 `_BREAKER_STATE: dict[str, BreakerState]`（足够小规模；如需 cluster 级别共享推 Phase 11+ Redis）
  - 默认值: 当 `PROXY_LIST` 未设置或为空 → None（直连 + WARNING 日志）
  - 复用: `crawler/config.py` 的 loguru logger 与现有 settings 模式

### G3 Pipeline 触发方式 (PIPE-03) — API + CLI + 启动 cron
- **D-03 (User-selected):** **三选一组合**:
  - (a) **API:** `POST /api/v1/pipeline/trigger`（已存在，确认并补全单元测试）
  - (b) **CLI:** `python -m crawler.run run-pipeline`（新增 `run-pipeline` 子命令，包内调用 `pipeline_orchestrator.trigger_run()`）
  - (c) **Startup cron:** celery-worker 启动后 30 秒延迟检测环境变量 `PIPELINE_BOOTSTRAP=true`，存在则入队一次完整 pipeline run（与 cron_scheduler 复用，**不是周期跑**，仅一次性 bootstrap）
- 理由: 新手一条命令 `docker compose up` 就能看到真实数据进入 Neo4j;开发者日常手工 trigger 通过 API/CLI
  - 实现位置:
    - (a) `backend/app/api/v1/pipeline.py` — 确认 POST 端点存在并测试
    - (b) `crawler/run.py` — argparse 子命令 + 调用 orchestrator
    - (c) `backend/app/core/pipeline/bootstrap.py`（新文件，30 秒延迟 + Celery 任务延迟入队）
  - 复用 `backend/app/core/pipeline/cron_scheduler.py` 的延迟运行 pattern

### G4 E2E 冒烟验证谱 (PIPE-04) — 边界 + 负向验证
- **D-04 (User-selected):** **包含采集、抽取、图谱写入 + 边界/负向场景**。约 7-8 条断言:
  - crawl: BOSS 爬虫成功抓取 ≥5 条 JD（200 网络或可解析 HTML）
  - dedup: 重复 JD 不入库，hash 计算正确
  - clean: 清洗后文本字段非空且去除 HTML
  - extract: LLM 抽取技能数 ≥10，且至少有一条 SKILL 由 cross-source 验证通过
  - graph_sync: Neo4j 中 `Skill/Position` 节点数 ≥5/3 且存在 `REQUIRES` 关系
  - **负向**: 当所有 PROXY 不可用时退化为直连（不直接 fail pipeline）
  - **降级**: 三个云端 LLM key 全部缺失 → 降级到 Ollama 仍能抽取（与 Phase 8 D-04 兼容）
  - **前端**: 真实图谱页加载 (`/position/data-engineer` 等)，节点数据 ≠ mock 的 5 个职位硬编码（Phase 9 已删除 mock，验证 page-level absence of mockServiceWorker）

### Claude's Discretion
- 启动 cron 的 30 秒延迟具体值（建议保持 30s，留 Celery worker 充分启动时间）
- 熔断窗口 5 分钟（用户选定）的精确阈值：失败次数 ≥3 进入冷却是用户选定的中间值
- E2E 脚本的存放位置 `tests/e2e/` 已有 INTEGRATION_TEST_PLAN.md，新断言可作为扩展或拆分为 `pipeline_smoke_test.py` pytest 集成测试
- Playwright 镜像 tag 选择（v1.49.0 与 Python package 的实际 pin 协调）

### 验证指标（硬性）
- **D-05:** **`POST /api/v1/pipeline/trigger` 返回 202** + pipeline run 状态可查
- **D-06:** **`python -m crawler.run run-pipeline` CLI 可运行，退出码 0**
- **D-07:** **`PIPELINE_BOOTSTRAP=true` + `docker compose up` 在 90 秒内入队 pipeline run**
- **D-08:** **`PROXY_LIST` 未设置时不阻断爬虫；设置时逐项试用并熔断**
- **D-09:** **E2E 冒烟 pytest 通过**，覆盖 D-04 列出的 7-8 条断言
- **D-10:** **`pytest` 全量无回归**（pipeline/celery 相关测试需同步）
- **D-11:** **`ruff check` + `mypy backend/app` 通过**

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 项目级决策（不重做）
- `.planning/PROJECT.md` — v2.1 真实数据切换、DEC-001~006、DEC-011
- `.planning/REQUIREMENTS.md` §PIPE-01~04 — 4 个 Pipeline 需求
- `.planning/ROADMAP.md` §Phase 10 — 成功标准、关键文件
- `.planning/STATE.md` — 当前状态、已锁定决策

### 前序阶段决策（不重做）
- `.planning/phases/09-frontend-mock-off/09-CONTEXT.md` — Phase 9 前端关闭 Mock（mock/ 目录已删，Vite proxy 已通）
- `.planning/phases/09-frontend-mock-off/09-UAT.md` — Phase 9 UAT 测试 7/7 通过 + DEC-012 (undefined vs null)
- `.planning/phases/08-backend-cleanup/08-CONTEXT.md` — Phase 8 后端清理（D-03 前端 demo 协调、D-04 LLM 校验仅 warning、D-07 .env.example 补 PROXY_LIST 字段）

### 后端配置 + Pipeline 框架
- `backend/app/config.py` — Settings、`model_validator`（CFG-01/02 校验已存在）
- `backend/app/core/pipeline/orchestrator.py` — DAG 编排，5 阶段 crawl→dedup∥clean→import→graph_sync
- `backend/app/core/pipeline/executor.py` — Stage 执行器
- `backend/app/core/pipeline/cron_scheduler.py` — 已存在的 cron pattern（D-03 复用 30 秒延迟逻辑）
- `backend/app/core/pipeline/loop_orchestrator.py` — 循环模式（如不涉及则不读）
- `backend/app/tasks/celery_app.py` — Celery worker 入口、execute_pipeline_stage 任务

### 爬虫 + 代理 (PIPE-02)
- `crawler/spiders/boss.py` — BOSS 爬虫（v2.1 唯一目标；lagou/51job 后续扩展属 Out of Scope）
- `crawler/config.py` — 已有 settings 解析 pattern（PROXY_LIST 解析点）
- `crawler/middleware/` — 新建目录（如不存在）放代理中间件
- `crawler/run.py` — CLI 入口（D-03 新增 run-pipeline 子命令的位置）

### 容器 + 镜像 (PIPE-01)
- `backend/Dockerfile.dev` — celery-worker 服务的 Dockerfile（D-01 重写 FROM 行）
- `docker-compose.dev.yml:175` — Ollama 容器（参考网络配置）
- `.planning/phases/08-backend-cleanup/08-CONTEXT.md` §G4 — `.env.example` 已含 PROXY_LIST 字段（D-02 配置读取源）

### API + 健康检查
- `backend/app/api/v1/pipeline.py` — POST `/api/v1/pipeline/trigger` 端点（D-03 确认存在并测试）
- `backend/app/api/v1/health.py` — `/health/detail`（D-04 健康断言用）

### 前端图谱 + 真实数据展示
- `frontend/src/stores/graph.ts` — Pinia graph store（E2E 前端断言参考）
- `frontend/src/pages/` — Graph3D/Graph2D 入口（`/position/:name` 路由）

### 测试与验证
- `tests/e2e/INTEGRATION_TEST_PLAN.md` — 已有集成测试计划（D-04 扩展为 pipeline_smoke_test.py）
- `tests/e2e/INTEGRATION_FINAL_REPORT.md` — 既有集成测试结果
- `backend/tests/unit/test_cron_scheduler.py` — 已存在（Phase 7 加）— D-03 cron 模式参考
- `backend/tests/unit/test_progress_tracker.py`, `test_quality_monitor.py`, `test_status_aggregator.py` — pipeline 相关单测
- `frontend/tests/` — 前端测试（无任何 Vitest 单元测试，D-04 前端断言需要 puppeteer/playwright Python）

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Celery worker Dockerfile pattern** — `backend/Dockerfile.dev` 已有，需替换 FROM 行（保留其余 COPY/RUN/CMD 结构）
- **cron_scheduler 30s 延迟 pattern** — `backend/app/core/pipeline/cron_scheduler.py` 有 `schedule_first_run_after_delay` 类似代码可直接复用
- **LLM 降级链** — `backend/app/core/extraction/llm_client.py` `call_llm_with_fallback()` 提供 MiMo→DeepSeek→Xunfei→Ollama 顺序（D-04 负向断言兼容性）
- **SSE 事件广播** — `backend/app/core/dashboard/sse_broadcaster.py` + Redis pub/sub（前端 `useDashboardRealtimeSync` 消费，D-03 触发后可在 dashboard 实时看进度）
- **`/health/detail` 端点** — 已有，可作为 D-04 E2E 前置断言（4 服务必须全 ok 才能跑 pipeline）
- **crawler/config.py settings pattern** — 已有 `BaseSettings` 模式（pydantic-settings），新增 PROXY_LIST 解析字段沿用同样风格

### Established Patterns
- **契约优先**: 删/改 API 端点先改 `starmap-contracts/openapi.yaml` 再 `gen:api`（CLAUDE.md 约定；Phase 10 仅新增路由则仍要补 openapi）
- **环境变量 pattern**: PROXY_LIST 已存在 `.env.example` 字段（Phase 8 D-07）；`crawler/config.py` 读取沿用 `Settings` 类
- **Pipeline stage pattern**: `executor.py` 中的 `run_stage()` 抽象 — D-03 trigger 不需要新增 stage，仅入队 orchestrator 已有 DAG
- **Celery task pattern**: `backend/app/tasks/celery_app.py` 的 `execute_pipeline_stage` task decorator 模式

### Integration Points
- `backend/Dockerfile.dev` — D-01 改 FROM
- `crawler/spiders/boss.py` — D-02 接入代理 middleware
- `crawler/run.py` — D-03 新增 run-pipeline 子命令
- `backend/app/core/pipeline/bootstrap.py`（新） — D-03 startup check
- `crawler/middleware/proxy_middleware.py`（新） — D-02 代理熔断
- `tests/e2e/pipeline_smoke_test.py`（新） — D-04 集成测试
- `docker-compose.dev.yml` — `celery-worker` 服务需确认环境变量列表包含 `PIPELINE_BOOTSTRAP`、`PROXY_LIST`
- `.env.example` — 已有 PROXY_LIST（Phase 8 D-07），补 `PIPELINE_BOOTSTRAP`

</code_context>

<specifics>
## Specific Ideas

- D-01 镜像锁定：建议 tag `v1.49.0-jammy`；需查 `backend/requirements.txt` 中 `playwright==` 行号选择兼容版本
- D-02 熔断实现：模块级 `dict[str, tuple[float, int]]` 记录 `(fail_window_start, fail_count)`；每次请求失败 `fail_count += 1`，5 分钟滑窗内 ≥3 失败 → 5 分钟冷却；冷却结束后重新接受。可选 backoff：reset 失败计数按窗口滑
- D-03 startup bootstrap 的 30 秒延迟用 `celery_app.conf.beat_schedule` 也行，但一次性用 `threading.Timer` 或 asyncio 延迟调用更轻量；建议放入 `backend/main.py` 启动 lifespan handler
- D-03 CLI 子命令示例：`python -m crawler.run run-pipeline [--source boss] [--limit 50]` — 复用 orchestrator.trigger_run()，传入可选项
- D-04 E2E 集成测试为 pytest 形式，运行命令 `pytest tests/e2e/pipeline_smoke_test.py -v -m smoke`（需配 marker）；CI 中只 `smoke` marker 跑
- D-04 前端断言：在 `tests/e2e/` 用 subprocess 启动前端 dev server + Playwright Python 加载 `http://localhost:5173/position/data-engineer`，对比 DOM 与 mock 数据判别
- PROXY_LIST 格式兼容 scrapy 中间件约定 `http://user:pass@host:port` 也支持 — 解析时区分

</specifics>

<deferred>
## Deferred Ideas

- **多爬虫并行（lagou/51job）** — Out of Scope（PIPE-02 仅 boss 跑通即可；REQUIREMENTS.md 已明示）
- **大规模数据采集** — Out of Scope（v2.1 验证链路通，不追数量）
- **生产环境部署** — Out of Scope（仅开发环境真实数据）
- **周期跑 cron** — Phase 10 仅一次性 bootstrap；周期 task 留 v2.2
- **Redis 共享代理熔断状态** — Phase 10 单 worker 进程 module-level dict 足够；cluster 部署时改 Redis 推 v2.2
- **E2E 全链路覆盖图谱渲染视觉断言** — Phase 10 仅数据层断言，视觉断言属 ui-review 范畴
- **真实 Proxy 池管理后台** — Out of Scope

</deferred>

---

*Phase: 10-pipeline-e2e-validation*
*Context gathered: 2026-07-10*
*Next: `/gsd:plan-phase 10`*
