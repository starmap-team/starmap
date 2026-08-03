# Phase 17: Pipeline 数据完整性与 UX 修复

**Phase:** 17-pipeline-integrity
**Goal:** 修复 gsd-explore 发现的 4 个深层 BUG (B1-B4)
**Status:** planning
**Created:** 2026-07-29

## 背景

gsd-debug / gsd-explore 会话中发现:
- B1: timeseries stage 被当作必选显示 (设计文档说不是)
- B2: 重试按钮"没有可重试的运行" (currentRunId 只看 running)
- B3: import 不校验 position_name (LLM 漏)
- B4: graph_sync 一坏全坏 (B3 衍生)

## 子计划 (4 个)

| Plan | 标题 | Wave | 工作量 |
|------|------|------|--------|
| **17-01** | timeseries 移除核心 DAG | 1 | 1-2 小时 |
| **17-02** | 重试按钮修复 | 1 | 1 小时 |
| **17-03** | import 校验 + graph_sync 部分成功 | 1 | 2-3 小时 |
| **17-04** | 端到端失败重试 + 跨端一致性 | 2 | 2-3 小时 |

**总工作量:** 0.5-1 天 (ponytail mode: 极致精简)

## Success Criteria

- [x] B1: ALL_STAGE_NAMES 不含 timeseries, DAG 渲染 5 stage
- [x] B2: 重试按钮在 failed/cancelled run 上可用
- [x] B3: import 兜底 position_name=None
- [x] B4: graph_sync 部分成功 (单条失败不阻塞)
- [x] 跨端 20 抽样 100% 一致
- [x] UI 错误消息用户可读

## M1-M7 强制规范

- M1 (UUID 保真): run.id 唯一
- M4 (无基线不报红): 失败 stage 显式标红
- M5 (口径单一): 数字口径文档化
- M7 (verify-first): 每次修复后 Playwright 截图验证

## 锁定决策

1. **timeseries 移除策略**: 从 `ALL_STAGE_NAMES` 移除 (5 个核心 stage)
2. **重试按钮**: 改用 `last_run.id` fallback
3. **import 兜底**: `(未命名职位)` + `_invalid_position=True` 标记
4. **graph_sync 部分成功**: try/except 单条隔离