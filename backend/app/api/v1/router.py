"""API v1 路由聚合。

每个业务模块一个路由文件，全部挂在 /api/v1 前缀下。
模块对应文档 §3.1 L7 交互层与 §8.2 后端结构。
"""
from fastapi import APIRouter

from app.api.v1 import admin, evolution, extract, graph, match, position, quality, resume

api_router = APIRouter()
api_router.include_router(graph.router, tags=["图谱查询"])
api_router.include_router(position.router, tags=["岗位管理"])
api_router.include_router(match.router, tags=["匹配诊断"])
api_router.include_router(evolution.router, tags=["演化分析"])
api_router.include_router(resume.router, tags=["简历解析"])
api_router.include_router(quality.router, tags=["质量监控"])
api_router.include_router(extract.router, tags=["信息抽取"])
api_router.include_router(admin.router, tags=["管理后台"])
