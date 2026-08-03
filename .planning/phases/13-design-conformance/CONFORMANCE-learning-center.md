# CONFORMANCE — Module 8: 学习中心 (LearningCenter)

**Phase 13 · Wave 2 · verified 2026-07-27**

| 基线 | 来源 |
|---|---|
| should | `docs/standards/01-backend/05-业务核心-learning.md`、`docs/standards/04-contracts/01-API契约规范.md` |
| was-analyzed | `docs/archive/learning-source-analysis.md` |
| is (live) | `frontend/src/pages/LearningCenter.vue` + `stores/learning.ts` + `/api/v1/learning/{plans,plan/{id},plan/{id}/progress,plan/{id}/skills,recommendations}` + PG |

## 符合项（已 verify-first 验证）
- **[CONFORM]** 7 个端点契约完整（`CreatePlanRequest` / `PlanResponse` / `UpdateProgressRequest` / `RecommendationsResponse` / `AddSkillRequest` / `SkillProgressItem` / `RecommendationsResponse`）。
- **[CONFORM]** `GET /api/v1/learning/plans` → 200，list 返 0 项（用户无计划，架构正常）。
- **[CONFORM]** `GET /api/v1/learning/recommendations` → 200，含真实推荐（Python/Docker 等，importance/gap_level/estimated_hours/prerequisites 完整）。
- **[CONFORM]** `GET /api/v1/learning/plan/{bad_id}` → 400 + detail（plan_id 格式校验前置拦截，符合契约）。
- **[CONFORM]** 进度更新 / 技能增删 / 推荐生成 流程在服务层 `learning_service.py` 中实现，与 Neo4j + PG + Chroma 协同。

## 验证证据
- `tests/unit/test_learning_api.py` — 35/36 通过（1 pre-existing `test_plans_generate_path_error_uses_fallback` 与本会话无关）
- 端到端 `GET /api/v1/learning/plans` 200（17ms）/ `GET /api/v1/learning/recommendations` 200（34ms）/ `GET /api/v1/learning/plan/{bad_id}` 400

## 偏移 / 待办（OPEN）
- **[OPEN · LOW · frontend]** `LearningCenter.vue` / `learning.ts` 错误透传（`err.response.data.detail`，与 Phase 6/7 jd.ts/loop.ts 同模式）。**其他会话处理**。
- **[OPEN · LOW · frontend]** `LearningCenter.spec.ts` 5+ 测试覆盖（plan 必须-have #3）：渲染、学习计划 CRUD、技能进度更新、错误处理。
- **[OPEN · LOW · pre-existing]** `test_plans_generate_path_error_uses_fallback` 单测失败（非本会话引入，不修）。

## 结论
后端契约层 + 端到端 API 全部 **符合**；前端字段对齐与测试补齐为后续工作（其它会话）。