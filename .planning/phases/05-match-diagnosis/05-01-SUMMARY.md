---
phase: 05-match-diagnosis
plan: 01
status: completed
date: 2026-07-27
---

# Phase 5 (MatchDiagnosis) — Execution Summary

## 范围
执行 `01-01-PLAN.md` 后端 4 个 must-have（前端对齐部分为其它会话工作，已记录为 OPEN）。

## 后端修复 + 验证（M13 verify-first）

| # | 问题 | 修复 | 验证 |
|---|---|---|---|
| 1 | cii 计算漏洞（`required=0` 时 cii=1.0 误读为"无通胀"） | `core/matching/service.py` `_apply_inflation_correction`: `cii=0.0 if required_count==0 else required_count/BASELINE` | rich 岗位 cii 1.0→**0.0**；单元测试 `test_empty_required` 已对齐新语义 |
| 2 | `/match/batch` 响应无 `summary`/扁平 `items` 别名（前端 store 按扁平消费） | `api/v1/match.py` `batch_match` 返回 `summary` 字段 + `items` 别名 | `summary={total:2, success:2, failed:0}`、`items_len=2` |
| 3 | `/match/competitiveness` 响应无 `items`/`skills` 别名（前端读 `data.items ?? data.skills` 恒空） | `get_competitiveness` 追加 `items`(bottleneck_skills) + `skills`({required_count, bonus_count, total}) | `items_len=5`、`skills={0,15,15}` |
| 4 | `/match/recommend` 报 422 “person_skills 必填”，前端传的是 `skills` 字段 | `ReverseMatchRequest` 加 `skills` 字段 + `@model_validator` 归并到 `person_skills` | `skills=[{name:Python...}]` 通过 200，返 10 个推荐 |

## 测试
- `tests/unit/test_run_match.py::TestApplyInflationCorrection` — 3/3 通过（含更新后的 `test_empty_required`）
- 其他 4 个 pre-existing 失败（`test_driver_exception_*`/`test_db_session_*`）非本会话引入，未处理

## 仍 OPEN（前端层，跨会话协作）
- `MatchDiagnosis.vue` 呈现 `note` 字段（M2 后端已就绪）
- `learningStore`/`learningAnalytics` 消费字段对齐（Fix 2/3/4 后端已就绪）
- "Chroma 不可用仍 200" 回归测试（M3 防回退）

详见 [CONFORMANCE-match.md](../../phases/13-design-conformance/CONFORMANCE-match.md)。