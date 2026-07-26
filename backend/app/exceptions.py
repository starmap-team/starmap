"""Domain exceptions for the service/core layer.

These are raised by service and core modules instead of HTTPException,
keeping business logic decoupled from the web framework. The API layer
maps them to appropriate HTTP responses.
"""
from __future__ import annotations

import uuid


class StarMapError(Exception):
    """Base exception for all StarMap domain errors."""


class PositionNotFoundError(StarMapError):
    """Raised when a target position is not found in the knowledge graph."""

    def __init__(self, position_name: str) -> None:
        self.position_name = position_name
        super().__init__(f'Position "{position_name}" not found in graph')


class PlanNotFoundError(StarMapError):
    """Raised when a learning plan is not found."""

    def __init__(self, plan_id: str) -> None:
        self.plan_id = plan_id
        super().__init__(f"Plan {plan_id} not found")


class PlanOwnershipError(StarMapError):
    """Raised when a user tries to access a plan they don't own."""

    def __init__(self, plan_id: str, user_id: str) -> None:
        self.plan_id = plan_id
        self.user_id = user_id
        super().__init__(f"User {user_id} does not own plan {plan_id}")


class RunNotFoundError(StarMapError):
    """Raised when a pipeline run is not found."""

    def __init__(self, run_id: str | uuid.UUID) -> None:
        self.run_id = run_id
        super().__init__(f"Pipeline run {run_id} not found")


class RunAlreadyTerminalError(StarMapError):
    """Raised when attempting to modify a run already in terminal state."""

    def __init__(self, status: str) -> None:
        self.status = status
        super().__init__(f"Run already in terminal state: {status}")


class ExtractionError(StarMapError):
    """Base for extraction failures."""

    def __init__(self, message: str, source: str | None = None) -> None:
        self.source = source
        super().__init__(message)


class ExtractionLLMError(ExtractionError):
    """LLM call failed during extraction."""


class ExtractionNormalizationError(ExtractionError):
    """Skill normalization failed during extraction."""


class PipelineError(StarMapError):
    """Base for pipeline execution failures."""

    def __init__(self, message: str, stage: str | None = None) -> None:
        self.stage = stage
        super().__init__(message)


class PipelineStageError(PipelineError):
    """A specific pipeline stage failed."""


class PipelineTimeoutError(PipelineError):
    """Pipeline stage timed out."""


class MatchingError(StarMapError):
    """Base for matching failures."""

    def __init__(self, message: str, position_id: str | None = None) -> None:
        self.position_id = position_id
        super().__init__(message)


class JudgeError(StarMapError):
    """Base for judge/evaluation failures."""


class LearningPathError(StarMapError):
    """Base for learning path failures."""


class QualityError(StarMapError):
    """Base for quality check failures."""


class DashboardError(StarMapError):
    """Base for dashboard data failures."""


class GraphProjectionError(StarMapError):
    """Base for graph projection/sync failures."""
