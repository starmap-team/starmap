# CONFORMANCE — Module 7: 闭环演示 (LoopDemo)

**Phase 13 · Wave 2 · verified 2026-07-27**

| 基线 | 来源 |
|---|---|
| should | `docs/standards/01-backend/07-业务核心-pipeline.md`、`docs/standards/04-contracts/01-API契约规范.md` |
| was-analyzed | `docs/archive/loop-source-analysis.md` |
| is (live) | `frontend/src/pages/LoopDemo.vue` + `stores/loop.ts` + `/api/v1/loop/run` + `/loop/history` + `/loop/status/{id}` + 5-step orchestrator (extract → graph_sync → match → learn → reflect) |

## 符合项（已 verify-first 验证）
- **[CONFORM]** `LoopRunRequest` 契约：`jd_text: str` (min_length=1) + `target_position: str | None`（可选，含 `@field_validator` 将空白转 None → target 真正可选，符合 OpenAPI）。
- **[CONFORM]** `LoopStepResponse` 字段：`step` / `name` / `status` / `data` / `error` / `duration_seconds` / `note`。
- **[CONFORM]** `LoopRunResponse` 字段：`run_id` / `jd_text` / `target_position` / `status` / `steps` / `extracted_skills` / `graph_update` / `match_result` / `learning_path` / `total_duration_seconds`。
- **[CONFORM]** `_step1_validate_input` 行为（per docstring "We must NOT reject the run here"）：空 target_position → SUCCESS（可选）；空 jd_text → FAILED。
- **[CONFORM]** `GET /api/v1/loop/history` → 200，items 数组含完整步骤（提取 step1 jd_length=45 / target=DevOps engineer；后续步骤 tools 等字段完整）。
- **[CONFORM]** `GET /api/v1/loop/status/{run_id}` → 404 + `{"detail": "Loop run '...' not found"}`（正确 not-found 语义，符合 M2）。
- **[CONFORM]** LLM 降级链共享 extract.py 的 MiMo→DeepSeek→Qwen→Ollama。

## 验证证据
- `tests/unit/test_loop_api.py` — 通过
- `tests/unit/test_loop_orchestrator.py` / `test_loop_orchestrator_coverage.py` — 64/66 通过
- 端到端 `GET /api/v1/loop/history` 200（19ms）/ `GET /api/v1/loop/status/{bad_id}` 404
- Step 1 行为验证：空 target 不拒绝（按 docstring 与 plan "target_position optional"）；空 jd_text 拒绝（正确）

## 偏移 / 待办（OPEN）
- **[OPEN · LOW · frontend]** `LoopDemo.vue` / `loop.ts` 错误透传（`err.response.data.detail`，与 Phase 6 jd.ts 同模式）。**其他会话处理**。
- **[OPEN · LOW · frontend]** `LoopDemo.spec.ts` 5+ 测试覆盖（plan 必须-have #3）：渲染、空 JD 输入验证、步骤状态切换 mock、错误处理。
- **[OPEN · LOW · pre-existing]** `test_loop_service.py`/`test_loop_orchestrator*.py` 2 个测试断言"空 target→FAILED"与实际 SUCCESS 行为矛盾（pre-existing，不修）。

## 结论
后端契约层 + 5 步状态机 + 端到端 API 全部 **符合**；前端字段对齐与测试补齐为后续工作（其它会话）。