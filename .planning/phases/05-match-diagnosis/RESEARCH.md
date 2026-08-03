# Phase 5 — 匹配诊断模块 (MatchDiagnosis) 研究报告

## 模块概述

MatchDiagnosis.vue (673 行) 是匹配诊断页面，是 StarMap 的核心业务功能之一。用户上传简历或输入技能，与目标岗位进行匹配评分，展示技能对比雷达图、差距分析、竞争力评估。

## 关键文件

| 文件 | 大小 | 说明 |
|------|------|------|
| `frontend/src/pages/MatchDiagnosis.vue` | 673 行 | 匹配诊断主页面 |
| `frontend/src/stores/match.ts` | - | 匹配状态管理 |
| `frontend/src/pages/__tests__/MatchDiagnosis.spec.ts` | 44 行 | 1 个冒烟测试 |
| `backend/app/api/v1/match.py` | - | 匹配 API 端点 |
| `backend/app/services/match_service.py` | - | 匹配服务 |
| `backend/app/core/matching/` | - | 匹配核心（scorer/path_builder/cache） |

## 子组件

ResumeUpload, PositionSearch, SkillRadar, SkillMatchAnimation, LoadingPulse, MatchBatchMode, GapAnalysisReport

## 后端 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/match/position` | POST | 岗位匹配 |
| `/api/v1/match/diagnose` | POST | 匹配诊断 |
| `/api/v1/match/result/{match_id}` | GET | 匹配结果详情 |
| `/api/v1/match/history` | GET | 匹配历史 |
| `/api/v1/match/competitiveness/{position}` | GET | 竞争力评估 |
| `/api/v1/match/batch` | POST | 批量匹配 |
| `/api/v1/match/recommend` | POST | 岗位推荐（反向匹配） |

## 测试覆盖现状

- 1 个冒烟测试（渲染不崩溃）
- 无匹配流程、雷达图、差距分析、批量模式测试

## 关键业务流

简历上传 → 技能抽取 → 岗位选择 → 匹配评分 → 雷达图对比 → 差距分析 → 学习路径推荐

## 已知关注点

1. 匹配请求/响应的字段对齐（MatchRequestInput / MatchResponse）
2. 雷达图数据映射（技能对比）
3. 批量匹配模式的状态管理
4. 竞争力评估的数据来源
