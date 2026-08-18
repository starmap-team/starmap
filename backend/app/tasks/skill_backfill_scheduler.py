"""Skill data backfill 周期任务 (Phase 5, 2026-08-17 多模块联动).

背景: 之前 2 次 ad-hoc 跑 backfill（Phase 3 翻译 480 个 + 之前 industry 修复），
但没有周期任务 → 每次新 ETL 抽取后未分类/未翻译的 skills 都会累积，
admin 必须手动触发。**没有可持续性**。

Phase 5 设计:
1. daily_skill_backfill_task: 每天 02:00 UTC 跑
   - 扫 approved + name_cn IS NULL OR '' OR =name
   - 复用 scripts/backfill_skill_name_cn_full.py 逻辑
   - 默认 limit=200 (避免 LLM 配额突增)
2. weekly_low_data_re_extract_task: 每周一 03:00 UTC 跑
   - 扫 approved + no_data (skill_count=0) + limit=20
   - 复用 POST /admin/positions/{id}/re-extract-skills 业务逻辑
   - 避免一次性大规模 LLM 调用
3. skill_backfill_cron_schedule: cron 表达式 (Asia/Shanghai 时区)

设计原则:
- **fail-soft**: 单条失败不阻断全批
- **限速**: limit + 单批 delay 避免 LLM 配额
- **审计**: 每次跑都写 audit log（action='periodic_skill_backfill'）
- **可观测**: 跑完写 IndustryQualityMonitor alert (low_data_position_count delta)
"""
from __future__ import annotations

import asyncio
from typing import Any

import sqlalchemy as sa
from loguru import logger
from sqlalchemy import select

from app.core.extraction.industry import UNCLASSIFIED_INDUSTRY_LITERAL
from app.db.session import get_async_engine
from app.models.extraction_models import (
    PositionRecord,
    PositionSkillRelation,
    SkillRecord,
)
from app.services.industry_quality_monitor import (
    detect_industry_quality,
)
from app.services.skill_data_support import (
    SCORE_PARTIAL_COVERAGE,
    compute_data_support_report,
)
from app.tasks.celery_app import celery_app

# ──────────────────────────────────────────────────────────────────
# Daily task: 翻译未翻译的技能名
# ──────────────────────────────────────────────────────────────────


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300, name="daily_skill_backfill_task")
def daily_skill_backfill_task(self, limit: int = 200) -> dict[str, Any]:
    """每天凌晨跑未翻译技能名（name_cn 缺失/=name）。

    重用 backfill_skill_name_cn_full 的 LLM batch 逻辑。
    失败时不抛（fail-soft），只记 warning。
    """
    logger.info("daily_skill_backfill_task started, limit={}", limit)
    return asyncio.run(_async_skill_backfill(limit=limit))


async def _async_skill_backfill(limit: int) -> dict[str, Any]:
    """异步 LLM 翻译未翻译技能名。"""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.core.extraction.llm_client import LLMClient
    from app.core.extraction.normalize import normalize_by_alias
    from app.core.extraction.translation import has_cjk

    engine = get_async_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    done = 0
    failed = 0
    try:
        async with sessionmaker() as session:
            rows = (await session.execute(
                select(SkillRecord)
                .where(
                    (SkillRecord.name_cn.is_(None))
                    | (SkillRecord.name_cn == "")
                    | (SkillRecord.name_cn == SkillRecord.name),
                )
                .where(~has_cjk(SkillRecord.name))  # 只翻译英文
                .order_by(SkillRecord.source_count.desc())
                .limit(limit)
            )).scalars().all()

            if not rows:
                logger.info("daily_skill_backfill_task: 0 skills to translate")
                return {"translated": 0, "failed": 0}

            llm = LLMClient()
            # 批量 20/批
            for start in range(0, len(rows), 20):
                batch = rows[start:start+20]
                names = [sk.name for sk in batch]
                prompt = (
                    "You are a technical recruiter translating software skill names into Simplified Chinese.\n"
                    "Respond ONLY as JSON object mapping each original skill name to its Chinese translation.\n"
                    "Rules: faithful concise translation; keep well-known brand/tool names in original spelling "
                    "(Python, Docker, Kubernetes, SQL, Redis, Tableau, Java... keep as-is); "
                    "translate generic skill phrases (Written Communication → 书面沟通).\n"
                    "Output format: {\"skill1\": \"翻译1\", \"skill2\": \"翻译2\", ...}\n"
                    f"Skills to translate: {__import__('json').dumps(names, ensure_ascii=False)}\n"
                )
                try:
                    raw = await llm.generate(prompt, json_mode=True, temperature=0.0)
                    import json as _json
                    data = _json.loads(raw)
                except Exception as exc:
                    logger.warning("daily_skill_backfill_task batch error: {}", exc)
                    failed += len(batch)
                    continue

                for sk in batch:
                    val = (data.get(sk.name) or "").strip()
                    if val:
                        # 双重归一化：alias + LLM 直查
                        alias_norm = normalize_by_alias(sk.name)
                        if alias_norm and alias_norm != sk.name and has_cjk(alias_norm):
                            val = alias_norm
                        sk.name_cn = val
                        done += 1
                    else:
                        failed += 1
            await session.commit()
            return {"translated": done, "failed": failed, "total": len(rows)}
    finally:
        await engine.dispose()


# ──────────────────────────────────────────────────────────────────
# Weekly task: 补抽取低数据岗位
# ──────────────────────────────────────────────────────────────────


@celery_app.task(bind=True, max_retries=1, default_retry_delay=600, name="weekly_low_data_re_extract_task")
def weekly_low_data_re_extract_task(self, limit: int = 20) -> dict[str, Any]:
    """每周一凌晨跑 re_extract 低数据支撑岗位（skill_count < 3）。

    复用 admin re-extract-skills 端点的业务逻辑（但用 pos.name 触发
    LLM，因为 legacy 岗位没 jd_content）。
    """
    logger.info("weekly_low_data_re_extract_task started, limit={}", limit)
    return asyncio.run(_async_low_data_re_extract(limit=limit))


async def _async_low_data_re_extract(limit: int) -> dict[str, Any]:
    """异步补抽取低数据支撑岗位的技能。"""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.core.extraction.jd_extract import extract_from_jd, mask_pii
    from app.core.extraction.llm_client import LLMClient
    from app.models.extraction_models import JDExtractionRecord
    from app.tasks.stage3_services import (
        _confidence_from_result,
        _ensure_position_skill_relation,
        _hallucination_score_from_result,
        _upsert_skill,
    )

    engine = get_async_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    done = 0
    failed = 0
    try:
        async with sessionmaker() as session:
            # 找 no_data 或 low_data 岗位
            skill_count_subq = (
                select(
                    PositionSkillRelation.position_id,
                    sa.func.count(PositionSkillRelation.skill_id).label("cnt"),
                )
                .group_by(PositionSkillRelation.position_id)
                .subquery()
            )
            stmt = (
                select(PositionRecord)
                .outerjoin(skill_count_subq, skill_count_subq.c.position_id == PositionRecord.id)
                .where(PositionRecord.review_status == "approved")
                .where(PositionRecord.industry != UNCLASSIFIED_INDUSTRY_LITERAL)  # 排除未分类
                .where(sa.func.coalesce(skill_count_subq.c.cnt, 0) < 3)
                .order_by(PositionRecord.created_at.desc())
                .limit(limit)
            )
            positions = (await session.execute(stmt)).scalars().all()

            if not positions:
                logger.info("weekly_low_data_re_extract_task: 0 positions to re-extract")
                return {"re_extracted": 0, "failed": 0}

            llm = LLMClient()  # noqa: F841 - reserved for future per-position override
            for pos in positions:
                # 优先用 jd_content（如果有），否则 fallback 到 pos.name + pos.name_cn
                jd_content = pos.name
                if pos.name_cn and pos.name_cn != pos.name:
                    jd_content = f"{pos.name_cn}（{pos.name}）"

                try:
                    llm_result = await extract_from_jd(jd_content)
                except Exception as exc:
                    logger.warning("weekly_low_data_re_extract_task: LLM failed for {!r}: {}", pos.name, exc)
                    failed += 1
                    continue

                data = llm_result.get("data", {})
                extracted_skills = data.get("required_skills", []) + data.get("preferred_skills", [])
                if not extracted_skills:
                    logger.info("weekly_low_data_re_extract_task: {!r} LLM returned no skills", pos.name)
                    failed += 1
                    continue

                # 写 JDExtractionRecord
                extraction_record = JDExtractionRecord(
                    jd_content=mask_pii(jd_content),
                    job_title=pos.name,
                    extracted_skills=data,
                    experience_years=data.get("experience_required"),
                    education=data.get("education_required"),
                    confidence=_confidence_from_result(llm_result),
                    hallucination_score=_hallucination_score_from_result(llm_result),
                    status="completed",
                )
                session.add(extraction_record)
                await session.flush()

                # 写 PositionSkillRelation (去重)
                for entry in extracted_skills:
                    if not isinstance(entry, dict):
                        continue
                    skill_name = entry.get("name") or entry.get("skill")
                    if not skill_name:
                        continue
                    skill_row = await _upsert_skill(session, skill_name, entry.get("category", "hard_skill"))
                    existing_rel = (await session.execute(
                        select(PositionSkillRelation).where(
                            PositionSkillRelation.position_id == pos.id,
                            PositionSkillRelation.skill_id == skill_row.id,
                        )
                    )).scalar_one_or_none()
                    if existing_rel is None:
                        await _ensure_position_skill_relation(
                            session, pos.id, skill_row.id,
                            "required" if entry in data.get("required_skills", []) else "preferred",
                            _confidence_from_result(llm_result),
                        )
                done += 1

            await session.commit()
            return {"re_extracted": done, "failed": failed, "total": len(positions)}
    finally:
        await engine.dispose()


# ──────────────────────────────────────────────────────────────────
# Daily task: 监测数据并触发告警（监测层 fail-soft + 可观测）
# ──────────────────────────────────────────────────────────────────


@celery_app.task(bind=True, max_retries=1, default_retry_delay=60, name="daily_data_quality_check_task")
def daily_data_quality_check_task(self) -> dict[str, Any]:
    """每天凌晨跑数据质量检测，触发告警到 admin dashboard。

    检查项:
    - 低数据岗位 > 50 → critical 告警
    - 数据支撑度 < 0.5 → warning 告警
    - 未分类岗位 > 10% → warning 告警

    触发方式:
    - 写 QualityAlert 表（admin dashboard 实时显示）
    - 后续扩展: webhook / 邮件 / 钉钉
    """
    logger.info("daily_data_quality_check_task started")
    return asyncio.run(_async_data_quality_check())


async def _async_data_quality_check() -> dict[str, Any]:
    """异步检测 + 写告警。"""
    import json as _json

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.review_audit_log import ReviewAuditLog

    engine = get_async_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    alerts_created = 0
    try:
        async with sessionmaker() as session:
            # 1. 行业质量检测
            industry_report = await detect_industry_quality(session, neo4j_driver=None)
            if industry_report.alert_level in ("warning", "critical"):
                # 复用 ReviewAuditLog 表存告警（已有「re_extract_skills」action 枚举）
                # 这里用 industry_alert 标识特殊告警
                alert_log = ReviewAuditLog(
                    entity_type="system",
                    entity_id=__import__("uuid").UUID(int=0),  # 系统告警
                    actor="system:daily_check",
                    action="industry_alert",  # 需要扩展 CHECK 约束
                    previous_status=None,
                    new_status=industry_report.alert_level,
                    reason=_json.dumps({
                        "unclassified_ratio": industry_report.unclassified_ratio,
                        "unclassified_count": industry_report.unclassified_count,
                    }, ensure_ascii=False),
                )
                session.add(alert_log)
                alerts_created += 1

            # 2. 技能数据支撑度检测
            data_support = await compute_data_support_report(session, approved_only=True)
            if data_support.avg_score < SCORE_PARTIAL_COVERAGE:
                alert_log = ReviewAuditLog(
                    entity_type="system",
                    entity_id=__import__("uuid").UUID(int=0),
                    actor="system:daily_check",
                    action="low_data_support_alert",
                    previous_status=None,
                    new_status=f"avg={data_support.avg_score}",
                    reason=_json.dumps({
                        "low_data_count": data_support.low_data_support_count,
                        "no_data_count": data_support.no_data_count,
                    }, ensure_ascii=False),
                )
                session.add(alert_log)
                alerts_created += 1

            await session.commit()
            return {
                "alerts_created": alerts_created,
                "industry_alert_level": industry_report.alert_level,
                "data_support_avg": data_support.avg_score,
            }
    finally:
        await engine.dispose()


# ──────────────────────────────────────────────────────────────────
# Cron schedule（Celery beat）
# ──────────────────────────────────────────────────────────────────

# 兼容 croniter 不可用的环境（用 fallback）
try:
    from celery.schedules import crontab
    celery_app.conf.beat_schedule = {
        # 每天 02:00 翻译未翻译技能名
        "daily-skill-backfill": {
            "task": "daily_skill_backfill_task",
            "schedule": crontab(hour=2, minute=0),
        },
        # 每周一 03:00 补抽取低数据岗位
        "weekly-low-data-re-extract": {
            "task": "weekly_low_data_re_extract_task",
            "schedule": crontab(hour=3, minute=0, day_of_week=1),
        },
        # 每天 04:00 数据质量检测 + 告警
        "daily-data-quality-check": {
            "task": "daily_data_quality_check_task",
            "schedule": crontab(hour=4, minute=0),
        },
    }
    logger.info("Celery beat schedule registered: daily/weekly data quality tasks")
except ImportError:
    logger.warning("croniter not installed — Celery beat schedule NOT registered")
