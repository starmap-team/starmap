"""验证基础设施：错误码枚举与结构化错误构建。

所有 API 错误均通过 build_error_response() 生成统一的 ErrorResponse 格式。
"""

from __future__ import annotations

from enum import StrEnum

from fastapi import status
from fastapi.responses import JSONResponse

from app.schemas.common import ErrorResponse, FieldError


class ErrorCode(StrEnum):
    """API 错误码枚举。

    统一蛇形大写命名，前端可根据 code 做粒度错误处理。
    """

    # ── 认证 (AUTH_*) ──
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_TOKEN_INVALID = "AUTH_TOKEN_INVALID"
    AUTH_TOKEN_REVOKED = "AUTH_TOKEN_REVOKED"
    AUTH_REFRESH_FAILED = "AUTH_REFRESH_FAILED"
    AUTH_PASSWORD_SAME_AS_OLD = "AUTH_PASSWORD_SAME_AS_OLD"
    AUTH_INVALID_RESET_TOKEN = "AUTH_INVALID_RESET_TOKEN"
    AUTH_MUST_CHANGE_PASSWORD = "AUTH_MUST_CHANGE_PASSWORD"
    AUTH_USER_NOT_FOUND = "AUTH_USER_NOT_FOUND"
    AUTH_FORBIDDEN = "AUTH_FORBIDDEN"
    AUTH_IP_BLOCKED = "AUTH_IP_BLOCKED"

    # ── 校验 (VAL_*) ──
    VALIDATION_ERROR = "VALIDATION_ERROR"
    VALIDATION_BODY_PARSE_ERROR = "VALIDATION_BODY_PARSE_ERROR"
    VALIDATION_TYPE_ERROR = "VALIDATION_TYPE_ERROR"

    # ── 资源 (RES_*) ──
    RES_NOT_FOUND = "RES_NOT_FOUND"
    RES_ALREADY_EXISTS = "RES_ALREADY_EXISTS"
    RES_CONFLICT = "RES_CONFLICT"
    RES_STALE = "RES_STALE"

    # ── 业务 (BIZ_*) ──
    BIZ_POSITION_NOT_FOUND = "POSITION_NOT_FOUND"
    BIZ_PLAN_NOT_FOUND = "PLAN_NOT_FOUND"
    BIZ_PLAN_OWNERSHIP = "PLAN_OWNERSHIP"
    BIZ_RUN_NOT_FOUND = "RUN_NOT_FOUND"
    BIZ_RUN_TERMINAL = "RUN_TERMINAL"
    BIZ_EXTRACTION_FAILED = "EXTRACTION_FAILED"
    BIZ_EXTRACTION_LLM_UNAVAILABLE = "EXTRACTION_LLM_UNAVAILABLE"
    BIZ_MATCH_NO_CANDIDATE = "MATCH_NO_CANDIDATE"

    # ── 系统 (SYS_*) ──
    SYS_INTERNAL_ERROR = "INTERNAL_ERROR"
    SYS_RATE_LIMITED = "RATE_LIMITED"
    SYS_SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    SYS_DATABASE_ERROR = "DATABASE_ERROR"


# 错误码 → HTTP 状态码映射
_ERROR_CODE_STATUS: dict[ErrorCode, int] = {
    # Auth
    ErrorCode.AUTH_INVALID_CREDENTIALS: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.AUTH_TOKEN_EXPIRED: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.AUTH_TOKEN_INVALID: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.AUTH_TOKEN_REVOKED: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.AUTH_REFRESH_FAILED: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.AUTH_PASSWORD_SAME_AS_OLD: status.HTTP_400_BAD_REQUEST,
    ErrorCode.AUTH_INVALID_RESET_TOKEN: status.HTTP_400_BAD_REQUEST,
    ErrorCode.AUTH_MUST_CHANGE_PASSWORD: status.HTTP_403_FORBIDDEN,
    ErrorCode.AUTH_USER_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.AUTH_FORBIDDEN: status.HTTP_403_FORBIDDEN,
    ErrorCode.AUTH_IP_BLOCKED: status.HTTP_403_FORBIDDEN,
    # Validation
    ErrorCode.VALIDATION_ERROR: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ErrorCode.VALIDATION_BODY_PARSE_ERROR: status.HTTP_400_BAD_REQUEST,
    ErrorCode.VALIDATION_TYPE_ERROR: status.HTTP_422_UNPROCESSABLE_ENTITY,
    # Resource
    ErrorCode.RES_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.RES_ALREADY_EXISTS: status.HTTP_409_CONFLICT,
    ErrorCode.RES_CONFLICT: status.HTTP_409_CONFLICT,
    ErrorCode.RES_STALE: status.HTTP_409_CONFLICT,
    # Business
    ErrorCode.BIZ_POSITION_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.BIZ_PLAN_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.BIZ_PLAN_OWNERSHIP: status.HTTP_403_FORBIDDEN,
    ErrorCode.BIZ_RUN_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.BIZ_RUN_TERMINAL: status.HTTP_409_CONFLICT,
    ErrorCode.BIZ_EXTRACTION_FAILED: status.HTTP_502_BAD_GATEWAY,
    ErrorCode.BIZ_EXTRACTION_LLM_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.BIZ_MATCH_NO_CANDIDATE: status.HTTP_404_NOT_FOUND,
    # System
    ErrorCode.SYS_INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ErrorCode.SYS_RATE_LIMITED: status.HTTP_429_TOO_MANY_REQUESTS,
    ErrorCode.SYS_SERVICE_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.SYS_DATABASE_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def build_error_response(
    detail: str,
    code: ErrorCode,
    status_code: int | None = None,
    fields: list[FieldError] | None = None,
    *,
    include_internal_detail: str | None = None,
) -> JSONResponse:
    """构建统一错误响应。

    Args:
        detail: 面向用户的错误描述
        code: 机器可读错误码（ErrorCode 枚举值）
        status_code: HTTP 状态码（None 时自动从 ErrorCode 推导）
        fields: 字段级错误详情（仅校验错误时使用）
        include_internal_detail: 内部诊断信息（仅非生产环境返回，生产环境置空）

    Returns:
        JSONResponse 以统一 ErrorResponse 格式序列化

    Examples:
        >>> build_error_response("岗位不存在", ErrorCode.BIZ_POSITION_NOT_FOUND)
        >>> build_error_response("校验失败", ErrorCode.VALIDATION_ERROR,
        ...     fields=[FieldError(field="password", value=None, message="不能为空", code="min_length")])
    """
    http_status = status_code if status_code is not None else _ERROR_CODE_STATUS.get(code, 500)

    response = ErrorResponse(
        detail=detail,
        code=code.value,
        fields=fields,
    )

    # 序列化为 dict 以便附加内部诊断信息
    body = response.model_dump(mode="json")

    # 非生产环境追加内部诊断（帮助调试）
    from app.config import settings

    if settings.app_env != "production" and include_internal_detail:
        body["_internal_detail"] = include_internal_detail

    return JSONResponse(status_code=http_status, content=body)
