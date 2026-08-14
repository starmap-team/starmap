"""FastAPI 应用入口。"""

from __future__ import annotations

import asyncio
import sys
import time
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.api.v1.router import api_router, auth_router
from app.config import settings
from app.core.security.client_ip import resolve_client_ip
from app.core.validation.errors import ErrorCode
from app.dependencies import get_current_user
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
    # CONCERN 2.3 (reliability audit 2026-08-15): log the effective rate-limit
    # knobs at startup so operators can verify staging/prod parity without
    # inspecting env vars. ``rate_limit_storage`` reports which backend will
    # serve the counters ("redis" if a Redis client is attached, else "memory").
    _rate_limit_storage = (
        "redis" if getattr(app.state.resources, "redis_client", None) is not None
        else "memory"
    )
    logger.info(
        "RateLimitMiddleware active: rate_limit_max={} rate_limit_window={}s "
        "rate_limit_storage={}",
        settings.rate_limit_max,
        settings.rate_limit_window,
        _rate_limit_storage,
    )
    # 2026-08-08: 启动时把 prompt_versions 表（管理后台注册的自定义版本/活跃选择）
    # 合并进内存注册表，避免重启丢失（此前仅存进程内存）
    if resources.pg_sessionmaker is not None:
        try:
            from sqlalchemy import select as _sel

            from app.core.extraction.prompt import apply_custom_prompt_versions
            from app.models.prompt_version import PromptVersion

            async with resources.pg_sessionmaker() as _session:
                rows = (await _session.execute(_sel(PromptVersion))).scalars().all()
            apply_custom_prompt_versions(
                [(r.prompt_name, r.version, r.content, r.is_active) for r in rows]
            )
            if rows:
                logger.info("Loaded {} custom prompt version(s) from DB", len(rows))
        except Exception as exc:  # noqa: BLE001 — 加载失败不阻断启动（降级为内置版本）
            logger.warning("[lifespan] Prompt versions load failed, using builtin: {}", exc)
    # Phase 10 PIPE-03 (c) D-03: 启动时若 PIPELINE_BOOTSTRAP=true,30 秒后入队一次 pipeline run
    # 该调用是 no-op（直接 return）如果环境变量未设置
    from app.core.pipeline.bootstrap import schedule_bootstrap_if_enabled

    schedule_bootstrap_if_enabled()
    # Phase 2 CRON-03: 启动 cron scanner 后台任务
    cron_task = None
    try:
        from app.core.pipeline.cron_scheduler import cron_scanner_loop

        cron_task = asyncio.create_task(cron_scanner_loop(interval_seconds=60))
        logger.info("Cron scanner loop started")
        yield
    finally:
        # 2026-08-14 门禁修复: shutdown 尽力而为 — 测试 teardown 中 TestClient
        # 关停时事件循环可能已关闭（resources/task 由早前测试在其他 loop 创建）
        # → await 抛 `'NoneType' object has no attribute 'send'`（flaky ERROR）。
        # 任何关闭失败降级为 warning，不阻断 shutdown。
        # （2026-08-07 起 cron cancel 后必须 await 带超时，否则 uvicorn --reload
        #   无限等待 → 该语义保留。）
        try:
            if cron_task is not None:
                cron_task.cancel()
                try:
                    await asyncio.wait_for(cron_task, timeout=5.0)
                except (TimeoutError, asyncio.CancelledError):
                    logger.warning("Cron scanner task did not stop within 5s (forced shutdown)")
                logger.info("Cron scanner loop stopped")
            try:
                await resources.close()
            except Exception as exc:  # noqa: BLE001 — 资源关闭尽力而为
                logger.warning("StarMap 关闭资源失败(非致命): {}", exc)
            logger.info("StarMap 关闭中...")
        except Exception as exc:  # noqa: BLE001 — 事件循环已关等 shutdown 竞态
            logger.warning("StarMap shutdown 异常(非致命): {}", exc)


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
# CONCERN 1.2 (security audit 2026-08-15): refuse startup if `cors_origins`
# is the wildcard `["*"]` while credentials are enabled — that combination
# is a CSRF-grade hole that Starlette does NOT silently reject for FastAPI's
# CORSMiddleware on every version, and human operators occasionally set it
# during debugging. Fail-fast at startup is the safer path.
_ALLOW_CREDENTIALS = True
if _ALLOW_CREDENTIALS and settings.cors_origins == ["*"]:
    raise ValueError(
        "CORS misconfiguration: cors_origins=['*'] is not allowed when "
        "allow_credentials=True. Set CORS_ALLOWED_ORIGINS to explicit "
        "origins (e.g. CORS_ALLOWED_ORIGINS=https://yourdomain.com)."
    )
logger.info(
    "CORS allow_origins in effect ({} entries): {}",
    len(settings.cors_origins),
    settings.cors_origins,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "Accept", "X-Requested-With"],
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

# P1 修复 (API-02): 速率限制中间件
# ponytail: Redis-backed fixed-window counter when available, in-memory fallback.
# In-memory is per-process only — Redis makes it work across workers.
# 窗口/阈值来自 settings（rate_limit_window / rate_limit_max），支持运行时调整。
# P0-AUDIT-FIX (2026-08-13): INCR + EXPIRE 两条命令间进程崩溃会留下无过期
# 时间的死键 → 该 IP 永久封禁。用 Lua 脚本在 Redis 内原子完成
# "INCR 后首次创建时设置窗口过期"，任意一步失败都不会留下死键。
_RATE_LIMIT_INCR_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""
_rate_buckets: dict[str, list[float]] = defaultdict(list)

# Phase 3.7: 高频端点白名单 — 这些是只读状态接口，不计入严格限流
# 只对 mutation 类（POST/PUT/DELETE）应用严格限制
_RATE_LIMIT_EXEMPT_PATH_PATTERNS = (
    "/api/v1/auth/me",             # 用户态每次请求都触发
    "/api/v1/auth/refresh",        # token 刷新
    "/api/v1/pipeline/status",
    "/api/v1/pipeline/stages",
    "/api/v1/pipeline/data-quality",
    "/api/v1/pipeline/datasources",
    "/api/v1/pipeline/schedules",
    "/api/v1/pipeline/config",
    "/api/v1/pipeline/events",      # SSE 长连接，不计入限流
    "/api/v1/pipeline/events-poll", # SSE 轮询 fallback
    "/api/v1/pipeline/realtime",    # 备用 SSE 端点
    "/api/v1/dashboard/realtime",   # Dashboard SSE
    "/api/v1/dashboard/realtime-poll",  # D8e: Dashboard SSE 轮询 fallback（高频）
)


def _is_rate_limit_exempt(path: str) -> bool:
    """只读状态查询端点不限流（高频轮询场景）。"""
    return any(path.startswith(p) for p in _RATE_LIMIT_EXEMPT_PATH_PATTERNS)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        client_ip = resolve_client_ip(request)
        path = request.url.path

        # Phase 3.7: 只读查询端点直接放行（不计入限流）
        if _is_rate_limit_exempt(path):
            return await call_next(request)

        # Try Redis-backed rate limit first (works across workers)
        # P1-10 fix (functional-review 2026-08-13): 属性名此前写成 "redis"，
        # 而 AppResources 的属性是 redis_client → getattr 恒 None → Redis 分支
        # 永不执行，跨 worker 限流失效（多进程下限流阈值放大 N 倍），专门写的
        # Lua 原子脚本成为死代码。修正为 redis_client。
        redis = getattr(request.app.state, "resources", None)
        redis_client = getattr(redis, "redis_client", None) if redis else None
        if redis_client:
            key = f"ratelimit:{client_ip}"
            try:
                count = await redis_client.eval(
                    _RATE_LIMIT_INCR_SCRIPT, 1, key, settings.rate_limit_window
                )
                if count > settings.rate_limit_max:
                    # CONCERN 1.8 (security audit 2026-08-15): rate-limit
                    # audit must NEVER break the 429 response. If the
                    # audit_log sink (loguru/Redis/DB persist) raises for
                    # any reason — Redis down mid-flight, structured-log
                    # failure, etc — fall back to a WARNING log and still
                    # return the rate-limit response to the client.
                    try:
                        audit_log(
                            AuditEntry(
                                event=AuditEvent.RATE_LIMITED,
                                actor=client_ip,
                                action=f"{request.method} {path}",
                                detail=(
                                    f"Exceeded {settings.rate_limit_max} "
                                    f"req/{settings.rate_limit_window}s (Redis)"
                                ),
                                ip=client_ip,
                            )
                        )
                    except Exception as audit_exc:  # noqa: BLE001
                        logger.warning(
                            "Rate-limit audit sink failed (Redis path); "
                            "suppressing audit but enforcing 429: {}",
                            audit_exc,
                        )
                    return JSONResponse(
                        status_code=429,
                        content={
                            "detail": "请求过于频繁，请稍后重试",
                            "code": ErrorCode.SYS_RATE_LIMITED.value,
                        },
                        headers={"Retry-After": str(settings.rate_limit_window)},
                    )
                return await call_next(request)
            except Exception:
                pass  # ponytail: Redis down → fall through to in-memory

        # In-memory fallback (per-process only)
        now = time.time()
        bucket = _rate_buckets[client_ip]
        _rate_buckets[client_ip] = [t for t in bucket if now - t < settings.rate_limit_window]
        # P2-2 fix: 定期清理整个内存限流桶中过期的 IP 条目，防止 dict 无限增长
        if len(_rate_buckets) > 10000:
            stale_keys = [k for k, v in _rate_buckets.items() if not v or now - v[-1] > settings.rate_limit_window]
            for k in stale_keys:
                del _rate_buckets[k]
        if len(_rate_buckets[client_ip]) >= settings.rate_limit_max:
            # CONCERN 1.8: same defence-in-depth as the Redis path —
            # audit failure must not block the 429 response.
            try:
                audit_log(
                    AuditEntry(
                        event=AuditEvent.RATE_LIMITED,
                        actor=client_ip,
                        action=f"{request.method} {path}",
                        detail=(
                            f"Exceeded {settings.rate_limit_max} "
                            f"req/{settings.rate_limit_window}s (in-memory)"
                        ),
                        ip=client_ip,
                    )
                )
            except Exception as audit_exc:  # noqa: BLE001
                logger.warning(
                    "Rate-limit audit sink failed (in-memory path); "
                    "suppressing audit but enforcing 429: {}",
                    audit_exc,
                )
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={"Retry-After": str(settings.rate_limit_window)},
            )
        _rate_buckets[client_ip].append(now)
        return await call_next(request)


app.add_middleware(RateLimitMiddleware)

app.include_router(api_router, prefix="/api/v1")
# Auth routes don't require authentication (login endpoint)
app.include_router(auth_router, prefix="/api/v1")


# ── 统一错误处理：域异常 + 校验异常 → 结构化 ErrorResponse ──
from fastapi.exceptions import RequestValidationError  # noqa: E402

from app.core.validation import (  # noqa: E402
    build_error_response,
)
from app.core.validation.handler import request_validation_exception_handler  # noqa: E402
from app.exceptions import (  # noqa: E402
    DashboardError,
    ExtractionError,
    ExtractionLLMError,
    GraphProjectionError,
    JudgeError,
    LearningPathError,
    MatchingError,
    PipelineError,
    PipelineTimeoutError,
    PlanNotFoundError,
    PlanOwnershipError,
    PositionNotFoundError,
    QualityError,
    RunAlreadyTerminalError,
    RunNotFoundError,
    StarMapError,
)

# ── FastAPI 请求体验证异常 (422) → 统一 ErrorResponse + field-level errors ──
# 必须在域异常之前注册，否则 FastAPI 默认 handler 会接管
app.add_exception_handler(RequestValidationError, request_validation_exception_handler)  # type: ignore[arg-type]


# ── 裸 raise HTTPException → 统一 ErrorResponse ──
# 路由层存在大量 `raise HTTPException(...)`（此前落入 FastAPI 默认 handler，
# 响应缺少 code/timestamp）。这里按 status 映射到 ErrorCode，一次性统一。
_HTTP_STATUS_TO_ERROR_CODE: dict[int, ErrorCode] = {
    status.HTTP_400_BAD_REQUEST: ErrorCode.VALIDATION_BODY_PARSE_ERROR,
    status.HTTP_401_UNAUTHORIZED: ErrorCode.AUTH_INVALID_CREDENTIALS,
    status.HTTP_403_FORBIDDEN: ErrorCode.AUTH_FORBIDDEN,
    status.HTTP_404_NOT_FOUND: ErrorCode.RES_NOT_FOUND,
    status.HTTP_405_METHOD_NOT_ALLOWED: ErrorCode.VALIDATION_ERROR,
    status.HTTP_409_CONFLICT: ErrorCode.RES_CONFLICT,
    status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorCode.VALIDATION_ERROR,
    status.HTTP_429_TOO_MANY_REQUESTS: ErrorCode.SYS_RATE_LIMITED,
    status.HTTP_500_INTERNAL_SERVER_ERROR: ErrorCode.SYS_INTERNAL_ERROR,
    status.HTTP_503_SERVICE_UNAVAILABLE: ErrorCode.SYS_SERVICE_UNAVAILABLE,
}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """裸 raise HTTPException → 统一 {detail, code, timestamp, fields?} 格式。"""
    code = _HTTP_STATUS_TO_ERROR_CODE.get(exc.status_code, ErrorCode.SYS_INTERNAL_ERROR)
    return build_error_response(str(exc.detail), code, status_code=exc.status_code)


# Starlette 对 404/405 使用独立的状态处理器（优先于类处理器），需显式覆盖
app.add_exception_handler(404, http_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(405, http_exception_handler)  # type: ignore[arg-type]


# ── 域异常 → 结构化 ErrorResponse ──

@app.exception_handler(PositionNotFoundError)
async def position_not_found_handler(request: Request, exc: PositionNotFoundError) -> JSONResponse:
    return build_error_response(str(exc), ErrorCode.BIZ_POSITION_NOT_FOUND)


@app.exception_handler(PlanNotFoundError)
async def plan_not_found_handler(request: Request, exc: PlanNotFoundError) -> JSONResponse:
    return build_error_response(str(exc), ErrorCode.BIZ_PLAN_NOT_FOUND)


@app.exception_handler(PlanOwnershipError)
async def plan_ownership_handler(request: Request, exc: PlanOwnershipError) -> JSONResponse:
    return build_error_response(str(exc), ErrorCode.BIZ_PLAN_OWNERSHIP)


@app.exception_handler(RunNotFoundError)
async def run_not_found_handler(request: Request, exc: RunNotFoundError) -> JSONResponse:
    return build_error_response(str(exc), ErrorCode.BIZ_RUN_NOT_FOUND)


@app.exception_handler(RunAlreadyTerminalError)
async def run_already_terminal_handler(request: Request, exc: RunAlreadyTerminalError) -> JSONResponse:
    return build_error_response(str(exc), ErrorCode.BIZ_RUN_TERMINAL)


@app.exception_handler(StarMapError)
async def starmap_error_handler(request: Request, exc: StarMapError) -> JSONResponse:
    logger.opt(exception=True).error("Domain error on {} {}: {}", request.method, request.url.path, exc)
    return build_error_response(
        "内部处理异常，请稍后重试",
        ErrorCode.SYS_INTERNAL_ERROR,
        include_internal_detail=str(exc),
    )


# M17: Global exception handler — catches unhandled exceptions, logs them,
# and returns a generic 500 without leaking internals.
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.opt(exception=True).error("Unhandled exception on {} {}: {}", request.method, request.url.path, exc)
    return build_error_response(
        "服务器内部错误，请稍后重试",
        ErrorCode.SYS_INTERNAL_ERROR,
        include_internal_detail=str(exc),
    )


@app.exception_handler(PipelineError)
async def pipeline_error_handler(request: Request, exc: PipelineError) -> JSONResponse:
    logger.opt(exception=True).error("Pipeline error on stage '{}': {}", exc.stage, exc)
    code = ErrorCode.BIZ_PIPELINE_STAGE_FAILED if not isinstance(exc, PipelineTimeoutError) else ErrorCode.BIZ_PIPELINE_TIMEOUT
    return build_error_response(str(exc), code, include_internal_detail=str(exc))


@app.exception_handler(ExtractionError)
async def extraction_error_handler(request: Request, exc: ExtractionError) -> JSONResponse:
    logger.opt(exception=True).error("Extraction error from '{}': {}", exc.source, exc)
    code = ErrorCode.BIZ_EXTRACTION_LLM_UNAVAILABLE if isinstance(exc, ExtractionLLMError) else ErrorCode.BIZ_EXTRACTION_NORMALIZATION
    return build_error_response(str(exc), code, include_internal_detail=str(exc))


@app.exception_handler(MatchingError)
async def matching_error_handler(request: Request, exc: MatchingError) -> JSONResponse:
    logger.opt(exception=True).error("Matching error for '{}': {}", exc.position_id, exc)
    return build_error_response(str(exc), ErrorCode.BIZ_MATCH_ERROR, include_internal_detail=str(exc))


@app.exception_handler(JudgeError)
async def judge_error_handler(request: Request, exc: JudgeError) -> JSONResponse:
    logger.opt(exception=True).error("Judge error: {}", exc)
    return build_error_response(str(exc), ErrorCode.BIZ_JUDGE_FAILED, include_internal_detail=str(exc))


@app.exception_handler(LearningPathError)
async def learning_path_error_handler(request: Request, exc: LearningPathError) -> JSONResponse:
    logger.opt(exception=True).error("Learning path error: {}", exc)
    return build_error_response(str(exc), ErrorCode.BIZ_LEARNING_PATH_FAILED, include_internal_detail=str(exc))


@app.exception_handler(QualityError)
async def quality_error_handler(request: Request, exc: QualityError) -> JSONResponse:
    logger.opt(exception=True).error("Quality check error: {}", exc)
    return build_error_response(str(exc), ErrorCode.BIZ_QUALITY_CHECK_FAILED, include_internal_detail=str(exc))


@app.exception_handler(DashboardError)
async def dashboard_error_handler(request: Request, exc: DashboardError) -> JSONResponse:
    logger.opt(exception=True).error("Dashboard error: {}", exc)
    return build_error_response(str(exc), ErrorCode.BIZ_DASHBOARD_ERROR, include_internal_detail=str(exc))


@app.exception_handler(GraphProjectionError)
async def graph_projection_error_handler(request: Request, exc: GraphProjectionError) -> JSONResponse:
    logger.opt(exception=True).error("Graph projection error: {}", exc)
    return build_error_response(str(exc), ErrorCode.BIZ_GRAPH_PROJECTION_FAILED, include_internal_detail=str(exc))


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


@app.get("/ready", tags=["系统"], response_model=None)
@app.get("/api/v1/ready", tags=["系统"], include_in_schema=False, response_model=None)
async def ready() -> dict[str, Any] | JSONResponse:
    """Readiness probe — returns 200 only when the app is fully bootstrapped."""
    checks: dict[str, str] = {}

    # DB ping
    db_ok = False
    try:
        from sqlalchemy import text as _text

        if resources.pg_engine is not None:
            async with resources.pg_engine.begin() as conn:
                db_ok = (await conn.execute(_text("SELECT 1"))).scalar() == 1
        checks["postgres"] = "ok" if db_ok else "unreachable"
    except Exception as exc:
        checks["postgres"] = f"error: {exc}"

    # users table populated
    users_ok = False
    try:
        if resources.pg_engine is not None:
            from sqlalchemy import text as _text

            async with resources.pg_engine.begin() as conn:
                cnt = (await conn.execute(_text("SELECT COUNT(*) FROM users"))).scalar()
                users_ok = (cnt or 0) >= 1
        checks["users_seeded"] = "ok" if users_ok else "no users"
    except Exception as exc:
        checks["users_seeded"] = f"error: {exc}"

    # alembic migration applied
    alembic_ok = False
    try:
        if resources.pg_engine is not None:
            from sqlalchemy import text as _text

            async with resources.pg_engine.begin() as conn:
                alembic_ok = (
                    await conn.execute(_text("SELECT version_num FROM alembic_version LIMIT 1"))
                ).scalar() is not None
        checks["alembic"] = "ok" if alembic_ok else "no migration record"
    except Exception as exc:
        checks["alembic"] = f"error: {exc}"

    if resources.redis_client is not None:
        try:
            checks["redis"] = "ok" if await resources.redis_client.ping() else "ping failed"
        except Exception as exc:
            checks["redis"] = f"error: {exc}"
    else:
        checks["redis"] = "not initialised"

    all_ok = all(v == "ok" for v in checks.values() if v != "not initialised")
    # LOG-04 fix: 生产环境不暴露内部服务细节和错误消息
    if _is_prod:
        payload: dict[str, object] = {"status": "ready" if all_ok else "not_ready"}
    else:
        payload = {"status": "ready" if all_ok else "not_ready", "checks": checks}
    if not all_ok:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=503, content=payload)
    return payload


# D-05/CFG-04: 详细健康检查 — 4 服务 ping + 3 LLM key 布尔（不泄露值）+ data stats


async def _detailed_health_payload() -> dict:
    """详细健康检查：服务 ping + LLM key 配置布尔 + data stats。

    生产环境也返回完整详情（per D-05；与现有 /health 一致无 auth 保护）。
    """
    services = await healthcheck_resources()

    # llm_keys: 仅返回布尔，永不返回 key 值（T-08-05 信息泄露防护）
    llm_keys = {
        "mimo": bool(settings.mimo_api_key),
        "deepseek": bool(settings.deepseek_api_key),
        "xunfei": bool(settings.xunfei_api_key),
    }

    # data_stats: 查询业务数据量概览（替代旧的 seed 检测逻辑）
    data_stats: dict[str, Any] = {"positions": 0, "skills": 0, "pipeline_runs": 0}
    if resources.pg_engine is not None:
        try:
            async with resources.pg_engine.begin() as conn:
                pos = await conn.execute(text("SELECT COUNT(*) FROM position_records"))
                positions = pos.scalar() or 0
                skl = await conn.execute(text("SELECT COUNT(*) FROM skill_records"))
                skills = skl.scalar() or 0
                runs = await conn.execute(text("SELECT COUNT(*) FROM pipeline_runs"))
                runs_count = runs.scalar() or 0
                data_stats = {
                    "positions": int(positions),
                    "skills": int(skills),
                    "pipeline_runs": int(runs_count),
                }
        except Exception as exc:  # pragma: no cover - defensive runtime check
            logger.warning("data_stats health query failed: {}", exc)

    return {
        "services": services,
        "llm_keys": llm_keys,
        "data_stats": data_stats,
        "demo_data": {
            "review_queue_seeded": data_stats["positions"] > 0,
            "pipeline_runs_count": data_stats["pipeline_runs"],
        },
    }


@app.get("/health/detail", tags=["系统"], dependencies=[Depends(get_current_user)])
async def health_detail() -> dict:
    """详细健康检查端点：服务状态 + LLM key 配置布尔 + demo 数据指示。"""
    return await _detailed_health_payload()


@app.get("/api/v1/health/detail", tags=["系统"], include_in_schema=False, dependencies=[Depends(get_current_user)])
async def health_detail_v1() -> dict:
    """契约兼容的 v1 详细健康检查端点。"""
    return await _detailed_health_payload()
