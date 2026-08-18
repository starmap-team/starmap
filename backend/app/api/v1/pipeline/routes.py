"""数据流水线监控 API — 子路由聚合入口（ Task 7）。

：routes.py 瘦身为聚合入口（< 300 行），按领域拆 6 个子路由：
status / runs / trigger / schedule / config / events。
外部 import 路径保持不变：``from app.api.v1.pipeline import router``。
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.pipeline.config_routes import router as _config_router
from app.api.v1.pipeline.events_routes import router as _events_router # noqa: E402,F401
from app.api.v1.pipeline.runs_routes import router as _runs_router
from app.api.v1.pipeline.schedule_routes import router as _schedule_router
from app.api.v1.pipeline.status_routes import router as _status_router
from app.api.v1.pipeline.trigger_routes import router as _trigger_router

router = APIRouter(prefix="/pipeline", tags=["数据流水线"])

router.include_router(_status_router)
router.include_router(_runs_router)
router.include_router(_trigger_router)
router.include_router(_schedule_router)
router.include_router(_config_router)
router.include_router(_events_router)

__all__ = ["router"]
