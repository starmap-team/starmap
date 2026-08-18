"""Pipeline PG↔Neo4j 一致性告警服务（D-06）。

阶段末调用 `check_pg_neo4j_consistency(run_id)`，比对 PG skill 数 vs Neo4j 节点数。
差异超阈值记录告警日志 + 阶段末 metrics（D-06：告警不阻断，不改数据）。
"""
from __future__ import annotations

import uuid
from typing import Any

from loguru import logger

from app.db.session import get_session_factory
from app.exceptions import StarMapError
from app.services.resources import resources as app_resources


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
    """取 PG skill 数 + Neo4j Skill 节点数。

    P1-13 fix (functional-review 2026-08-13): 此前恒返回 (0, 0) 占位 → D-06
    一致性告警永远是 no-op，graph_sync/import 阶段末的调用从不产生告警。
    现实现真实双库计数：PG 读 skill_records，Neo4j 读 :Skill 节点。任一侧
    不可用时降级为 0（不抛错，保证调用方安全）。
    """
    pg_count = 0
    try:
        import sqlalchemy as sa

        from app.models.extraction_models import SkillRecord

        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(sa.select(sa.func.count()).select_from(SkillRecord))
            pg_count = int(result.scalar() or 0)
    except StarMapError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("pipeline_consistency PG count failed (non-fatal): {}", exc)

    neo4j_count = 0
    driver = app_resources.neo4j_driver
    if driver is not None:
        try:
            async with driver.session() as session:
                result = await session.run("MATCH (n:Skill) RETURN count(n) AS total")
                record = await result.single()
                if record is not None:
                    neo4j_count = int(record["total"] or 0)
        except StarMapError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("pipeline_consistency Neo4j count failed (non-fatal): {}", exc)

    return pg_count, neo4j_count
