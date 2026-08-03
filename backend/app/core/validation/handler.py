"""验证基础设施：全局异常处理器与 Pydantic 校验错误格式化。

将 FastAPI 默认的 Pydantic ValidationError 转化为统一的 ErrorResponse 格式，
按字段拆分错误信息，方便前端逐字段高亮。
"""

from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.core.validation.errors import ErrorCode, build_error_response
from app.schemas.common import FieldError


def _location_to_field_path(loc: tuple[str | int, ...]) -> str:
    """将 Pydantic 错误位置元组转为前端可用的字段路径。

    Examples:
        ('body', 'password')          → 'password'
        ('body', 'skills', 0, 'name') → 'skills[0].name'
        ('body', 'items', 2)          → 'items[2]'
    """
    parts: list[str] = []
    for item in loc:
        if item == "body" or item == "__root__":
            continue
        if parts and isinstance(item, int):
            parts[-1] = f"{parts[-1]}[{item}]"
        elif isinstance(item, int):
            parts.append(f"[{item}]")
        else:
            parts.append(str(item))
    return ".".join(parts) if parts else "body"


def pydantic_errors_to_field_errors(exc: ValidationError | RequestValidationError) -> list[FieldError]:
    """将 Pydantic 校验异常转为 FieldError 列表。

    Args:
        exc: Pydantic ValidationError 或 FastAPI RequestValidationError

    Returns:
        FieldError 列表，每条对应一个校验失败字段
    """
    # 统一获取 errors() 列表
    errors = exc.errors() if isinstance(exc, ValidationError) else exc.errors()
    field_errors: list[FieldError] = []

    for err in errors:
        loc = tuple(err.get("loc", ()))
        field_path = _location_to_field_path(loc)
        error_type = err.get("type", "value_error")
        error_msg = err.get("msg", "校验失败")

        # 构建用户友好的错误消息
        user_msg = _error_type_to_user_message(error_type, error_msg, field_path)

        field_errors.append(
            FieldError(
                field=field_path,
                value=None,  # 生产环境不泄露用户输入
                message=user_msg,
                code=error_type,
            )
        )

    return field_errors


def _error_type_to_user_message(error_type: str, raw_msg: str, field_path: str) -> str:
    """将 Pydantic 内部错误类型转为中文用户友好消息。

    Args:
        error_type: Pydantic 错误类型（如 'string_too_short', 'missing'）
        raw_msg: Pydantic 原始消息
        field_path: 字段路径

    Returns:
        面向用户的中文消息
    """
    mapping: dict[str, str] = {
        "missing": f"「{field_path}」为必填字段",
        "string_too_short": raw_msg,  # Pydantic 已生成包含 min_length 的消息
        "string_too_long": raw_msg,
        "string_pattern_mismatch": f"「{field_path}」格式不正确",
        "value_error.email": "邮箱地址格式不正确",
        "value_error.number.not_ge": raw_msg,
        "value_error.number.not_le": raw_msg,
        "type_error.integer": f"「{field_path}」必须为整数",
        "type_error.float": f"「{field_path}」必须为数字",
        "type_error.str": f"「{field_path}」必须为文本",
        "type_error.bool": f"「{field_path}」必须为布尔值",
        "type_error.list": f"「{field_path}」必须为列表",
        "type_error.dict": f"「{field_path}」必须为对象",
        "json_invalid": "请求体不是合法的 JSON 格式",
        "value_error.any_str.min_length": raw_msg,
        "value_error.any_str.max_length": raw_msg,
    }
    return mapping.get(error_type, raw_msg)


# ── FastAPI 全局异常处理器 ──


async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """处理 FastAPI 请求体验证异常 (422)。

    将 Pydantic 校验错误转化为统一的 ErrorResponse + FieldError 列表。
    """
    field_errors = pydantic_errors_to_field_errors(exc)
    return build_error_response(
        detail="请求数据校验失败",
        code=ErrorCode.VALIDATION_ERROR,
        fields=field_errors,
        include_internal_detail=str(exc),
    )


async def pydantic_validation_exception_handler(
    request: Request, exc: ValidationError
) -> JSONResponse:
    """处理 Pydantic 校验异常（非请求体场景，如响应模型校验失败）。"""
    field_errors = pydantic_errors_to_field_errors(exc)
    return build_error_response(
        detail="数据处理校验失败",
        code=ErrorCode.VALIDATION_ERROR,
        fields=field_errors,
        include_internal_detail=str(exc),
    )
