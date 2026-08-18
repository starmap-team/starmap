"""DataSourceMetric model — tracks each source's crawl results (Task 1).

Used by health_monitor for:
- 24h success_rate per source
- Error-type weighted熔断 (Fix M1)
- Source auto-recovery (suggestion 3)
- 最近 N 次 attempts 历史
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.pipeline_models import Base

class DataSourceMetric(Base):
 """每个数据源每次爬取的指标。"""

 __tablename__ = "data_source_metrics"

 id: Mapped[uuid.UUID] = mapped_column(
 PGUUID(as_uuid=True),
 primary_key=True,
 default=uuid.uuid4,
 )
 source_id: Mapped[uuid.UUID] = mapped_column(
 PGUUID(as_uuid=True),
 ForeignKey("data_sources.id", ondelete="CASCADE"),
 nullable=False,
 index=True,
 )
 run_id: Mapped[uuid.UUID | None] = mapped_column(
 PGUUID(as_uuid=True),
 nullable=True,
 index=True,
 )
 started_at: Mapped[datetime] = mapped_column(
 DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
 )
 finished_at: Mapped[datetime | None] = mapped_column(
 DateTime(timezone=True), nullable=True
 )
 status: Mapped[str] = mapped_column(
 String(20), nullable=False, comment="success | failed | blocked | timeout"
 )
 records_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
 records_duplicate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
 error_type: Mapped[str | None] = mapped_column(
 String(32), nullable=True, comment="connection | parse | auth | rate_limit | blocked"
 )
 error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
 duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
