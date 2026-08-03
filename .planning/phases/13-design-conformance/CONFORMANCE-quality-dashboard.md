# CONFORMANCE — Module 11: 图谱质量 (QualityDashboard)

**Phase 13 · Wave 3 · verified 2026-07-27**

| 基线 | 来源 |
|---|---|
| should | `docs/standards/05-evaluation/01-评估套件规范.md`、`docs/standards/01-backend/08-业务核心-dashboard.md`、`docs/standards/04-contracts/01-API契约规范.md`（M4 强制规范） |
| was-analyzed | `docs/archive/quality-source-analysis.md` |
| is (live) | `frontend/src/pages/QualityDashboard.vue` + `stores/quality.ts` + `/api/v1/quality/{dashboard,report,evaluate,trends,alerts}` + PG `extraction_evaluation_records` + `jd_extraction_records` |

## 符合项（已 verify-first 验证）
- **[CONFORM]** `/api/v1/quality/dashboard` → 200，27ms，含 `report{precision, recall, f1, warning_level, details[]}` + `baseline_available=False` + `evaluation_explanation`（M4 强制规范：n 评估基线=gray+解释，不报红）。**后端 M4 闭环已在 Wave 1 验证**。
- **[CONFORM]** `/api/v1/quality/report` → 200，22ms，`warning_level=gray`，details[] 4 项全 `status=fail`（维度数值诚实呈现，由前端消费）。
- **[CONFORM]** `details[]` 4 维度：precision/recall/f1（threshold=0.8）/hallucination_rate（threshold=0.10）。
- **[CONFORM]** `evaluation_count/baseline_available/evaluation_explanation` 三件套在 `/dashboard` 响应中完整存在（Wave 1 M4 后端 fix 验证）。

## 验证证据
- 端到端 2 端点 200 OK
- 后端 fix 验证：evaluation_count=0 → warning_level=gray（M4 闭环）

## 偏移 / 待办（OPEN）
- **[OPEN · MEDIUM · frontend]** `QualityDashboard.vue` / `stores/quality.ts` 消费 `baseline_available` + `evaluation_explanation` 字段（后端已就绪，**M4 前端闭环**）。具体：card.color 应在 `baseline_available=False` 时显灰/信息态（不再按"value=0+status=fail"误显红）。定位 `frontend/src/stores/quality.ts` (card.color) + `pages/QualityDashboard.vue:97,109`。**其他会话处理**。
- **[OPEN · LOW · UX]** 提供“触发评估”按钮（`POST /api/v1/quality/evaluate` 已存在）引导建立基线。
- **[OPEN · LOW · frontend]** `QualityDashboard.spec.ts` 5+ 测试覆盖（空基线渲染 "未评估" 灰态、评估成功/失败态、告警列表等）。

## 结论
后端契约层 + M4 修复全部 **符合**（verify-first）；前端"未评估"灰态为 M4 必闭环前端层（后端数据已就绪），留 OPEN。