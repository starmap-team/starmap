# Phase 9 — 数据大屏模块 (DataDashboard) 研究报告

## 模块概述

DataDashboard.vue (859 行) 是数据大屏页面，集成 ECharts 图表展示核心数据指标。

## 关键文件

| 文件 | 大小 | 说明 |
|------|------|------|
| `frontend/src/pages/DataDashboard.vue` | 859 行 | 数据大屏主页面 |
| `frontend/src/pages/__tests__/DataDashboard.spec.ts` | 40 行 | 1 个冒烟测试 |

## 后端 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/dashboard/overview` | GET | 数据总览 |
| `/api/v1/dashboard/trends` | GET | 趋势数据 |
| `/api/v1/dashboard/distribution` | GET | 分布数据 |
| `/api/v1/dashboard/realtime` | GET (SSE) | 实时数据流 |
| `/api/v1/dashboard/realtime-poll` | GET | 实时轮询数据 |

## 测试覆盖现状

- 1 个冒烟测试（仅验证渲染）

## 已知关注点

1. 5 个 API 端点的数据流对齐
2. ECharts 图表数据映射
3. SSE 实时数据流处理
