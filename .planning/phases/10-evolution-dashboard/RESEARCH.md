# Phase 10 — 演化看板模块 (EvolutionDashboard) 研究报告

## 模块概述

EvolutionDashboard.vue (592 行) 是演化看板模块，展示技能演化趋势、新兴技能、职业路径等。

## 关键文件

| 文件 | 大小 | 说明 |
|------|------|------|
| `frontend/src/pages/EvolutionDashboard.vue` | 592 行 | 演化看板主页面 |
| `frontend/src/pages/__tests__/EvolutionDashboard.spec.ts` | 42 行 | 1 个冒烟测试 |

## 后端 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/evolution/trends` | GET | 趋势数据 |
| `/api/v1/evolution/analyze` | POST | 触发分析 |
| `/api/v1/evolution/changelog/{id}` | GET | 变更日志 |
| `/api/v1/evolution/paths/all` | GET | 所有路径 |
| `/api/v1/evolution/paths/{position}` | GET | 单岗位路径 |
| `/api/v1/evolution/emerging-skills` | GET | 新兴技能 |
| `/api/v1/evolution/snapshots` | GET | 快照列表 |
| `/api/v1/evolution/review-queue` | GET | 审核队列 |
| `/api/v1/evolution/cii-history/{position}` | GET | CII 历史 |
| `/api/v1/evolution/portability/{skill}` | GET | 技能迁移性 |

## 测试覆盖现状

- 1 个冒烟测试
