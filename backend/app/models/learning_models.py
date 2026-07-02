"""SQLAlchemy models for the learning center subsystem.

Tables:
- learning_plans: User learning plans tied to target positions
- learning_progress: Per-skill progress tracking within a plan
- skill_prerequisites: Skill prerequisite DAG edges
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class LearningPlan(Base):
    """A user's learning plan targeting a specific position.

    Created from match diagnosis results, tracks the overall plan state
    including which skills need to be learned and the estimated timeline.
    """

    __tablename__ = "learning_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True, default="anonymous",
    )
    position: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
        comment="Target position name",
    )
    skills: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=list,
        comment="List of skill dicts: {name, importance, gap_level, learning_path}",
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active",
        comment="active | completed | archived",
    )
    match_score_at_creation: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="Match score when plan was created",
    )
    estimated_hours: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="Total estimated learning hours",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<LearningPlan {self.id} position={self.position} status={self.status}>"


class LearningProgress(Base):
    """Per-skill progress within a learning plan.

    Tracks mastery status and percentage for each skill the user
    needs to learn as part of their plan.
    """

    __tablename__ = "learning_progress"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True,
    )
    skill_name: Mapped[str] = mapped_column(
        String(255), nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="not_started",
        comment="not_started | in_progress | mastered",
    )
    progress_pct: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="0.0 - 100.0",
    )
    importance: Mapped[str] = mapped_column(
        String(20), nullable=False, default="required",
        comment="required | bonus",
    )
    estimated_hours: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="Estimated hours to master this skill",
    )
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return (
            f"<LearningProgress plan={self.plan_id} "
            f"skill={self.skill_name} status={self.status} pct={self.progress_pct}>"
        )


class SkillPrerequisite(Base):
    """Skill prerequisite DAG edges.

    Stores the dependency relationships between skills, forming a
    directed acyclic graph (DAG) used for learning path generation.
    """

    __tablename__ = "skill_prerequisites"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    skill: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
        comment="The skill that has a prerequisite",
    )
    prerequisite: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
        comment="The prerequisite skill that must be learned first",
    )
    strength: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0,
        comment="Prerequisite strength 0.0-1.0 (1.0 = hard requirement)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return (
            f"<SkillPrerequisite {self.skill} <- {self.prerequisite} "
            f"strength={self.strength}>"
        )
