# Phase 17 CONTEXT — Pipeline 数据完整性与 UX 修复

## 用户决策 (从 explore 会话)

用户报告的 4 个深层问题:
1. **timeseries 阶段是否必要?** — 设计文档明确说它不属于核心 ETL DAG
2. **graph_sync 一直失败** — import stage 产出 `position_name=None` 的坏数据
3. **重试按钮"没有可重试的运行"** — `currentRunId` 只查 `current_run` (running 状态)
4. **数据完整性担忧** — status 字段作 stage gate + outbox 模式,数据不会错乱

## Phase 17 范围

**包含 (4 个 BUG 修复):**
- B1: timeseries 不应作为必选 stage 显示
- B2: 重试按钮支持失败/完成的 run
- B3: import stage 防御性校验 position_name
- B4: graph_sync 错误处理 (B3 衍生)

**不包含:**
- Pipeline 重构 (留作 Phase 18+)
- 数据完整性重构 (已有 status gate + outbox 足够)
- 阶段间协调机制重设计 (不在范围)

## 锁定决策

1. **timeseries 移除策略:** 从 `ALL_STAGE_NAMES` 移除,加 `OPTIONAL_STAGES` 单独列表
2. **重试按钮:** 改用 `last_run.id` 而非 `current_run.id`,加 `GET /pipeline/runs?status=failed` 端点
3. **import 校验:** 在 `execute_import` 末尾加 `position_name` 非空检查,坏数据标 `_invalid` 而不删除 (留 trace)
4. **graph_sync 错误:** 已有用户友好错误消息,继续完善 (允许部分成功)

## 风险

| 风险 | 缓解 |
|------|------|
| 修改 ALL_STAGE_NAMES 影响 DAG 渲染 | 同步更新 PipelineDag.vue (Phase 16-02 已加 timeseries row) |
| import 校验导致坏数据被标 `_invalid` 阻塞下游 | 加 audit log 记录,让运维可见 |
| 重试按钮兼容老 API 响应 | 渐进式: 先用 `last_run` fallback,后端加新端点 |