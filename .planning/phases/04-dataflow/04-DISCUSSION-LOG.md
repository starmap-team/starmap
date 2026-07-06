# Phase 4 Discussion Log: 数据流贯通

**Phase:** 04 of 6
**Date:** 2026-07-06
**Mode:** discuss (default)

## Gray Areas Discussed

### G1 闭环 5 步全真执行（LOOP-FLOW-02）

**Q1.1: Step 降级语义如何定？**
- A. 严苛闭环：失败立即中断 (✅ **Selected**)
- B. 容错闭环：降级但记录警告
- C. 重试 + 部分降级混合

**Q1.2: 如何验证 5 步全真？**
- A. 仅添加 E2E 集成测试触发验证 (✅ **Selected**)
- B. 添加重试 + 错误码上报
- C. 引入依赖健康检查探针

**Locked decisions:**
- D-01: 严苛闭环策略
- D-02: 不引入重试 / circuit breaker
- D-03: E2E 集成测试验证闭环
- D-04: Neo4j/LLM 不可用时 FAILED 冒泡

---

### G2 EVAL 三方报告整合（EVAL-01/03/04）

**Q2.1: 报告整合入口方式？**
- A. 现有 quality_report.py 加 --ci 子命令 (✅ **Selected**)
- B. 新建 aggregate_report.py
- C. 不动报告，只要函数能返回真实数据

**Q2.2: Golden Set 足够吗？**
- A. 接受现有 10 条 Golden (✅ **Selected**)
- B. 扩充到 20 条
- C. 跳到 50 条 + LLM 扩充

**Locked decisions:**
- D-05: quality_report.py 加 --ci 子命令
- D-06: 接受现有 10 条 Golden Set
- D-07: CI 模式输出三表合一 markdown
- D-08: 真实计算为准，无数据返回 fail

---

### G3 LLM judge 真接线（EVAL-02）

**Q3.1: 复用还是新建 LLM 调用？**
- A. 复用现有 call_llm_with_fallback (✅ **Selected**)
- B. judge_eval 独立写 LLM 调用
- C. 不接 LLM，仅调函数补 EVAL-01

**Q3.2: Judge 启用策略？**
- A. 可选启用 + 失败回退 (✅ **Selected**)
- B. 每次 eval 都调 LLM
- C. 仅存桩函数

**Locked decisions:**
- D-09: 复用 call_llm_with_fallback
- D-10: 可选启用 + 失败回退
- D-11: 默认 10 秒超时
- D-12: 不缓存 LLM judge 结果

---

### G4 端到端可观测性

**Q4.1: 抽取→图谱→匹配→学习计划 ID 串联策略？**
- A. 不加 trace_id，run_id 已贯穿 (✅ **Selected**)
- B. 加 UUID trace_id
- C. 推 Phase 7

**Q4.2: 如何验证贯通性？**
- A. 测试代码里调用 5 个 API 验证连通 (✅ **Selected**)
- B. 新增 /pipeline/traces/{run_id} 端点
- C. 不做贯通验证

**Locked decisions:**
- D-13: 不加 trace_id
- D-14: 测试代码调用 5 个 API 验证连通
- D-15: 不新增 /pipeline/traces/{run_id} 端点

---

## Pre-Phase 4 Already-Decided Items (Carried Forward)

- LOOP-FLOW-01 (`sync_from_pipeline`): 已在 graph_service.py:581 实现（DEC-P1-01）
- EXTRACT-FLOW-01 (prompt fields): 已在 prompt.py 第 44-46/98-108/166-169/217-220 行
- EXTRACT-FLOW-02 (graph_writer dead code): 已在 graph_writer.py 213-330 处理四类新三元组
- EXTRACT-FLOW-03 (depth param): 已在 graph_service.py:218 fetch_position_graph(depth=1..5)
- LOOP-FLOW-03 (loop_results persistence): 已在 Phase 1 实现
- MATCH-LEARN-01/02 (create_plan_from_match): 已在 learning_service.py:20 实现

## Deferred Ideas

- circuit breaker / 重试机制 → Phase 7+
- trace_id 跨表贯穿 → 不需要
- Golden Set 扩充 → 评测优化范畴
- LLM judge 缓存 → 性能优化范畴
- `/pipeline/traces/{run_id}` 端点 → 不新增
- Neo4j/LLM 健康检查探针 → Phase 7+