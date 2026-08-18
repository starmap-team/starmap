"""Step 3 — Neo4j graph sync (Phase 07-02 D-01/D-05).

Extracted from ``loop_orchestrator.py._step3_graph_update``.

Behaviour unchanged. On success the returned ``LoopStepResult.data`` keeps
the raw ``sync_result`` payload (which carries ``nodes_written`` /
``edges_written`` from ``graph_sync.sync_from_pipeline``) — these are the
D-05 / Phase 07-02 metric row fields the frontend ``LoopStepGraph`` card
consumes. Missing keys degrade to ``None`` rather than being renamed, so
the upstream contract stays the single source of truth.
"""
from __future__ import annotations

import time
from typing import Any

from loguru import logger

from app.core.pipeline.loop.common import (
    STEP_NAMES,
    LoopStepResult,
    StepStatus,
)
from app.exceptions import PipelineStageError, StarMapError


async def run_graph_update_step(
    run_id: str,
    extraction_data: dict[str, Any],
    target_position: str = "",
) -> LoopStepResult:
    """Step 3: Sync extracted skills/positions into Neo4j graph.

    Args:
        run_id: Closed-loop run identifier (used for outbox correlation).
        extraction_data: Step 2 output (skills, position_name, …).
        target_position: Resolved target position name from Step 1.

    Returns:
        LoopStepResult — SUCCESS carries the raw ``sync_result`` (with
        ``nodes_written`` / ``edges_written`` counts). FAILED carries the
        underlying error string and a status flag.
    """
    start = time.monotonic()
    try:
        from app.services.graph_sync import sync_from_pipeline

        driver = None
        try:
            from app.services.resources import resources as app_resources
            driver = app_resources.neo4j_driver
        except PipelineStageError:
            raise
        except StarMapError:
            raise
        except Exception as exc:
            logger.debug("Neo4j driver not available inside step 3: {}", exc)

        if driver is None:
            return LoopStepResult(
                step=3,
                name=STEP_NAMES[3],
                status=StepStatus.FAILED,
                data={"error": "neo4j_driver_unavailable"},
                error="Neo4j driver not available",
                duration_seconds=time.monotonic() - start,
            )

        # Phase 2 SYNC-02: Pass extraction_data for DB-query + graph_writer mode
        try:
            sync_result = await sync_from_pipeline(
                run_id=run_id,
                extraction_data=extraction_data,
                target_position=target_position,
            )
        except PipelineStageError:
            raise
        except StarMapError:
            raise
        except Exception as exc:
            logger.warning("sync_from_pipeline failed: {}", exc)
            sync_result = {"synced": False, "error": str(exc)}

        logger.info(
            "Graph sync step for run {}: synced={}, nodes={}, edges={}",
            run_id,
            sync_result.get("synced", False),
            sync_result.get("nodes_written", sync_result.get("nodes", 0)),
            sync_result.get("edges_written", sync_result.get("edges", 0)),
        )

        if not sync_result.get("synced"):
            return LoopStepResult(
                step=3,
                name=STEP_NAMES[3],
                status=StepStatus.FAILED,
                data=sync_result,
                error=sync_result.get("error") or "Graph sync failed",
                duration_seconds=time.monotonic() - start,
            )

        return LoopStepResult(
            step=3,
            name=STEP_NAMES[3],
            status=StepStatus.SUCCESS,
            data=sync_result,
            duration_seconds=time.monotonic() - start,
        )
    except PipelineStageError:
        raise
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("Loop orchestrator error: {}", exc)
        return LoopStepResult(
            step=3,
            name=STEP_NAMES[3],
            status=StepStatus.FAILED,
            data={"error": str(exc)},
            error=str(exc),
            duration_seconds=time.monotonic() - start,
        )


__all__ = ["run_graph_update_step"]
