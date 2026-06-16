"""SQLAlchemy models package."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


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
    "ExtractionEvaluationRecord",
    "JDExtractionRecord",
    "PositionRecord",
    "PositionSkillRelation",
    "RawJDRecord",
    "SkillAliasRecord",
    "SkillRecord",
    "SystemConfig",
]
