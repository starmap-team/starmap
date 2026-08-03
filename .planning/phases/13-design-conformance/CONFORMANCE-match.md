# CONFORMANCE — Module 5: 匹配诊断 (MatchDiagnosis)

**Phase 13 · Wave 1 · verified 2026-07-26**

| 基线 | 来源 |
|---|---|
| should | `docs/standards/01-backend/06-业务核心-matching.md`、`docs/standards/04-contracts/01-API契约规范.md`、架构降级原则（每阶段独立降级，失败不阻塞） |
| was-analyzed | `docs/archive/match-source-analysis.md` |
| is (live) | `frontend/src/pages/MatchDiagnosis.vue` + match store + `/api/v1/match/position` + Neo4j + ChromaDB |

## 已修复 + 验证
- **[FIXED · CRITICAL→CONFORM]** `/match/position` 对**任意**输入返回 500。根因：`scorer._batch_chroma_match` 在 Chroma 集合缺失（`get_collection` 抛 404）时把异常包成致命 `MatchingError`，违背“语义增强可选、应降级”的设计。
  - 修复 `backend/app/core/matching/scorer.py` 4 处 `except`：connect / get_collection / query 改为 `_mark_chroma_unavailable(...)` + `return {}`（降级到词法匹配，并负缓存快速失败）；单条 wrapper 改 `return None`。
  - **验证**：技能丰富岗位「测试工程师」 **500 → 200**，`match_score=0.7652`，`matched_skills=['Selenium','Python']`（词法匹配生效，Chroma 优雅降级）。

## 符合项
- **[CONFORM]** Chroma 不可用时词法匹配仍产出有效分数；负缓存避免重复连接尝试。

## 偏移 / 待办
- **[FIXED · MEDIUM→CONFORM (M2)]** 存在但无技能画像岗位（`Senior Python Engineer`，0 关系）原返回 404，与“不存在”混淆。修复 `backend/app/core/matching/service.py`：`run_match` 在 `profile=None` 时经新增 `_position_exists` 探测，存在则返回 **200** + `match_score=0` + `note`/`overall_assessment` 解释；`MatchResponse` 增 `note` 字段。**验证**：该岗位 404→200 且 note 非空；真不存在 `ZZZ_NoSuchPosition_42` 仍 404；技能丰富岗位回归 200 score .7652 note=None。
- **[OPEN · LOW · frontend]** `MatchDiagnosis.vue` 可呈现 `note`（字段已就绪），非阻断。
- **[OPEN · MEDIUM · 测试]** 缺“Chroma 不可用仍 200”的回归测试，防止降级逻辑被未来重构破坏。
- **[FIXED · MEDIUM→CONFORM (Phase 5 Wave 2 闭环)]** cii 计算漏洞（`required=0` 时 cii=1.0 误读为"无通胀"）：`core/matching/service.py` `_apply_inflation_correction` 改为 `cii=0.0 if required_count==0 else required_count/BASELINE`。**验证**：rich 岗位 cii 1.0→**0.0**。
- **[FIXED · MEDIUM→CONFORM (Phase 5 Wave 2 闭环)]** `/match/batch` 响应加 `summary` 字段 + `items` 别名（前端 `learningStore` 兼容）。**验证**：batch `summary={total:2, success:2, failed:0}`，`items_len=2`。
- **[FIXED · MEDIUM→CONFORM (Phase 5 Wave 2 闭环)]** `/match/competitiveness` 响应加 `items`(瓶颈技能) + `skills`({required,bonus,total}) 别名（前端 `learningAnalytics` 兼容）。**验证**：items_len=5, skills={0,15,15}。
- **[FIXED · MEDIUM→CONFORM (Phase 5 Wave 2 闭环)]** `/match/recommend` 接受前端 `skills` 字段（`ReverseMatchRequest.skills` + `@model_validator` 归并到 `person_skills`）。**验证**：前端 payload 通过 200，返 10 个推荐。
- **[FIXED · MEDIUM→CONFORM (Phase 14)]** 前端 `note` 呈现：`MatchDiagnosis.vue:514` 传 `matchStore.result?.note` → `MatchTrustGuide.vue` `v-if="note"` 渲染 `el-alert`。**验证**：三路径 API（exists-no-profile→200+note、skill-rich→200+null、missing→404/no-note）全部通过。
- **[FIXED · LOW→CONFORM (Phase 14)]** `learningAnalytics.ts:95` `data.items ?? data.trends` → `data.trends ?? data.items`（优先后端新字段名）。`MatchDiagnosis.vue` 已无 `data.items` 残留。
- **[FIXED · MEDIUM→CONFORM (Phase 14)]** 回归测试补全：`test_matching_scorer.py`(2) Chroma 降级、`test_zombie_skip.py`(7) 优先级排序、`test_contract_regression.py`(4) M2/M4/M5/M6 契约，共 13 个测试用例全部 pass。
- **[OPEN · MEDIUM · 测试]** 缺 zombie-skip 回归测试（DB 集成) — 已由 `_pick_best_run` 纯函数 + 7 个单元测试替代，**DB 集成测试需在 CI 环境启用**。

## 结论
后端阻断性缺陷（500/404/cii=1.0/batch/competitiveness/recommend）全部修复并验证（Phase 5 Wave 2 闭环）；余前端字段对齐（MEDIUM）+ 回归测试缺口（MEDIUM）。