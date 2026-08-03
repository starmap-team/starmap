# Pipeline 核心规范

完整现状见 [流水线架构](../../architecture/pipeline.md)。

## 当前调度

当前 `STAGE_EXECUTORS` 对应 `crawl -> dedup_clean -> import_sync`。旧的细粒度 executor 函数可作为内部兼容实现，但不代表调度 DAG。

## 规则

- `PipelineRun.stages` 持久化每阶段状态和审计信息。
- 阶段只在依赖满足时分发；状态转换必须幂等。
- 取消同时写 DB 状态和 Redis stop flag。
- 重试只重置目标失败阶段；恢复流程明确重置范围。
- PG 写入先于图投影，图写失败记录 Outbox 并可重放。
- SSE 是实时通知，轮询是降级；两者使用相同事件语义。
- 数据源配置和暂停状态由数据库驱动。

## 验证

覆盖 DAG、取消、重试、恢复、卡死清理、outbox 和每个 executor 的错误路径；live stack 使用 `tests/e2e/pipeline_smoke_test.py`。
