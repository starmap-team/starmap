"""质量监控 API。对应§7.4 图谱质量仪表盘。"""
from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.exceptions import QualityError, StarMapError
from app.models.extraction_models import ExtractionEvaluationRecord, JDExtractionRecord
from app.schemas.quality import (
    ComprehensiveReport,
    QualityDashboard,
    QualityDetail,
    QualityReport,
    ResumeEvalResponse,
)

router = APIRouter(prefix="/quality", tags=["质量监控"])





def _warning_level(f1: float, hallucination_rate: float, total_extractions: int = 0) -> str:
    if total_extractions == 0:
        return "gray"
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
        sa.func.count(JDExtractionRecord.id).filter(
            sa.and_(
                JDExtractionRecord.hallucination_score.isnot(None),
                JDExtractionRecord.hallucination_score > 0.5,
            )
        ),
    )
    total, pending, hallucinated = (await session.execute(extraction_counts_stmt)).one()
    total_extractions = int(total or 0)
    pending_review = int(pending or 0)
    hallucination_rate = (int(hallucinated or 0) / total_extractions) if total_extractions else 0.0

    report = QualityReport(
        precision=float(precision or 0.0),
        recall=float(recall or 0.0),
        f1=float(f1 or 0.0),
        warning_level=_warning_level(float(f1 or 0.0), hallucination_rate, total_extractions),
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
    # Count positions and skills from the database
    from app.models.extraction_models import PositionRecord, PositionSkillRelation, SkillRecord
    pos_count = (await session.execute(sa.select(sa.func.count()).select_from(PositionRecord))).scalar() or 0
    skill_count = (await session.execute(sa.select(sa.func.count()).select_from(SkillRecord))).scalar() or 0
    edge_count = (await session.execute(sa.select(sa.func.count()).select_from(PositionSkillRelation))).scalar() or 0

    # Compute average trust score from extraction confidence
    if total_extractions > 0:
        avg_confidence = (
            await session.execute(
                sa.select(
                    sa.func.coalesce(sa.func.avg(JDExtractionRecord.confidence), 0.0)
                ).where(JDExtractionRecord.confidence > 0)
            )
        ).scalar() or 0.0
    else:
        avg_confidence = 0.0

    # Also use skill source_count as trust proxy
    avg_source = (
        await session.execute(
            sa.select(sa.func.coalesce(sa.func.avg(SkillRecord.source_count), 0.0))
        )
    ).scalar() or 0.0
    source_trust = min(1.0, float(avg_source) / 10.0) if float(avg_source) > 0 else 0.0
    avg_trust = max(float(avg_confidence), source_trust)

    # Compute high trust ratio
    high_trust_count = 0
    if total_extractions > 0:
        high_trust_count = (
            await session.execute(
                sa.select(sa.func.count()).select_from(JDExtractionRecord).where(
                    JDExtractionRecord.confidence > 0.8
                )
            )
        ).scalar() or 0
    high_source_count = (
        await session.execute(
            sa.select(sa.func.count()).select_from(SkillRecord).where(SkillRecord.source_count >= 8)
        )
    ).scalar() or 0
    total_entity_count = total_extractions + int(pos_count) + int(skill_count)
    if total_entity_count > 0:
        high_trust_ratio = (high_trust_count + int(high_source_count)) / total_entity_count
    else:
        high_trust_ratio = 0.0

    # Generate trust distribution from skill source_counts
    trust_distribution = []
    trust_ranges = [
        ("0-20%", 0, 0.2), ("20-40%", 0.2, 0.4), ("40-60%", 0.4, 0.6),
        ("60-80%", 0.6, 0.8), ("80-100%", 0.8, 1.01),
    ]
    for label, lo, hi in trust_ranges:
        cnt_stmt = sa.select(sa.func.count()).select_from(SkillRecord).where(
            sa.and_(SkillRecord.source_count >= lo * 10, SkillRecord.source_count < hi * 10)
        )
        cnt = (await session.execute(cnt_stmt)).scalar() or 0
        trust_distribution.append({"range": label, "count": int(cnt)})

    # Build hallucination trend from skill_timeseries data (real data only)
    from app.repositories.quality_repo import fetch_hallucination_trend
    hallucination_trend = await fetch_hallucination_trend(session)

    # Generate source distribution from skill categories
    source_dist_stmt = (
        sa.select(SkillRecord.category, sa.func.count())
        .group_by(SkillRecord.category)
        .order_by(sa.func.count().desc())
        .limit(8)
    )
    source_rows = (await session.execute(source_dist_stmt)).all()
    source_distribution = [
        {"name": cat or "unknown", "count": int(cnt), "trust": round(avg_trust, 2)}
        for cat, cnt in source_rows
    ]

    # H9: weekly_new_nodes — count skills/positions created in the last 7 days
    from datetime import UTC, datetime, timedelta
    week_ago = datetime.now(UTC) - timedelta(days=7)
    weekly_new_skills = (
        await session.execute(
            sa.select(sa.func.count()).select_from(SkillRecord)
            .where(SkillRecord.first_detected_at >= week_ago)
        )
    ).scalar() or 0
    weekly_new_positions = (
        await session.execute(
            sa.select(sa.func.count()).select_from(PositionRecord)
            .where(PositionRecord.created_at >= week_ago)
        )
    ).scalar() or 0
    weekly_new_nodes = int(weekly_new_skills) + int(weekly_new_positions)

    # H9: audit_pass_rate — ratio of approved vs total reviewed extractions
    approved_count = (
        await session.execute(
            sa.select(sa.func.count()).select_from(JDExtractionRecord)
            .where(JDExtractionRecord.status == "completed")
        )
    ).scalar() or 0
    total_reviewed = approved_count + pending_review
    audit_pass_rate = (int(approved_count) / total_reviewed) if total_reviewed > 0 else 0.0

    # H11: audit_queue — low-trust records needing review (as list for frontend table)
    low_trust_records = (
        await session.execute(
            sa.select(JDExtractionRecord)
            .where(
                sa.and_(
                    JDExtractionRecord.confidence < 0.5,
                    JDExtractionRecord.status != "completed",
                )
            )
            .limit(20)
        )
    ).scalars().all()
    audit_queue = [
        {
            "id": int(r.id) if r.id is not None else 0,
            "position": r.job_title or "",
            "skill": "",
            "trust": int((r.confidence or 0) * 100),
        }
        for r in low_trust_records
    ]

    # Phase 13 一致性审计：评估基线可用性 — 无 golden-set 评估时 0/0/0 表示“未评估”而非“质量差”
    evaluation_count = int(
        (await session.execute(sa.select(sa.func.count()).select_from(ExtractionEvaluationRecord))).scalar() or 0
    )
    baseline_available = evaluation_count > 0
    if not baseline_available:
        evaluation_explanation = (
            "尚未运行 golden-set 评估（评估记录 0 条），precision/recall/F1 暂不可信；"
            "红色仅表示“未评估”，不代表抽取质量差。请触发一次评估（/quality/evaluate）以建立基线。"
        )
        report.warning_level = "gray"  # 顶层告警降级，避免误报红色
    else:
        evaluation_explanation = ""

    return QualityDashboard(
        report=report,
        total_nodes=int(pos_count) + int(skill_count),
        total_edges=int(edge_count),
        total_positions=int(pos_count),
        total_skills=int(skill_count),
        total_extractions=total_extractions,
        pending_review=pending_review,
        hallucination_rate=hallucination_rate,
        avg_trust_score=float(avg_trust),
        high_trust_ratio=float(high_trust_ratio),
        trust_distribution=trust_distribution,
        hallucination_trend=hallucination_trend,
        source_distribution=source_distribution,
        weekly_new_nodes=weekly_new_nodes,
        audit_pass_rate=round(audit_pass_rate, 4),
        audit_queue=audit_queue,
        evaluation_count=evaluation_count,
        baseline_available=baseline_available,
        evaluation_explanation=evaluation_explanation,
    )


@router.post("/evaluate")
async def evaluate_quality(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, object]:
    """触发质量评估流程：基于现有数据计算综合质量得分。"""
    # 1. 计算抽取记录的平均置信度
    avg_confidence = (
        await session.execute(
            sa.select(sa.func.avg(JDExtractionRecord.confidence))
            .where(JDExtractionRecord.status == "completed")
        )
    ).scalar() or 0.0

    # 2. 计算幻觉率
    avg_hallucination = (
        await session.execute(
            sa.select(sa.func.avg(JDExtractionRecord.hallucination_score))
            .where(JDExtractionRecord.hallucination_score.isnot(None))
        )
    ).scalar() or 0.0

    # 3. 计算总抽取数（QA B3）：不要只数 'completed'，要把 'pending_review' / 'approved'
    # 也算进来。Loop 写入路径并不把 status 立刻置为 'completed'，导致此前总被算成 0。
    total_extractions = (
        await session.execute(
            sa.select(sa.func.count()).select_from(JDExtractionRecord)
            .where(JDExtractionRecord.status.in_(["completed", "pending_review", "approved"]))
        )
    ).scalar() or 0

    # 4. 综合质量得分: confidence * (1 - hallucination_rate)
    score = float(avg_confidence) * (1.0 - float(avg_hallucination))
    score = round(min(1.0, max(0.0, score)), 4)

    return {
        "score": score,
        "avg_confidence": round(float(avg_confidence), 4),
        "hallucination_rate": round(float(avg_hallucination), 4),
        "total_extractions": int(total_extractions),
        "status": "pass" if score >= 0.75 else "warning" if score >= 0.60 else "fail",
    }


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


# ---------------------------------------------------------------------------
# Sprint 1.2 新增: 质量趋势时间线 + 异常告警
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Sprint 2.2: 简历抽取评估 + 综合质量报告
# ---------------------------------------------------------------------------




@router.post("/evaluate/resume", response_model=ResumeEvalResponse)
async def evaluate_resume_extraction(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ResumeEvalResponse:
    """简历抽取 F1 评估：基于 golden set 运行抽取并计算 precision/recall/F1。

    加载 data/resume_golden_set.json 中的黄金样本，运行简历抽取 pipeline，
    并与期望技能对比计算 F1 分数。

    x-audit-note: L3 — Internal API, no frontend consumer. Used by backend quality pipelines.
    """
    try:
        from app.services.resume_service import run_resume_evaluation

        result = await run_resume_evaluation()

        if not result.get("success"):
            return ResumeEvalResponse(
                success=False,
                error=result.get("error", "Evaluation failed"),
            )

        metrics = result["metrics"]
        f1 = metrics.get("f1", 0.0)
        hallucination_rate = 0.0  # Resume eval doesn't compute hallucination

        # Store evaluation results in DB for historical tracking
        try:
            for sample in metrics.get("per_sample", []):
                record = ExtractionEvaluationRecord(
                    golden_id=sample.get("sample_id", "unknown"),
                    precision=sample.get("precision", 0.0),
                    recall=sample.get("recall", 0.0),
                    f1_score=sample.get("f1", 0.0),
                    job_title_match=None,
                    experience_error=None,
                    education_match=None,
                )
                session.add(record)
            await session.commit()
        except QualityError as exc:
            logger.exception("Quality check failed: {}", exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except StarMapError:
            raise
        except Exception as exc:
            logger.exception("Unexpected error in quality: {}", exc)
            raise HTTPException(status_code=500, detail="è´¨éæ£æ¥å¼å¸¸") from exc

        return ResumeEvalResponse(
            success=True,
            total_samples=metrics.get("total_samples", 0),
            precision=metrics.get("precision", 0.0),
            recall=metrics.get("recall", 0.0),
            f1=f1,
            macro_f1=metrics.get("macro_f1", 0.0),
            warning_level=_warning_level(f1, hallucination_rate, metrics.get("total_samples", 0)),
            per_sample=metrics.get("per_sample", []),
            summary=metrics.get("summary", {}),
        )
    except FileNotFoundError:
        return ResumeEvalResponse(
            success=False,
            error="Golden set file not found: data/resume_golden_set.json",
        )
    except QualityError as exc:
        logger.exception("Quality check failed: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except StarMapError:
        raise
    except Exception as exc:
        # M3: 简历评估是非关键质检操作,任何失败降级为 success=False 的 200 响应,不抛 500。
        logger.warning("Resume evaluation failed, degrading to success=False: {}", exc)
        return ResumeEvalResponse(success=False, error=str(exc))


@router.get("/comprehensive-report", response_model=ComprehensiveReport)
async def get_comprehensive_report(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ComprehensiveReport:
    """综合质量报告：JD 质量 + 简历评估 + 图谱统计 + 改进建议。

    聚合以下维度数据：
    1. JD 抽取质量 (precision/recall/F1 from DB)
    2. 简历抽取质量 (from latest resume evaluation)
    3. 图谱统计 (positions, skills, edges)
    4. 综合评分与改进建议

    x-audit-note: L4 — Internal API, no frontend consumer. Used by backend quality pipelines.
    """
    # 1. Build JD quality report (reuse existing dashboard logic)
    dashboard = await _build_quality_dashboard(session)
    jd_report = dashboard.report

    # 2. Get latest resume evaluation from DB
    latest_resume_eval = (
        await session.execute(
            sa.select(ExtractionEvaluationRecord)
            .where(ExtractionEvaluationRecord.golden_id.like("resume_%"))
            .order_by(ExtractionEvaluationRecord.evaluated_at.desc())
            .limit(50)
        )
    ).scalars().all()

    if latest_resume_eval:
        avg_precision = sum(r.precision for r in latest_resume_eval) / len(latest_resume_eval)
        avg_recall = sum(r.recall for r in latest_resume_eval) / len(latest_resume_eval)
        avg_f1 = sum(r.f1_score for r in latest_resume_eval) / len(latest_resume_eval)
        resume_response = ResumeEvalResponse(
            success=True,
            total_samples=len(latest_resume_eval),
            precision=round(avg_precision, 4),
            recall=round(avg_recall, 4),
            f1=round(avg_f1, 4),
            warning_level=_warning_level(avg_f1, 0.0, len(latest_resume_eval)),
        )
    else:
        resume_response = ResumeEvalResponse(
            success=False,
            error="No resume evaluation data found. Run POST /quality/evaluate/resume first.",
        )

    # 3. Dashboard summary
    dashboard_summary = {
        "total_extractions": dashboard.total_extractions,
        "total_positions": dashboard.total_positions,
        "total_skills": dashboard.total_skills,
        "total_edges": dashboard.total_edges,
        "hallucination_rate": dashboard.hallucination_rate,
        "avg_trust_score": dashboard.avg_trust_score,
        "high_trust_ratio": dashboard.high_trust_ratio,
        "pending_review": dashboard.pending_review,
    }

    # 4. Overall score and recommendations
    scores = [jd_report.f1]
    if resume_response.success:
        scores.append(resume_response.f1)
    overall_score = sum(scores) / len(scores) if scores else 0.0

    # Determine overall status
    if overall_score >= 0.85:
        overall_status = "pass"
    elif overall_score >= 0.70:
        overall_status = "warning"
    elif overall_score > 0:
        overall_status = "fail"
    else:
        overall_status = "unknown"

    # Generate recommendations
    recommendations: list[str] = []
    if jd_report.precision < 0.80:
        recommendations.append(f"JD 抽取精度偏低 ({round(jd_report.precision, 2)}), 建议优化抽取 prompt 或增加 anti-hallucination 检查")
    if jd_report.recall < 0.80:
        recommendations.append(f"JD 抽取召回率偏低 ({round(jd_report.recall, 2)}), 建议检查技能归一化词表覆盖率")
    if dashboard.hallucination_rate > 0.10:
        recommendations.append(f"幻觉率偏高 ({dashboard.hallucination_rate:.1%}), 建议加强 LLM 输出验证规则")
    if dashboard.pending_review > 20:
        recommendations.append(f"待审核记录过多 ({dashboard.pending_review}), 建议优先处理审核队列")
    if not resume_response.success:
        recommendations.append("简历抽取评估未运行，请执行 POST /quality/evaluate/resume")
    elif resume_response.f1 < 0.70:
        recommendations.append(f"简历抽取 F1 偏低 ({round(resume_response.f1, 2)}), 建议增加 golden set 样本量并优化 prompt")
    if dashboard.total_skills < 100:
        recommendations.append(f"图谱技能数偏少 ({dashboard.total_skills}), 建议触发 pipeline run 采集真实数据")
    if not recommendations:
        recommendations.append("各项指标正常，质量体系运行良好")

    return ComprehensiveReport(
        jd_report=jd_report,
        resume_eval=resume_response,
        dashboard_summary=dashboard_summary,
        overall_score=round(overall_score, 4),
        overall_status=overall_status,
        recommendations=recommendations,
    )

# ── Sub-routers (Phase 7 quality domain split) ──
from app.api.v1.quality_trends_alerts import router as trends_alerts_router  # noqa: E402

router.include_router(trends_alerts_router, prefix="")
