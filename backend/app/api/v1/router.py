"""API v1 路由聚合。

每个业务模块一个路由文件，全部挂在 /api/v1 前缀下。
模块对应文档 §3.1 L7 交互层与 §8.2 后端结构。
"""
from fastapi import APIRouter

from app.api.v1 import admin, dashboard, datasource, evolution, extract, graph, judge, learning, loop, match, pipeline, position, quality, resume

api_router = APIRouter()
api_router.include_router(graph.router, tags=["图谱查询"])
api_router.include_router(position.router, tags=["岗位管理"])
api_router.include_router(match.router, tags=["匹配诊断"])
api_router.include_router(evolution.router, tags=["演化分析"])
api_router.include_router(resume.router, tags=["简历解析"])
api_router.include_router(quality.router, tags=["质量监控"])
api_router.include_router(extract.router, tags=["信息抽取"])
api_router.include_router(admin.router, tags=["管理后台"])
api_router.include_router(judge.router, tags=["Judge 评估"])
api_router.include_router(pipeline.router, tags=["数据流水线"])
api_router.include_router(datasource.router, tags=["数据源管理"])
api_router.include_router(loop.router, tags=["闭环验证"])
api_router.include_router(learning.router, tags=["学习中心"])
api_router.include_router(dashboard.router, tags=["数据大屏"])
