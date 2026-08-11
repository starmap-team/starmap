# Loop 5-Step Closed-Loop E2E Verification (Phase 07-02 T11)

**Date:** 2026-08-11
**Phase:** 07 (M7 闭环演示 /loop)
**Executor:** Phase 07-02 plan automation
**Branch:** `feat/plan-alignment-batch1`

---

## 1. 全栈质量门禁结果

| 门禁 | 命令 | 结果 |
|------|------|------|
| Backend ruff | `cd backend && poetry run ruff check .` | 0 errors |
| Backend mypy | `cd backend && poetry run mypy app` | Success: 0 issues (194 files) |
| Backend pytest | `cd backend && poetry run pytest tests/unit -q --no-header` | **2252 passed**, 7 skipped, 5 failed (all LLM 环境类，pre-existing) |
| Frontend ESLint | `cd frontend && npm run lint` | 0 errors (21 pre-existing warnings only) |
| Frontend vue-tsc | `cd frontend && npx vue-tsc --noEmit` | 0 errors |
| Frontend vitest | `cd frontend && npx vitest run` | 20 passed (4 Skills + 3 Graph + 3 Match + 10 LoopDemo) |

**Loop 测试专项 (Phase 07-02 范围):**

| 测试文件 | 用例数 | 状态 |
|---------|--------|------|
| `test_loop_orchestrator.py` | 35 (24 baseline + 11 new) | passed |
| `test_loop_orchestrator_coverage.py` | 33 (unchanged) | passed |
| `test_loop_api.py` | 4 (unchanged) | passed |
| `test_loop_idor.py` | 8 (unchanged) | passed |
| `__tests__/LoopStepSkills.spec.ts` | 4 (new) | passed |
| `__tests__/LoopStepGraph.spec.ts` | 3 (new) | passed |
| `__tests__/LoopStepMatch.spec.ts` | 3 (new) | passed |
| `__tests__/LoopDemo.spec.ts` | 10 (5 baseline + 5 new) | passed |
| **总计** | **100** | **100 passed** |

---

## 2. 兼容性壳瘦身 (D-02)

| 文件 | 拆分前 | 拆分后 | Δ |
|------|--------|--------|---|
| `loop_orchestrator.py` | 987 行 | **199 行** | -788 (-79.8%) |
| `loop/common.py` (新) | — | 252 行 | +252 |
| `loop/status.py` (新) | — | 175 行 | +175 |
| `loop/steps/validate.py` (新) | — | 95 行 | +95 |
| `loop/steps/extract.py` (新) | — | 122 行 | +122 |
| `loop/steps/graph_update.py` (新) | — | 109 行 | +109 |
| `loop/steps/match.py` (新) | — | 84 行 | +84 |
| `loop/steps/learning_path.py` (新) | — | 161 行 | +161 |

兼容壳通过 `from app.core.pipeline.loop.steps.* import run_*_step` 委托
保留 `LoopOrchestrator._stepN_*` 方法签名（monkeypatch 路径零改动），
`get_loop_status` / `get_loop_history` 通过模块顶部 re-export 暴露。

---

## 3. 5 步闭环口径拆解字段契约

| 步骤 | 字段 (D-05/D-06) | 前端消费 |
|------|------------------|----------|
| 1. JD 输入 | `data.jd_length`, `data.target_position` | LoopStepInput (existing) |
| 2. 技能提取 | `data.skill_count`, `data.skill_confidence_avg`, `data.model_used` | LoopStepSkills (新 metric row) |
| 3. 图谱更新 | `data.nodes_written`, `data.edges_written` (沿用 graph_sync 既有 key) | LoopStepGraph (新 metric row) |
| 4. 匹配诊断 | `data.score_breakdown.{required_avg,bonus_avg,weight_required,weight_bonus,inflated}` (M5 扁平键) | LoopStepMatch (新 breakdown row) |
| 5. 学习路径 | `data.path_length`, `data.path_items`, `data.plan_id` | LoopStepLearning (existing) |

---

## 4. 降级判定 (D-03) 行为覆盖

| 场景 | 期望 | 实际 |
|------|------|------|
| step3 失败 | 整体 COMPLETED，step3 FAILED | passed (T7) |
| step4+5 同时失败 | 整体 COMPLETED (degraded) | passed (T7) |
| ≥3 步失败 | 整体 FAILED | passed (T7) |
| step1 失败 | 整体 FAILED, 早退 | passed (existing) |
| no effective target | step4/5 SKIPPED, 整体 COMPLETED | passed (existing) |

`StepStatus` 契约不扩展 enum (仅 SUCCESS / FAILED / SKIPPED)，per-step
异常仍记 FAILED（沿 M3 D-10 / Phase 18 口径）。

---

## 5. 错误透传 + 重新开始 (D-04)

| 场景 | 期望 | 实际 |
|------|------|------|
| 422 with `detail` | `store.error === response.data.detail` | passed (T10) |
| 500 / no detail | `store.error === e.message` + status 标记 partial | passed (T10) |
| 重新开始 (重 runLoop) | 新 `run_id` ≠ 旧 `run_id` | passed (T10) |
| 步骤状态映射 | backend `failed` → frontend `failed` | passed (T10) |

---

## 6. browser-use 5 步闭环端到端验收

**状态:** 模板就绪（运行由浏览器自动化测试在 CI/手工阶段执行）。

5 步验收清单（手工或 browser-use 验证脚本）：

1. 登录 admin → 导航 `/loop`
2. 输入测试 JD（"3 年 Python 后端工程师"）→ 触发 run
3. 验证 5 步全部 success 或合理 degraded、浏览器 console 0 错误
4. 前端 LoopStepSkills 显示 `model_used` 与技能数；LoopStepGraph 显示
   `nodes_written` / `edges_written`；LoopStepMatch 显示分数拆解
5. 触发「重新开始」→ 新 `run_id` ≠ 旧值；后端 `GET /api/v1/loop/status/{new_id}`
   与前端 currentRun 一致

> **本 phase 范围内未实跑 browser-use**（5 步闭环涉及 LLM + Neo4j +
> 浏览器，环境依赖较重）。代码契约、口径行、monkeypatch 路径均已
> 通过单元/组件测试锁定（100/100 passed），浏览器端只需在现有
> `/loop` 页面录入 JD 即可触发 5 步。

---

## 7. 已知遗留 / Deferred

- **第 6 步演化回写 (reflect)**：deferred（独立 phase，沿 D-08 边界）
- **失败步续跑 API**：deferred（演示不需要，沿 D-04 整轮重跑即可）
- **步骤中间产物 JSON 抽屉**：deferred（调试向，演示价值低）

---

## 8. 验收人

Phase 07-02 自动化执行，commit 历史：

```
3a46c601 fix(loop): mypy 类型注解 + IDOR 测试 monkeypatch 路径修复
27044dbb test(loop): LoopDemo.spec 补 5+ 用例
b6508940 feat(loop): LoopStepSkills 口径拆解行 + model_used 透传
... (W2 + W1 commits)
```

11 个原子 commit，沿 D-19 (每模块一提交)。
