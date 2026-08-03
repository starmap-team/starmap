"""认证域 Schema：登录、令牌刷新、密码管理。

所有字段含完整约束，前端可据此生成表单校验规则。
"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.services import auth_service

# ── 请求模型 ──


class LoginRequest(BaseModel):
    """登录请求。"""

    username: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_\-\.]+$",
        description="用户名，仅允许字母、数字、下划线、连字符、点号",
        examples=["admin"],
    )
    password: str = Field(
        min_length=1,
        max_length=128,
        description="用户密码（服务端仅存储 bcrypt 哈希）",
        examples=["starmap2024"],
    )


class RefreshRequest(BaseModel):
    """刷新令牌请求。"""

    refresh_token: str = Field(
        min_length=1,
        max_length=1024,
        description="有效的 refresh token（JWT 字符串）",
    )


class LogoutRequest(BaseModel):
    """登出请求。"""

    refresh_token: str = Field(
        min_length=1,
        max_length=1024,
        description="待撤销的 refresh token",
    )


class ChangePasswordRequest(BaseModel):
    """修改密码请求。"""

    old_password: str = Field(
        min_length=1,
        max_length=128,
        description="当前密码",
    )
    new_password: str = Field(
        min_length=auth_service.MIN_PASSWORD_LENGTH,
        max_length=128,
        description=f"新密码（至少 {auth_service.MIN_PASSWORD_LENGTH} 个字符）",
    )


class ForgotPasswordRequest(BaseModel):
    """忘记密码请求。"""

    email: EmailStr = Field(
        description="注册邮箱地址",
        examples=["user@example.com"],
    )


class ResetPasswordRequest(BaseModel):
    """重置密码请求。"""

    token: str = Field(
        min_length=1,
        max_length=512,
        description="密码重置令牌",
    )
    new_password: str = Field(
        min_length=auth_service.MIN_PASSWORD_LENGTH,
        max_length=128,
        description=f"新密码（至少 {auth_service.MIN_PASSWORD_LENGTH} 个字符）",
    )


# ── 响应模型 ──


class TokenUser(BaseModel):
    """嵌套在 Token 响应中的用户摘要。"""

    id: str = Field(description="用户唯一标识")
    username: str = Field(description="用户名")
    role: str = Field(description="角色（admin / viewer）")
    must_change_password: bool = Field(
        default=False,
        description="是否需要在首次登录时修改密码",
    )


class LoginResponse(BaseModel):
    """登录成功响应。"""

    access_token: str = Field(description="JWT access token")
    refresh_token: str = Field(description="JWT refresh token")
    expires_in: int = Field(ge=1, description="Token 有效期（秒）")
    user: TokenUser = Field(description="当前用户信息")


class RefreshResponse(BaseModel):
    """令牌刷新响应。"""

    access_token: str = Field(description="新的 JWT access token")
    expires_in: int = Field(ge=1, description="Token 有效期（秒）")


class MessageResponse(BaseModel):
    """通用消息响应（登出/密码修改确认等）。"""

    message: str = Field(min_length=1, description="操作结果消息")
