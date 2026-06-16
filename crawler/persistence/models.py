"""SQLAlchemy ORM 模型（对应 docs/contract-jd-source.md 契约）。"""
from __future__ import annotations

import enum
from datetime import datetime
from sqlalchemy import (
    BigInteger,
    Boolean,
    CHAR,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class JdStatus(str, enum.Enum):
    raw = "raw"
    extracted = "extracted"
    duplicate = "duplicate"
    failed = "failed"


class JdRaw(Base):
    """契约 v1 §四：jd_raw 表。"""

    __tablename__ = "jd_raw"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_site: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    raw_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    clean_text: Mapped[str] = mapped_column(Text, nullable=False)
    job_title: Mapped[str] = mapped_column(String(200), nullable=False)
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    publish_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    crawled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    content_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    status: Mapped[JdStatus] = mapped_column(
        SAEnum(JdStatus, name="jd_status"), nullable=False, default=JdStatus.raw
    )
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_jd_raw_status", "status"),
        Index("idx_jd_raw_source_site", "source_site"),
        Index("idx_jd_raw_crawled_at", "crawled_at"),
        Index("idx_jd_raw_content_hash", "content_hash"),
    )


class ComplianceLog(Base):
    """契约 v1 §五：compliance_log 表。"""

    __tablename__ = "compliance_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_site: Mapped[str] = mapped_column(String(32), nullable=False)
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    robots_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    user_agent: Mapped[str] = mapped_column(String(200), nullable=False)
    qps: Mapped[float] = mapped_column(Float, nullable=False)
    response_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_bytes: Mapped[int] = mapped_column(Integer, nullable=True)
    crawled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = ["Base", "JdRaw", "ComplianceLog", "JdStatus"]
