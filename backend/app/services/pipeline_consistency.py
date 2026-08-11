"""Pipeline PG↔Neo4j 一致性告警服务（D-06）。

阶段末调用 `check_pg_neo4j_consistency(run_id)`，比对 PG skill 数 vs Neo4j 节点数。
差异超阈值记录告警日志 + 阶段末 metrics（D-06：告警不阻断，不改数据）。

完整实现见后续增强任务（独立一致性断言层 deferred）；当前仅日志告警接口。
"""
from __future__ import annotations

import uuid
from typing import Any

from loguru import logger


async def check_pg_neo4j_consistency(run_id: str | uuid.UUID) -> dict[str, Any]:
    """PG↔Neo4j 一致性检查（仅日志告警；不改数据）。

    Returns:
        dict with keys: pg_count, neo4j_count, diff, severity, alerted
    """
    try:
        pg_count, neo4j_count = await _fetch_counts()
    except Exception as exc:  # noqa: BLE001
        logger.warning("pipeline_consistency check failed (non-fatal) for run_id={}: {}", run_id, exc)
        return {"pg_count": None, "neo4j_count": None, "diff": None, "severity": "unknown", "alerted": False}

    diff = abs(pg_count - neo4j_count)
    # 阈值：差异 > 1% 或绝对值 > 100 视为异常
    threshold = max(int(pg_count * 0.01), 100) if pg_count > 0 else 0
    severity = "warning" if diff > threshold else "ok"
    alerted = severity == "warning"

    if alerted:
        logger.warning(
            "PG↔Neo4j consistency alert for run_id={}: pg={} neo4j={} diff={} severity={}",
            run_id, pg_count, neo4j_count, diff, severity,
        )

    return {
        "pg_count": pg_count,
        "neo4j_count": neo4j_count,
        "diff": diff,
        "severity": severity,
        "alerted": alerted,
    }


async def _fetch_counts() -> tuple[int, int]:
    """取 PG skill 数 + Neo4j 节点数。当前实现仅占位（依赖外部驱动初始化）。"""
    # 占位：实际查询逻辑在后续增强中加入。当前返回 (0, 0) 保证不抛错
    return 0, 0
