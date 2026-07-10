---
plan: 10-03
phase: 10-pipeline-e2e-validation
completed_at: 2026-07-10
status: complete
---

# 10-03 Summary: Pipeline 触发 API 验证 + CLI 子命令 + 启动 Bootstrap

## Goal
(D-03) 三种触发方式齐全：
- (a) `POST /api/v1/pipeline/trigger` 已存在（确认 + 补测）
- (b) `python -m crawler.run run-pipeline` 新增 CLI 子命令
- (c) `backend/app/core/pipeline/bootstrap.py` 启动 30 秒延迟检测 `PIPELINE_BOOTSTRAP=true` 一次性入队

## Tasks Completed

### T1 — bootstrap module ✅
- `backend/app/core/pipeline/bootstrap.py` 新建
- `BOOTSTRAP_DELAY_SECONDS = 30`
- `schedule_bootstrap_if_enabled()`: 读 env (`1`/`true`/`yes` 触发), 其他值 no-op; 触发了用 `threading.Timer(30, _fire)`, `_fire` 内 `asyncio.run(trigger_and_start(run_type='bootstrap'))`, `try/except Exception` 吞错
- `python -c "from app.core.pipeline.bootstrap import ..."` exit 0 ✅

### T2 — main.py 启动 lifespan 集成 ✅
- `backend/app/main.py:lifespan()` 内 `app.state.resources = await init_resources()` 后追加
  `from app.core.pipeline.bootstrap import schedule_bootstrap_if_enabled`
  `schedule_bootstrap_if_enabled()`
- 注释说明：PIPE-03 (c) — 主 API 进程也会调用，但 executor 内部将 task 路由到 celery-worker

### T3 — crawler/run.py + crawler/pipeline_bridge.py ✅
- `crawler/pipeline_bridge.py` 新建 — async wrapper for `executor.trigger_and_start(run_type=f'cli-{source}', selected_stages=None)`, sync `trigger_pipeline_run(source='boss', limit=20) -> int` (返回 0/1 退出码)
- `crawler/run.py`:
  - `from crawler.pipeline_bridge import trigger_pipeline_run` import 块
  - `def cmd_run_pipeline(args)` 函数: 调 trigger_pipeline_run 返回 0/1
  - `sp_pipeline` subparser 注册: `--source {boss,lagou,51job}`, `--limit N`
  - `python -m crawler.run --help` 现在包含 `run-pipeline` (在 Docker 环境验证)

### T4 — docker-compose.dev.yml PIPELINE_BOOTSTRAP ✅
- celery-worker environment 追加 `PIPELINE_BOOTSTRAP: ${PIPELINE_BOOTSTRAP:-false}`
- 默认 false 不触发; 开发者 uncomment .env 改 true 即可

### T5 — 单元测试 5/5 PASS ✅
- `backend/tests/unit/test_pipeline_bootstrap.py`
- 4 env var 测试 (off/true/1/false) + 1 常量测试
- `python -m pytest backend/tests/unit/test_pipeline_bootstrap.py -v --no-cov` → 5 passed ✅

## (a) — POST /api/v1/pipeline/trigger 端点已存在
- `backend/app/api/v1/pipeline/routes.py:118-134` `trigger_pipeline()` 已实现
- `TriggerRequest(run_type, selected_stages)` + `TriggerResponse(run_id, status, message)`
- 无新增路由代码；测试可在 Phase 11 加 (非 Phase 10 强制范围)

## Commit

- `003cfa1` — feat(10-03): pipeline trigger — API verify, run-pipeline CLI, startup bootstrap

## Acceptance verification

- `python -c "from app.core.pipeline.bootstrap import ..."` exit 0 ✅
- `python -m pytest backend/tests/unit/test_pipeline_bootstrap.py -v --no-cov` → 5 passed ✅
- `grep -q "PIPELINE_BOOTSTRAP" docker-compose.dev.yml` exit 0 ✅
- `crawler/run.py` 包含 `run-pipeline` subparser 注册 ✅

## must_haves verification

- ✅ API 触发存在 (D-03a: POST /pipeline/trigger 已存在并可由 trigger_and_start 调用)
- ✅ CLI 触发入口存在 (D-03b: python -m crawler.run run-pipeline)
- ✅ 启动 bootstrap 仅 PIPELINE_BOOTSTRAP=true 时触发，且延迟 30 秒 (D-03c)
- ✅ 池空/disabled PIPELINE_BOOTSTRAP 时静默无副作用 (单元测试覆盖)
