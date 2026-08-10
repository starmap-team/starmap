"""Pipeline service layer — re-exports for pipeline orchestration.

Layer-boundary rule: api/v1 → services → core. pipeline/routes.py must not
import app.core.pipeline.* / app.core.dashboard.sse_broadcaster directly;
it consumes the re-exports here so the dependency direction stays
api → services → core.
"""
from __future__ import annotations

from app.core.dashboard.sse_broadcaster import (  # noqa: F401 — §pipeline re-export (路由经 service 访问 core)
    event_stream,
    get_recent_events,
    publish_event,
)
from app.core.matching import MatchService  # noqa: F401
from app.core.pipeline.cron_scheduler import compute_next_cron  # noqa: F401
from app.core.pipeline.executor import (  # noqa: F401
    advance_pipeline,
    build_spider_registry,
    resume_run,
    retry_stage,
    trigger_and_start,
)
from app.core.pipeline.orchestrator import (  # noqa: F401
    RunAlreadyTerminalError,
    RunNotFoundError,
    StageStatus,
    cancel_run,
    get_run_history,
    get_status,
)
from app.core.pipeline.quality_monitor import (  # noqa: F401
    generate_alerts,
    get_quality_snapshot,
)
from app.core.pipeline.source_quality_sync import sync_source_quality  # noqa: F401
from app.core.pipeline.sse.contracts import PipelineContext  # noqa: F401
from app.core.pipeline.sse.engine import PipelineEngine, _build_result  # noqa: F401
from app.core.pipeline.sse.steps import (  # noqa: F401
    LearningPathStep,
    MatchStep,
    RecommendStep,
    ResumeParseStep,
    SkillExtractStep,
)
from app.core.pipeline.status_aggregator import (  # noqa: F401
    compute_data_quality_aggregates,
    invalidate_status_cache,
    read_or_compute_status_aggregates,
)

__all__ = [
    "MatchService",
    "PipelineContext",
    "PipelineEngine",
    "LearningPathStep",
    "MatchStep",
    "RecommendStep",
    "ResumeParseStep",
    "SkillExtractStep",
    "StageStatus",
    "RunAlreadyTerminalError",
    "RunNotFoundError",
    "cancel_run",
    "get_run_history",
    "get_status",
    "advance_pipeline",
    "build_spider_registry",
    "resume_run",
    "retry_stage",
    "trigger_and_start",
    "compute_next_cron",
    "generate_alerts",
    "get_quality_snapshot",
    "sync_source_quality",
    "compute_data_quality_aggregates",
    "invalidate_status_cache",
    "read_or_compute_status_aggregates",
    "event_stream",
    "get_recent_events",
    "publish_event",
    "_build_result",
]
