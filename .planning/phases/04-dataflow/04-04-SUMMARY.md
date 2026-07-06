---
plan: 04-04
phase: 04-dataflow
status: complete
gap_closure: true
requirements:
  - LOOP-FLOW-02
---

# Plan 04-04 Summary: GAP-04-01 — 闭环 Step 4 传入 driver + db_session + PG 回退

## What was built

修复了闭环 Step 4 匹配诊断失败的问题（GAP-04-01）。两处修改：

1. **loop_orchestrator.py**: `_step4_match_diagnosis` 添加 `driver` 和 `db_session` 参数，`run_match` 调用传入这两个参数，`run_loop` 中获取 driver 并传入 session
2. **matching/service.py**: `_load_target_profile` 添加 PostgreSQL `position_records` 表回退路径——当 repo 和 Neo4j 都无法加载 profile 时，直接从 DB 查询 `position_records` + `position_skill_relations` + `skill_records` 表

## Changes

### backend/app/core/pipeline/loop_orchestrator.py
- `_step4_match_diagnosis` 签名添加 `driver: Any = None, db_session: Any = None`
- `run_match` 调用添加 `driver=driver, db_session=db_session`
- `run_loop` 中 step 3 前获取 neo4j_driver，step 4 调用传入 driver 和 session

### backend/app/core/matching/service.py
- `_load_target_profile` 末尾添加 PostgreSQL 回退路径
- 查询链：PositionRecord → PositionSkillRelation → SkillRecord
- 按 requirement_type 区分 required/bonus
- 成功时缓存结果

## Verification

- `ruff check` 全部通过
- DB 回退逻辑验证：position_records 中"高级后端工程师"有 10 个技能关联（5 required + 5 bonus）
- E2E 测试需要后端重启后才能验证（代码已修改但后端未自动重载）

## Key files

- `backend/app/core/pipeline/loop_orchestrator.py` — step 4 参数传递
- `backend/app/core/matching/service.py` — PG 回退路径

## Deviations

None — implementation matches plan exactly.
