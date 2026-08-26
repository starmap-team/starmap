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


async def _persist_loop_row(
    *,
    record_id: int,
    result: LoopResult,
    session: AsyncSession | None,
    status: str | None,
) -> None:
    """落库 loop_results 行(steps_json + 可选 status/completed_at/error_log)。

    session 为 None 时用独立 session_factory(隔离调用方 session 的连接池污染)。
    """
    from app.models.pipeline_models import LoopResultRecord

    if session is not None:
        row = await session.get(LoopResultRecord, record_id)
        if row is not None:
            row.steps_json = result.to_dict()
            if status is not None:
                row.status = status
                row.completed_at = datetime.now(UTC)
                if status == LoopRunStatus.FAILED.value:
                    errors = [s.error for s in result.steps if s.error]
                    row.error_log = "; ".join(errors) if errors else None
            await session.commit()
            return
        raise LookupError(f"loop_results row {record_id} not found")

    # 独立 session 落库: 用全新 engine(不共享污染连接池), 用完 dispose。
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.config import settings

    own_engine = create_async_engine(settings.postgres_uri, pool_pre_ping=True, pool_size=1, max_overflow=0)
    try:
        from sqlalchemy.ext.asyncio import async_sessionmaker as _asm

        own_factory = _asm(own_engine, expire_on_commit=False)
        async with own_factory() as own:
            row = await own.get(LoopResultRecord, record_id)
            if row is None:
                raise LookupError(f"loop_results row {record_id} not found")
            row.steps_json = result.to_dict()
            if status is not None:
                row.status = status
                row.completed_at = datetime.now(UTC)
                if status == LoopRunStatus.FAILED.value:
                    errors = [s.error for s in result.steps if s.error]
                    row.error_log = "; ".join(errors) if errors else None
            await own.commit()
    finally:
        await own_engine.dispose()


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
    if db_record is None:
        return
    try:
        from app.models.pipeline_models import LoopResultRecord

        await _persist_loop_row(record_id=db_record.id, result=result, session=session, status=None)
    except PipelineStageError:
        raise
    except StarMapError:
        raise
    except Exception as exc:
        # 调用方 session 事务 aborted 时改走独立 session 重试, 保证步骤进度可落库。
        try:
            await _persist_loop_row(record_id=db_record.id, result=result, session=None, status=None)
        except BaseException:  # noqa: BLE001
            logger.exception("Failed to update loop steps_json in DB (retry): {}", exc)


async def _complete_loop_run(
    db_record: LoopResultRecord | None,
    result: LoopResult,
    session: AsyncSession | None = None,
) -> None:
    """UPDATE status and completed_at when the loop finishes; fall back to in-memory."""
    if db_record is not None:
        try:
            from app.models.pipeline_models import LoopResultRecord

            status_val = result.status.value
            await _persist_loop_row(
                record_id=db_record.id, result=result, session=session, status=status_val,
            )
            return
        except PipelineStageError:
            raise
        except StarMapError:
            raise
        except Exception as exc:
            # 调用方 session 事务 aborted 时改走独立 session 重试, 保证完成状态落库。
            try:
                await _persist_loop_row(
                    record_id=db_record.id, result=result, session=None, status=status_val,
                )
                return
            except BaseException:  # noqa: BLE001
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
