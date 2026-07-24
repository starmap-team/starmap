# Evolution 核心规范

## 范围

`core/evolution/` 维护快照、差异、信任评分、新兴技能、时间序列、路径推荐和完整编排。

## 规则

- Snapshot 对岗位/时间窗口幂等。
- Diff 使用明确变更类型，调用方必须穷尽处理。
- Trust score 来自 `trust_scorer.py`，禁止默认占位分数。
- Emergence 基于时序证据，不用 LLM 猜测市场趋势。
- Path 推荐是有界候选，不作为完整事实图。
- 单岗位失败进入 summary，不丢弃其他成功结果。
- PostgreSQL 保存演化事实；Neo4j 关系是派生投影。

## 入口

服务层位于 `services/evolution_service.py`、`timeseries_service.py`；周期任务使用 `run_evolution_pipeline`。

## 验证

```bash
cd backend && poetry run pytest tests/unit -k evolution
```
