"""SQLAlchemy models package."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


from app.models.audit_models import (  # noqa: E402, F401
    AuditEventRecord,
)
from app.models.data_source_metric import (  # noqa: E402, F401
    DataSourceMetric,
)
from app.models.evolution_models import (  # noqa: E402, F401
    EvolutionChangelog,
    EvolutionPath,
    EvolutionSnapshot,
    SkillTimeseries,
)
from app.models.extraction_models import (  # noqa: E402, F401
    ExtractionEvaluationRecord,
    JDExtractionRecord,
    MatchResult,
    PositionRecord,
    PositionSkillRelation,
    ReviewQueue,
    SkillAliasRecord,
    SkillRecord,
    SystemConfig,
)
from app.models.learning_models import (  # noqa: E402, F401
    LearningPlan,
    LearningProgress,
    SkillPrerequisite,
)
from app.models.orphan_cleanup import (  # noqa: E402, F401
    OrphanCleanupQueue,
)
from app.models.pipeline_models import (  # noqa: E402, F401
    DataSourceRecord,
    GraphWriteOutbox,
    LoopResultRecord,
    PipelineRun,
    PipelineSchedule,
    SourceTrustConfig,
)
from app.models.prompt_version import (  # noqa: E402, F401
    PromptVersion,
)
from app.models.review_audit_log import (  # noqa: E402, F401
    ReviewAuditLog,
)
from app.models.user import (  # noqa: E402, F401
    ALLOWED_ROLES,
    ROLE_ADMIN,
    ROLE_USER,
    User,
)

__all__ = [
    "ALLOWED_ROLES",
    "ROLE_ADMIN",
    "ROLE_USER",
    "Base",
    "AuditEventRecord",
    "DataSourceMetric",
    "DataSourceRecord",
    "EvolutionChangelog",
    "EvolutionPath",
    "EvolutionSnapshot",
    "ExtractionEvaluationRecord",
    "GraphWriteOutbox",
    "JDExtractionRecord",
    "LearningPlan",
    "LearningProgress",
    "LoopResultRecord",
    "MatchResult",
    "OrphanCleanupQueue",
    "PipelineRun",
    "PipelineSchedule",
    "PositionRecord",
    "PositionSkillRelation",
    "PromptVersion",
    "ReviewAuditLog",
    "ReviewQueue",
    "SkillAliasRecord",
    "SkillPrerequisite",
    "SkillRecord",
    "SkillTimeseries",
    "SourceTrustConfig",
    "SystemConfig",
    "User",
]
