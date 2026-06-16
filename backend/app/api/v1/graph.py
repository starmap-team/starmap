"""图谱查询 API。"""
from __future__ import annotations

from fastapi import APIRouter, Query

router = APIRouter(prefix="/graph", tags=["图谱查询"])


@router.get(
    "/panorama",
    summary="全景图谱",
    description="阶段2骨架接口。后续由图谱查询服务返回 AntV G6 nodes/edges。",
)
async def get_panorama(
    tech_stack: str | None = Query(default=None, description="技术栈筛选"),
    level: str | None = Query(default=None, description="岗位级别筛选"),
):
    return {
        "message": "TODO",
        "filters": {"tech_stack": tech_stack, "level": level},
        "nodes": [],
        "edges": [],
    }


@router.get(
    "/position/{position_name}",
    summary="岗位详情",
    description="阶段3前的占位接口。",
)
async def get_position_detail(position_name: str):
    return {"message": "TODO", "position": position_name}
