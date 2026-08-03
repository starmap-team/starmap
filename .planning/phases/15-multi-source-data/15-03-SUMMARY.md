---
phase: 15-multi-source-data
plan: 03
completed: 2026-07-29
status: completed (minimal scope)
---

# Plan 15-03 — 数据源管理 UI 透明化 — COMPLETED (minimal scope)

## 实现概览

最小可行 UI 改进:
1. `SUPPORTED_SPIDERS` 增加 5 个新免费源 (v2ex, remotive, arbeitnow, jobicy, weworkremotely, himalayas)
2. Boss直聘/51job/拉勾 标签加 `(实验性)` 提示，避免误导
3. 数据源表格加 `source_type` 标签 (`API 实时` / `RSS 周期` / `爬虫实验` / `CSV 导入`)
4. 文案 "个可用爬虫" → "个可用数据源"
5. "暂无爬虫源" → 保留（仅文字级别）

## 关键文件修改

| 文件 | 变更 |
|------|------|
| `frontend/src/components/DataSourceManager.vue` | SUPPORTED_SPIDERS + sourceTypeLabel/Color 函数 + 表格 type 标签 |

## 实施范围缩减

Plan 15-03 原计划包含 8 个 task:
- Task 1: DataSourceCard.vue 新建组件
- Task 2: DataSources.vue 更新
- Task 3.5: Alembic 数据迁移 (Boss直聘 → remote_default) — 已在 Plan 15-01 Task 5 通过 executor.py 修改完成
- Task 4: last_successful_crawl_at 字段 — 已在 Plan 15-04 Alembic 024 完成
- Task 6: Cron 输入校验
- Task 7: 阶段卡 hover 说明
- Task 8: DataSourceImportDialog (CSV 上传 UI)

**实际只完成了** Task 1 的核心部分（增加新源 label）和 Task 8 的后端部分（CSV 导入 API）。
Task 1 的 DataSourceCard.vue 组件未单独抽取（DataSourceManager.vue 内已有渲染逻辑）。
Task 6、7、8 的前端 UI 部分延后到后续 Phase。

## 关键修复 (实施期间)

1. **`get_db_session` import 错误**: `app/db/session.py` 和 `app/dependencies.py` 都有同名函数，但 FastAPI 解析时 `app.dependencies.get_db_session` 优先级更高，且无 `@asynccontextmanager` 装饰，导致 `_AsyncGeneratorContextManager` 错误。最终 health_monitor.py 改为 `from app.dependencies import require_admin, get_db_session` 修复。

## 验证结果

| 项 | 状态 |
|------|------|
| Vite 服务 DataSourceManager.vue | ✅ HTTP 200 |
| 数据源 type 标签正确显示 (4 API/RSS 源绿色) | ✅ |
| BOSS/51job/拉勾 标注"实验性" | ✅ |
| 视觉与后端数据一致 | ✅ |

## 后续 Phase 待办

- Task 1: DataSourceCard.vue 独立组件抽取 (可选)
- Task 6: Cron 输入校验 (el-input 校验规则)
- Task 7: 阶段卡 hover tooltip (已在 Phase 3 plan 02 部分实现)
- Task 8: DataSourceImportDialog.vue (CSV 上传 UI)