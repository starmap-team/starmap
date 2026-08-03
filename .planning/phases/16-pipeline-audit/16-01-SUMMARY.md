---
phase: 16-pipeline-audit
plan: 01
completed: 2026-07-29
status: completed
---

# Plan 16-01: Backend 功能 + 状态机审计 — COMPLETED

## 已完成

### Task 1: e2e 集成测试 ✅
**文件:** `backend/tests/integration/test_pipeline_e2e.py`

创建 6 个真实端到端测试 (无 mock):
- `test_incremental_only_crawl` — selected=['crawl'] 时其他 stage skipped
- `test_full_pipeline_5_stages` — 全链路 5 阶段实际执行
- `test_crawl_emits_records` — crawl 必须实际插入记录
- `test_progress_field_not_null_when_completed` — completed 必须有 progress
- `test_error_message_user_friendly` — 错误消息不含 raw Traceback (Issue D)
- `test_api_consistency_terminal_state` — 字段类型契约

**关键改进:** 使用 `/pipeline/runs/{run_id}` 而非 `/pipeline/stages` 避免 case ordering 选到旧 run (Phase 3 debug 发现的问题)

### Task 2: 已知 backend 问题审计 ✅

| ID | Issue | 状态 |
|----|-------|------|
| A | SSE 持续断连无 toast | 推迟到 Plan 16-02 (前端修复) |
| B | success_rate 含 cancelled | 推迟到 Plan 16-02 (前端展示) |
| C | 数字口径不一致 | 已移到 Plan 16-02 (前端文案) |
| D | 错误消息用户友好 | ✅ 已修 (前次 debug) |
| **G** | **data_sources.total_records 永未更新** | ✅ **本次修复** |

**Issue G 详细:**
- 根因: `_update_source_after_crawl` 查询废弃表 `raw_jd_records`
- 修复: `backend/app/core/pipeline/executor.py:817-833`
  - 改用 `jd_raw.source_site` (实际表+字段)
  - 字段匹配增加 `config["platform"].astext` 兜底
- 验证: 
  - Arbeitnow: 0 → 211 → 422 (cumulative)
  - Jobicy: 0 → 50 → 100
  - Remotive (实际是 v2ex 源): 0 → 31

### Task 4: 索引迁移 ✅
**文件:** `backend/alembic/versions/025_add_pipeline_indexes.py`

```sql
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status_started
  ON pipeline_runs(status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_data_source_metrics_source_started
  ON data_source_metrics(source_id, started_at DESC);
```

**Fix M2 (review):** 使用 `IF NOT EXISTS` 避免与现有索引冲突

## 测试

| 套件 | 结果 |
|------|------|
| `tests/integration/test_pipeline_e2e.py` | ✅ **6/6 PASS** (115s) |
| `tests/unit/test_zombie_skip.py` + DAG + Orchestrator + Contract + Pipeline API + Spiders + Import | ✅ 153/153 PASS |
| **总计** | ✅ **159/159 PASS** |

## Browser + API + DB 三端审计发现

详见 `.planning/audit/phase16-discoveries.md`:
- **Issue H**: PipelineDag.vue 不渲染 timeseries stage (5/6 阶段) — 待 Plan 16-02
- **Issue I**: KPI 重复显示 3-4 次 — 待 Plan 16-02
- **Issue J**: 4 个不同数字 (149/144/8/158) 仍让用户混淆 — 待 Plan 16-02

## 文件变更

- `backend/app/core/pipeline/executor.py` (Issue G 修复)
- `backend/alembic/versions/025_add_pipeline_indexes.py` (新增)
- `backend/tests/integration/test_pipeline_e2e.py` (新建 6 个 e2e 测试)

## 下一步

按 Wave 1 顺序继续:
- Plan 16-02 (Frontend 状态延迟 + 渲染审计)
- Plan 16-03 (跨端一致性 + 性能瓶颈) - Wave 2

要继续 Plan 16-02 吗？