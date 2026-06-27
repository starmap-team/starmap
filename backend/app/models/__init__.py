"""SQLAlchemy models package."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


from app.models.evolution_models import (  # noqa: E402, F401
    EvolutionChangelog,
    EvolutionPath,
    EvolutionSnapshot,
    SkillTimeseries,
)
from app.models.extraction_models import (  # noqa: E402, F401
    ExtractionEvaluationRecord,
    JDExtractionRecord,
    PositionRecord,
    PositionSkillRelation,
    RawJDRecord,
    SkillAliasRecord,
    SkillRecord,
    SystemConfig,
)

__all__ = [
    "Base",
    "EvolutionChangelog",
    "EvolutionPath",
    "EvolutionSnapshot",
    "ExtractionEvaluationRecord",
    "JDExtractionRecord",
    "PositionRecord",
    "PositionSkillRelation",
    "RawJDRecord",
    "SkillAliasRecord",
    "SkillRecord",
    "SkillTimeseries",
    "SystemConfig",
]
