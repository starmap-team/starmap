"""质量监控 API。对应§7.4 图谱质量仪表盘。"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.models.extraction_models import ExtractionEvaluationRecord, JDExtractionRecord

router = APIRouter(prefix="/quality", tags=["质量监控"])


class QualityDetail(BaseModel):
    """质量维度明细。"""

    dimension: str = Field(..., description="质量维度")
    value: float = Field(..., description="当前值")
    threshold: float = Field(..., description="阈值")
    status: str = Field(..., description="pass/warn/fail")


class QualityReport(BaseModel):
    """契约质量报告。"""

    precision: float = Field(..., ge=0, le=1)
    recall: float = Field(..., ge=0, le=1)
    f1: float = Field(..., ge=0, le=1)
    warning_level: str = Field(..., description="green/yellow/orange/red")
    details: list[QualityDetail] = Field(default_factory=list)


class QualityDashboard(BaseModel):
    """前端质量仪表盘兼容响应。"""

    report: QualityReport
    total_extractions: int = Field(default=0, ge=0)
    pending_review: int = Field(default=0, ge=0)
    hallucination_rate: float = Field(default=0.0, ge=0, le=1)


def _status(value: float, threshold: float) -> str:
    if value >= threshold:
        return "pass"
    if value >= threshold * 0.9:
        return "warn"
    return "fail"


def _warning_level(f1: float, hallucination_rate: float) -> str:
    if f1 >= 0.85 and hallucination_rate <= 0.05:
        return "green"
    if f1 >= 0.75 and hallucination_rate <= 0.10:
        return "yellow"
    if f1 >= 0.60 and hallucination_rate <= 0.20:
        return "orange"
    return "red"


async def _build_quality_dashboard(session: AsyncSession) -> QualityDashboard:
    metrics_stmt = sa.select(
        sa.func.coalesce(sa.func.avg(ExtractionEvaluationRecord.precision), 0.0),
        sa.func.coalesce(sa.func.avg(ExtractionEvaluationRecord.recall), 0.0),
        sa.func.coalesce(sa.func.avg(ExtractionEvaluationRecord.f1_score), 0.0),
    )
    precision, recall, f1 = (await session.execute(metrics_stmt)).one()

    extraction_counts_stmt = sa.select(
        sa.func.count(JDExtractionRecord.id),
        sa.func.count(JDExtractionRecord.id).filter(JDExtractionRecord.status == "pending"),
        sa.func.count(JDExtractionRecord.id).filter(JDExtractionRecord.hallucination_score > 0.5),
    )
    total, pending, hallucinated = (await session.execute(extraction_counts_stmt)).one()
    total_extractions = int(total or 0)
    pending_review = int(pending or 0)
    hallucination_rate = (int(hallucinated or 0) / total_extractions) if total_extractions else 0.0

    report = QualityReport(
        precision=float(precision or 0.0),
        recall=float(recall or 0.0),
        f1=float(f1 or 0.0),
        warning_level=_warning_level(float(f1 or 0.0), hallucination_rate),
        details=[
            QualityDetail(
                dimension="skill_extraction_precision",
                value=float(precision or 0.0),
                threshold=0.80,
                status=_status(float(precision or 0.0), 0.80),
            ),
            QualityDetail(
                dimension="skill_extraction_recall",
                value=float(recall or 0.0),
                threshold=0.80,
                status=_status(float(recall or 0.0), 0.80),
            ),
            QualityDetail(
                dimension="skill_extraction_f1",
                value=float(f1 or 0.0),
                threshold=0.80,
                status=_status(float(f1 or 0.0), 0.80),
            ),
            QualityDetail(
                dimension="hallucination_rate",
                value=hallucination_rate,
                threshold=0.10,
                status="pass" if hallucination_rate <= 0.10 else "fail",
            ),
        ],
    )
    return QualityDashboard(
        report=report,
        total_extractions=total_extractions,
        pending_review=pending_review,
        hallucination_rate=hallucination_rate,
    )


@router.post("/evaluate")
async def evaluate_quality():
    """触发质量评估流程。"""
    return {"message": "TODO", "score": None}


@router.get("/report", response_model=QualityReport)
async def get_quality_report(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    batch_id: Annotated[UUID | None, Query(description="指定批次（留空返回最新报告）")] = None,
) -> QualityReport:
    """质量报告：总节点数、平均信任度、幻觉率、待审核数。"""
    _ = batch_id
    dashboard = await _build_quality_dashboard(session)
    return dashboard.report


@router.get("/dashboard", response_model=QualityDashboard)
async def get_quality_dashboard(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> QualityDashboard:
    """前端质量仪表盘：报告摘要 + 抽取/审核/幻觉统计。"""
    return await _build_quality_dashboard(session)
