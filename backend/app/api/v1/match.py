"""匹配诊断 API（占位）。对应模块D（§5.4）、匹配引擎（§6.3），W9-W10 流B 实现。"""
from fastapi import APIRouter

router = APIRouter(prefix="/match", tags=["匹配诊断"])


@router.post("/position")
async def match_position(target_position: str):
    """匹配诊断主接口：简历技能 → 目标岗位对比 → 差距 + 学习路径。"""
    return {"message": "TODO", "match_score": None}


@router.get("/result/{match_id}")
async def get_match_result(match_id: str):
    """获取匹配诊断结果详情。"""
    return {"message": "TODO", "match_id": match_id}
