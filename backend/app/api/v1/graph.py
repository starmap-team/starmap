"""图谱查询 API。"""
from __future__ import annotations

from fastapi import APIRouter, Query

router = APIRouter(prefix="/graph", tags=["图谱查询"])


@router.get(
    "/query",
    summary="图谱查询",
    description="阶段2骨架接口。后续由图谱查询服务返回 AntV G6 nodes/edges。",
)
async def graph_query(
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
    "/position/{position_id}/skills",
    summary="岗位技能矩阵",
    description="阶段3前的占位接口。",
)
async def get_position_skills(position_id: str):
    return {"message": "TODO", "position_id": position_id, "skills": []}
