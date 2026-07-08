"""FastAPI 应用入口。"""
from __future__ import annotations

import asyncio
import sys
import time
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.api.v1.router import api_router
from app.config import settings
from app.services.resources import healthcheck_resources, init_resources, resources
from app.utils.audit import AuditEntry, AuditEvent, audit_log

# AP-10: Structured JSON logging for production (enables ELK/Loki querying)
# Remove loguru's default handler and add JSON-serialized sink in production
logger.remove()
if _is_prod := (settings.app_env == "production"):
    logger.add(
        sys.stderr,
        serialize=True,  # JSON-structured output
        level=settings.app_log_level,
        format="{time:YYYY-MM-DDTHH:mm:ssZ} | {level} | {name}:{function}:{line} | {message}",
    )
else:
    logger.add(
        sys.stderr,
        level=settings.app_log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>",
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期：启动时初始化连接，关闭时释放。"""
    logger.info("StarMap 启动中... env={}", settings.app_env)
    app.state.resources = await init_resources()
    # Phase 2 CRON-03: 启动 cron scanner 后台任务
    cron_task = None
    try:
        from app.core.pipeline.cron_scheduler import cron_scanner_loop
        cron_task = asyncio.create_task(cron_scanner_loop(interval_seconds=60))
        logger.info("Cron scanner loop started")
        yield
    finally:
        if cron_task is not None:
            cron_task.cancel()
            logger.info("Cron scanner loop stopped")
        await resources.close()
        logger.info("StarMap 关闭中...")


# P0 修复 (API-03): 生产环境禁用 Swagger/ReDoc/OpenAPI
_is_prod = settings.app_env == "production"

app = FastAPI(
    title="星图 StarMap API",
    description="人才能力星云导航系统 - 后端 API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
)

# P0 修复 (AUTH-04): CORS 收紧 methods/headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
)

# P1 修复 (API-04): 安全响应头中间件
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# P1 修复 (API-02): 内存速率限制中间件
# ponytail: stdlib sliding-window, per-IP, no external deps.
# Upgrade to Redis-backed (slowapi) if multi-process or distributed.
_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX = 120  # requests per window per IP
_rate_buckets: dict[str, list[float]] = defaultdict(list)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        # Sliding window: keep only timestamps within the window
        bucket = _rate_buckets[client_ip]
        _rate_buckets[client_ip] = [t for t in bucket if now - t < _RATE_LIMIT_WINDOW]
        if len(_rate_buckets[client_ip]) >= _RATE_LIMIT_MAX:
            audit_log(AuditEntry(
                event=AuditEvent.RATE_LIMITED,
                actor=client_ip,
                action=f"{request.method} {request.url.path}",
                detail=f"Exceeded {_RATE_LIMIT_MAX} req/{_RATE_LIMIT_WINDOW}s",
                ip=client_ip,
            ))
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={"Retry-After": str(_RATE_LIMIT_WINDOW)},
            )
        _rate_buckets[client_ip].append(now)
        return await call_next(request)


app.add_middleware(RateLimitMiddleware)

app.include_router(api_router, prefix="/api/v1")


# M17: Global exception handler — catches unhandled exceptions, logs them,
# and returns a generic 500 without leaking internals.
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.opt(exception=True).error("Unhandled exception on {} {}: {}", request.method, request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# P0 修复 (SEC-10): 健康检查不暴露版本号和服务详情
async def _health_payload() -> dict:
    if _is_prod:
        # 生产环境：仅返回状态，不暴露内部细节
        return {"status": "ok"}
    details = await healthcheck_resources()
    return {"status": "ok", "version": "0.1.0", "env": settings.app_env, "services": details}


@app.get("/health", tags=["系统"])
async def health() -> dict:
    """根级健康检查端点。"""
    return await _health_payload()


@app.get("/api/v1/health", tags=["系统"], include_in_schema=False)
async def health_v1() -> dict:
    """契约兼容的 v1 健康检查端点。"""
    return await _health_payload()
