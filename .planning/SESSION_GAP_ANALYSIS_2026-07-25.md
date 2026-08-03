---
title: 本次会话修复 Gap 分析
date: 2026-07-25
session: 全角色浏览器测试 + UX 优化
---

# 本次会话修复 Gap 分析

## 已验证修复 ✅（有截图/API/DB 证据）

| 修复项 | 验证方式 | 证据 |
|--------|---------|------|
| Redis 认证 | `redis-cli ping` → PONG | ✅ |
| SSE /pipeline/events 限流白名单 | `curl` 连续 5 次 → 全部 200 | ✅ |
| SSE 连接数限制上调 (10→25) | 代码已更新到容器 | ✅ |
| 僵尸 run 手动清理 | `pipeline_runs` 表 running=0 | ✅ |
| zombie 自动检测代码 | `get_status()` 中有 30min 阈值 | ✅ |
| 3d-force-graph 包安装 | 容器内 package.json 存在 | ✅ |
| Vite 错误遮罩关闭 | `hmr.overlay: false` 在 vite.config.ts | ✅ |
| KPI 空状态文案 | 代码中有 `历史累计` 字样 | ✅ |
| DAG consumed 集合防重复 | 代码中有 `consumed` Set | ✅ |
| ContentReviewPanel 批量操作 | 代码中有 `batchApprove/batchReject` | ✅ |
| ContentReviewPanel 数据口径 tooltip | 代码中有 el-tooltip | ✅ |

## 未验证修复 ⚠️（代码改了但页面效果未确认）

| 修复项 | 问题 | 需要的验证 |
|--------|------|-----------|
| DAG 显示 "SimHash去重" + "清洗标准化" | 代码改了但 HMR 不生效，截图仍显示 dedup_clean | 需要重启前端容器后截图确认 |
| KPI "今日 0 / 历史累计 46" | 代码改了但 HMR 不生效 | 需要重启前端容器后截图确认 |
| ContentReviewPanel 批量操作按钮 | 代码改了但 HMR 不生效 | 需要重启前端容器后截图确认 |

## 未修复 ❌（只有半截或完全没做）

| 项 | 问题 | 归属 Phase |
|----|------|-----------|
| 70/56/39 口径统一 | 只加了 tooltip 解释，三个 API 仍返回不同数字 | Phase 1 |
| graph.ts Store 对齐 | 未检查 graph store 的 fetchOverview 返回结构 | Phase 1 |
| Home.spec.ts 测试 | 未写 | Phase 1 |
| 岗位列表模块 | 完全未开始 | Phase 2 |
| PipelineMonitor.spec.ts 测试 | 未写 | Phase 3 |
| SSE 事件流前端验证 | 未验证 pipeline_update 事件是否正确分发 | Phase 3 |

## 结论

本次会话做了**基础设施修复**（Redis、限流、包依赖），但**业务逻辑修复**只完成了一半。后续执行 Phase 1-3 时必须按 VERIFY_FIRST_METHODOLOGY.md 逐条验证。