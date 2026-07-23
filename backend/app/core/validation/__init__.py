"""验证基础设施包。

提供：
- ErrorCode 枚举 → 统一的错误码体系
- build_error_response() → 结构化错误响应构建器
- exception handlers → FastAPI 全局异常→统一格式转换
"""

from app.core.validation.errors import ErrorCode, build_error_response
from app.core.validation.handler import (
    pydantic_errors_to_field_errors,
    pydantic_validation_exception_handler,
    request_validation_exception_handler,
)

__all__ = [
    "ErrorCode",
    "build_error_response",
    "pydantic_errors_to_field_errors",
    "pydantic_validation_exception_handler",
    "request_validation_exception_handler",
]
