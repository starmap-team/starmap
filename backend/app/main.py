"""FastAPI 应用入口。"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.v1.router import api_router
from app.config import settings
from app.services.resources import healthcheck_resources, init_resources, resources


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化连接，关闭时释放。"""
    logger.info("StarMap 启动中... env={}", settings.app_env)
    app.state.resources = await init_resources()
    try:
        yield
    finally:
        await resources.close()
        logger.info("StarMap 关闭中...")


app = FastAPI(
    title="星图 StarMap API",
    description="人才能力星云导航系统 - 后端 API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


async def _health_payload() -> dict:
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
