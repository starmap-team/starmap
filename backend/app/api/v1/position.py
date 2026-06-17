"""岗位管理 API。"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/positions", tags=["岗位管理"])


class SkillNode(BaseModel):
    """岗位所需技能骨架。"""

    skill_id: str = Field(..., description="技能唯一标识")
    name: str = Field(..., description="技能名称")
    category: str = Field(..., description="技能分类")
    confidence: float = Field(default=1.0, ge=0, le=1, description="置信度")
    source_count: int = Field(default=0, ge=0, description="来源文档计数")


class PositionNode(BaseModel):
    """契约中的 PositionNode。"""

    position_id: str = Field(..., description="岗位唯一标识")
    name: str = Field(..., description="岗位名称")
    industry: str = Field(..., description="所属行业")
    description: str = Field(..., description="岗位描述")
    skills_required: list[SkillNode] = Field(default_factory=list, description="岗位所需技能")
    discovered_at: str | None = Field(default=None, description="发现时间")


class PositionListResponse(BaseModel):
    """岗位列表响应。"""

    items: list[PositionNode] = Field(default_factory=list, description="岗位列表")
    total: int = Field(default=0, ge=0, description="岗位总数")
    page: int = Field(default=1, ge=1, description="当前页")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")


@router.get(
    "",
    summary="岗位列表",
    description="阶段2骨架接口。返回岗位列表响应结构，阶段3接入图谱/关系数据库查询。",
    response_model=PositionListResponse,
)
async def list_positions(
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 20,
    industry: Annotated[str | None, Query(description="行业筛选")] = None,
    search: Annotated[str | None, Query(description="搜索关键词")] = None,
) -> PositionListResponse:
    _ = (industry, search)
    return PositionListResponse(page=page, page_size=page_size)


@router.get(
    "/{position_id}",
    summary="岗位详情",
    description="阶段3前的占位接口。",
)
async def get_position(position_id: str):
    return {"message": "TODO", "position_id": position_id}


@router.post("/discover", summary="触发岗位发现流程")
async def discover_position():
    return {"message": "TODO"}
