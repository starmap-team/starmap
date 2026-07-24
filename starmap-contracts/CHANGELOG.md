# Changelog

## Unreleased

- Centralized backend API models under `backend/app/schemas/`.
- Added exported JSON Schema under `starmap-contracts/schemas/` and frontend runtime validation integration.
- Expanded auth/admin/evolution/pipeline contract coverage without preserving hand-written endpoint totals in documentation.
- Aligned documentation with `/api/v1`, unified error responses and the contract-first generation flow.

## v1.2.0 — 2026-07-02

- 新增 5 个 API 模块（13 个端点）：
  - **数据流水线** (`/pipeline/*`)：状态概览、运行记录、运行详情、手动触发
  - **数据看板** (`/dashboard/*`)：KPI 概览、实时指标
  - **学习路径** (`/learning/*`)：路径列表、路径详情、学习进度
  - **数据源管理** (`/datasources/*`)：数据源列表、详情、更新
  - **反馈循环** (`/loop/*`)：循环状态、提交反馈
- 新增 14 个 Schema 定义：PipelineStatus, PipelineRun, DashboardOverview, DashboardMetrics, LearningPath, LearningProgress, DatasourceConfig, LoopStatus, FeedbackRequest
- 端点总数：41 | Schema 总数：27
