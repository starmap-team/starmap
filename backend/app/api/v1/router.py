"""API v1 路由聚合。

每个业务模块一个路由文件，全部挂在 /api/v1 前缀下。
模块对应文档 §3.1 L7 交互层与 §8.2 后端结构。

P0 修复 (AUTH-01): api_router 层统一添加 get_current_user 依赖，
所有端点默认需要认证；admin 子路由额外叠加 require_admin。
"""
from fastapi import APIRouter, Depends

from app.api.v1 import (
    admin,
    admin_data_truth,
    admin_users,
    auth,
    dashboard,
    evolution,
    extract,
    graph,
    health_monitor,
    import_jd,
    judge,
    learning,
    loop,
    match,
    pipeline,
    position,
    quality,
    resume,
)
from app.api.v1.datasource import admin_router as datasource_admin_router
from app.api.v1.datasource import router as datasource_router
from app.api.v1.position import admin_router as position_admin_router
from app.dependencies import get_current_user

# Auth router 不需要认证依赖（登录端点本身不需要 token）
auth_router = APIRouter()
auth_router.include_router(auth.router)

# SSE 事件流 router：不受 api_router 全局 get_current_user 拦截。
# SSE 端点用 query token 鉴权（EventSource 无法设 header），由端点自身
# 的 get_current_user_sse 处理；若挂在 api_router 下，router 级
# get_current_user(只认 Bearer) 会在 production 先抛 401，query token 永不生效。
events_router = APIRouter(prefix="/pipeline")
from app.api.v1.pipeline.events_routes import router as _events_router  # noqa: E402

events_router.include_router(_events_router)
# 2026-08-25 (BUG#D1): dashboard SSE 端点（/dashboard/realtime + /realtime-poll）
# 从 api_router 移出 —— 全局 get_current_user(只认 Bearer) 会先于
# get_current_user_sse 抛 401，EventSource query token 永不生效。
# 独立 router 由 main.py 以 /api/v1 前缀挂载（不经 api_router 认证），
# 由端点自身的 get_current_user_sse 处理 query token / Bearer。
dashboard_sse_router = APIRouter()
from app.api.v1.dashboard import sse_router as _dashboard_sse_router  # noqa: E402

dashboard_sse_router.include_router(_dashboard_sse_router)

api_router = APIRouter(dependencies=[Depends(get_current_user)])
api_router.include_router(graph.router, tags=["图谱查询"])
api_router.include_router(position.router, tags=["岗位管理"])
api_router.include_router(position_admin_router, tags=["岗位管理"])
api_router.include_router(match.router, tags=["匹配诊断"])
api_router.include_router(evolution.router, tags=["演化分析"])
api_router.include_router(resume.router, tags=["简历解析"])
api_router.include_router(quality.router, tags=["质量监控"])
api_router.include_router(extract.router, tags=["信息抽取"])
api_router.include_router(admin.router, tags=["管理后台"])
api_router.include_router(admin_users.router)
api_router.include_router(admin_data_truth.router, tags=["数据源诊断"])
api_router.include_router(judge.router, tags=["Judge 评估"])
api_router.include_router(pipeline.router, tags=["数据流水线"])
api_router.include_router(datasource_router, tags=["数据源管理"])
api_router.include_router(datasource_admin_router, tags=["数据源管理"])
api_router.include_router(loop.router, tags=["闭环验证"])
api_router.include_router(learning.router, tags=["学习中心"])
api_router.include_router(dashboard.router, tags=["数据大屏"])
api_router.include_router(import_jd.router, tags=["JD 导入 (Phase 15)"])
api_router.include_router(health_monitor.router, tags=["健康度监控 (Phase 15-04)"])
