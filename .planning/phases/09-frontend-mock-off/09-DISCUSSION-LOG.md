# Phase 9: 前端关闭 Mock - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-10
**Phase:** 09-frontend-mock-off
**Areas discussed:** MSW 关闭策略, 空状态展示方式, 环境变量与代理确认, msw 依赖清理

---

## MSW 关闭策略

| Option | Description | Selected |
|--------|-------------|----------|
| 彻底删除 | 删除 enableMocking() 调用、mock/ 目录、mockServiceWorker.js、从 package.json 移除 msw 依赖 | |
| 保留开关但默认关闭 | 保留 VITE_USE_MSW 开关机制，默认 false，删除 mockServiceWorker.js 和硬编码数据 | |
| 删除调用但保留依赖 | 删除 enableMocking() 调用和 mock/ 目录，但保留 msw 在 package.json devDependencies 中 | ✓ |

**User's choice:** 删除调用但保留依赖
**Notes:** 保留 msw 依赖以备未来可能需要 mock 新 API，避免重新安装和 init 的开销

---

## 空状态展示方式

| Option | Description | Selected |
|--------|-------------|----------|
| 隐藏图表区域 | 删除 getPlaceholder* 函数，无数据时返回 null，图表区域完全隐藏 | |
| 显示空状态组件 | 删除 getPlaceholder* 函数，无数据时显示 custom-empty 空状态组件（与 18 个现有组件一致） | ✓ |
| 保留占位但改文案 | 保留 getPlaceholder* 函数但改为显示"暂无数据"文字覆盖层 | |

**User's choice:** 显示空状态组件
**Notes:** placeholder 半透明占位图给用户"有数据但很淡"的错觉，空状态组件更诚实

---

## 环境变量与代理确认

| Option | Description | Selected |
|--------|-------------|----------|
| 创建 .env.development | 创建 .env.development 固化 VITE_USE_MSW=false + VITE_API_BASE_URL，补全 env.d.ts 声明 | ✓ |
| 不创建，用代码默认值 | 不创建 .env 文件，仅在代码中硬编码默认值 | |

**User's choice:** 创建 .env.development
**Notes:** 本地开发默认走真实 API，环境变量显式声明避免隐式依赖

---

## msw 依赖清理

| Option | Description | Selected |
|--------|-------------|----------|
| 保留依赖 | 保留 msw 在 devDependencies 中，仅删除 mock/ 目录和 mockServiceWorker.js | ✓ |
| 移除依赖 | 从 package.json 移除 msw，重新生成 lockfile | |

**User's choice:** 保留依赖
**Notes:** 与 D-01 一致，保留以备未来

---

## Claude's Discretion

- main.ts 删除 enableMocking 后的 bootstrap() 函数简化（保留 async 结构）
- useDashboardCharts.ts 删除 getPlaceholder* 后，computed 返回 null 时的父组件处理逻辑
- custom-empty 空状态的具体文案
- env.d.ts 中 VITE_USE_MSW 声明是否保留（建议保留 — msw 依赖仍在）

## Deferred Ideas

- msw 依赖彻底移除 — 推 v2.2+ 确认不再需要 mock 后
- .env.production 文件 — 生产环境配置属部署范畴
- 前端 API 错误重试/降级策略 — 属未来优化
- 图表骨架屏（skeleton）— UX 优化范畴
- MSW 单元测试 mock — 未来可能用于 Vitest 单元测试
