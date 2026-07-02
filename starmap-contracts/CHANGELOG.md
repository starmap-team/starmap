# Changelog

## v1.2.0 — 2026-07-02

- 新增 5 个 API 模块（13 个端点）：
  - **数据流水线** (`/pipeline/*`)：状态概览、运行记录、运行详情、手动触发
  - **数据看板** (`/dashboard/*`)：KPI 概览、实时指标
  - **学习路径** (`/learning/*`)：路径列表、路径详情、学习进度
  - **数据源管理** (`/datasources/*`)：数据源列表、详情、更新
  - **反馈循环** (`/loop/*`)：循环状态、提交反馈
- 新增 14 个 Schema 定义：PipelineStatus, PipelineRun, DashboardOverview, DashboardMetrics, LearningPath, LearningProgress, DatasourceConfig, LoopStatus, FeedbackRequest
- 端点总数：41 | Schema 总数：27

## v1.1.0

- 新增阶段4兼容端点：`/resume/upload`、`/match/diagnose`、`/admin/review-queue`、`/admin/seed/reset`。
- 扩展 `MatchResult`，补充 `match_id`、目标岗位、差距明细、缺失必备/加分技能、总体评估与预计学习时长。
- 新增管理后台数据源、审核队列、演示数据重置相关 Schema。

## v1.0.0

- 初始契约定义
- 15 个 API 端点
- 12 个 Schema 定义
