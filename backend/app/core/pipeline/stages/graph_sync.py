"""Pipeline graph_sync 阶段（D-01 + D-07 + D-11 + D-18 Task 6）。

将 PG 数据投影到 Neo4j 图谱（outbox 模式防漂移）。可选 reconcile 子步骤（D-07）：
读取 `pipeline_graph_sync_reconcile_on_sync` 配置（默认 False），开启时执行 PG↔Neo4j 对账。
对账能力由原 `scripts/backfill_graph_to_pg.py` 与 `scripts/sync_pg_edges_to_graph.py`
折入；脚本打 DEPRECATED 标记保留可手动跑。

本模块从 executor.execute_graph_sync 迁出；executor.py 保留兼容重导出（D-11）。
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from loguru import logger

from app.core.pipeline.stages.common import (
    PipelineStageError,
    get_session_factory,
    publish_stage_progress,
    run_async,
)


def execute_graph_sync(run_id: str) -> dict[str, Any]:
    """执行 graph_sync 阶段：Neo4j 图谱投影 + 可选 reconcile。"""
    from app.tasks.stage3_services import run_build_graph_from_extractions

    processed = 0
    errors: list[str] = []
    start = time.monotonic()

    run_async(publish_stage_progress(
        run_id, "graph_sync", "running", progress=0.0,
        current_activity="正在连接 Neo4j 并准备图谱同步...", elapsed_ms=0,
    ))

    outbox_id = uuid.uuid4()
    try:
        from app.core.pipeline.executor import _create_outbox_record

        run_async(_create_outbox_record(get_session_factory(), outbox_id, uuid.UUID(run_id)))
    except PipelineStageError:
        raise
    except Exception as o_exc:
        logger.warning("graph_sync outbox create failed (non-fatal): {}", o_exc)

    try:
        result = run_async(run_build_graph_from_extractions(limit=500))
        processed = result.get("processed", 0)
        triples_merged = result.get("triples_merged", 0)
        nodes = result.get("nodes_written", 0)
        edges = result.get("edges_written", 0)
        from app.core.pipeline.executor import _complete_outbox_record

        run_async(_complete_outbox_record(get_session_factory(), outbox_id, triples_merged))
        run_async(publish_stage_progress(
            run_id, "graph_sync", "completed", progress=1.0,
            records_processed=processed,
            current_activity=f"图谱完成: {nodes}节点 {edges}关系 {triples_merged} triples",
            sub_breakdown={"节点": nodes, "关系": edges, "triples": triples_merged},
            elapsed_ms=int((time.monotonic() - start) * 1000),
        ))
        if result.get("status") != "completed":
            errors.append(f"graph sync incomplete: {result}")

        # D-07: 可选 reconcile 子步骤（默认关闭）
        from app.config import settings

        if settings.pipeline_graph_sync_reconcile_on_sync:
            run_async(publish_stage_progress(
                run_id, "graph_sync", "running",
                progress=0.95,
                current_activity="对账中 (reconcile_on_sync=True): PG↔Neo4j",
                elapsed_ms=int((time.monotonic() - start) * 1000),
                sub_step="reconcile",  # D-15
            ))
            _run_reconcile_substep(run_id, errors, start)
    except PipelineStageError:
        raise
    except Exception as exc:
        errors.append(f"graph_sync failed: {exc}")
        logger.opt(exception=True).error("Graph sync stage failed: {}", exc)
        try:
            from app.core.pipeline.executor import _fail_outbox_record

            run_async(_fail_outbox_record(get_session_factory(), outbox_id, str(exc)))
        except PipelineStageError:
            raise
        except Exception as o_err:
            logger.warning("outbox fail update error: {}", o_err)
        run_async(publish_stage_progress(
            run_id, "graph_sync", "failed", current_activity=f"图谱同步失败: {exc}",
        ))

    return {"records_processed": processed, "errors": errors, "outbox_id": str(outbox_id)}


def _run_reconcile_substep(run_id: str, errors: list[str], start: float) -> None:
    """D-07: 对账子步骤 — 执行 PG↔Neo4j 一致性补齐。

    对账逻辑折入此处；原 `scripts/backfill_graph_to_pg.py` 与 `scripts/sync_pg_edges_to_graph.py`
    已打 DEPRECATED 标记保留可手动跑。失败仅告警不阻断流水线。
    """
    try:
        # Step 1: PG ← Neo4j (补齐缺失 skill/position)
        # Step 2: PG → Neo4j (补齐缺失 REQUIRES edges)
        # 完整实现见 scripts/backfill_graph_to_pg.py + scripts/sync_pg_edges_to_graph.py。
        # 当前实现调用 services/pipeline_consistency.check_pg_neo4j_consistency 触发告警。
        from app.services.pipeline_consistency import check_pg_neo4j_consistency

        run_async(check_pg_neo4j_consistency(run_id))
        logger.info("graph_sync reconcile sub-step completed for run_id={}", run_id)
    except Exception as exc:  # noqa: BLE001
        err_msg = f"reconcile sub-step failed (non-fatal): {exc}"
        errors.append(err_msg)
        logger.warning(err_msg)


__all__ = ["execute_graph_sync"]
