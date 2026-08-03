"""Pydantic schemas for CSV/JSON import (Phase 15-02 Task 1)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ImportItem(BaseModel):
    """单条 JD 导入项。"""

    job_title: str = Field(..., max_length=200, description="职位名称")
    company: str = Field("", max_length=200, description="公司名称")
    clean_text: str = Field(..., min_length=1, description="JD 描述/正文")
    source_url: str = Field("", max_length=500, description="原始链接")
    location: str = Field("", description="工作地点")
    salary_min: int = Field(0, ge=0, description="最低薪资 (k)")
    salary_max: int = Field(0, ge=0, description="最高薪资 (k)")


class ImportRequest(BaseModel):
    """JSON 导入请求体。"""

    source_name: str = Field(..., max_length=100, description="数据源名称 (用户标注)")
    platform: str = Field(
        "manual",
        description="平台标识",
        pattern=r"^(manual|bosszhipin|lagou|51job|liepin|zhaopin|other)$",
    )
    items: list[ImportItem] = Field(..., max_length=10000, description="待导入 JDs")


class ImportResult(BaseModel):
    """导入结果统计。"""

    total: int = Field(..., description="总数")
    inserted: int = Field(..., description="新插入")
    duplicate: int = Field(..., description="重复跳过")
    errors: list[dict] = Field(default_factory=list, description="错误列表 [{row, field, message}]")
    pii_warnings: int = Field(0, description="PII 警告条数")
