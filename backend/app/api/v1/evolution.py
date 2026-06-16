"""演化分析 API（占位）。对应§5.2 能力更新 + §7.3 岗位演进，W7-W8 流B 实现。"""
from fastapi import APIRouter

router = APIRouter(prefix="/evolution", tags=["演化分析"])


@router.get("/trends")
async def get_trends():
    """技能热度趋势、岗位变迁时间线、新兴岗位预警（§8.3 演化看板）。"""
    return {"items": []}


@router.post("/analyze")
async def analyze_evolution():
    """触发演化分析流程。"""
    return {"message": "TODO"}
