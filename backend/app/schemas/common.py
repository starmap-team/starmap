"""通用 Schema：错误响应、分页、字段级错误。

这些模型是前后端数据一致性校验的基础设施。
所有 API 错误响应统一使用 ErrorResponse 格式。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class FieldError(BaseModel):
    """字段级校验错误。

    用于 422 响应中逐字段指出校验失败的字段、值和原因。
    前端据此高亮对应的表单输入框。

    Examples:
        {"field": "password", "value": "123", "message": "密码长度不能少于 8 个字符", "code": "min_length"}
        {"field": "skills_required[0].name", "value": "", "message": "技能名称不能为空", "code": "value_error.empty"}
    """

    field: str = Field(
        description="出错字段路径。嵌套对象用 '.' 分隔，数组用 '[n]' 索引",
        examples=["password", "skills_required[0].name"],
    )
    value: Any | None = Field(
        default=None,
        description="接收到的问题值（生产环境可能省略以保护隐私）",
    )
    message: str = Field(
        description="面向用户的错误描述",
        examples=["密码长度不能少于 8 个字符"],
    )
    code: str = Field(
        description="机器可读错误码",
        examples=["min_length", "value_error.email", "type_error.int"],
    )


class ErrorResponse(BaseModel):
    """统一错误响应格式。

    所有 API 错误（400/401/403/404/409/422/500 等）均使用此格式。
    与 starmap-contracts/openapi.yaml 中 Error schema 保持一致。

    Examples:
        业务错误:
        {"detail": "岗位不存在", "code": "POSITION_NOT_FOUND", "timestamp": "2026-07-23T14:30:00Z"}

        校验错误:
        {"detail": "请求数据校验失败", "code": "VALIDATION_ERROR",
         "timestamp": "...", "fields": [{"field": "password", ...}]}
    """

    detail: str = Field(
        description="面向用户的错误摘要",
        examples=["岗位不存在", "请求数据校验失败"],
    )
    code: str = Field(
        description="机器可读错误码（大写蛇形命名）",
        examples=["POSITION_NOT_FOUND", "VALIDATION_ERROR", "UNAUTHORIZED"],
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="错误发生时间 (ISO 8601 UTC)",
    )
    fields: list[FieldError] | None = Field(
        default=None,
        description="字段级错误详情（仅校验错误时返回）",
    )


class PaginationMeta(BaseModel):
    """分页元信息。"""

    page: int = Field(ge=1, description="当前页码（从 1 开始）")
    page_size: int = Field(ge=1, le=100, description="每页数量")
    total: int = Field(ge=0, description="符合条件的总记录数")
    total_pages: int = Field(ge=0, description="总页数")


class PaginatedResponse(BaseModel):
    """泛型分页响应基类。

    具体业务模块继承此类并指定 items 类型。

    Usage:
        class PositionListResponse(PaginatedResponse):
            items: list[PositionNode]
    """

    items: list[Any] = Field(default_factory=list, description="当前页数据列表")
    pagination: PaginationMeta = Field(description="分页元信息")
