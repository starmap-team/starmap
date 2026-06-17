"""R3 jd_extraction_records 表的 SQLAlchemy ORM。

对应 backend/alembic/versions/001_initial_migration.py 定义的 jd_extraction_records 表。
R1 联调脚本只负责写入，schema 变更权属 R3。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class JdExtractionRecord(Base):
    """R3 的抽取结果表。

    注意：此表由 R3 后端通过 Alembic 管理。R1 联调脚本只 INSERT/UPDATE，
    不修改 schema。如需字段调整请走契约变更流程。
    """

    __tablename__ = "jd_extraction_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    jd_content: Mapped[str] = mapped_column(Text, nullable=False)
    job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    extracted_skills: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, server_default=text("'{}'") if False else "{}"
    )
    experience_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    education: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")
    hallucination_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")

    __table_args__ = (
        Index("ix_jd_extraction_records_status", "status"),
        Index("ix_jd_extraction_records_created_at", "created_at"),
    )


__all__ = ["Base", "JdExtractionRecord"]
