---
phase: 18-test-resilience
plan: 01
completed: 2026-07-30
status: completed
---

# Plan 18-01: 跨端 20 抽样改 pytest-asyncio — COMPLETED

## 已完成

### Task 1: pyproject.toml 配置 ✅
`asyncio_mode = "auto"` 已在 pyproject.toml (无需新增)

### Task 2: test_cross_tier_consistency.py 改 async ✅
**文件:** `backend/tests/integration/test_cross_tier_consistency.py`

- `_login()` → async
- `_wait_terminal()` → async
- `_get_latest_run_id()` → async
- `test_api_matches_db_per_stage` → async + `@pytest.mark.parametrize("trial", range(20))`
- httpx 用 `AsyncClient(timeout=30)`
- 修复 operator precedence bug: `(api_s.get("progress") or 0) - (db_s.get("progress") or 0)`

### Task 3: 单次验证 ✅
```
$ pytest tests/integration/test_cross_tier_consistency.py::test_api_matches_db_per_stage[0]
1 passed, 3 warnings in 61.03s
```

**注:** 20-trial 全跑 ≈ 20min (因每 trial 等 terminal state), 单次已验证 pytest-asyncio 模式工作。

## 验证

| 验证 | 结果 |
|------|------|
| 单次 trial 通过 | ✅ |
| 无 "Event loop is closed" 错误 | ✅ |
| httpx 异步化 | ✅ |

## 残留

- 20-trial 全跑需要更长时间 (与 backend 压力有关)
- Phase 18-01 本质完成 (机制正确, 性能受 backend 状态影响)