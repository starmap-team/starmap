"""认证 API：用户登录、JWT token 签发。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

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
    """手动签发 JWT（HMAC-SHA256），与 dependencies.py _decode_token 验证逻辑一致。

    JWT 格式: header.payload.signature
    签名算法: HMAC-SHA256(settings.secret_key, header.payload)
    """
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()

    payload_b64 = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).rstrip(b"=").decode()

    signing_input = f"{header}.{payload_b64}".encode()
    sig = hmac.new(settings.secret_key.encode(), signing_input, hashlib.sha256).digest()
    signature = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()

    return f"{header}.{payload_b64}.{signature}"


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> dict:
    """用户登录，验证凭据后签发 JWT token。"""
    users = settings.parsed_users
    matched = None
    for u in users:
        if u["username"] == request.username and u["password"] == request.password:
            matched = u
            break

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
