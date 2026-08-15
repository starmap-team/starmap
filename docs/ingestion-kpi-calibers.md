# 入库 KPI 口径定义（活文档）

> 状态：活文档 · 唯一事实源：`backend/app/core/pipeline/status_aggregator.py`
> 本文档与 `status_aggregator.py` 的 `compute_status_aggregates` 保持一致。
> 若聚合逻辑变更，必须**同步更新本文件**与 `backend/scripts/kpi_audit.py` 的运行时断言。

## 目的

消除「DAG 显示采集 70 但今日 KPI 为 0」类跨页歧义：PipelineMonitor 前端三段 KPI
（今日采集量 / 今日新增 / 历史累计 / 成功率）必须从**同一** `pipeline.pipelineStatus`
派生，而 `pipelineStatus` 的四个聚合字段全部来自 `status_aggregator.compute_status_aggregates`
（经 `backend/app/api/v1/pipeline/status_routes.py` 的 `GET /pipeline/status` 输出）。

## 三段 KPI 的 SQL 级定义（照抄 status_aggregator.py:44-115）

以下定义以 `backend/app/core/pipeline/status_aggregator.py` 为准。所有时间窗均按
`datetime.now(UTC)` 计算（UTC naive，与 `pipeline_runs.started_at` 的存储口径一致）。

### 1. today_crawl_volume — 今日采集量

今日各 run 的 `crawl` 阶段 `records_processed` 之和（**含重复**；与 DAG/历史
「处理量」同源，避免「今日跑了多次却显示 0」的困惑）：

```sql
SELECT COALESCE(SUM((s->>'records_processed')::int), 0)
FROM pipeline_runs, jsonb_array_elements(stages::jsonb) s
WHERE s->>'name' = 'crawl' AND started_at >= :today_start
  AND status IN ('completed', 'running', 'failed')
```

- 语义：真实采集活动量（跑了几次算几次，不做去重）。
- 若查询抛异常，聚合器 fail-soft 返回 `0`（不阻断 status 响应）。

### 2. today_crawl_new — 今日新增

今日 `jd_raw` 实际新增行数（爬虫 upsert 重复不改 `crawled_at`，故诚实区分新增 vs 重复）：

```sql
SELECT COUNT(*) FROM jd_raw WHERE crawled_at >= :today_start
```

### 3. total_jd_raw — 历史累计

`jd_raw` 全表行数：

```sql
SELECT COUNT(*) FROM jd_raw
```

### 4. success_rate — 成功率

近 7 天 `completed` / (`completed` + `failed`)：

```sql
SELECT COUNT(*) FROM pipeline_runs WHERE status = 'completed' AND started_at >= :seven_days_ago;
SELECT COUNT(*) FROM pipeline_runs WHERE status = 'failed'    AND started_at >= :seven_days_ago;
-- success_rate = completed / (completed + failed)，无记录时返回 0.0
```

### 5. avg_quality_score — 近 7 天质量均分（辅助字段）

```sql
SELECT AVG(quality_score) FROM pipeline_runs
WHERE status = 'completed' AND started_at >= :seven_days_ago
```

## 前端消费约定（IC-07 防跨页漂移）

- 前端 `frontend/src/composables/usePipelineMonitor.ts` 的 `kpiCards` computed
  必须从 `pipeline.pipelineStatus` 直接读取 `today_crawl_volume` /
  `today_crawl_new` / `total_jd_raw` / `success_rate`，**不得**在前端本地重新
  聚合或改用其它字段推导。
- 回归守卫：`frontend/src/composables/__tests__/usePipelineMonitor.kpi.spec.ts`
  断言三段 KPI 从同一 `pipelineStatus` fixture 派生且与 `status_aggregator`
  的聚合值一致。

## 注意：quality dashboard 是**不同**口径（防误读）

`backend/app/api/v1/quality.py`（`GET /quality/dashboard`）统计的
`pending_review` / `avg_trust_score` / `total_positions`（仅 approved 岗位）等字段
**不是**本文档定义的四段 KPI：

- `pending_review` = `position_records` + `skill_records` 的 `pending_review` 计数
  （审核队列口径，非采集/新增口径）。
- `avg_trust_score` = Neo4j `Skill.trust_score` 均值（信任度口径）。
- `total_positions` = `review_status='approved'` 岗位数（发布口径）。

两者口径不同**是设计意图**：PipelineMonitor 展示采集活动量，Quality Dashboard
展示审核/质量状态。跨页一致性要求的是**重叠指标**（如待审计数）两边一致，
由 `evaluation/ingestion_consistency.py` 的 `cross_page_kpi_drift` 门禁守护。
