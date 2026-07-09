---
phase: 08-backend-cleanup
plan: 03
subsystem: infra
tags: [healthcheck, httpx, ollama, fastapi, cfg]

# Dependency graph
requires: []
provides:
  - "/health/detail 端点（4 服务 ping + 3 LLM key 布尔 + demo 数据指示）"
  - "healthcheck_resources 含 Ollama ping（第 4 服务）"
  - "/api/v1/health/detail 契约兼容别名"
affects: [09-frontend-mock, 10-pipeline-e2e]

# Tech tracking
tech-stack:
  added: []  # httpx 已是项目依赖（llm_client.py 使用）
  patterns: [httpx-timeout-ping, bool-only-key-disclosure-guard, expanding-bindparam-in-clause]

key-files:
  created: []
  modified:
    - backend/app/services/resources.py
    - backend/app/main.py
    - backend/tests/unit/test_health.py

key-decisions:
  - "D-05: llm_keys 仅返回 bool() 包装值，永不返回 key 字符串（T-08-05 信息泄露防护）"
  - "D-09: /health/detail 生产环境也返回完整详情（与现有 /health 一致无 auth；SEC-03 auth 属未来范畴）"
  - "Ollama URL 取自 settings.qwen_model_path；空值时返回 not_configured，httpx timeout=3.0s 防 DoS（T-08-08）"

patterns-established:
  - "Pattern: 服务 ping 统一 try/except 返回 ok/error:not_initialized 三态字符串"
  - "Pattern: 敏感配置仅以布尔形式对外暴露（bool(settings.secret_field)）"

requirements-completed: [CFG-04]

# Metrics
duration: 12min
completed: 2026-07-09
---

# Phase 8 Plan 3: Detailed Healthcheck Summary

**新增 /health/detail 端点：4 服务 ping（Neo4j/PostgreSQL/Redis/Ollama via httpx）+ 3 LLM key 布尔（不泄露值）+ demo 数据指示，Ollama ping 扩展至 healthcheck_resources**

## Performance

- **Duration:** ~12 min
- **Tasks:** 1 (TDD: RED → GREEN)
- **Files modified:** 3

## Accomplishments
- 扩展 `healthcheck_resources()` 添加 Ollama ping（httpx GET /api/tags，timeout=3.0s），复用现有 try/except 三态 pattern
- 新增 `/health/detail` 与 `/api/v1/health/detail` 端点，返回 services(4)/llm_keys(3 bool)/demo_data(review_queue_seeded + pipeline_runs_count)
- llm_keys 严格使用 `bool()` 包装，永不泄露 key 值（D-05/T-08-05）
- demo_data 通过硬编码 demo 实体名集合检测 review_queue auto-seed 残留 + pipeline_runs 总数
- 新增 2 个测试（test_health_detail_ok + test_health_detail_no_key_leak），全部通过

## Task Commits

1. **Task 1: 添加 Ollama ping + /health/detail 端点 (CFG-04)** - `cc06d8e` (feat)

**Plan metadata:** (pending)

## Files Created/Modified
- `backend/app/services/resources.py` - 添加 `import httpx` 与 Ollama ping 块（第 4 服务健康检查）
- `backend/app/main.py` - 添加 `_detailed_health_payload()` + `/health/detail` + `/api/v1/health/detail` 路由
- `backend/tests/unit/test_health.py` - 添加 test_health_detail_ok + test_health_detail_no_key_leak

## Decisions Made
- llm_keys 用 `bool(settings.x_api_key)` 而非直接返回字符串 — 强制 D-05 信息泄露防护，即使未来误改也不会泄露
- Ollama 空配置返回 `"not_configured"`（区别于 `"not_initialized"`）— 让运维区分“服务未初始化”与“未配置 URL”两种状态
- demo_data 查询使用 SQLAlchemy `bindparam(expanding=True)` 处理 IN 子句（参数化，非字符串拼接）— 防 SQL 注入
- demo_data 查询失败时返回默认值 `{False, 0}` 并 logger.warning — 服务降级 pattern，不中断健康检查

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] 清理内联 `__import__("sqlalchemy")` 为正规 import**
- **Found during:** Task 1 (Part B 实现)
- **Issue:** 初版用 `__import__("sqlalchemy").bindparam(...)` 内联导入，可读性差且 mypy 难以静态分析
- **Fix:** 在 main.py 顶部添加 `from sqlalchemy import bindparam, text`，替换内联导入
- **Files modified:** backend/app/main.py
- **Verification:** ruff check + mypy 通过
- **Committed in:** cc06d8e (task commit)

**2. [Rule 2 - Missing Critical] Ollama 空配置防御**
- **Found during:** Task 1 (Part A 实现)
- **Issue:** config.py 中 `qwen_model_path` 默认空字符串，直接 httpx GET 空 URL 会抛意外异常类型
- **Fix:** 添加 `if ollama_url:` 守卫，空值返回 `"not_configured"`，与现有 `"not_initialized"` pattern 一致
- **Files modified:** backend/app/services/resources.py
- **Verification:** 空配置场景不抛异常，返回明确状态字符串
- **Committed in:** cc06d8e (task commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 missing critical/robustness)
**Impact on plan:** 两者均为正确性/可维护性必需，无范围蔓延。

## Issues Encountered
- 单独运行 test_health.py 时触发项目全局 60% 覆盖率门禁（35%）— 这是项目级 pytest 配置在子集运行时的已知行为，非本计划引入；完整测试套件不受影响。4 个测试全部通过。

## Self-Check: PASSED

- [x] `backend/app/services/resources.py` 存在且含 "ollama" (grep count: 7)
- [x] `backend/app/main.py` 存在且含 "health/detail" (grep count: 2: 主路由 + v1 别名)
- [x] `backend/tests/unit/test_health.py` 存在且含 4 个测试函数
- [x] commit `cc06d8e` 存在于 git log
- [x] GET /health/detail 返回 200，keys = [services, llm_keys, demo_data]
- [x] llm_keys 全部为 bool 类型（无 key 值泄露）
- [x] ruff check + mypy 通过

---
*Phase: 08-backend-cleanup*
*Completed: 2026-07-09*
