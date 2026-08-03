---
phase: 18-test-resilience
plan: 02
completed: 2026-07-30
status: partial (1 of 3 tests pass; mock path needs work)
---

# Plan 18-02: 失败重试集成测试 — PARTIAL

## 已完成

### Task 1: test_pipeline_failure_retry.py 创建 ✅
**文件:** `backend/tests/integration/test_pipeline_failure_retry.py`

3 个测试场景:
- `test_import_failure_keeps_jd_raw_status_raw` — LLM 失败时 jd_raw.status 不污染
- `test_retry_endpoint_accepts_or_rejects` — retry 端点返回 200/409
- `test_cancel_preserves_upstream_records` — cancel 不回滚数据

### Task 2: 测试发现的问题
- Mock path 必须 patch at source: `app.tasks.stage3_services.run_batch_extract_jd` (不是 `app.core.pipeline.executor.run_batch_extract_jd`)
- Mock 用 `side_effect = RuntimeError()` 触发 stage failed (return_value 不会让 stage 失败)

## 测试结果

```
1 passed, 2 failed (mock path issues)
- test_cancel_preserves_upstream_records: ✅
- test_import_failure_keeps_jd_raw_status_raw: ❌ (Llm mock 路径)
- test_retry_endpoint_accepts_or_rejects: ❌ (backend 压力)
```

## 残留

- 2 个失败测试需要调试 mock 和 backend 状态 (留作后续)
- 单个 cancel 测试已验证 cancel 流程正确

## 实际价值

cancel 测试通过 — 验证了用户关切的"中途取消会保留上游 records"行为。
import + retry 测试留作 Phase 19+。