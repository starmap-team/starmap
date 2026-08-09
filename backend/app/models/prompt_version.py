"""PromptVersion model — persists custom prompt versions & active selection.

管理后台的 Prompt 工程 Tab 通过 /admin/prompts 注册/切换 prompt 版本；
此前版本注册只写进程内存 dict，重启即丢（伪持久化）。
此表是版本注册与活跃选择的持久化落点，启动时合并进内存注册表。
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.pipeline_models import Base


class PromptVersion(Base):
    """自定义 prompt 版本（覆盖代码内置版本）。"""

    __tablename__ = "prompt_versions"
    __table_args__ = (
        UniqueConstraint("prompt_name", "version", name="uq_prompt_name_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    prompt_name: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="jd_extraction / anti_hallucination / llm_judge / resume_extraction"
    )
    version: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="版本标识，如 v1 / custom_20260808"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="prompt 模板内容")
    is_active: Mapped[bool] = mapped_column(
        nullable=False, default=False, comment="是否为该 prompt 当前活跃版本"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
