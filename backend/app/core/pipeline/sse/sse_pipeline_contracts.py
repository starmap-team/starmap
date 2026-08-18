"""SSE 流水线事件契约（D-09 Phase 03 Task 10）。

文档化 SSE 事件 schema（事件名/字段/幂等语义），不重构协议。
前端 useSSE 显式订阅子步骤事件。

事件分类：
- 阶段级：stage.started / stage.progress / stage.sub_step / stage.completed / stage.failed
- 流水线级：pipeline.completed / pipeline.failed
- 系统级：heartbeat（保留位）
"""
from __future__ import annotations

from typing import Any, TypedDict


class StageStartedEvent(TypedDict, total=False):
    """阶段开始事件。"""

    run_id: str
    stage: str  # crawl / dedup / clean / import / graph_sync / timeseries
    status: str  # "started" / "running"
    event_id: str  # 全局唯一；客户端按 last_event_id 去重
    ts: str  # ISO 8601


class StageProgressEvent(TypedDict, total=False):
    """阶段进度事件（每阶段 1 条 / 60s 或每 10 条记录）。"""

    run_id: str
    stage: str
    status: str  # "running"
    progress: float  # [0.0, 1.0]
    records_processed: int
    current_activity: str
    recent_samples: list[dict[str, Any]]
    sub_breakdown: dict[str, int]
    elapsed_ms: int
    event_id: str
    ts: str


class StageSubStepEvent(TypedDict, total=False):
    """阶段内子步骤事件（D-15 引入，区分逻辑子阶段）。

    sub_step 取值约定：
    - import: "extract" / "normalize" / "persist"
    - crawl: "crawl:<source_name>"（每数据源一条）
    - graph_sync: "reconcile"（D-07 对账子步骤，仅 reconcile_on_sync=True 时）
    """

    run_id: str
    stage: str
    status: str  # "running"
    progress: float
    current_activity: str
    sub_step: str  # 见上约定
    elapsed_ms: int
    event_id: str
    ts: str


class StageCompletedEvent(TypedDict, total=False):
    """阶段完成事件。"""

    run_id: str
    stage: str
    status: str  # "completed"
    progress: float  # 1.0
    records_processed: int
    current_activity: str
    sub_breakdown: dict[str, int]
    elapsed_ms: int
    event_id: str
    ts: str


class StageFailedEvent(TypedDict, total=False):
    """阶段失败事件。"""

    run_id: str
    stage: str
    status: str  # "failed"
    current_activity: str
    error: str  # 错误详情
    event_id: str
    ts: str


class PipelineCompletedEvent(TypedDict, total=False):
    """流水线完成事件。"""

    run_id: str
    status: str  # "completed"
    total_records: int
    duration_ms: int
    event_id: str
    ts: str


# 幂等语义：
# - 所有 event_id 全局唯一（UUID 或 ULID）
# - 客户端按 last_event_id 去重
# - EventSource 原生支持 Last-Event-ID header 自续传
# - 轮询 fallback 用 since=<unix_ts> 参数（）

# 重连协议：
# - 断开：客户端重试用指数退避（baseDelay=1000ms, maxDelay=30000ms）
# - 连续 3 次失败切换轮询 fallback（/pipeline/events-poll?since=<ts>）
# - 轮询期间每 60s 重试 SSE 连接

# 轮询 fallback 协议：
# - GET /pipeline/events-poll?since=<unix_ts>
# - 返回 JSON 数组，每项 {type, data, event_id, ts}
# - 客户端维护 lastEventId；下次轮询 since=lastEventId 时间戳


# 订阅示例（前端 useSSE storeHandlers）：
# storeHandlers = {
# "stage.sub_step": (data) => { /* 子步骤 */ },
# "stage.progress": (data) => { /* 进度 */ },
# "stage.completed": (data) => { /* 阶段完成 */ },
# "stage.failed": (data) => { /* 阶段失败 */ },
# "pipeline.completed": (data) => { /* 流水线完成 */ },
# }


__all__ = [
    "StageStartedEvent",
    "StageProgressEvent",
    "StageSubStepEvent",
    "StageCompletedEvent",
    "StageFailedEvent",
    "PipelineCompletedEvent",
]
