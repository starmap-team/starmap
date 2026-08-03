# Phase 4 — 数据源管理模块 (DataSources) 研究报告

## 模块概述

DataSources.vue (645 行) 是数据源管理页面，包含数据源列表、健康检查、统计图表、同步触发等功能。

## 关键文件

| 文件 | 大小 | 说明 |
|------|------|------|
| `frontend/src/pages/DataSources.vue` | 645 行 | 数据源管理页面 |
| `frontend/src/stores/datasource.ts` | - | 数据源状态管理 |
| `frontend/src/pages/__tests__/DataSources.spec.ts` | 44 行 | 1 个冒烟测试 |
| `backend/app/api/v1/datasource.py` | - | 后端 API 端点 |

## 后端 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/datasources` | GET | 数据源列表 |
| `/api/v1/datasources/health` | GET | 健康检查 |
| `/api/v1/datasources/{source_id}` | GET | 单个数据源详情 |
| `/api/v1/datasources/{source_id}` | PUT | 更新数据源 |
| `/api/v1/datasources/{source_id}/stats` | GET | 数据源统计 |
| `/api/v1/datasources/{source_id}/sync` | POST | 触发同步 |

## 测试覆盖现状

- 1 个冒烟测试（渲染不崩溃）
- 无 loading 态、空数据态、健康状态、同步触发测试

## 已知问题

1. 数据源健康状态刷新机制
2. 同步触发后的状态反馈
3. ECharts 图表数据映射
