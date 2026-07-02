"""SQLAlchemy models for data pipeline monitoring."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from app.models import Base


class PipelineRun(Base):
    """Records of ETL pipeline runs (crawl -> dedup -> clean -> import -> graph_sync)."""

    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    run_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="full",
        comment="'full' | 'incremental' | 'source_sync'",
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="running",
        comment="'running' | 'completed' | 'failed' | 'cancelled'",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    stages: Mapped[dict | list | None] = mapped_column(
        JSON, nullable=True, default=list,
        comment="[{name, status, duration_ms, records_processed, errors}]",
    )
    total_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_stages: Mapped[list | None] = mapped_column(
        JSON, nullable=True,
        comment="List of stage names to execute; null = all stages",
    )

    def __repr__(self) -> (
        str
    ):
        return (
            f"<PipelineRun {self.id} type={self.run_type} "
            f"status={self.status} quality={self.quality_score:.2f}>"
        )


class PipelineSchedule(Base):
    """Cron-based pipeline scheduling configuration."""

    __tablename__ = "pipeline_schedules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    cron_expression: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="cron expression, e.g. '0 2 * * *'",
    )
    run_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="incremental",
    )
    selected_stages: Mapped[list | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(
        default=True, nullable=False,
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )


class DataSourceRecord(Base):
    """Configuration and status of external data sources."""

    __tablename__ = "data_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True,
        comment="'BOSS直聘' | '拉勾网' | '51Job' | 'GitHub' | 'ESCO'",
    )
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="crawler",
        comment="'crawler' | 'api' | 'manual' | 'import'",
    )
    authority_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5,
        comment="Source authority weight 0.0-1.0",
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active",
        comment="'active' | 'paused' | 'error'",
    )
    last_crawl_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    total_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    config: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=dict,
        comment="Crawler / API configuration parameters",
    )

    def __repr__(self) -> str:
        return (
            f"<DataSourceRecord {self.name} type={self.source_type} "
            f"status={self.status} authority={self.authority_score:.2f}>"
        )
