"""PostgreSQL SQLAlchemy models for the evolution subsystem.

Tables:
- evolution_snapshot: Point-in-time skill profiles per position
- evolution_changelog: Skill changes detected by DiffEngine
- evolution_path: EVOLVES_TO relationships with evidence
- skill_timeseries: Skill frequency tracking over time windows
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class EvolutionSnapshot(Base):
    """Point-in-time snapshot of a position's skill profile.

    Captures the full set of required/preferred skills at a given point,
    enabling DiffEngine to compute changes between snapshots.
    """

    __tablename__ = "evolution_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    position_name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )
    snapshot_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
    )
    required_skills: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=list,
        comment="List of {name, category, proficiency} dicts",
    )
    preferred_skills: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=list,
        comment="List of {name, category, proficiency} dicts",
    )
    source_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Number of JDs contributing to this snapshot",
    )
    metadata_json: Mapped[dict] = mapped_column(
        JSON, nullable=True, default=dict,
        comment="Extra metadata (query window, filters applied, etc.)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return (
            f"<EvolutionSnapshot {self.position_name} "
            f"date={self.snapshot_date.date()} skills={len(self.required_skills or [])}>"
        )


class EvolutionChangelog(Base):
    """Skill changes detected by DiffEngine between two snapshots.

    Each row represents a single skill change event (added, removed,
    promoted, demoted, retained) for a specific position.
    """

    __tablename__ = "evolution_changelog"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    position_name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )
    skill_name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )
    change_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="added_required | added_preferred | removed | promoted | demoted | retained",
    )
    old_proficiency: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_proficiency: Mapped[str | None] = mapped_column(String(50), nullable=True)
    old_requirement: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="required | preferred | null (if new)",
    )
    new_requirement: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="required | preferred | null (if removed)",
    )
    snapshot_from_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True,
    )
    snapshot_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True,
    )
    trust_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5,
        comment="Trust score from TrustScorer (0.0-1.0)",
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5,
        comment="Detection confidence (0.0-1.0)",
    )
    evidence_json: Mapped[dict] = mapped_column(
        JSON, nullable=True, default=dict,
        comment="Evidence details (source JDs, timestamps, etc.)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return (
            f"<EvolutionChangelog {self.position_name} "
            f"{self.skill_name} {self.change_type}>"
        )


class EvolutionPath(Base):
    """EVOLVES_TO relationship between positions with evidence.

    Stores discovered evolution paths (e.g., "Backend Engineer" →
    "Full Stack Engineer") with Jaccard similarity and supporting evidence.
    """

    __tablename__ = "evolution_paths"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    source_position: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )
    target_position: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )
    similarity: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="Jaccard similarity between position skill sets",
    )
    evidence_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Number of supporting evidence items",
    )
    skill_overlap: Mapped[dict] = mapped_column(
        JSON, nullable=True, default=list,
        comment="List of overlapping skill names",
    )
    key_gaps: Mapped[dict] = mapped_column(
        JSON, nullable=True, default=list,
        comment="List of skills the target requires but source doesn't",
    )
    avg_months: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Estimated months for transition",
    )
    trust_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5,
    )
    first_detected: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return (
            f"<EvolutionPath {self.source_position} → {self.target_position} "
            f"sim={self.similarity:.2f}>"
        )


class SkillTimeseries(Base):
    """Skill frequency tracking over time windows.

    Enables trend analysis and Z-score emergence detection by storing
    per-skill, per-window frequency counts.
    """

    __tablename__ = "skill_timeseries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    skill_name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
    )
    window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    frequency: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Number of JDs mentioning this skill in this window",
    )
    source_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Number of independent sources",
    )
    positions: Mapped[dict] = mapped_column(
        JSON, nullable=True, default=list,
        comment="List of positions mentioning this skill",
    )
    category: Mapped[str] = mapped_column(
        String(100), nullable=False, default="general",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return (
            f"<SkillTimeseries {self.skill_name} "
            f"window={self.window_start.date()}-{self.window_end.date()} "
            f"freq={self.frequency}>"
        )
