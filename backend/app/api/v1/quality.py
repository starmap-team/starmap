"""质量监控 API（占位）。对应§7.4 图谱质量仪表盘，W9-W10 流C 对接。"""
from fastapi import APIRouter

router = APIRouter(prefix="/quality", tags=["质量监控"])


@router.post("/evaluate")
async def evaluate_quality():
    """触发质量评估流程。"""
    return {"message": "TODO", "score": None}


@router.get("/report")
async def get_quality_report():
    """质量报告：总节点数、平均信任度、幻觉率、待审核数。"""
    return {"total_nodes": 0, "avg_trust": 0.0, "hallucination_rate": 0.0, "pending_review": 0}
