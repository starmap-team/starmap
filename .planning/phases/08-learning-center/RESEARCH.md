# Phase 8 — 学习中心模块 (LearningCenter) 研究报告

## 模块概述

LearningCenter.vue (769 行) 是学习中心页面，展示个人学习计划、技能进度、推荐资源。

## 关键文件

| 文件 | 大小 | 说明 |
|------|------|------|
| `frontend/src/pages/LearningCenter.vue` | 769 行 | 学习中心主页面 |
| `frontend/src/pages/__tests__/LearningCenter.spec.ts` | 43 行 | 1 个冒烟测试 |

## 后端 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/learning/plans` | GET | 学习计划列表 |
| `/api/v1/learning/plan` | POST | 创建学习计划 |
| `/api/v1/learning/plan/{plan_id}` | GET | 学习计划详情 |
| `/api/v1/learning/plan/{plan_id}/progress` | PUT | 更新技能进度 |
| `/api/v1/learning/plan/{plan_id}/skills` | POST | 添加技能到计划 |
| `/api/v1/learning/recommendations` | GET | 学习推荐 |

## 测试覆盖现状

- 1 个冒烟测试

## 已知关注点

1. 学习计划 CRUD 数据流
2. 技能进度更新
3. 推荐资源展示
