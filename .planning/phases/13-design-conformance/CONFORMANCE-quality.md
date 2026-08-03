# CONFORMANCE — Module 11: 图谱质量 (QualityDashboard)

**Phase 13 · Wave 1 · verified 2026-07-26**

| 基线 | 来源 |
|---|---|
| should | `docs/standards/05-evaluation/01-评估套件规范.md`、`docs/standards/01-backend/08-业务核心-dashboard.md`、`docs/standards/04-contracts/01-API契约规范.md` |
| was-analyzed | `docs/archive/quality-source-analysis.md` |
| is (live) | `frontend/src/pages/QualityDashboard.vue` + `stores/quality.ts` + `/api/v1/quality/dashboard` + PG `extraction_evaluation_records` |

## 已修复 + 验证（后端契约）
- **[FIXED · HIGH]** 无评估基线时 `precision/recall/f1=0` 触发 `warning_level=red`，把“未评估”误报为“质量差”，违反评估规范（指标须在有意义时呈现）与高 UX 原则。
  - 修复 `backend/app/api/v1/quality.py`：`QualityDashboard` 增字段 `evaluation_count` / `baseline_available` / `evaluation_explanation`；`_build_quality_dashboard` 计数 `ExtractionEvaluationRecord`，无基线时 `report.warning_level` 降为 `gray` 并填解释。
  - **验证**：`report.warning_level` **red → gray**；`baseline_available=False`；`evaluation_explanation` 非空（说明红色=未评估，并指引 `/quality/evaluate` 建基线）。

## 偏移 / 待办
- **[FIXED · MEDIUM→CONFORM (M4)]** 前端“未评估”态：`stores/quality.ts` 已含 `baseline_available/evaluation_count/evaluation_explanation`；`QualityDashboard.vue` 在 `baseline_available===false` 时渲染 info 型 `el-alert`“抽取质量（precision/recall/F1）暂未评估”+解释，并 `v-else-if` 隐藏 precision/recall 卡（避免 0/0/0 误读为红/失败）。**验证（page 层）**：/quality 渲染该 alert（type=info，0 console error；body 中 “precision” 仅出现在该解释文案，非红 fail 卡）；与 DB `extraction_evaluation_records=0`、API `baseline_available=false`/`warning_level=gray` 一致 → M4 全端闭环。
- **[OPEN · LOW · UX]** 提供“触发评估”按钮引导建立基线（`POST /quality/evaluate` 已存在，前端缺入口）。
- **[OPEN · LOW · UX]** 提供“触发评估”按钮引导建立基线（`POST /quality/evaluate` 已存在，前端缺入口）。

## 结论
误导性红色已在**契约层**修正并验证；前端可视化“未评估”态为明确的下一步小改（数据已就绪）。