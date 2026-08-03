# 数据流水线

> 状态：活文档
> 最近核对：2026-07-24

StarMap 当前的 ETL 调度由 `backend/app/core/pipeline/orchestrator.py` 维护状态，`executor.py` 执行阶段，`backend/app/tasks/celery_app.py` 通过 Celery 分发任务。

## 当前阶段

```mermaid
flowchart LR
    C[crawl] --> D[dedup_clean]
    D --> I[import_sync]
    I --> PG[(PostgreSQL)]
    I --> O[GraphWriteOutbox]
    O --> N[(Neo4j projection)]
```

| 阶段 | 作用 |
|---|---|
| `crawl` | 按启用的数据源配置采集并写入原始 JD 记录 |
| `dedup_clean` | 精确/近似去重、文本清理、规范化和有效性检查 |
| `import_sync` | LLM 抽取并持久化 PG，再同步图投影 |

`executor.py` 仍包含部分旧的细粒度执行函数，供兼容和组合调用；调度事实以 `STAGE_EXECUTORS` 与 `StageName` 为准，不以历史报告中的五阶段或六阶段图为准。

## 运行与恢复

- `PipelineRun.stages` 持久化阶段状态、时间、进度、处理量和错误。
- 管理员可触发、取消、重试、恢复和处理卡死 run。
- Redis STOP flag 与数据库状态共同阻止取消后的阶段继续分发。
- SSE `/pipeline/events` 提供实时更新，轮询端点作为降级路径。
- 单阶段失败按依赖关系标记后续阶段；所有阶段终态后才结束 run。

## 其他流水线

- 闭环流程：`loop_orchestrator.py` 执行 JD -> 抽取 -> 图更新 -> 匹配 -> 学习路径。
- 求职者分析：`/pipeline/analyze` 以 SSE 返回简历解析、技能抽取、匹配和推荐过程。
- 演化流程：`run_evolution_pipeline` 是独立 Celery 周期任务，不属于当前三阶段 ETL DAG。
- 技能时间序列由演化服务刷新，不应被文档误写为当前 ETL 的必选阶段。

## 验证

```bash
# 需要已启动后端和管理员 token
python tests/e2e/pipeline_smoke_test.py
python tests/e2e/smoke_test.py --base-url http://localhost:8000 --all
```

单元测试应覆盖 DAG 就绪判断、失败传播、取消、重试、恢复、幂等和 outbox 状态转换。