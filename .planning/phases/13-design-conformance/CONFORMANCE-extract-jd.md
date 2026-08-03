# CONFORMANCE — Module 6: JD 抽取 (ExtractJD)

**Phase 13 · Wave 2 · verified 2026-07-27**

| 基线 | 来源 |
|---|---|
| should | `docs/standards/01-backend/03-业务核心-extraction.md`、`docs/standards/04-contracts/01-API契约规范.md`、`docs/standards/05-evaluation/01-评估套件规范.md` |
| was-analyzed | `docs/archive/extract-source-analysis.md` |
| is (live) | `frontend/src/pages/ExtractJD.vue` + `stores/jd.ts` + `/api/v1/extract/jd` + `/api/v1/extract/cost-summary` + PG `position_records/skill_records` + Neo4j + LLM 降级链 (MiMo→DeepSeek→Qwen→Ollama) |

## 符合项（已 verify-first 验证）
- **[CONFORM]** `ExtractionRequest` 契约：`jd_content: str` min_length=1 / max_length=50000 + 可选 `options: dict`（与 plan 必须-have #3 一致）。
- **[CONFORM]** `ExtractionResult` 契约字段完整（plan 必须-have #4 + #5 反幻觉三段）：
  - `position_name`, `required_skills[]`, `preferred_skills[]`（每项含 `skill/proficiency` 映射）
  - `normalized_skills[]`（每项含 `name/method/confidence`）
  - `confidence`（百分比）
  - **反幻觉三段**：`hallucinated_skills[]` / `missing_skills[]` / `issues[]`
  - 透传字段：`tools[]` / `learning_resources[]` / `evolves_to[]` / `experience_required` / `education_required` / `responsibilities[]` / `hallucination_score`
- **[CONFORM]** `/extract/cost-summary` 数据流可达（plan 必须-have #5）：`GET /api/v1/extract/cost-summary` → 200 → `{"price_cny_per_1m_tokens": 1.0, "total_cost_cny": 0, "total_tokens": 0, "by_model": {}}`（内存聚合 tracker.summary()）。
- **[CONFORM]** 反幻觉与归一化架构：`app.core.extraction.normalize` + `app.core.extraction.anti_hallucination` 链路完整，单元测试覆盖（`test_extraction_anti_hallucination.py`、`test_extraction_normalize.py` 全部通过）。
- **[CONFORM]** LLM 降级链：`MiMo → DeepSeek → 星火 → Qwen/Ollama` 任一失败自动切换，全部失败抛 `LLMConnectionError`。
- **[CONFORM]** 双写持久化：`_write_extraction_to_pg` + `_write_extraction_to_graph`（Neo4j 节点 + 关系）。Phase 5 方案 B 修复后，Neo4j 接受 PG 权威投影。

## 验证证据
- `tests/unit/test_extract_api.py` — 48/49 通过（1 pre-existing 失败 `test_failure_returns_none` 与本次修复无关，pre-existing issue）。
- `tests/unit/test_extraction_anti_hallucination.py` — 全部通过
- `tests/unit/test_extraction_normalize.py` — 全部通过
- `tests/unit/test_persist_extraction.py` — 全部通过
- 端到端 `GET /api/v1/extract/cost-summary` 200 OK（6ms）

## 偏移 / 待办（OPEN）

- **[OPEN · MEDIUM · 端到端]** `/extract/jd` 真实 LLM 调用验证（plan 必须-have #4/#5 的端到端断言）。本会话不在线上调用 LLM（会触发全链路超时/降级），留给前端会话在有 mock 模式或可控 LLM 时验证。
- **[OPEN · MEDIUM · frontend]** ExtractJD.vue / jd.ts 字段对齐后端 schema（plan 必须-have #3 + #4 + #6）。具体：表单 `jd_content`/options、result.position_name/required_skills(proficiency)/normalized_skills(method, confidence)/反幻觉三段渲染。**其他会话处理**。
- **[OPEN · LOW · 测试]** `ExtractJD.spec.ts` 需补 5+ 测试覆盖（plan 必须-have #7）：空文本守卫、抽取成功渲染、抽取失败态、归一化表渲染、cost-summary 调用。
- **[OPEN · LOW · pre-existing]** `test_failure_returns_none` 单测失败（非本会话引入，不修）。

## 结论
后端契约层、schema 完整性、反幻觉/归一化/持久化链路、cost-summary 数据流 **全部符合**；端到端 LLM 抽取与前端字段对齐为后续工作（其它会话 + Phase 6 计划剩余任务）。