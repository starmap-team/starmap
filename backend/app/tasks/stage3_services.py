"""Stage 3 task services for extraction, graph ingestion, and evolution analysis."""
from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa
from loguru import logger
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.extraction.graph_writer import (
    GraphConfig,
    batch_write_extractions,
    skill_entry_category,
    skill_entry_name,
)
from app.core.extraction.jd_extract import extract_from_jd, mask_pii
from app.db.session import get_async_engine
from app.exceptions import StarMapError
from app.models.extraction_models import (
    JDExtractionRecord,
    PositionRecord,
    PositionSkillRelation,
    SkillRecord,
)


def _confidence_from_result(result: dict[str, Any]) -> float:
    validation = result.get("validation") or {}
    return float(validation.get("confidence") or 0.85)


def _hallucination_score_from_result(result: dict[str, Any]) -> float | None:
    validation = result.get("validation") or {}
    if validation.get("is_valid", True):
        return 0.0
    confidence = float(validation.get("confidence") or 0.0)
    return round(1.0 - confidence, 4)


async def _upsert_position(
    session: AsyncSession,
    name: str,
    *,
    source_run_id: uuid.UUID | None = None,
    name_cn: str | None = None,
) -> PositionRecord:
    existing = (
        await session.execute(sa.select(PositionRecord).where(PositionRecord.name == name))
    ).scalar_one_or_none()
    if existing is not None:
        # D8f fix: 抽取 I18N-01 翻译结果曾丢弃（306 岗位仅 3 中文名根因）——
        # 已存在岗位若有新翻译结果也回填，避免重复翻译
        if name_cn and not (existing.name_cn or "").strip():
            existing.name_cn = name_cn
            await session.flush()
        return existing

    record = PositionRecord(
        name=name,
        name_cn=name_cn,  # D8f: 抽取时持久化 I18N-01 翻译结果
        source_run_id=source_run_id,
        created_by="system:pipeline",
    )
    session.add(record)
    await session.flush()
    return record


async def _upsert_skill(session: AsyncSession, name: str, category: str, *, source_run_id: uuid.UUID | None = None) -> SkillRecord:
    existing = (
        await session.execute(sa.select(SkillRecord).where(SkillRecord.name == name))
    ).scalar_one_or_none()
    if existing is not None:
        existing.source_count += 1
        existing.category = existing.category or category
        return existing

    record = SkillRecord(
        name=name,
        category=category,
        source_count=1,
        source_run_id=source_run_id,
        created_by="system:pipeline",
    )
    session.add(record)
    await session.flush()
    return record


async def _ensure_position_skill_relation(
    session: AsyncSession,
    position_id: Any,
    skill_id: Any,
    requirement_type: str,
    confidence: float,
) -> None:
    existing = (
        await session.execute(
            sa.select(PositionSkillRelation).where(
                PositionSkillRelation.position_id == position_id,
                PositionSkillRelation.skill_id == skill_id,
                PositionSkillRelation.requirement_type == requirement_type,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.confidence = max(float(existing.confidence or 0.0), confidence)
        return

    session.add(
        PositionSkillRelation(
            position_id=position_id,
            skill_id=skill_id,
            requirement_type=requirement_type,
            confidence=confidence,
        )
    )


async def persist_extraction_result(
    session: AsyncSession,
    jd_content: str,
    extraction_result: dict[str, Any],
    *,
    job_title: str | None = None,
    source_run_id: uuid.UUID | None = None,
) -> tuple[JDExtractionRecord, str, dict[str, str]]:
    """Persist a successful extraction and update relational evolution source tables.

    Returns (record, position_id, skill_ids) — position_id 与 {skill_name: id} 供
    write_single_extraction_to_graph 穿线 canonical_id（C-1 根治：图节点写库即带 id）。
    """
    data = extraction_result["data"]
    # D5 fix (2026-08-12): LLM 未返回 position_name 时回退到 JD 标题（管线 import 已传
    # job_title），不再落 "Unknown Position" 占位符 —— 该占位符曾产生 103 条幻影关系
    # 污染 PG SSOT 且无图对应（双库不一致根因之一）。
    position_name = str(data.get("position_name") or job_title or "").strip()
    if not position_name:
        position_name = "Unknown Position"
    confidence = _confidence_from_result(extraction_result)
    record = JDExtractionRecord(
        jd_content=mask_pii(jd_content),
        job_title=position_name,
        extracted_skills=data,
        experience_years=data.get("experience_required"),
        education=data.get("education_required"),
        confidence=confidence,
        hallucination_score=_hallucination_score_from_result(extraction_result),
        status="completed",
    )
    session.add(record)
    await session.flush()

    position = await _upsert_position(
        session,
        position_name,
        source_run_id=source_run_id,
        name_cn=data.get("name_cn"),  # D8f: I18N-01 翻译结果持久化
    )
    skill_ids: dict[str, str] = {}
    for requirement_type, entries in (
        ("required", data.get("required_skills", [])),
        ("preferred", data.get("preferred_skills", [])),
    ):
        for entry in entries:
            skill_name = skill_entry_name(entry)
            if not skill_name:
                continue
            skill = await _upsert_skill(session, skill_name, skill_entry_category(entry, default="general"), source_run_id=source_run_id)
            skill_ids[skill_name] = str(skill.id)
            await _ensure_position_skill_relation(
                session,
                position.id,
                skill.id,
                requirement_type,
                confidence,
            )

    return record, str(position.id), skill_ids


async def _load_source_counts(sessionmaker: async_sessionmaker) -> dict[str, int]:
    """Load current source counts from SkillRecord table."""
    try:
        async with sessionmaker() as session:
            rows = (
                await session.execute(
                    sa.select(SkillRecord.name, SkillRecord.source_count)
                )
            ).all()
            return {row.name: row.source_count for row in rows if row.source_count}
    except StarMapError:
        raise
    except Exception as exc:
        logger.warning("Failed to load source counts, continuing without them: {}", exc)
        return {}


async def run_batch_extract_jd(
    jd_text: str,
    options: dict[str, Any] | None = None,
    *,
    job_title: str | None = None,
    source_run_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Run extraction, persist it, and ingest the resulting triples into Neo4j.

    Phase 7 P0-1 fix: wraps the Neo4j write in the graph-write outbox protocol
    so a Postgres commit followed by a Neo4j failure leaves a recoverable
    ``graph_write_outbox`` row (status='failed') instead of silent PG/Neo4j drift.
    """
    engine = get_async_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        options_with_counts = dict(options or {})
        source_counts = await _load_source_counts(sessionmaker)
        if source_counts:
            options_with_counts["source_counts"] = source_counts
        result = await extract_from_jd(jd_text, options=options_with_counts)
        if not result.get("success"):
            return {"status": "failed", "error": result.get("error", "Unknown extraction error")}

        async with sessionmaker() as session:
            async with session.begin():
                record, position_id, skill_ids = await persist_extraction_result(
                    session, jd_text, result, job_title=job_title, source_run_id=source_run_id
                )

        # H1 fix: outbox run_id=NULL for ad-hoc extraction; extraction_ids links
        # back to JDExtractionRecord for audit/retry traceability.
        # executor is imported lazily to avoid circular import (executor imports
        # stage3_services at function scope — see executor.py:513, 611).
        from app.core.pipeline import executor as _ex

        outbox_id = uuid.uuid4()
        try:
            await _ex._create_outbox_record(
                sessionmaker, outbox_id, None, extraction_ids=[record.id],
            )
        except StarMapError:
            raise
        except Exception as o_exc:  # pragma: no cover - outbox is best-effort
            logger.warning("run_batch_extract_jd outbox create failed (non-fatal): {}", o_exc)

        try:
            graph_summary = await write_single_extraction_to_graph(
                result["data"],
                canonical_ids={"position_id": position_id, "skills": skill_ids},
            )
            try:
                await _ex._complete_outbox_record(
                    sessionmaker, outbox_id, int(graph_summary.get("triples_merged", 0)),
                )
            except StarMapError:
                raise
            except Exception as o_exc:  # pragma: no cover
                logger.warning("run_batch_extract_jd outbox complete failed (non-fatal): {}", o_exc)
            return {
                "status": "completed",
                "extraction_id": str(record.id),
                "position_name": record.job_title,
                "required_skill_count": len(result["data"].get("required_skills", [])),
                "preferred_skill_count": len(result["data"].get("preferred_skills", [])),
                "graph": graph_summary,
            }
        except StarMapError:
            raise
        except Exception as exc:
            logger.exception("Stage3 service error: {}", exc)
            try:
                await _ex._fail_outbox_record(sessionmaker, outbox_id, str(exc))
            except StarMapError:
                raise
            except Exception as o_exc:  # pragma: no cover
                logger.warning("run_batch_extract_jd outbox fail update error: {}", o_exc)
            raise
    finally:
        await engine.dispose()


async def write_single_extraction_to_graph(
    extraction: dict[str, Any],
    canonical_ids: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write a single extraction result to Neo4j.

    canonical_ids: {"position_id", "skills": {name: id}} from the PG persist
    step — threaded so graph nodes carry canonical_id at write time (C-1 根治).
    """
    config = GraphConfig()
    async with config.get_driver() as driver:
        summaries = await batch_write_extractions([extraction], driver, canonical_ids_list=[canonical_ids])
    return summaries[0] if summaries else {}


async def sync_approved_position_to_graph(position_name: str) -> dict[str, Any]:
    """审核即入图 (D8f): 岗位审核通过后立即同步该岗位的抽取记录入图。

    背景: 原 graph_sync 每次全量重放最近 500 条已审核抽取记录（order_by created_at
    desc limit 500，无本次 run 过滤），导致"本次采集 0 新增但图谱处理 2473"的
    数值误导，且审核通过后需等下一轮流水线才入图（闭环滞后）。
    本函数: 审核通过时调用，只处理指定岗位的 completed 抽取记录 → 立即写图。
    """
    engine = get_async_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as session:
            records = (
                await session.execute(
                    sa.select(JDExtractionRecord)
                    .where(
                        JDExtractionRecord.status == "completed",
                        JDExtractionRecord.job_title == position_name,
                    )
                    .order_by(JDExtractionRecord.created_at.desc())
                    .limit(10)
                )
            ).scalars().all()
            extractions = [rec.to_extraction_payload() for rec in records]
            position_id = None
            name_cn_value: str | None = None
            # D8f: 中文化独立于抽取记录 —— 岗位缺中文名时无论有无抽取记录都补
            pos = (
                await session.execute(
                    sa.select(PositionRecord).where(PositionRecord.name == position_name)
                )
            ).scalar_one_or_none()
            if pos is not None:
                position_id = str(pos.id)
                if not (pos.name_cn or "").strip():
                    name_cn = await _translate_position_name(position_name)
                    if name_cn:
                        pos.name_cn = name_cn
                        name_cn_value = name_cn
                        await session.flush()
                        # D8f fix: session 无 autocommit，flush 后必须 commit 否则回滚
                        await session.commit()
                else:
                    name_cn_value = pos.name_cn
            # D8f: 翻译结果回传 extraction payload → Neo4j 节点同步 name_cn
            if name_cn_value:
                for payload in extractions:
                    payload["name_cn"] = name_cn_value

        config = GraphConfig()
        async with config.get_driver() as driver:
            canonical_ids_list: list[dict[str, Any] | None] | None = (
                [{"position_id": position_id, "skills": {}} for _ in extractions]
                if position_id else None
            )
            summaries = await batch_write_extractions(
                extractions, driver, canonical_ids_list=canonical_ids_list,
            )
            # D8f: 无抽取记录时仍写岗位节点（审核即入图的最小单元），
            # 保证岗位在图中存在（后续抽取可 merge 补关系）
            if not extractions and position_id:
                from app.core.extraction.graph_writer import merge_position

                await merge_position(
                    driver,
                    {"name": position_name, "name_cn": name_cn_value or ""},
                    canonical_id=position_id,
                )

        return {
            "status": "completed",
            "position": position_name,
            "extractions": len(extractions),
            "triples_merged": sum(int(s.get("triples_merged", 0)) for s in summaries),
            "nodes_touched": sum(int(s.get("nodes_touched", 0)) for s in summaries),
        }
    finally:
        await engine.dispose()


async def _translate_position_name(position_name: str) -> str | None:
    """LLM 翻译岗位名为中文（D8f 中文化）。失败静默返回 None（不阻断入图）。"""
    try:
        from app.core.extraction.llm_client import LLMClient
        from app.core.extraction.translation import has_cjk, translate_title_industry

        if has_cjk(position_name):
            return position_name
        llm = LLMClient()
        translated = await translate_title_industry(llm, title=position_name)
        return translated.get("name_cn") or None
    except Exception as exc:  # noqa: BLE001 — 翻译失败不阻断审核闭环
        logger.warning("translate position name failed for {!r}: {}", position_name, exc)
        return None


async def run_build_graph_from_extractions(
    limit: int = 100,
    since: datetime | None = None,
) -> dict[str, Any]:
    """Load persisted extraction records and ingest their triples into Neo4j.

    Phase 16 数据审核闭环: 仅同步已审核通过 (approved) 的岗位对应的抽取记录。
    新抽取的数据默认 review_status='pending_review'，需人工审核后才进入图谱。

    D8f (增量): since 非空时只处理该时间点之后创建的抽取记录 —— graph_sync
    阶段传本次 run 的 started_at，数值 = 本次流水线真实新增，不再全量重放历史
    （原实现 order_by desc limit 500 全量重放，导致"本次采集 0 但图谱处理 2473"
    的数值误导）。since=None = 全量（手动全量重建用）。
    """
    bounded_limit = max(1, min(int(limit), 1000))
    engine = get_async_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as session:
            # 严格门控: 只同步岗位已审核通过的抽取记录
            approved_positions = sa.select(PositionRecord.name).where(
                PositionRecord.review_status == "approved"
            )
            q = (
                sa.select(JDExtractionRecord)
                .where(
                    JDExtractionRecord.status == "completed",
                    JDExtractionRecord.job_title.in_(approved_positions),
                )
                .order_by(JDExtractionRecord.created_at.desc())
                .limit(bounded_limit)
            )
            if since is not None:
                q = q.where(JDExtractionRecord.created_at >= since)
            rows = (await session.execute(q)).scalars().all()

        extractions = [record.to_extraction_payload() for record in rows]
        # 2026-08-07 数据一致性: 抽取技能 upsert 到 PG skill_records (PG 为 SSOT)
        # graph_sync 此前只写 Neo4j → 新抽取技能 PG 缺失 (canonical_id 无法关联)
        try:
            from app.repositories.extract_repo import upsert_skill_record

            seen: set[str] = set()
            failed_skills: list[str] = []
            for payload in extractions:
                for sk in (payload.get("required_skills") or []) + (payload.get("preferred_skills") or []):
                    name = sk.get("skill") or sk.get("name") if isinstance(sk, dict) else str(sk)
                    if name and name not in seen:
                        seen.add(name)
                        try:
                            await upsert_skill_record(session, name=name, review_status="approved")
                        except Exception as single_sk_exc:  # noqa: BLE001 — 单条失败记入观测但不阻断
                            failed_skills.append(name)
                            logger.warning(
                                "skill_records upsert failed for skill={!r} (non-fatal): {}",
                                name, single_sk_exc,
                            )
            await session.commit()
            # D-06 SSOT 可观测化: 失败技能列表写日志告警 (outbox 表 + 一致性告警由 services/pipeline_consistency.py 在阶段末调用)
            if failed_skills:
                logger.warning(
                    "stage3 skill_records upsert: {} failed (skills={})",
                    len(failed_skills), failed_skills[:10],
                )
        except Exception as sk_exc:  # noqa: BLE001 — 技能入库失败不阻断图谱构建
            logger.warning("skill_records upsert failed (non-fatal): {}", sk_exc)
        config = GraphConfig()
        async with config.get_driver() as driver:
            summaries = await batch_write_extractions(extractions, driver)

        return {
            "status": "completed",
            "processed": len(extractions),
            "triples_merged": sum(int(s.get("triples_merged", 0)) for s in summaries),
            "relationships_touched": sum(int(s.get("relationships_touched", 0)) for s in summaries),
            # D8c fix: 补 nodes_touched 汇总（graph_sync 读它展示"触及节点"，
            # 此前不返回 → 阶段卡节点恒 0）
            "nodes_touched": sum(int(s.get("nodes_touched", 0)) for s in summaries),
        }
    finally:
        await engine.dispose()


async def run_analyze_evolution_trends(days: int = 90) -> dict[str, Any]:
    """Analyze recent extraction records and refresh skill source counts."""
    bounded_days = min(max(int(days), 7), 730)
    since = datetime.now(UTC) - timedelta(days=bounded_days)
    engine = get_async_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as session:
            records = (
                await session.execute(
                    sa.select(JDExtractionRecord)
                    .where(JDExtractionRecord.status == "completed", JDExtractionRecord.created_at >= since)
                    .order_by(JDExtractionRecord.created_at.desc())
                    .limit(5000)
                )
            ).scalars().all()

            skill_counts: Counter[str] = Counter()
            skill_categories: dict[str, str] = {}
            related_positions: dict[str, set[str]] = defaultdict(set)

            for record in records:
                payload = record.to_extraction_payload()
                position_name = str(payload.get("position_name") or record.job_title)
                for entries in (payload.get("required_skills", []), payload.get("preferred_skills", [])):
                    for entry in entries or []:
                        skill_name = skill_entry_name(entry)
                        if not skill_name:
                            continue
                        skill_counts[skill_name] += 1
                        skill_categories.setdefault(skill_name, skill_entry_category(entry, default="general"))
                        related_positions[skill_name].add(position_name)

            for skill_name, count in skill_counts.items():
                await session.execute(
                    insert(SkillRecord)
                    .values(name=skill_name, category=skill_categories.get(skill_name, "general"), source_count=count)
                    .on_conflict_do_update(
                        index_elements=[SkillRecord.name],
                        set_={
                            "source_count": count,
                            "category": skill_categories.get(skill_name, "general"),
                            "last_detected_at": datetime.now(UTC),
                        },
                    )
                )
            await session.commit()

        # C-5 入口闭环: POST /evolution/analyze 与 6h beat 共用本入口 (celery_app.py:63-73).
        # SkillRecord 频次落库后追加完整演化管线 (snapshot → diff → trust → changelog →
        # D-04 回写 / D-07 一致性校验). 管线自身 fail-soft; 此处再兜一层防入口失败.
        try:
            from app.core.evolution.orchestrator import run_evolution_pipeline

            pipeline_summary = await run_evolution_pipeline(months_back=max(1, bounded_days // 30))
        except Exception as exc:  # noqa: BLE001 — 演化管线失败不阻断趋势分析
            logger.warning("run_analyze_evolution_trends: evolution pipeline failed (non-fatal): {}", exc)
            pipeline_summary = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}

        top_trends = [
            {
                "skill_name": name,
                "trend": "rising" if count >= 5 else "stable",
                "confidence": min(1.0, round(0.5 + count / max(len(records), 1), 4)),
                "source_count": count,
                "related_positions": sorted(related_positions[name])[:10],
            }
            for name, count in skill_counts.most_common(20)
        ]
        return {
            "status": "completed",
            "days": bounded_days,
            "records_analyzed": len(records),
            "skills_analyzed": len(skill_counts),
            "trends": top_trends,
            "pipeline": pipeline_summary,
        }
    finally:
        await engine.dispose()
