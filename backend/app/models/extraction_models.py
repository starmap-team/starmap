"""PostgreSQL SQLAlchemy models for extraction pipeline."""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class JDExtractionRecord(Base):
    """Records of JD extraction runs."""

    __tablename__ = "jd_extraction_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    jd_content: Mapped[str] = mapped_column(Text, nullable=False)
    job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    extracted_skills: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    experience_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    education: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    hallucination_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )

    def __repr__(self) -> str:
        return f"<JDExtractionRecord {self.id} job_title={self.job_title} status={self.status}>"


class RawJDRecord(Base):
    """Raw JD crawl data: original source before extraction."""

    __tablename__ = "raw_jd_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_platform: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    title_raw: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    crawl_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )
    hash_dedup: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    def __repr__(self) -> str:
        return f"<RawJDRecord {self.id} title={self.title_raw}>"


class SkillAliasRecord(Base):
    """Normalization step 1: alias → standard skill mapping."""

    __tablename__ = "skill_alias_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    alias: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    standard_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<SkillAliasRecord {self.alias}->{self.standard_name}>"


class ExtractionEvaluationRecord(Base):
    """QA evaluation: F1/precision/recall per extraction sample."""

    __tablename__ = "extraction_evaluation_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    extraction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True,
    )
    golden_id: Mapped[str] = mapped_column(String(100), nullable=False)
    precision: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recall: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    f1_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    job_title_match: Mapped[bool] = mapped_column(sa.Boolean, nullable=True)
    experience_error: Mapped[float | None] = mapped_column(Float, nullable=True)
    education_match: Mapped[bool | None] = mapped_column(sa.Boolean, nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<ExtractionEvaluationRecord {self.id} F1={self.f1_score:.3f}>"


class PositionSkillRelation(Base):
    """M2M: which position requires which skill, with metadata."""

    __tablename__ = "position_skill_relations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    position_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True,
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True,
    )
    requirement_type: Mapped[str] = mapped_column(String(20), nullable=False, default="required")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<PositionSkillRelation pos={self.position_id} skill={self.skill_id}>"


class SystemConfig(Base):
    """Configuration and prompt version tracking."""

    __tablename__ = "system_config"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    config_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    config_value: Mapped[str] = mapped_column(Text, nullable=False)
    config_type: Mapped[str] = mapped_column(String(20), nullable=False, default="string")
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<SystemConfig {self.config_key}={self.config_value[:50]}>"


class SkillRecord(Base):
    """Master list of known skills with detection metadata."""

    __tablename__ = "skill_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="general")
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    last_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<SkillRecord {self.name} category={self.category}>"


class PositionRecord(Base):
    """Master list of known positions."""

    __tablename__ = "position_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<PositionRecord {self.name}>"
