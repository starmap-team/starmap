"""数据流水线监控 API — 子路由聚合入口（ Task 7）。

：routes.py 瘦身为聚合入口（< 300 行），按领域拆 6 个子路由：
status / runs / trigger / schedule / config / events。
外部 import 路径保持不变：``from app.api.v1.pipeline import router``。
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.pipeline.config_routes import router as _config_router
from app.api.v1.pipeline.runs_routes import router as _runs_router
from app.api.v1.pipeline.schedule_routes import router as _schedule_router
from app.api.v1.pipeline.status_routes import router as _status_router
from app.api.v1.pipeline.trigger_routes import router as _trigger_router

# NOTE: events_routes 不在此聚合 — 它挂到独立的 events_router
# (app.api.v1.router.events_router), 避免被 api_router 全局 get_current_user
# 拦截(SSE 用 query token 鉴权, 全局依赖只认 Bearer header)。

router = APIRouter(prefix="/pipeline", tags=["数据流水线"])

router.include_router(_status_router)
router.include_router(_runs_router)
router.include_router(_trigger_router)
router.include_router(_schedule_router)
router.include_router(_config_router)

__all__ = ["router"]
