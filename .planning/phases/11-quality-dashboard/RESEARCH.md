# Phase 11 — 图谱质量模块 (QualityDashboard) 研究报告

## 模块概述

QualityDashboard.vue (579 行) 是图谱质量模块，展示图谱数据质量评估报告。

## 关键文件

| 文件 | 大小 | 说明 |
|------|------|------|
| `frontend/src/pages/QualityDashboard.vue` | 579 行 | 图谱质量主页面 |
| `frontend/src/pages/__tests__/QualityDashboard.spec.ts` | 41 行 | 1 个冒烟测试 |

## 后端 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/quality/evaluate` | POST | 触发质量评估 |
| `/api/v1/quality/report` | GET | 质量报告 |
| `/api/v1/quality/dashboard` | GET | 质量仪表盘 |
| `/api/v1/quality/evaluate/resume` | POST | 简历质量评估 |
| `/api/v1/quality/comprehensive-report` | GET | 综合报告 |

## 测试覆盖现状

- 1 个冒烟测试
