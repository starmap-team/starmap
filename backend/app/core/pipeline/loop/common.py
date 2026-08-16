"""Loop orchestration shared types & persistence helpers (Phase 07-02 D-10).

Contains:
  - StepStatus / LoopRunStatus enums
  - STEP_NAMES map
  - LoopStepResult / LoopResult dataclasses (with to_dict)
  - PostgreSQL persistence helpers used by run_loop:
      _insert_loop_run / _update_steps_json / _complete_loop_run
  - In-memory fallback cache constants

Extracted from the original ``loop_orchestrator.py``; the legacy module
re-exports every name from here so existing callers keep working.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import PipelineStageError, StarMapError

if TYPE_CHECKING:
    from app.models.pipeline_models import LoopResultRecord


class StepStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class LoopRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


STEP_NAMES: dict[int, str] = {
    1: "JD输入",
    2: "技能提取",
    3: "图谱更新",
    4: "匹配诊断",
    5: "学习路径",
}


@dataclass
class LoopStepResult:
    """Result of a single loop step."""

    step: int
    name: str
    status: StepStatus
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_seconds: float = 0.0
    note: str | None = None


@dataclass
class LoopResult:
    """Complete result of a closed-loop run."""

    run_id: str
    jd_text: str
    target_position: str | None
    status: LoopRunStatus
    steps: list[LoopStepResult] = field(default_factory=list)
    extracted_skills: list[dict[str, Any]] = field(default_factory=list)
    graph_update: dict[str, Any] = field(default_factory=dict)
    match_result: dict[str, Any] = field(default_factory=dict)
    learning_path: dict[str, Any] = field(default_factory=dict)
    total_duration_seconds: float = 0.0
    # SEC-04 QA-FIX (F#11): 携带归属用户，供 in-memory 历史回退路径做 IDOR 过滤。
    user_id: str = "system"

    def to_dict(self) -> dict[str, Any]:
        # ponytail: defer the verification build until to_dict time so step-level
        # modules can stay decoupled from the status/checks helper.
        from app.core.pipeline.loop.status import _build_loop_verification

        return {
            "run_id": self.run_id,
            "jd_text": self.jd_text[:200] + ("..." if len(self.jd_text) > 200 else ""),
            "target_position": self.target_position,
            "status": self.status.value,
            "steps": [
                {
                    "step": s.step,
                    "name": s.name,
                    "status": s.status.value,
                    "data": s.data,
                    "error": s.error,
                    "duration_seconds": round(s.duration_seconds, 2),
                    "note": s.note,
                }
                for s in self.steps
            ],
            "extracted_skills": self.extracted_skills,
            "graph_update": self.graph_update,
            "match_result": self.match_result,
            "learning_path": self.learning_path,
            "total_duration_seconds": round(self.total_duration_seconds, 2),
            # Phase 3: 逐步核验摘要
            "verification": _build_loop_verification(self.steps),
        }


# Fallback in-memory history storage (used only when no DB session is provided)
_LOOP_RESULTS: dict[str, LoopResult] = {}
_LOOP_HISTORY_MAX = 200


# ---------------------------------------------------------------------------
# PostgreSQL persistence helpers
# ---------------------------------------------------------------------------

async def _insert_loop_run(
    run_id: str,
    session: AsyncSession | None = None,
    user_id: str = "system",  # SEC-04
) -> LoopResultRecord | None:
    """INSERT a new running loop_results row; return the ORM object or None."""
    if session is None:
        return None
    try:
        from app.models.pipeline_models import LoopResultRecord

        record = LoopResultRecord(
            run_id=run_id,
            user_id=user_id,  # SEC-04
            steps_json={},
            status=LoopRunStatus.RUNNING.value,
        )
        session.add(record)
        await session.commit()
        return record
    except PipelineStageError:
        raise
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("Failed to insert loop run to DB: {}", exc)
        return None


async def _update_steps_json(
    db_record: LoopResultRecord | None,
    result: LoopResult,
    session: AsyncSession | None = None,
) -> None:
    """UPDATE steps_json after each step completes."""
    if db_record is None or session is None:
        return
    try:
        from app.models.pipeline_models import LoopResultRecord

        # Re-fetch to avoid detached-instance issues
        db_record = await session.get(LoopResultRecord, db_record.id)
        if db_record is None:
            return
        db_record.steps_json = result.to_dict()
        await session.commit()
    except PipelineStageError:
        raise
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("Failed to update loop steps_json in DB: {}", exc)


async def _complete_loop_run(
    db_record: LoopResultRecord | None,
    result: LoopResult,
    session: AsyncSession | None = None,
) -> None:
    """UPDATE status and completed_at when the loop finishes; fall back to in-memory."""
    if db_record is not None and session is not None:
        try:
            from app.models.pipeline_models import LoopResultRecord

            db_record = await session.get(LoopResultRecord, db_record.id)
            if db_record is not None:
                db_record.status = result.status.value
                db_record.steps_json = result.to_dict()
                db_record.completed_at = datetime.now(UTC)
                if result.status == LoopRunStatus.FAILED:
                    errors = [s.error for s in result.steps if s.error]
                    db_record.error_log = "; ".join(errors) if errors else None
                await session.commit()
                return
        except PipelineStageError:
            raise
        except StarMapError:
            raise
        except Exception as exc:
            logger.exception(
                "Failed to complete loop run in DB, falling back to in-memory: {}",
                exc,
            )

    # Fallback: in-memory history storage
    _LOOP_RESULTS[result.run_id] = result
    if len(_LOOP_RESULTS) > _LOOP_HISTORY_MAX:
        excess = len(_LOOP_RESULTS) - _LOOP_HISTORY_MAX
        for old_key in list(_LOOP_RESULTS.keys())[:excess]:
            del _LOOP_RESULTS[old_key]


# Re-export the time helper for step modules that build LoopStepResult timing.
# (Avoids forcing them to also import ``time``.)
def _now_monotonic() -> float:
    return time.monotonic()


__all__ = [
    "StepStatus",
    "LoopRunStatus",
    "STEP_NAMES",
    "LoopStepResult",
    "LoopResult",
    "_LOOP_RESULTS",
    "_LOOP_HISTORY_MAX",
    "_insert_loop_run",
    "_update_steps_json",
    "_complete_loop_run",
]
