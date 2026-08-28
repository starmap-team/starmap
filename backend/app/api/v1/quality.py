"""质量监控 API。对应§7.4 图谱质量仪表盘。"""
from __future__ import annotations

from datetime import timedelta
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db_session
from app.exceptions import QualityError, StarMapError
from app.models.extraction_models import (
    ExtractionEvaluationRecord,
    JDExtractionRecord,
    PositionRecord,
    SkillRecord,
)
from app.models.review_audit_log import ReviewAuditLog
from app.schemas.quality import (
    ComprehensiveReport,
    QualityDashboard,
    QualityDetail,
    QualityReport,
    ResumeEvalResponse,
)

router = APIRouter(prefix="/quality", tags=["质量监控"])





def _status(value: float, threshold: float) -> str:
    """值-阈值门禁 → pass/warn/fail。

    三态语义由 test_quality_service.py 锚定：
    - value >= threshold → "pass"
    - value >= threshold * 0.9 → "warn"（临界区）
    - 否则 → "fail"
    （此前该函数在重构中丢失，测试先行但实现缺失——HEAD 即 NameError 预存 bug）
    """
    if value >= threshold:
        return "pass"
    if value >= threshold * 0.9:
        return "warn"
    return "fail"


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
 # 2026-08-15 F1 优化: 取"最新一轮评估"而非全史平均 — 每次 /evaluate/resume
 # 追加记录，全史平均会被旧基线稀释（如 0.857→0.894→0.956 的历史混合）。
 # 以 max(evaluated_at) 前 5 秒窗口圈定最近一轮（同批记录微秒级差异）。
 # 2026-08-23 fix: scalar_subquery 在 asyncpg 手动事务下抛 InterfaceError，
 # 且表为空时 max() 返回 NULL → 比较恒 false。改为先查 max 再普通查询。
    _latest_ts = (await session.execute(
        sa.select(sa.func.max(ExtractionEvaluationRecord.evaluated_at))
    )).scalar()
    if _latest_ts is None:
        # 无任何评估记录: 指标归零,不抛错
        precision = recall = f1 = 0.0
    else:
        metrics_stmt = sa.select(
            sa.func.coalesce(sa.func.avg(ExtractionEvaluationRecord.precision), 0.0),
            sa.func.coalesce(sa.func.avg(ExtractionEvaluationRecord.recall), 0.0),
            sa.func.coalesce(sa.func.avg(ExtractionEvaluationRecord.f1_score), 0.0),
        ).where(ExtractionEvaluationRecord.evaluated_at >= _latest_ts - timedelta(seconds=5))
        precision, recall, f1 = (await session.execute(metrics_stmt)).one()

    extraction_counts_stmt = sa.select(
        sa.func.count(JDExtractionRecord.id),
        sa.func.count(JDExtractionRecord.id).filter(
            sa.and_(
                JDExtractionRecord.hallucination_score.isnot(None),
                JDExtractionRecord.hallucination_score > 0.5,
            )
        ),
    )
    pending_pos = (
        await session.execute(
            sa.select(sa.func.count())
            .select_from(PositionRecord)
            .where(PositionRecord.review_status == "pending_review")
        )
    ).scalar() or 0
    pending_skill = (
        await session.execute(
            sa.select(sa.func.count())
            .select_from(SkillRecord)
            .where(SkillRecord.review_status == "pending_review")
        )
    ).scalar() or 0
    total, hallucinated = (await session.execute(extraction_counts_stmt)).one()
    total_extractions = int(total or 0)
    pending_review = int(pending_pos or 0) + int(pending_skill or 0)
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
                threshold=settings.quality_hallucination_rate_threshold,
                status="pass" if hallucination_rate <= settings.quality_hallucination_rate_threshold else "fail",
            ),
        ],
    )
 # Count positions and skills from the database
    from app.models.extraction_models import PositionSkillRelation
    pos_count = (await session.execute(
        sa.select(sa.func.count()).select_from(PositionRecord)
        .where(PositionRecord.review_status == "approved")
    )).scalar() or 0
    skill_count = (await session.execute(sa.select(sa.func.count()).select_from(SkillRecord))).scalar() or 0
    edge_count = (await session.execute(sa.select(sa.func.count()).select_from(PositionSkillRelation))).scalar() or 0

 # avg_trust_score now comes from Neo4j Skill.trust_score via the
 # shared metrics module (routed through services layer). The previous
 # `max(extraction-conf, source-count/10)` blend was a different metric from
 # the admin overview's Neo4j avg, so the two pages disagreed.
    from app.services.quality_service import avg_skill_trust  # noqa: PLC0415
    avg_trust = await avg_skill_trust()

 # Compute high trust ratio
    high_trust_count = 0
    if total_extractions > 0:
        high_trust_count = (
            await session.execute(
                sa.select(sa.func.count()).select_from(JDExtractionRecord).where(
                    JDExtractionRecord.confidence > settings.quality_high_trust_confidence
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
    from app.services.quality_service import compute_trust_distribution  # noqa: PLC0415

    trust_distribution = await compute_trust_distribution(session)

 # Build hallucination trend from skill_timeseries data (real data only)
    from app.repositories.quality_repo import fetch_hallucination_trend
    hallucination_trend = await fetch_hallucination_trend(session)

 # 数据源贡献分布：真实数据源（jd_raw.source_site，status='extracted' 有效记录，
 # 排除 fixture_* 测试数据）
    source_dist_stmt = sa.text(
        "SELECT source_site, COUNT(*) AS cnt FROM jd_raw "
        "WHERE status = 'extracted' AND source_site NOT LIKE 'fixture\\_%' "
        "GROUP BY source_site ORDER BY cnt DESC LIMIT 8"
    )
    source_rows = (await session.execute(source_dist_stmt)).all()
    source_distribution = [
        {"name": site or "unknown", "count": int(cnt), "trust": 0.0}
        for site, cnt in source_rows
    ]

 # weekly_new_nodes now routes through the shared metrics module
 # (via services layer) so the Quality Dashboard and the Admin Overview use
 # the same SQL/date window. Previously this was trailing-7d while the admin
 # used week-start, which produced identical values mid-week but diverged at
 # week boundaries.
    from app.services.quality_service import weekly_new_nodes as fetch_weekly_new_nodes  # noqa: PLC0415
    weekly_new_nodes = (await fetch_weekly_new_nodes(session)).total

 # H9: audit_pass_rate — ratio of approved vs rejected REVIEW transitions.
 # 原实现把 JDExtractionRecord.status='completed'（抽取完成）当"审核通过"，
 # pending=0 时恒 100%（假正常）；审核权威数据在 review_audit_log（action: approve/reject）。
 # 改为从审核日志计算；无审核记录返回 0.0（未评估，诚实）。
    approved_count = (
        await session.execute(
            sa.select(sa.func.count()).select_from(ReviewAuditLog)
            .where(ReviewAuditLog.action == "approve")
        )
    ).scalar() or 0
    rejected_count = (
        await session.execute(
            sa.select(sa.func.count()).select_from(ReviewAuditLog)
            .where(ReviewAuditLog.action == "reject")
        )
    ).scalar() or 0
    total_reviewed = approved_count + rejected_count
    audit_pass_rate = (int(approved_count) / total_reviewed) if total_reviewed > 0 else 0.0

 # H11: audit_queue — 待审核记录（与 admin 内容审核同源：position_records + skill_records 的
 # pending_review）。修复前查 JDExtractionRecord（全 completed → 队列恒空），与实际审核流
 # 脱节；现对齐 review_service 状态机（），队列内容与 /admin/review-items 一致。
    pos_rows = (
        await session.execute(
            sa.select(PositionRecord.id, PositionRecord.name)
            .where(PositionRecord.review_status == "pending_review")
            .order_by(PositionRecord.submitted_at.asc().nulls_last())
            .limit(10)
        )
    ).all()
    skill_rows = (
        await session.execute(
            sa.select(SkillRecord.id, SkillRecord.name, SkillRecord.source_count)
            .where(SkillRecord.review_status == "pending_review")
            .order_by(SkillRecord.submitted_at.asc().nulls_last())
            .limit(10)
        )
    ).all()
    audit_queue = [
        {
            "id": str(r.id),
            "entity_type": "position",
            "entity_id": str(r.id),
            "position": r.name or "",
            "skill": "",
            # 2026-08-20 (debug 修复 Q3): 原硬编码 trust=0 → 前端渲染红色 0% 进度条，
            # 所有待审岗位像"全被标红"。岗位无信任度概念（信任度属于技能），置 null
            # 前端显示"未评估"。
            "trust": None,
            "review_status": "pending_review",
        }
        for r in pos_rows
    ]
    audit_queue += [
        {
            "id": str(r.id),
            "entity_type": "skill",
            "entity_id": str(r.id),
            "position": "",
            "skill": r.name or "",
            # 2026-08-20 (debug 修复 Q3): 原 source_count/10*100 把"来源数"当"信任度"
            # （两个不同概念）。信任度应查 Neo4j trust_score；待审技能可能未投影，
            # 诚实置 null 前端显示"未评估"。
            "trust": None,
            "review_status": "pending_review",
        }
        for r in skill_rows
    ]
 # 队列上限 20 条（岗位 + 技能合计）
    audit_queue = audit_queue[:20]

    evaluation_count = int(
        (await session.execute(sa.select(sa.func.count()).select_from(ExtractionEvaluationRecord))).scalar() or 0
    )
    baseline_available = evaluation_count > 0
    if not baseline_available:
        evaluation_explanation = (
            "尚未运行 golden-set 评估（评估记录 0 条），precision/recall/F1 暂不可信；"
            "红色仅表示“未评估”，不代表抽取质量差。"
 # 2026-08-14 规范驱动改进 : 文案指向真实写入端点。
 # /quality/evaluate 仅只读算分，不写 ExtractionEvaluationRecord；
 # 建立基线需提供 backend/data/resume_golden_set.json 后调用
 # /quality/evaluate/resume（golden set 缺失时返回 No golden samples found）。
            "建立基线需提供 resume golden set 后调用 /quality/evaluate/resume。"
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
        hallucination_numerator=int(hallucinated or 0),
        hallucination_denominator=total_extractions,
        hallucination_window_days=30,
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
) -> QualityReport:
    """质量报告：总节点数、平均信任度、幻觉率、待审核数。"""
    dashboard = await _build_quality_dashboard(session)
    return dashboard.report


@router.get("/dashboard", response_model=QualityDashboard)
async def get_quality_dashboard(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> QualityDashboard:
    """前端质量仪表盘：报告摘要 + 抽取/审核/幻觉统计。"""
    return await _build_quality_dashboard(session)


# ---------------------------------------------------------------------------
# 新增: 质量趋势时间线 + 异常告警
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# : 简历抽取评估 + 综合质量报告
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


# ── 数据质量区 (批2 可持续, 2026-08-28) ──
# 共识计划 AC4: 图内岗位数(Neo4j) / PG全量 / 隐藏数(no_skills+非IT) / 未分类 / 重名组。
# 口径: 隐藏按 quality_hint∈{no_skills}+industry非IT 计; 未分类按 industry 三态;
#       两者正交可重叠, 不违反「图内+隐藏=PG全量」恒等。
@router.get("/data-quality")
async def get_data_quality(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, int]:
    """岗位数据质量计数（图内/PG全量/隐藏/未分类/重名组）。"""
    from sqlalchemy import func

    from app.core.extraction.industry_gate import IT_INDUSTRY_WHITELIST

    # PG 全量 approved 岗位
    pg_total = int(
        (
            await session.execute(
                sa.select(func.count()).select_from(PositionRecord).where(
                    PositionRecord.review_status == "approved"
                )
            )
        ).scalar()
        or 0
    )
    # 隐藏数: quality_hint=no_skills 或 industry 非 IT（approved 内）
    hidden_no_skill = int(
        (
            await session.execute(
                sa.select(func.count()).select_from(PositionRecord).where(
                    PositionRecord.review_status == "approved",
                    PositionRecord.quality_hint == "no_skills",
                )
            )
        ).scalar()
        or 0
    )
    hidden_non_it = int(
        (
            await session.execute(
                sa.select(func.count()).select_from(PositionRecord).where(
                    PositionRecord.review_status == "approved",
                    PositionRecord.industry.is_not(None),
                    PositionRecord.industry.not_in(IT_INDUSTRY_WHITELIST),
                )
            )
        ).scalar()
        or 0
    )
    hidden_total = hidden_no_skill + hidden_non_it
    # 未分类: industry 三态（approved 内）
    unclassified = int(
        (
            await session.execute(
                sa.select(func.count()).select_from(PositionRecord).where(
                    PositionRecord.review_status == "approved",
                    PositionRecord.industry.in_((None, "", "未分类")),
                )
            )
        ).scalar()
        or 0
    )
    # 重名组: name_cn 分组 count>1
    dup_groups = int(
        (
            await session.execute(
                sa.select(func.count())
                .select_from(
                    sa.select(PositionRecord.name_cn)
                    .where(
                        PositionRecord.name_cn.is_not(None),
                        PositionRecord.name_cn != "",
                    )
                    .group_by(PositionRecord.name_cn)
                    .having(func.count() > 1)
                    .subquery()
                )
            )
        ).scalar()
        or 0
    )
    # 图内岗位数 = PG 全量 - 隐藏（Neo4j 投影 = approved 且非隐藏）
    graph_total = max(pg_total - hidden_total, 0)
    return {
        "graph_positions": graph_total,
        "pg_positions": pg_total,
        "hidden_positions": hidden_total,
        "hidden_no_skill": hidden_no_skill,
        "hidden_non_it": hidden_non_it,
        "unclassified": unclassified,
        "duplicate_groups": dup_groups,
    }

# ── Sub-routers ( quality domain split) ──
from app.api.v1.quality_trends_alerts import router as trends_alerts_router  # noqa: E402

router.include_router(trends_alerts_router, prefix="")
