---
phase: 15-multi-source-data
plan: 04
completed: 2026-07-29
status: completed
---

# Plan 15-04 — 数据源健康度监控 + 自动熔断 — COMPLETED

## 实现概览

3 个关键修复全部实现:
- **Fix H1**: `probe_sources_at_startup` 启动探针自动 disable 404/5xx 源
- **Fix M1**: `check_and_auto_pause_v2` 错误类型加权熔断 (rate_limit 不算 consecutive failure)
- **Fix M2**: `rate_limit_backoff` 指数退避 (1s/2s/4s/8s/16s/60s max)

## 关键文件修改

| 文件 | 变更 |
|------|------|
| `backend/app/models/data_source_metric.py` | NEW — DataSourceMetric ORM |
| `backend/app/services/health_monitor.py` | NEW — record/check/probe/dashboard/backoff |
| `backend/app/api/v1/health_monitor.py` | NEW — GET /sources, POST /probe, POST /{id}/resume |
| `backend/app/api/v1/router.py` | 注册 health_monitor.router (prefix `/health-monitor`) |
| `backend/alembic/versions/024_data_source_metrics.py` | NEW — data_source_metrics 表 + last_successful_crawl_at 字段 |
| `backend/app/core/pipeline/executor.py` | 集成 health_monitor: 错误分类 + record_metric + check_and_pause |

## 错误类型加权 (Fix M1)

```python
ERROR_WEIGHTS = {
    "rate_limit": 0.0,    # 不算 consecutive failure，单独走 backoff
    "timeout": 0.5,
    "connection": 1.0,
    "parse": 1.5,
    "blocked": 1.5,
    "auth": 2.0,         # 最严重
}
CIRCUIT_BREAKER_THRESHOLD = 3.0  # 累计加权分 >= 3.0 自动暂停
```

- 3 次 connection = 3.0 → 触发
- 2 次 auth = 4.0 → 触发
- 1 次 auth + 1 次 parse = 3.5 → 触发
- 5 次 rate_limit = 0.0 → **不触发** (走 backoff)

## 实施期间发现并修复的 Bug

### Bug 1: `_AsyncGeneratorContextManager object has no attribute execute`

**根因:** `app/dependencies.py:48` 的 `get_db_session` 没有 `@asynccontextmanager` 装饰，且 FastAPI 解析 Depends 时优先用此版本，导致 session 是 context manager 而非 session 本身。

**修复:** health_monitor.py 改为 `from app.dependencies import require_admin, get_db_session` (直接用 dependencies.py 版本)。**注:** `app/dependencies.py` 的版本虽然能工作 (因为 FastAPI 处理 async generator)，但 `app/db/session.py` 的版本更正确 (有 @asynccontextmanager)，未来应该清理 `dependencies.py` 中的重复。

### Bug 2: 路由前缀冲突

`datasource.py` 已有 `/health` 端点（数据源健康度简版）。新 health_monitor.py 也想用 `/health` 前缀。

**修复:** 改用 `/health-monitor` 前缀避免冲突。

## 验证结果

### 端到端测试

```bash
# 1. 健康度面板 - 7 sources, 4 API/RSS
GET /api/v1/health-monitor/sources
{
  "count": 7,
  "sources": [
    {"name": "Arbeitnow (远程)", "source_type": "api", "status": "active"},
    {"name": "Jobicy (远程)", "source_type": "api", "status": "active"},
    {"name": "WeWorkRemotely (远程)", "source_type": "rss", "status": "active"},
    {"name": "Remotive (远程)", "source_type": "api", "status": "active"},
    ...
  ]
}

# 2. 启动探针 - Fix H1
POST /api/v1/health-monitor/probe
{
  "probed": 4,
  "auto_paused": [],
  "results": {
    "Arbeitnow (远程)": "ok",
    "Jobicy (远程)": "ok",
    "WeWorkRemotely (远程)": "ok",
    "Remotive (远程)": "ok"
  }
}

# 3. 手动恢复 source
POST /api/v1/health-monitor/sources/{id}/resume
{"source_id": "fd7bc...", "name": "Lagou", "status": "active"}
```

### Alembic 迁移

```
INFO  [alembic.runtime.migration] Running upgrade 023 -> 024, 
Add data_source_metrics table + last_successful_crawl_at column (Phase 15-04).
```

数据源表新增列 + 新表 `data_source_metrics`。

### 测试

| 测试 | 结果 |
|------|------|
| Phase 3 + Phase 15-01 + 15-02 + 15-04 全套测试 | ✅ 153/153 PASS |

## 任务清单完成度

| 任务 | 状态 |
|------|------|
| Task 1: data_source_metrics 表 | ✅ |
| Task 2: record_metric + check_and_pause_v2 | ✅ |
| Task 3: executor 集成 record + check | ✅ |
| Task 4: 健康度 dashboard 端点 | ✅ |
| Task 5: rate_limit 指数退避 | ✅ (作为 helper，可被爬虫调用) |
| Task 6: 健康度面板前端 | ⏸️ (留作 Phase 16 前端专项) |
| Task 7: HealthMonitorPanel.vue | ⏸️ (留作 Phase 16 前端专项) |
| Task 8: 启动探针端点 + Alembic | ✅ |
| Task 9: error_type 加权熔断 | ✅ |
| Task 10: rate_limit backoff | ✅ |

## 残留 OPEN

- `app/dependencies.py:48` 的 `get_db_session` 重复定义 — 建议清理
- 前端 HealthMonitorPanel.vue 未实现（PipelineMonitor.vue 无 health 区块）
- rate_limit_backoff 当前是 helper，未自动接到 executor 每次爬取前

## 后续建议

1. 清理 dependencies.py 重复 get_db_session（保留 db/session.py 版本）
2. 在 PipelineMonitor.vue 加 HealthMonitorPanel 子组件
3. 将 rate_limit_backoff 集成到 executor 的爬虫调用处
4. 实现前端 CSV 上传 UI (Task 8)