## 验收标准：Phase 1 Task 3 前后端联调修复

### 当前状态（修复前 — 2026-07-25 截图）
- Home 页 KPI 卡片显示 70 个岗位（图谱节点总数）
- 岗位列表显示 56 条
- 管理后台显示 39 已发布 + 17 待审
- 三个数字让用户困惑（已完成 tooltip 解释但底层未统一）

### 需要修复的核心问题（基于源码分析报告）

#### [HIGH] `positionsByKA` Map 响应式丢失
**文件:** `frontend/src/stores/graph.ts`
**预期验证:** 修改后 Vue 响应式系统能正确追踪 Map 变化

#### [HIGH] KPI 零值被 `??` 运算符吞噬
**文件:** `frontend/src/pages/Home.vue:34-35`
**预期验证:** independentPositions=0 时不显示错误值

#### [MEDIUM] `handleSearchSelect` 缺少 `await`
**文件:** `frontend/src/composables/home/useHomeInteractions.ts`
**预期验证:** 搜索选择后 position 层正确加载

#### [MEDIUM] 错误处理仅 DEV console.error
**文件:** `frontend/src/stores/graph.ts`
**预期验证:** API 失败时用户看到 ElMessage 错误提示

### 修复后验证（必须执行）
1. 后端: `docker restart starmap-backend` + `curl /health` → ok
2. 前端: `docker restart starmap-frontend` + Playwright 截图
3. 截图证据: `tests/e2e/investigations/ux/home_after.png`
4. 控制台: 0 errors
5. lint: ruff check + npx eslint 通过