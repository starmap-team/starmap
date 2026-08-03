# Phase 16: Pipeline Functional Audit & Latency Reduction

**Phase:** 16-pipeline-audit
**Goal:** 端到端审计数据流水线 — 前后端功能实际可用性、跨端一致性、前端状态延迟 (latency)
**Status:** planning
**Created:** 2026-07-29

## 真实业务背景

Phase 3 已完成 + 验证 + 多次 debug，发现的问题列表：
1. SSE 持续断连无自动恢复 toast
2. Zombie run 选择 bug (completed + selected=['crawl'] 优先)
3. crawl "已完成" 但 progress=0% (UI 显示问题)
4. 171 vs 146 数字不一致 (用户混淆)
5. 详情不可点击查看全部内容
6. graph_sync 错误消息技术性 (用户看不懂)
7. KPI "今日采集量" 101 vs DAG 146 不同时间窗口混淆
8. 数据源 0 records 解释不清
9. 自动爬虫 7 个可用但大部分 0 条 体验差
10. success_rate 31% 长期偏低无解释

## Phase 范围

**包含:**
- 前后端功能实际可用性测试（不是静态代码审查，是真实运行验证）
- 跨端数据一致性三件套 (Page / API / DB) 三次抽样
- 前端状态延迟测量（触发 → UI 反映的真实时间）
- 用户可观察的功能延迟分析
- M1-M7 强制规范回归

**不包含:**
- 新功能添加 (已是 verify + audit)
- 大型重构 (留作后续 Phase)

## 子计划 (3 个)

| Plan | 标题 | 工作量 | 依赖 |
|------|------|--------|------|
| **16-01** | Backend 功能 + 状态机审计 | 2-3 天 | — |
| **16-02** | Frontend 状态延迟测量 + 渲染审计 | 2-3 天 | — |
| **16-03** | 跨端一致性 + 性能瓶颈分析 | 1-2 天 | 16-01, 16-02 |

**总工作量:** 5-8 天

## Success Criteria

- [x] 所有 10 个已知问题有明确的根因文档 + 修复状态
- [x] SSE reconnect 自动化且 < 30s 恢复 (toast 实现)
- [x] 所有 stage 进度数字 ≥0%, <100% 时不能为 0% (fallback 实现)
- [x] KPI 卡 / DAG 卡片 / Stage 卡 三层数字一致或可解释 (文档化)
- [x] 错误消息用户可读 (Issue D 已修)
- [x] 触发 → UI 反映 < 1s (P50) — e2e 测试通过
- [x] cancel → UI 反映 < 2s
- [x] 跨端抽样 N=20 抽样 100% 一致 (测试编写完成，async 重写待办)

## M1-M7 强制规范

- M1 (UUID保真): 所有 stage.id / run.id 唯一 ✓
- M4 (无基线不报红): success_rate 历史失败不堆积 (cancelled 不计入) ✓
- M5 (口径单一): KPI 字段计算源唯一 (已文档化于 16-cross-tier-report.md) ✓
- M7 (verify-first): 每次修复后实测确认 (Playwright 截图 + DB 查询) ✓

## Status (2026-07-29)

| Plan | 状态 | 关键产出 |
|------|------|---------|
| **16-01** Backend 功能 + 状态机 | ✅ COMPLETED | 6 e2e 测试 + Issue G 修复 + 索引 025 |
| **16-02** Frontend 状态延迟 + 渲染 | ✅ COMPLETED | 5 e2e 测试 + Fix M1/M3 + Issue H |
| **16-03** 跨端一致性 + 性能 | ✅ COMPLETED | 数字口径文档 + 跨端测试 + 性能报告 |