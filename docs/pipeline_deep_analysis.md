# StarMap 数据流水线模块 — 前后端深度分析报告

> 分析日期: 2026-07-19  
> 覆盖范围: 后端 `app/core/pipeline/` + `app/pipeline/` + `app/api/v1/pipeline/` + 前端 `pages/` + `stores/` + `components/` + `composables/`

---

## 一、整体架构概览

StarMap 数据流水线是一个**多层次的数据处理体系**，后端由 **三套独立管道系统** + **多套辅助模块** 组成，前端提供 **监控可视化** + **交互分析**。

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        StarMap 数据流水线 全景图                            │
├───────────────────────────────┬──────────────────────────────────────────┤
│          后端 (Python)         │            前端 (Vue 3 + TS)              │
│                               │                                          │
│  ┌─────────────────────────┐  │  ┌────────────────────────────────────┐  │
│  │  1. ETL DAG 管道         │  │  │  PipelineMonitor.vue               │  │
│  │  crawler→dedup∥clean    │◄─┼──│  主监控页面                         │  │
│  │  →import→graph→ts        │  │  │  + KPI卡片 + DAG视图 + 质量面板    │  │
│  │  (Celery 异步执行)        │  │  └────────────────────────────────────┘  │
│  ├─────────────────────────┤  │  ┌────────────────────────────────────┐  │
│  │  2. 闭环管道 (Loop)       │  │  │  PipelineAnalysis.vue              │  │
│  │  JD→提取→图谱→匹配→学习   │◄─┼──│  求职者分析向导                     │  │
│  │  (同步5步，错误隔离)       │  │  │  简历上传→技能提取→匹配→学习路径     │  │
│  ├─────────────────────────┤  │  └────────────────────────────────────┘  │
│  │  3. 求职者分析管道        │  │  ┌────────────────────────────────────┐  │
│  │  简历→提取→匹配→学习→推荐 │◄─┼──│  Pinia Stores                       │  │
│  │  (SSE 流式推送)           │  │  │  pipelineRun + pipelineConfig       │  │
│  └─────────────────────────┘  │  │  + usePipelineMonitor composable     │  │
│                               │  └────────────────────────────────────┘  │
│  ┌─────────────────────────┐  │  ┌────────────────────────────────────┐  │
│  │  辅助模块                 │  │  │  组件体系                           │  │
│  │  data_fusion (SimHash)    │  │  │  PipelineDag + StageCard +          │  │
│  │  quality_monitor (质量)   │  │  │  SourcePanel + QualityPanel         │  │
│  │  source_authority (权威)  │  │  │  (全部通过 composable 粘合)         │  │
│  │  cron_scheduler (调度)    │  │  └────────────────────────────────────┘  │
│  │  status_aggregator (聚合) │  │                                          │
│  └─────────────────────────┘  │  ┌────────────────────────────────────┐  │
│                               │  │  通信层                             │  │
│  ┌─────────────────────────┐  │  │  REST API (17个端点)                │  │
│  │  Celery 任务层            │  │  │  SSE 事件流 (4种事件类型)           │  │
│  │  7个异步任务               │◄─┼──│  + 轮询降级 (自动fallback)         │  │
│  │  + Beat 定时              │  │  └────────────────────────────────────┘  │
│  └─────────────────────────┘  │                                          │
└───────────────────────────────┴──────────────────────────────────────────┘
```

---

## 二、后端深度分析

### 2.1 三套管道体系对比

| 维度 | ETL DAG 管道 | 闭环管道 (Loop) | 求职者分析管道 |
|------|-------------|----------------|---------------|
| **文件** | `core/pipeline/orchestrator.py` + `executor.py` | `core/pipeline/loop_orchestrator.py` | `pipeline/engine.py` + `steps.py` |
| **步骤数** | 6 阶段 (含 timeseries) | 5 步骤 | 5 步骤 |
| **执行方式** | Celery 异步 + DAG 调度 | 同步顺序 (async) | SSE 流式推送 |
| **并行支持** | DAG fork/merge | 无 | 匹配步骤内并发 |
| **错误处理** | 单阶段失败→标红，可选阶段自动跳过 | 单步失败→隔离，后续步骤可降级 | 单步超时+全局超时 |
| **触发方式** | 手动/Cron/API | API 调用 | 前端上传简历 |
| **数据源** | 爬虫 (BOSS直聘) | JD 文本输入 | 简历文件上传 |
| **图谱写入** | graph_sync 阶段 | Step 3 内嵌 | 无（仅匹配） |
| **API路由** | `/pipeline/*` (20个端点) | `/loop/*` | `/pipeline/analyze` |

### 2.2 ETL DAG 管道 — 核心引擎

#### 2.2.1 DAG 拓扑

```
         ┌──────────┐
         │  crawl   │  爬虫采集 (BOSS直聘, 全量200条/增量50条)
         │  (Root)  │
         └────┬─────┘
              │
         ┌────┴────┐
         ▼         ▼
    ┌────────┐ ┌────────┐
    │ dedup  │ │ clean  │  SimHash去重 ∥ 清洗标准化 (并行)
    │        │ │        │
    └───┬────┘ └───┬────┘
        └─────┬────┘
              ▼
         ┌────────┐
         │ import │  LLM技能提取 → PostgreSQL + Neo4j
         └───┬────┘
             ▼
         ┌────────┐
         │ graph   │  图谱同步/构建 (Neo4j 7节点+8关系类型)
         │ _sync   │
         └───┬────┘
             ▼
         ┌────────┐
         │ timeseries│ 技能时序数据刷新
         └────────┘
```

#### 2.2.2 状态机设计

**运行状态 (RunStatus)**: `running` → `completed` / `failed` / `cancelled`

**阶段状态 (StageStatus)**: `pending` → `running` → `completed` / `failed` / `skipped` / `cancelled`

**执行循环**:
1. `trigger_and_start()` → 创建 `PipelineRun` + 自动取消 stuck 运行（>30min）
2. `advance_pipeline()` → 计算就绪阶段 → 标记 running → `execute_pipeline_stage.delay()` (Celery)
3. Celery worker 执行阶段函数 → `update_stage_status()` → 回调 `advance_pipeline()`
4. `all_stages_done()` → `complete_run()` → 自动更新数据源权威分 + 低质量自动暂停

#### 2.2.3 关键设计决策

- **STOP 标志机制**: 取消运行时通过 Redis `pipeline:stop:{run_id}` (TTL 1h)，Celery worker 在阶段开始前检查
- **可选阶段**: `graph_sync` 和 `timeseries` 为 optional，失败不阻塞 pipeline 完成
- **阶段选择**: 触发时可指定 `selected_stages`，未选中的阶段标记为 `skipped`
- **Stuck 清理**: `trigger_and_start()` 自动取消启动超过30分钟仍为 `running` 的旧 run

#### 2.2.4 各阶段实现细节

| 阶段 | 执行函数 | 核心逻辑 | 数据源更新 |
|------|---------|---------|-----------|
| **crawl** | `execute_crawl()` | 调用 BOSS 直聘爬虫，upsert 到 `jd_raw` 表 | `_update_source_after_crawl()`: 更新 total_records + last_crawl_at |
| **dedup** | `execute_dedup()` | 两遍去重: Redis content-hash (精确) + SimHash (模糊) | `_update_source_after_dedup()`: 更新 duplicate_rate |
| **clean** | `execute_clean()` | 文本清理: strip空白 + 提取首行作为标题 | 无 |
| **import** | `execute_import()` | 取 cleaned JDs → `batch_extract_jd()` (LLM) → 写 PostgreSQL | `_update_source_after_import()`: 更新 valid_records + avg_quality_score |
| **graph_sync** | `execute_graph_sync()` | 调用 `build_graph_from_extractions()` → 写入 Neo4j (limit 500) | 无 |
| **timeseries** | `execute_timeseries()` | 刷新技能时序数据窗口 | 无 |

### 2.3 闭环管道 (Loop Orchestrator)

5步端到端流程，**每步独立 try/except 隔离**:

```
Step 1: JD输入验证 → Step 2: LLM技能提取 → Step 3: 图谱更新
→ Step 4: 匹配诊断 → Step 5: 学习路径生成
```

**整体状态判定逻辑**:
- 仅步骤4/5失败 → 仍标记 `completed`（降级容忍）
- ≥3步失败 → 标记 `failed`
- 其余 → `completed`

**关键设计**:
- 每步完成后立即 `_update_steps_json()` 持久化到 `loop_results` 表（JSONB）
- DB 不可用时 fallback 到内存存储 `_LOOP_RESULTS`（上限 200 条）
- Step 1 验证失败立即终止（不降级，因为 JD/目标岗位是核心输入）
- Step 5 自动调用 `create_plan_from_match()` 创建学习计划到 DB

### 2.4 求职者分析管道 (Pipeline Engine)

```python
# 5步 SSE 流式管道
engine = PipelineEngine([
    ResumeParseStep(),      # PDF/DOCX → 纯文本
    SkillExtractStep(),     # LLM → 结构化技能
    MatchStep(),            # 并发岗位匹配 (50并发)
    LearningPathStep(),     # 学习路径填充
    RecommendStep(),        # 岗位推荐
])
result = await engine.run(context)  # AsyncIterator[SSE事件]
```

每步输出包含: `step_name`, `status`, `progress`, `data`, `error`, `duration_ms`

### 2.5 辅助模块体系

| 模块 | 文件 | 功能 | 缓存策略 |
|------|------|------|---------|
| **数据融合** | `data_fusion.py` | SimHash去重 + 源权威加权 + 交叉验证 (N源确认) | 无 |
| **质量监控** | `quality_monitor.py` | 4维度评分 (完整性/准确性/新鲜度/重复率) + 异常检测 (z-score) + 告警生成 | 无 |
| **状态聚合** | `status_aggregator.py` | 计算今日采集量/成功率/质量分/一致性/时效性/趋势 | Redis TTL 10min |
| **源权威** | `source_authority.py` | 复合权威分: quality(50%) + volume(25%) + consistency(25%) | 无 |
| **Cron调度** | `cron_scheduler.py` | croniter 解析 + 60s循环扫描 + 触发 pipeline | 无 |
| **SimHash** | `simhash.py` | 64位指纹 + 字符3-gram 分词 + Hamming距离 | 无 |

### 2.6 数据模型 (PostgreSQL)

```sql
-- 核心表 (alembic versions: 005 + 007)
pipeline_runs (
    id UUID PK,
    run_type TEXT,           -- 'full' | 'incremental'
    status TEXT,             -- 'running' | 'completed' | 'failed' | 'cancelled'
    stages JSONB,            -- [{name, status, started_at, completed_at, duration_ms, ...}]
    total_records INT,
    new_records INT,
    updated_records INT,
    quality_score FLOAT,
    error_log TEXT,
    selected_stages TEXT[],  -- PostgreSQL array
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
)

pipeline_schedules (
    id UUID PK,
    name TEXT,
    cron_expression TEXT,
    run_type TEXT,
    selected_stages TEXT[],
    enabled BOOLEAN,
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ
)

data_source_records (
    id SERIAL PK,
    name TEXT,
    source_type TEXT,         -- 'crawler' | 'api' | 'manual'
    status TEXT,              -- 'active' | 'paused' | 'disabled'
    authority_score FLOAT,
    total_records INT,
    valid_records INT,
    duplicate_rate FLOAT,
    avg_quality_score FLOAT,
    last_crawl_at TIMESTAMPTZ,
    config JSONB
)

loop_results (
    id SERIAL PK,
    run_id TEXT UNIQUE,
    user_id TEXT,             -- SEC-04: 用户隔离
    status TEXT,
    steps_json JSONB,         -- 完整 LoopResult.to_dict()
    error_log TEXT,
    created_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
)
```

### 2.7 API 端点总览 (20个)

| 方法 | 端点 | 用途 |
|------|------|------|
| GET | `/pipeline/status` | 全局状态 + KPI + 运行中/上次/最近失败 run |
| GET | `/pipeline/runs` | 分页运行历史 (支持 status_filter) |
| GET | `/pipeline/runs/{run_id}` | 单次运行详情 |
| POST | `/pipeline/trigger` | 手动触发 (可选 run_type + selected_stages) |
| POST | `/pipeline/runs/{run_id}/cancel` | 软取消 + Redis STOP flag |
| POST | `/pipeline/runs/{run_id}/retry` | 单阶段重试 |
| POST | `/pipeline/runs/{run_id}/resume` | 断点续跑 (重置所有 failed→pending) |
| GET | `/pipeline/stages` | 各阶段实时状态 |
| GET | `/pipeline/data-quality` | 质量指标 + 趋势 + 告警 |
| GET | `/pipeline/datasources` | 数据源列表 |
| GET | `/pipeline/events` | SSE 实时事件流 |
| GET | `/pipeline/events-poll` | SSE 轮询降级端点 |
| GET/POST/PUT/DELETE | `/pipeline/schedules` | 定时调度 CRUD |
| POST | `/pipeline/schedules/{id}/trigger` | 手动触发调度 |
| GET/PUT | `/pipeline/config` | 运行时配置读写 |
| POST | `/pipeline/analyze` | 求职者分析 (SSE流) |
| POST | `/pipeline/export` | 分析结果导出 (JSON) |

### 2.8 Celery 任务

```python
# 7个异步任务 + Beat periodic
execute_pipeline_stage(run_id, stage_name)     # 核心: 执行单阶段 + 推进DAG
advance_pipeline_task(run_id)                  # 异步推进DAG
scheduled_pipeline_run(schedule_id)            # Cron触发
batch_extract_jd(jd_text)                      # 批量JD提取
build_graph_from_extractions(limit)            # Neo4j图谱构建
analyze_evolution_trends()                     # 演化趋势分析 (每6h)
sweep_orphan_runs()                            # 孤儿任务清理

# Celery Beat schedule
beat_schedule = {
    'analyze-evolution-trends': {
        'task': 'analyze_evolution_trends',
        'schedule': crontab(hour='*/6'),
    },
}
```

---

## 三、前端深度分析

### 3.1 页面架构

```
Router
├── /pipeline → PipelineMonitor.vue  (ETL DAG 全链路监控)
└── /analysis → PipelineAnalysis.vue (求职者分析向导)
```

**PipelineMonitor.vue** 是核心页面，布局为:

```
┌──────────────────────────────────────────────┐
│  BusinessBanner (业务说明横幅)                 │
├──────────────────────────────────────────────┤
│  页面头部: 标题 + SSE标签 + 自动刷新开关       │
│  + [触发] [断点续跑] [取消] [调度] [配置] [刷新]│
├──────────────────────────────────────────────┤
│  4个 KPI 卡片: 采集量 | 成功率 | 质量分 | 数据源│
├──────────────────────────────────────────────┤
│  PipelineDag:                                  │
│    [爬虫采集]                                   │
│      ↙      ↘                                  │
│  [去重] ∥ [清洗]  (并行)                       │
│      ↘      ↙                                  │
│    [数据入库]                                   │
│       ↓                                        │
│    [图谱构建]                                   │
├──────────────────┬───────────────────────────┤
│  PipelineSource  │  PipelineQualityPanel      │
│  Panel           │  仪表盘 + ECharts趋势图     │
│  (数据源列表)     │  + 4维度进度条              │
├──────────────────┴───────────────────────────┤
│  定时调度表格 (含 名称/Cron/类型/开关/操作)      │
└──────────────────────────────────────────────┘
```

### 3.2 组件体系

| 组件 | Props | 功能 |
|------|-------|------|
| `PipelineDag.vue` | `timelineStages`, `retryingStages`, `loading`, `isRunning` | 5阶段DAG时间线视图，含 fork/merge 箭头 |
| `PipelineStageCard.vue` | `stage`, `retrying` | 单阶段卡片: 状态圆点+脉冲动画/进度条/耗时/处理量/错误/重试按钮 |
| `PipelineSourcePanel.vue` | `dataSources`, `loading` | 数据源卡片列表 / 空状态 SVG |
| `PipelineQualityPanel.vue` | `dataQuality`, `qualityTrendOption`, `qualityTrendDir`, `loading` | 仪表盘 + ECharts折线图 (优秀线80/警戒线60) + 4维度进度条 |

### 3.3 Store 设计

采用 **职责分离 + Barrel Re-export** 模式:

```
pipeline.ts (Barrel)
├── pipelineRun.ts  → 运行时状态 (7个state + 10个API操作 + 4个SSE handler)
└── pipelineConfig.ts → 配置/调度 (2个state + 7个API操作)
```

**pipelineRun Store 核心状态**:

```typescript
pipelineStatus: PipelineStatus | null   // 全局状态 + KPI
runs: PipelineRun[]                     // 历史运行列表
stages: PipelineStage[]                 // 当前阶段状态
dataQuality: DataQualityMetrics | null  // 质量指标 + 趋势 + 告警
dataSources: DataSourceDetail[]         // 数据源列表
liveEvents: Array                       // SSE实时事件 (最近50条)
qualityAlerts: QualityAlert[]           // SSE质量告警 (最近50条)
milestones: DataMilestone[]             // SSE里程碑
recentExtractions: ExtractionComplete[] // SSE抽取完成
```

### 3.4 Composable 逻辑层 — `usePipelineMonitor()`

所有业务逻辑集中在 composable 中，使 Vue 组件保持为纯展示层:

```typescript
// 自动刷新: 默认10秒间隔，触发pipeline后降至5秒
autoRefresh + refreshInterval + timer

// SSE实时连接: 4种事件分发到store handlers
sseBase/pipeline/events → {
  pipeline_update    → handlePipelineEvent()
  quality_alert      → handleQualityAlert()
  data_milestone     → handleMilestone()
  extraction_complete → handleExtractionComplete()
}

// 业务操作:
- KPI卡片计算 (4个computed)
- 流水线触发 (全量/增量 + 阶段选择)
- 失败重试/断点续跑
- 定时调度 CRUD
- 配置管理 (5个参数: timeout/concurrency×2/retry_max/retry_backoff)
- 质量趋势图表 (ECharts option)
```

### 3.5 SSE 实时通信架构

```
后端 SSE Broadcaster
  (Redis pub/sub)
       │
       ▼
  /pipeline/events
  (EventSource API)
       │
       ▼
  useSSE() composable
  ├── 指数退避重连 (最多10次)
  ├── 自动轮询降级 (连续3次失败 → /pipeline/events-poll)
  ├── 60秒重连尝试
  └── Token 静默刷新
       │
       ▼
  storeHandlers {
    pipeline_update       → pipelineRun.handlePipelineEvent()
    quality_alert         → pipelineRun.handleQualityAlert()
    data_milestone        → pipelineRun.handleMilestone()
    extraction_complete   → pipelineRun.handleExtractionComplete()
  }
```

### 3.6 前后端数据流全链路

```
1. 触发流水线
   前端: handleTrigger() → POST /pipeline/trigger {run_type, selected_stages}
   后端: trigger_and_start() → create_run() → advance_pipeline()
         → Celery execute_pipeline_stage.delay() → SSE publish_event()
   前端: SSE ← pipeline_update → handlePipelineEvent() → fetchStages() + fetchStatus()
         KPI 卡片 + DAG 视图实时更新

2. 阶段执行
   后端: Celery worker → execute_crawl/dedup/... → update_stage_status()
         → advance_pipeline() → 下一个阶段
   前端: SSE ← pipeline_update → DAG 卡片状态切换 + 进度条动画

3. 质量监控
   后端: complete_run() → update_authority_scores() → 低质量自动暂停
         → generate_alerts() (z-score异常)
   前端: SSE ← quality_alert → 质量告警列表 + ECharts趋势刷新

4. 求职者分析
   前端: 上传简历 → POST /pipeline/analyze
   后端: PipelineEngine.run() → SSE StreamingResponse
   前端: SSE 接收5步进度 → 步骤条动画
```

---

## 四、前后端强弱信号分析

### 4.1 后端优势

| 方面 | 评价 |
|------|------|
| **DAG 设计** | 成熟，支持 fork/merge 并行 (dedup∥clean)，依赖管理清晰 |
| **错误隔离** | 闭环管道的每步 try/except + 可选阶段机制，单点失败不阻塞整体 |
| **取消机制** | 双重保障 (DB status + Redis STOP flag)，防止孤儿 Celery 任务 |
| **数据源治理** | 权威评分 (3维度加权) + 质量阈值自动暂停，闭环反馈 |
| **代码组织** | orchestrator/executor 职责分离，data_fusion/quality_monitor/source_authority 模块化良好 |
| **测试覆盖** | 7个单元测试文件 + pipeline 冒烟测试 |

### 4.2 后端可改进点

| 方面 | 现状 | 建议 |
|------|------|------|
| **爬虫单一** | 仅 BOSS 直聘 | 扩展多平台爬虫 (拉勾、猎聘等)，利用 DataSourceRecord 框架 |
| **去重实现** | 两遍去重但 exact pass 未完全分离 | 明确 Redis content-hash 和 SimHash 的结果分开计数 |
| **clean 阶段** | 仅 strip + 提取标题，处理过于简单 | 增加 HTML 标签清理、特殊字符处理、语言检测 |
| **import 阶段** | JD 逐个 LLM 调用，无批处理优化 | 可考虑 batch prompt 减少 API 调用次数 |
| **graph_sync** | limit 500 硬编码 | 应基于 run 的实际数据量动态决定 |
| **错误恢复** | retry 后状态同步依赖 advance_pipeline | 增加显式的 stage 状态验证步骤 |

### 4.3 前端优势

| 方面 | 评价 |
|------|------|
| **架构分层** | Page → Composable → Store → API，职责清晰 |
| **SSE 弹性** | 指数退避重连 + 自动轮询降级，连接可靠性高 |
| **实时可视化** | DAG 时间线 + KPI 卡片 + ECharts 质量趋势，全链路可观测 |
| **Store 设计** | pipelineRun/pipelineConfig 职责分离 + Barrel 向后兼容 |
| **组件复用** | BusinessBanner、StageCard 等组件可跨页面复用 |

### 4.4 前端可改进点

| 方面 | 现状 | 建议 |
|------|------|------|
| **类型安全** | Store 使用 `request.get/post` + 手动类型转换 | 可迁移到 OpenAPI 生成的类型化客户端 `api.getPipelineStatus()` |
| **错误处理** | catch 后仅 `ElMessage.error` | 增加错误分类 (网络/业务/权限) + 重试引导 |
| **加载状态** | 全局 `loading` 无法反映具体操作 | 考虑 per-action loading (如 retryStage 按钮级 loading 已有) |
| **运行历史** | 无专用历史查看页面 | 可将 runs 列表独立为一个可展开的详细视图 |
| **测试** | Store 测试覆盖好，但组件测试较少 | 增加 PipelineDag/StageCard 的 vitest 测试 |
| **移动端** | PipelineDag 有响应式媒体查询 | 小屏下可添加轮播或折叠模式 |

---

## 五、架构图

```
                    ┌──────────────────────────────────────┐
                    │           用户交互层                   │
                    │  PipelineMonitor ┊ PipelineAnalysis   │
                    └──────────────┬───────────────────────┘
                                   │ REST + SSE
                    ┌──────────────▼───────────────────────┐
                    │           API 路由层                   │
                    │  /pipeline/* (20端点) + /loop/*       │
                    │  SSE /pipeline/events                 │
                    └──────┬───────────────────┬───────────┘
                           │                   │
              ┌────────────▼─────┐    ┌────────▼──────────┐
              │   ETL DAG 编排    │    │  闭环/分析 编排     │
              │  orchestrator.py │    │  loop_orchestrator │
              │  executor.py     │    │  pipeline/engine   │
              └────────┬─────────┘    └────────┬──────────┘
                       │                       │
              ┌────────▼─────────┐    ┌────────▼──────────┐
              │   Celery Workers  │    │  同步服务调用       │
              │  execute_pipeline │    │  jd_extract        │
              │  _stage (6阶段)   │    │  graph_sync        │
              │  + Beat 定时      │    │  match_service     │
              └────────┬─────────┘    │  learning_service  │
                       │              └────────┬──────────┘
              ┌────────▼──────────────────────▼──────────┐
              │              共享服务层                    │
              │  PostgreSQL ┊ Neo4j ┊ Redis ┊ Chroma      │
              │  graph_sync ┊ dedup ┊ match ┊ learning   │
              │  timeseries ┊ recommendation             │
              └────────────────────┬─────────────────────┘
                                   │
              ┌────────────────────▼─────────────────────┐
              │              辅助模块                      │
              │  data_fusion ┊ quality_monitor            │
              │  source_authority ┊ status_aggregator     │
              │  cron_scheduler ┊ simhash                 │
              └──────────────────────────────────────────┘
```

---

## 六、关键数字总结

| 指标 | 数值 |
|------|------|
| 后端管道文件 | 14个核心文件 |
| 前端管道文件 | 12个 (2 pages + 4 components + 3 stores + 1 composable + 2 types) |
| API 端点 | 20个 (含 SSE) |
| Celery 任务 | 7个异步任务 + 1个 Beat schedule |
| PostgreSQL 表 | 4张 (pipeline_runs, pipeline_schedules, data_source_records, loop_results) |
| Neo4j 本体 | 7节点类型 + 8关系类型 |
| 前端 Store 状态 | pipelineRun: 9个state + 14个action | pipelineConfig: 2个state + 7个action |
| SSE 事件类型 | 4种 (pipeline_update, quality_alert, data_milestone, extraction_complete) |
| 单元测试 | 后端: 7个pipeline测试文件 | 前端: 2个store测试 (30+用例) + 6个e2e文件 |
| 质量监控维度 | 4维度 (完整性/准确性/新鲜度/重复率) |
| 数据源权威评分 | 3维度加权 (quality 50% + volume 25% + consistency 25%) |
