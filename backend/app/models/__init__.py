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
from app.models.learning_models import (  # noqa: E402, F401
    LearningPlan,
    LearningProgress,
    SkillPrerequisite,
)
from app.models.pipeline_models import (  # noqa: E402, F401
    DataSourceRecord,
    LoopResultRecord,
    PipelineRun,
    PipelineSchedule,
)
from app.models.audit_models import (  # noqa: E402, F401
    AuditEventRecord,
)

__all__ = [
    "Base",
    "AuditEventRecord",
    "DataSourceRecord",
    "EvolutionChangelog",
    "EvolutionPath",
    "EvolutionSnapshot",
    "ExtractionEvaluationRecord",
    "JDExtractionRecord",
    "LearningPlan",
    "LearningProgress",
    "LoopResultRecord",
    "PipelineRun",
    "PipelineSchedule",
    "PositionRecord",
    "PositionSkillRelation",
    "RawJDRecord",
    "SkillAliasRecord",
    "SkillPrerequisite",
    "SkillRecord",
    "SkillTimeseries",
    "SystemConfig",
]
