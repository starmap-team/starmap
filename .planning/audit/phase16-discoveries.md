---
title: Phase 16 Browser/API/DB 三端审计发现
date: 2026-07-29
method: Playwright + curl + SQLAlchemy 真实运行测试
---

# Phase 16 三端审计发现 (2026-07-29)

## 测试方法

```python
# 1. Chrome via Playwright (调试端口 9222 已运行)
# 2. JWT 注入 localStorage
# 3. 触发 pipeline
# 4. 截图 + DOM 文本提取
# 5. 同时查询 API + DB 对比
```

## 发现的问题

### 🔴 Issue 1 (HIGH): data_sources.total_records 永未更新

**症状:** UI 显示所有 7 个数据源 `0 条`，但本次 run 实际插入 144 条

**验证:**
- DB 直接查询: `data_sources.total_records` 全部为 0（除旧 Lagou 39）
- API 返回的 `/pipeline/stages` 显示 crawl 处理量 144
- 截图: 数据源管理表格 "记录量" 列全部为 0

**根因:** `backend/app/core/pipeline/executor.py:795-801` `_update_source_after_crawl` 函数:
```python
def _update_source_after_crawl(run_id: str, records_count: int) -> None:
    try:
        ...
        # 这里应该更新 data_sources.total_records 但没做
```

**Plan 16-01 增补:** Issue G — `_update_source_after_crawl` 必须更新 total_records 字段

### 🔴 Issue 2 (HIGH): 爬虫采集"已完成 0%"

**症状:** 截图显示 "爬虫采集 已完成 0% 13.8s 144"

**根因:** Plan 16-02 Task 2 的 fallback (completed + null progress → 100) 还未实施

**Plan 16-02 Task 2:** 已规划，待实施

### 🟡 Issue 3 (MEDIUM): 数字口径混乱 (4 个不同数字)

| 显示位置 | 数字 | 实际语义 |
|---------|------|---------|
| Hero Card | 181 | 累计 + LLM 输入? |
| KPI 今日采集量 | 121 | `jd_raw.crawled_at >= today_start` (累计) |
| DAG crawl 处理量 | 144 | 本次 run `records_processed` |
| DAG clean 处理量 | 17 | 去重后清洗数 |

**根因:** KPI / DAG / stage card 三个口径独立计算，UI 没区分

**Plan 16-02 Task 3:** 已规划 (Issue C + Issue G)

### 🟢 Issue 4 (LOW): DAG 不显示 timeseries stage

**症状:** ALL_STAGE_NAMES 包含 6 个 stage，API 返回 6 个 stage，但 PipelineDag.vue 硬编码只渲染 5 个

**根因:** `frontend/src/components/PipelineDag.vue:152-228` 有 5 个 stage rows (crawl/dedup/clean/import/graph_sync) + 4 个 arrow rows

**决策:** 之前 `usePipelineMonitor.ts:9` 注释 `ponytail: timeseries stage was removed from the active pipeline`，但 ALL_STAGE_NAMES 仍包含 timeseries

**Plan 16-02 增补:** Issue H — PipelineDag.vue 加 timeseries row 或从 ALL_STAGE_NAMES 移除

### 🟢 Issue 5 (LOW): KPI 重复显示 3-4 次

**症状:** `body.innerText` 包含 "今日采集量" 4 次

**根因:** 多处渲染 KPI (header, mobile, 大屏等) 但隐藏 CSS 没生效

**根因细节:** 检查 `kpiCards` computed 是否有重复或多个 v-for 引用

**Plan 16-02 增补:** Issue I — 检查 v-for 重复

### 🟢 Issue 6 (LOW): "3/5 阶段已完成" 但实际有 6 个 stage

**症状:** DAG header 显示 "3/5 阶段已完成" 但 ALL_STAGE_NAMES 有 6 个

**根因:** PipelineDag.vue:40 `completedCount` 用 `props.timelineStages.filter(s => s.status === 'completed')` 但 `timelineStages` 来自 usePipelineMonitor.ts 的 6 元素 map
DAG 模板只渲染 5 个，timeseries 始终不显示

**根因细节:** 与 Issue 4 同一根因

## 新增需修问题

| ID | 文件 | 修复 |
|----|------|------|
| Issue G | `backend/app/core/pipeline/executor.py:795` | `_update_source_after_crawl` 更新 `total_records` |
| Issue H | `frontend/src/components/PipelineDag.vue` | 加 timeseries row 或从 ALL_STAGE_NAMES 移除 |
| Issue I | `frontend/src/pages/PipelineMonitor.vue` | 检查 KPI 重复渲染 |

## 已规划待实施 (原计划)

- 16-01 Issue A: SSE reconnect
- 16-01 Issue B: success_rate cancelled 区分
- 16-01 Issue C: 数字口径 (已移到 16-02)
- 16-01 Issue D: 错误消息用户友好 (已实施)
- 16-02 Issue E: SSE reconnect toast
- 16-02 Issue F: 进度 fallback
- 16-02 Issue G: 数据源 0 records 区分 (扩展含 total_records 修复)
- 16-03: 跨端一致性 + 性能