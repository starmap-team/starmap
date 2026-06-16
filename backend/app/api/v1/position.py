"""岗位管理 API。"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/positions", tags=["岗位管理"])


@router.get(
    "/",
    summary="岗位列表",
    description="阶段2骨架接口。后续接入图谱/关系数据库查询。",
)
async def list_positions():
    return {"items": []}


@router.post("/discover", summary="触发岗位发现流程")
async def discover_position():
    return {"message": "TODO"}
