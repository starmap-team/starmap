# Phase 17 RESEARCH — Pipeline 修复技术调研

## 1. timeseries stage 移除

### 现状
- [docs/architecture/pipeline.md:30](docs/architecture/pipeline.md) 明确: "timeseries 为可选扩展阶段，不属于核心 ETL DAG"
- 代码:
  - `ALL_STAGE_NAMES = ['crawl', 'dedup', 'clean', 'import', 'graph_sync', 'timeseries']` (6 个)
  - `STAGE_EXECUTORS['timeseries'] = execute_timeseries` (实际存在)
  - `OPTIONAL_STAGES = frozenset({GRAPH_SYNC, TIMESERIES})`
- Phase 16-02 我刚加 PipelineDag.vue Row 6 渲染 timeseries
- API `/pipeline/stages` 返回 timeseries stage

### 修复方案
**方案 A: 移除 ALL_STAGE_NAMES (推荐)**
- `ALL_STAGE_NAMES` 改为 5 个核心 stage
- `OPTIONAL_STAGES` 保留含 timeseries (向后兼容)
- PipelineDag.vue 改为只渲染核心 5 stage
- API `/pipeline/stages` 仍可返回 timeseries (不被消费)

**方案 B: 明确标注 (备选)**
- ALL_STAGE_NAMES 保持 6 个
- PipelineDag.vue 加 badge "Evolution service"

采用方案 A — 符合设计文档 "不属于核心 ETL DAG"

### 文件影响
- `frontend/src/stores/pipelineConfig.ts` — `ALL_STAGE_NAMES` 改 5 个
- `frontend/src/components/PipelineDag.vue` — 去掉 Row 6 (timeseries)
- `frontend/src/pages/PipelineMonitor.vue` — 触发对话框 checkbox 改 5 个

## 2. 重试按钮修复 (B2)

### 现状
- [frontend/src/composables/usePipelineMonitor.ts:437](frontend/src/composables/usePipelineMonitor.ts#L437)
```ts
const currentRunId = computed(() => pipeline.pipelineStatus?.current_run?.id)
```
- `current_run` 只在 `status='running'` 时存在
- 失败/完成的 run **没有** `current_run`,所以 retry 按钮显示"没有可重试的运行"

### 修复方案
**优先 1: 改用 `last_run.id` (后端已有此字段)**
```ts
const currentRunId = computed(() => {
  return pipeline.pipelineStatus?.last_run?.id
    || pipeline.pipelineStatus?.current_run?.id
})
```

**优先 2: 后端加 `GET /pipeline/runs?status=failed` (可选,后续 Phase)**
- 找最近 failed run
- 准确知道哪个 stage failed

采用优先 1 — 1 行改动,后端无需变

## 3. import stage position_name 校验 (B3)

### 现状
- `execute_import` 写 `jd_extraction_records` 时直接接受 LLM 输出
- LLM 有时漏 `position_name` (返回 None)
- `graph_writer.py:221` 遇到 None → 抛 ValueError → 整个 batch 失败

### 修复方案
**方案 A: import 端校验 (推荐)**
```python
# backend/app/core/pipeline/executor.py execute_import
if not extraction.get("position_name"):
    extraction["position_name"] = "(未命名职位)"  # 兜底
    invalid_count += 1
    logger.warning(f"extraction {eid} missing position_name, using fallback")
```

**方案 B: 重试 LLM (过度设计)**
- 检测到 None → 重新调用 LLM 抽取
- 成本高,不推荐

**方案 C: 在 graph_sync 端跳过 None records**
- 已经做了 (单个失败抛错)
- 改: 跳过 None,只 merge 有 name 的

采用方案 A — 兜底而非删除,保留 trace

### 4. graph_sync 部分成功

### 现状
- 当前 `graph_writer.merge_position` 遇到 None 抛错 → 整个 batch 中断
- 一条坏数据导致所有好数据都不入库

### 修复方案
**方案: try/except 单条隔离**
```python
for extraction in extractions:
    try:
        merge_position(...)
        merged += 1
    except ValueError as e:
        if "position_name" in str(e):
            skipped += 1
            continue  # 跳过坏数据
        raise  # 其他错误仍抛
```

## 风险评估

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| PipelineDag.vue 改动后其他测试失败 | LOW | LOW | e2e 测试覆盖 |
| import 兜底产生"未命名职位"节点 | MED | MED | 加 UI 标识"系统生成" |
| 重试按钮兼容老 API | LOW | LOW | 渐进式 |