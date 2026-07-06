# Phase 4: 数据流贯通 - Context

**Gathered:** 2026-07-06
**Status:** Ready for planning

<domain>
## Phase Boundary

端到端数据流贯通——从 JD 抽取→技能归一化→图谱写入→匹配诊断→学习计划生成→演化分析→质量监控的整条链路真实执行；补充三方评估报告（JD F1 + Resume F1 + Match Accuracy）和 LLM judge 真接线。Phase 4 不重构（Phase 6）、不样式统一（Phase 5）、不新增图谱 schema（DEC-004：仅追加字段）。

前置阶段已实现（**不在本阶段重做**）：
- LOOP-FLOW-01: `sync_from_pipeline` 已实现在 `graph_service.py:581`（DEC-P1-01 选 B 路线）
- EXTRACT-FLOW-01: `extraction/prompt.py` 已有 prerequisites/learning_resources/evolves_to/tools 字段提取
- EXTRACT-FLOW-02: `graph_writer.build_triples_from_extraction` 已处理上述四类三元组（lines 279-319）
- EXTRACT-FLOW-03: `fetch_position_graph` depth 参数生效，限制 [1,5]
- LOOP-FLOW-03: `loop_results` 已持久化（DEC-P1-02 新建 loop_results 表）
- MATCH-LEARN-01/02: `create_plan_from_match()` 在 `learning_service.py:20` 已实现，存 match_score

本阶段 4 个真正灰色地带：
1. LOOP-FLOW-02: 闭环 5 步全真执行验证（降级语义、失败策略）
2. EVAL-01/03/04: 三方评估报告整合入口与 Golden Set 现状
3. EVAL-02: `judge_eval.py` LLM judge 真接线（复用 + 降级）
4. 端到端可观测性（贯通性如何验证）

</domain>

<decisions>
## Implementation Decisions

### G1 闭环 5 步全真执行（LOOP-FLOW-02）
- **D-01:** **严苛闭环策略**——任意一步失败立即标 FAILED，不静默降级；保证"5 步全真"的硬指标可被验证
- **D-02:** **不引入重试 / circuit breaker**——超出 Phase 4 范围；保持单次执行严格度
- **D-03:** **E2E 集成测试验证闭环**——新增 `tests/e2e/test_loop_5steps.py`（或合并到现有 `tests/e2e/smoke_test.py`），从 `POST /loop/run` 触发，跑完 5 步后查询 PG 校验每张表都有 run_id 关联记录
- **D-04:** **Neo4j/LLM 不可用时 FAILED 冒泡**——失败必须显式记录，不允许任何"假成功"

### G2 EVAL 三方报告整合（EVAL-01/03/04）
- **D-05:** **`quality_report.py` 加 `--ci` 子命令**——保持现有入口不变，新增 CI 模式读取 git HEAD 输出 markdown 表格，**不重写三函数**（已实现在 `quality_report.py:70/184/238`）
- **D-06:** **接受现有 10 条 Golden Set**——`evaluation/golden_set_*.jsonl` 现状已够，**不手工扩充**；Phase 4 不动评测集，只补整合入口
- **D-07:** **CI 模式输出三表合一 markdown**——JD F1 + Resume F1 + Match Accuracy 同行展示，便于 PR 检查
- **D-08:** **真实计算为准**——三函数从 `_load_jsonl` 读真实数据，不引入 mock；无数据时返回 0.0 + status=fail

### G3 LLM judge 真接线（EVAL-02）
- **D-09:** **复用 `call_llm_with_fallback`**——`evaluation/judge_eval.py:28` 已有 `try import`，**不新建 LLM 调用层**
- **D-10:** **可选启用 + 失败回退**——LLM judge 失败时静默回退到 `compute_skill_f1`（`judge_eval.py:75`），不阻塞主流程
- **D-11:** **默认 10 秒超时**——避免 LLM 调用拖慢评估；超时即回退
- **D-12:** **不缓存 LLM judge 结果**——避免 stale judge；EVAL-02 只评估"是否真接线"，不做性能优化

### G4 端到端可观测性
- **D-13:** **不加 trace_id**——闭环 5 步都从 `run_id` 拉起，`pipeline_runs.run_id` 已贯穿；避免新增字段（DEC-004）
- **D-14:** **测试代码调用 5 个 API 验证连通**——`tests/e2e/test_loop_5steps.py` 顺序调 `POST /loop/run` → `GET /learning/plan/{plan_id}` → `GET /match/results/{match_id}`，验证 plan_id/match_id 可逆查
- **D-15:** **不新增 `/pipeline/traces/{run_id}` 端点**——超出 Phase 4 范围；可逆查性由 E2E 测试覆盖

### Claude's Discretion
- E2E 测试中是否使用 pytest fixtures 共享 Neo4j driver / PG session（建议复用现有 `tests/conftest.py`）
- `--ci` 子命令的退出码策略（建议：任一指标 fail → exit 1）
- LLM judge prompt 模板的具体措辞（建议：直接评估技能集重合度 + 简单 yes/no 评分）
- `quality_report.py --ci` 是否同时输出 JSON（建议：同时输出便于机器解析）

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 项目级决策
- `.planning/PROJECT.md` — 项目定义、5大功能+2创新点
- `.planning/REQUIREMENTS.md` §Phase 4 — 10 个需求（EXTRACT-FLOW-01~03, LOOP-FLOW-01~03, MATCH-LEARN-01~02, EVAL-01~04）
- `.planning/ROADMAP.md` §Phase 4 — 成功标准、关键文件
- `.planning/STATE.md` — 当前状态 + DEC-001~009 已锁定决策

### 前序阶段决策（不重做）
- `.planning/phases/01-core-bugfix/01-CONTEXT.md` — DEC-P1-01（sync_from_pipeline B 路线）、DEC-P1-02（loop_results 新表）、DEC-P1-03（match_results 双写）
- `.planning/phases/01-core-bugfix/01-SPEC.md` — Phase 1 8 个需求基线
- `.planning/phases/02-hardcode-elimination/02-SUMMARY.md` — Phase 2 EVOLVES_TO/图谱驱动完成状态
- `.planning/phases/03-frontend-closure/03-CONTEXT.md` — Phase 3 前端闭环决策 D-01~14

### 后端（已就绪，Phase 4 直接验证 / 集成）
- `backend/app/core/pipeline/loop_orchestrator.py` — 5 步闭环编排（`_step1_extraction` ~ `_step5_learning_plan`，`loop_orchestrator.py:327` 是 step3）
- `backend/app/core/extraction/prompt.py` — 13 字段抽取 prompt（已含 prerequisites/learning_resources/evolves_to/tools）
- `backend/app/core/extraction/graph_writer.py` — `build_triples_from_extraction()` 处理四类新三元组（`graph_writer.py:213`）
- `backend/app/services/graph_service.py:218` — `fetch_position_graph(depth=1..5)` 已实现多跳遍历
- `backend/app/services/graph_service.py:581` — `sync_from_pipeline()` 已实现
- `backend/app/services/learning_service.py:20` — `create_plan_from_match()` 已实现
- `backend/app/services/match_service.py` — `run_match()` 已双写 match_results 表
- `backend/app/core/extraction/llm_client.py` — `call_llm_with_fallback()` 复用入口

### 评估脚本（已部分就绪，需补整合入口）
- `scripts/quality_report.py:70` — `evaluate_jd_extraction()` 已实现
- `scripts/quality_report.py:184` — `evaluate_resume_extraction()` 已实现
- `scripts/quality_report.py:238` — `evaluate_matching()` 已实现
- `scripts/quality_report.py:329` — `main()` 入口，需补 `--ci` 子命令
- `evaluation/judge_eval.py:75` — `compute_skill_f1()` 规则回退，需补 LLM judge 真接线
- `evaluation/golden_set_*.jsonl` — 现有 10 条 Golden Set（D-06 不扩充）

### 测试入口
- `tests/e2e/smoke_test.py` — 现有 E2E 冒烟测试（`python tests/e2e/smoke_test.py --base-url http://localhost:8000 --all`）
- `tests/conftest.py` — pytest fixtures，Phase 4 复用

</canonical_refs>

## Existing Code Insights

### Reusable Assets
- `call_llm_with_fallback()` (`extraction/llm_client.py`) — D-09 复用，不新建 LLM 调用层
- `LoopOrchestrator._step1~_step5()` (`pipeline/loop_orchestrator.py`) — 5 步编排已实现，D-03 E2E 测试直接触发
- `quality_report.py` 三函数 — D-05 仅加 `--ci` 子命令，不重写函数
- `tests/conftest.py` fixtures — D-13 测试复用现有 PG/Neo4j fixtures

### Established Patterns
- 三方评估格式：metric / target / current / status 四列（`quality_report.py:373`），D-07 CI 模式沿用
- LLM 调用 fallback 链：primary LLM → secondary LLM → raise，已在 `call_llm_with_fallback` 实现
- 闭环 5 步：`step1_extraction` → `step2_dedup` → `step3_graph_update` → `step4_match` → `step5_learning_plan`
- ID 串联：`run_id` 贯穿 pipeline_runs → extraction_records → match_results → learning_plans（通过 `match_id`/`plan_id` 字段）

### Integration Points
- `tests/e2e/test_loop_5steps.py`（D-03/D-14 新建）：触发 `POST /loop/run` → 轮询 status → 验证 `GET /learning/plan/{plan_id}` 返回 plan
- `scripts/quality_report.py`（D-05 改造）：加 `--ci` 子命令，输出 CI 友好 markdown + JSON
- `evaluation/judge_eval.py`（D-09/D-10 改造）：补 `invoke_llm_judge()` 包装 `call_llm_with_fallback`，超时/异常回退到 `compute_skill_f1`

</canonical_refs>

<specifics>
## Specific Ideas

- `tests/e2e/test_loop_5steps.py` 用例：跑完 5 步后断言 5 张表（pipeline_runs / extraction_records / match_results / learning_plans / loop_results）都有 run_id 记录
- `quality_report.py --ci` 输出格式：markdown 表格 + 末尾 `## Warning Level: green/yellow/orange/red`，与现有格式保持一致
- LLM judge prompt 模板（Claude 决定具体措辞）：要求 LLM 评估"技能集重合度 + 命名规范度"，1-5 分

</specifics>

<deferred>
## Deferred Ideas

- **circuit breaker / 重试机制** — D-02 明确不在 Phase 4 范围；推 Phase 7+ 或后续里程碑
- **trace_id 跨表贯穿** — D-13 明确不加；现有 run_id 足够，run_id 已贯穿
- **Golden Set 扩充到 20+/50+ 条** — D-06 明确不动；当前 10 条够用，扩充属评测优化范畴
- **LLM judge 结果缓存** — D-12 明确不缓存；避免 stale judge，缓存属性能优化范畴
- **`/pipeline/traces/{run_id}` 端点** — D-15 明确不新增；E2E 测试已覆盖贯通性
- **Neo4j/LLM 健康检查探针** — 超出 Phase 4 范围；可作 Phase 7+ 基础设施增强

</deferred>

---
*Phase: 04-dataflow*
*Context gathered: 2026-07-06*