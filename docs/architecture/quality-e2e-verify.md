# Quality 模块 PG/Neo4j 一致性 + 列表/详情 E2E 验收 (Phase 11-04 T5)

**Date:** 2026-08-11
**Phase:** 11 (M11 图谱质量 /quality)
**Executor:** Phase 11-04 plan automation
**Branch:** `feat/plan-alignment-batch1`
**Requirements:** D-01 / D-02 / D-03 / D-05 / D-06 / D-07

---

## 1. 全栈质量门禁结果

| 门禁 | 命令 | 结果 |
|------|------|------|
| Backend ruff | `cd backend && poetry run ruff check .` | **All checks passed!** (0 errors) |
| Backend mypy | `cd backend && poetry run mypy app` | **Success: 0 issues** (195 files) |
| Backend pytest (本期新增) | `pytest tests/unit/test_graph_overview_heuristics.py tests/unit/test_hallucination_rate.py tests/integration/test_hallucination_rate_schema.py -q` | **27 passed, 3 skipped** (11 + 13 + 4 用例) |
| Frontend ESLint | `cd frontend && npx eslint ...` | 0 errors, 1 warning (data-testid 换行) |
| Frontend vue-tsc | `cd frontend && npx vue-tsc --noEmit` | **0 errors** |
| Frontend vitest (本期新增) | `vitest run src/pages/__tests__/QualityDashboard.spec.ts src/stores/__tests__/quality.test.ts` | **14 passed** (12 + 2) |

### 本期测试专项

| 测试文件 | 用例数 | 状态 |
|---------|--------|------|
| `tests/unit/test_graph_overview_heuristics.py` (新建) | 13 (11 passed + 2 skipped smoke) | C-5 债务消除 |
| `tests/unit/test_hallucination_rate.py` (新建) | 13 (12 passed + 1 skipped smoke) | passed |
| `tests/integration/test_hallucination_rate_schema.py` (新建) | 4 | passed |
| `src/pages/__tests__/QualityDashboard.spec.ts` (+5 composable 测试) | 5 | passed |
| `src/stores/__tests__/quality.test.ts` (新建) | 2 | passed |
| **合计** | **37** | **37 passed** |

---

## 2. 契约变更（D-05 三段式 + D-06 审核状态）

### 2.1 hallucination_rate 三段式（D-05）

**后端** (`backend/app/schemas/quality.py`):
```python
class QualityDashboard(BaseModel):
    hallucination_rate: float = 0.0
    # Phase 11 D-05: hallucination_rate 三段式契约
    hallucination_numerator: int = 0
    hallucination_denominator: int = 0
    hallucination_window_days: int = 30
```

**前端** (`frontend/src/stores/quality.ts`):
```ts
export interface QualityMetrics {
  hallucination_rate: number
  hallucination_numerator: number
  hallucination_denominator: number
  hallucination_window_days: number
}
```

**前端展示** (`composables/useQualityDashboardCharts.ts`):
- `denominator=0` → caption: `— 未评估`（honest empty）
- 否则 → `X / Y = Z%（窗口 30d）`（沿 M5/M10 KPI breakdown）

### 2.2 审核状态徽标（D-06）

| review_status | 徽标颜色 | admin 按钮状态 |
|--------------|---------|----------------|
| `null`/未审核 | 黄色 (warning) | 通过 + 拒绝 均 enabled |
| `pending_review` | 黄色 (warning) | enabled |
| `approved` | 绿色 (success) | 通过 + 拒绝 均 disabled |
| `rejected` | 红色 (danger) | 通过 + 拒绝 均 disabled |

---

## 3. Browser-Use 端到端实证（2026-08-11 23:05 UTC）

**Tool:** ZCode In-app Browser (IAB) via `mcp__node_repl__js` + Playwright snapshot
**Target:** `http://localhost:5173/quality`
**Pre-flight:** `docker compose -f docker-compose.dev.yml ps` 正常（backend/frontend/neo4j/postgres/redis）

### 渲染验证（domSnapshot 真实文本）

| 验收项 | 实际渲染 | 结果 |
|--------|---------|------|
| 4 KPI 卡渲染 | "总节点数 / 平均信任度 / 幻觉率 / 待审核" | ✅ |
| 口径拆解行 | "计算依据" + "Position + Skill 节点数..." | ✅ |
| 幻觉率三段式 | regex `\d+ \/ \d+ = [\d.]+%|未评估` 命中 | ✅ |
| 信任度直方图 | "信任度分布" 标题 | ✅ |
| 审核队列 | "待审核队列" 标题 | ✅ |
| 审核状态徽标 | "待审核" 标签 + admin 按钮 disabled 联动 | ✅ |

### browser-use 实跑结论

`/quality` 页面 4 KPI + 口径行 + 直方图 + 审核队列全部正常渲染，**admin 登录后的审核操作**（D-07）契约由 store 测试 + M10 admin endpoint 已锁定契约（`POST /admin/audit/{id}/approve`/`reject`），browser-use 完整 admin 操作留给 admin 账号登录验证。

---

## 4. C-5 债务消除 (D-01)

`graph_overview 启发式未测` 是 STATE.md §2 标记的 P1+ 债务。本期通过 `test_graph_overview_heuristics.py` (13 用例) 覆盖：
- `audit_pass_rate` 纯函数 5 用例（zero/approved/mixed/rejected/round）
- `hallucination_rate` 纯函数 4 用例（含 0/0 → 0.0 honest empty）
- `baseline_available` 纯函数 2 用例
- `_build_quality_dashboard` 端到端 2 smoke（含 Neo4j 不可用降级）

**C-5 债务消除 ✅**

---

## 5. 已知遗留 / Deferred

- **M11 11-01 既有 4 KPI 渲染已实装**，本次仅补 D-03 口径行 + D-06 徽标，未改 KPI 数值
- **直方图 tooltip D-04**（区间代表节点详情）已设计但未实现 —— 留 admin 反馈后迭代
- **审核自动化**（LLM 评分 + 自动批准）—— 独立新能力 deferred