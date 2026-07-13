# Phase 13: 测试覆盖率提升 - Discussion Log

**Date:** 2026-07-13
**Phase:** 13-test-coverage
**Mode:** discuss (default)

## Areas Discussed

### Area 1: Fix-first vs Add-first 策略

**Question:** 41 个旧测试失败怎么处理？修好它们让 CI 全绿，还是先写新测试？

**Options presented:**
1. Fix-first — Wave 0 先修 41 个失败测试，然后 Wave 1-3 写新测试
2. Add-first + xfail 旧测试 — 直接写新测试，旧失败标记 xfail
3. Quick-fix auth only + xfail rest — 只修简单的 Auth JWT 残留（12 个），其他 xfail

**User response:** "关于测试这一块的要求，所有测试如果发生错误，第一步不是修测试，测试目的是为了发现项目bug和问题缺陷，进行优化，从项目代码、架构入手而非一味修复测试，为了测试而测试，你需要保障项目质量来确保测试质量"

**Decision:** Bug-fix + fill gaps — 测试失败 = 项目 bug，从项目代码入手修复，不为通过测试而修测试。保障项目质量来确保测试质量。

**Notes:** 这是一个重要的原则性决策，改变了整个 Phase 的执行方向。41 个失败测试被分类为 10 个代码 bug（Category A: 项目代码 bug）和测试基础设施问题（Category B: mock/fixture 过期）。

---

### Area 2: 后端覆盖策略 — 深度 vs 广度

**Question:** 后端 30 个模块低于 80% 覆盖率。集中火力给核心业务链路写深度测试，还是均匀覆盖？

**Options presented:**
1. 深度优先 — 核心业务链路（Pipeline/LLM/抽取/图谱）
2. 广度优先 — 每个低覆盖模块 ≥5 个测试
3. 按 ROADMAP 字面执行

**User selection:** 深度优先 — 核心业务链路

**Decision:** 集中火力给 Pipeline 执行器(9%)、LLM 客户端(23%)、抽取 API(37%)、图谱 API(44%) 写深度测试。其他低覆盖模块只写基本 smoke 测试。

---

### Area 3: 前端测试范围 — Store vs Composable

**Question:** 前端 10 个 Store 无测试 + 31 个 composable 无测试。先写 Store 还是 composable？

**Options presented:**
1. Store 优先 + useSSE — 5 个核心 Store + 最关键 composable
2. Store + 3 composable 全写 — 按 ROADMAP 字面
3. Store only，composable 延后

**User selection:** Store + 3 composable 全写

**Decision:** 5 个核心 Store（learning, loop, evolution, dashboard, pipeline）+ 3 个 composable（useSSE, useLearning*, useG6*）全部写测试。

---

### Area 4: CI 门禁阈值

**Question:** CI 覆盖率门禁当前 60%，实际 78%。是否提高？

**Options presented:**
1. 保持 60% — 留缓冲
2. 提高到 70% — 防回退
3. 提高到 80% — 与实际匹配

**User selection:** 提高到 70%

**Decision:** `--cov-fail-under=70`，比当前 78% 低 8% 留缓冲，比旧 60% 高 10% 防回退。

---

## Deferred Ideas

- 前端组件测试（33 个组件无测试）— Phase 14 拆分后再补
- E2E 测试增强 — 独立 Phase
- 前端覆盖率门禁 — 需 vitest coverage 配置
- Mutation testing / Property-based testing — 长期目标

---
*Discussion completed: 2026-07-13*
