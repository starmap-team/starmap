"""认证 API：用户登录、JWT token 签发。"""
from __future__ import annotations

import time
import uuid

import bcrypt
import jwt
from fastapi import APIRouter, HTTPException, status
from loguru import logger
from pydantic import BaseModel, Field

from app.config import settings

router = APIRouter(prefix="/auth", tags=["认证"])


class LoginRequest(BaseModel):
    """登录请求体。"""

    username: str = Field(..., min_length=1, description="用户名")
    password: str = Field(..., min_length=1, description="密码")


class LoginResponse(BaseModel):
    """登录响应体。"""

    token: str = Field(..., description="JWT token")
    user: dict = Field(..., description="用户信息 {sub, role, username}")


def _encode_jwt(payload: dict[str, str | int | float]) -> str:
    """签发 JWT（PyJWT），与 dependencies.py _decode_token 验证逻辑一致。"""
    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm="HS256",
    )


def _verify_password(plain: str, stored: str) -> bool:
    """验证密码。支持 bcrypt hash 和明文（过渡期）。

    bcrypt hash 以 $2b$ 或 $2a$ 开头，否则视为明文。
    """
    if stored.startswith(("$2b$", "$2a$")):
        return bcrypt.checkpw(plain.encode(), stored.encode())
    # Legacy plaintext fallback (transition period)
    return plain == stored


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> dict:
    """用户登录，验证凭据后签发 JWT token。"""
    users = settings.parsed_users
    matched = None
    for u in users:
        if u["username"] == request.username:
            if _verify_password(request.password, u["password"]):
                matched = u
            break  # Only one entry per username; stop after finding the match

    if not matched:
        logger.warning("Login failed for username: {}", request.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    now = time.time()
    payload: dict[str, str | int | float] = {
        "sub": matched["username"],
        "role": matched["role"],
        "username": matched["username"],
        "exp": now + settings.token_expire_hours * 3600,
        "iat": now,
        "nbf": now,                          # SEC-03: not valid before issuance
        "iss": settings.jwt_issuer,          # SEC-03: issuer identifier
        "aud": settings.jwt_audience,        # SEC-03: audience identifier
        "jti": str(uuid.uuid4()),            # SEC-03: unique token ID for revocation
    }
    token = _encode_jwt(payload)

    logger.info("User '{}' logged in (role={})", matched["username"], matched["role"])

    return {
        "token": token,
        "user": {
            "sub": payload["sub"],
            "role": payload["role"],
            "username": payload["username"],
        },
    }
