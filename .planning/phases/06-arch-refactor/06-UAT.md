---
status: complete
phase: 06-arch-refactor
source: 06-01-SUMMARY.md, 06-02-SUMMARY.md, 06-03-SUMMARY.md
started: 2026-07-07T08:30:00Z
updated: 2026-07-07T08:45:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Home.vue script ≤ 60 行
expected: Home.vue `<script setup>` 部分精简到 ≤60 行，仅包含 import + composable 调用 + 生命周期钩子
result: pass

### 2. Home.vue composables 存在
expected: `frontend/src/composables/home/` 下有 7 个 composable 文件 + index.ts
result: pass

### 3. Home.vue 总行数 ≤ 350
expected: `wc -l frontend/src/pages/Home.vue` ≤ 350（ROADMAP 硬指标 D-16）
result: pass

### 4. create_async_engine 单点调用
expected: `create_async_engine(settings.postgres_uri)` 仅在 `backend/app/db/session.py:28` 出现 1 次
result: pass

### 5. run_async 单点定义
expected: `def run_async` 仅在 `backend/app/utils/async_helpers.py:13` 定义 1 次
result: pass

### 6. get_async_engine 统一调用
expected: 所有 `create_async_engine` 调用点已迁移到 `get_async_engine()`，覆盖 executor/celery/cron/resources/stage3
result: pass

### 7. SimHash 单一模块
expected: `simhash.py` 拥有唯一实现；`data_fusion.py` 为薄包装层（import + re-export）
result: pass

### 8. data_fusion SimHash 薄包装
expected: `data_fusion.py` 中 SimHash 相关函数体委托给 `simhash.py`，自身不含 hashlib import
result: pass

### 9. db/session.py 存在且 API 正确
expected: `get_async_engine()` (lru_cache) + `get_session_factory()` (lru_cache) + `pool_pre_ping=True`
result: pass

### 10. resume_eval.py deprecation 注释
expected: `resume_eval.py` 包含 deprecation 注释，说明 Phase 7+ 迁移计划
result: pass

### 11. loop.ts 保持独立（带文档注释）
expected: `loop.ts` 未合并但添加了文档注释说明原因，指向 Phase 7+
result: pass

### 12. ruff check 通过
expected: `ruff check backend/app/` 全绿
result: pass

## Summary

total: 12
passed: 12
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

(none — all resolved)
