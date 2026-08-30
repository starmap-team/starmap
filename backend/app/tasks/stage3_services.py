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
from app.models.extraction_models import JDExtractionRecord, PositionRecord, PositionSkillRelation, SkillRecord


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
    industry: str | None = None) -> PositionRecord | None:
    """Upsert a position record, classifying industry and rejecting non-IT roles.

    2026-08-28 (debug: non-IT roles mixed into IT graph): 新建岗位时：
    - 用 LLM industry + 关键词兜底分类写 industry 字段（此前恒 NULL → 79% 岗位无分类）
    - 明确非 IT 岗位（销售/HR/财务等）不建岗位，返回 None（不污染 IT 图谱）
    """
    # 非 IT 岗位门禁：明确销售/HR/财务/行政等不建岗位（无 LLM 成本，零副作用）
    from app.core.extraction.industry_gate import (
        classify_industry_fallback,
        is_non_it_position,
    )

    if is_non_it_position(name, industry):
        logger.info("industry gate: skip non-IT position {!r} industry={!r}", name[:60], industry)
        return None

    clean_industry = classify_industry_fallback(name, industry)

    existing = (
        await session.execute(sa.select(PositionRecord).where(PositionRecord.name == name))
    ).scalar_one_or_none()
    if existing is not None:
 # fix: 抽取 I18N-01 翻译结果曾丢弃（306 岗位仅 3 中文名根因）——
 # 已存在岗位若有新翻译结果也回填，避免重复翻译
        if name_cn and not (existing.name_cn or "").strip():
            existing.name_cn = name_cn
            await session.flush()
        # 2026-08-28: 已存在岗位若 industry 为空则回填分类（幂等，仅当缺失）
        if not (existing.industry or "").strip() and clean_industry:
            existing.industry = clean_industry
            await session.flush()
        return existing

    record = PositionRecord(
        name=name,
        name_cn=name_cn,  #: 抽取时持久化 I18N-01 翻译结果
        industry=clean_industry,  #: 2026-08-28: industry 分类入库（修复 79% 未分类）
        source_run_id=source_run_id,
        created_by="system:pipeline")
    session.add(record)
    await session.flush()
    return record

async def _upsert_skill(session: AsyncSession, name: str, category: str, *, source_run_id: uuid.UUID | None = None) -> SkillRecord:
    # 2026-08-20 (修复 B): 新抽取技能自动中文化 —— 英文技能入库即 LLM 批量翻译写 name_cn，
    # 后续业务无需二次处理。复用 backfill_skill_name_cn_batch._translate_batch（20 条/批）。
    existing = (
        await session.execute(sa.select(SkillRecord).where(SkillRecord.name == name))
    ).scalar_one_or_none()
    if existing is not None:
        existing.source_count += 1
        existing.category = existing.category or category
        return existing

    record = SkillRecord(
        name=name,
        name_cn=None,
        category=category,
        source_count=1,
        source_run_id=source_run_id,
        created_by="system:pipeline")
    session.add(record)
    await session.flush()

    # 自动翻译：仅当技能名不含中文且 LLM 可用时执行（失败静默降级，name_cn 留空后续回填）
    try:
        from app.core.extraction.translation import has_cjk
        if not has_cjk(name):
            from app.core.extraction.llm_client import LLMClient
            from scripts.backfill_skill_name_cn_batch import _translate_batch  # type: ignore[attr-defined]
            llm = LLMClient()
            translated = await _translate_batch(llm, [name])
            name_cn = translated.get(name)
            if name_cn and has_cjk(name_cn):
                record.name_cn = name_cn
                await session.flush()
    except Exception as exc:  # noqa: BLE001 — 翻译失败不阻断抽取入库
        logger.warning("_upsert_skill auto-translate failed for '{}' (non-fatal): {}", name, exc)

    return record

async def _ensure_position_skill_relation(
    session: AsyncSession,
    position_id: Any,
    skill_id: Any,
    requirement_type: str,
    confidence: float) -> None:
    existing = (
        await session.execute(
            sa.select(PositionSkillRelation).where(
                PositionSkillRelation.position_id == position_id,
                PositionSkillRelation.skill_id == skill_id,
                PositionSkillRelation.requirement_type == requirement_type)
        )
    ).scalars().first()
    if existing is not None:
        existing.confidence = max(float(existing.confidence or 0.0), confidence)
        return

    session.add(
        PositionSkillRelation(
            position_id=position_id,
            skill_id=skill_id,
            requirement_type=requirement_type,
            confidence=confidence)
    )

async def persist_extraction_result(
    session: AsyncSession,
    jd_content: str,
    extraction_result: dict[str, Any],
    *,
    job_title: str | None = None,
    source_run_id: uuid.UUID | None = None) -> tuple[JDExtractionRecord, str, dict[str, str]]:
    """Persist a successful extraction and update relational evolution source tables.

    Returns (record, position_id, skill_ids) — position_id 与 {skill_name: id} 供
    write_single_extraction_to_graph 穿线 canonical_id（C-1 根治：图节点写库即带 id）。
    """
    data = extraction_result["data"]
 # D5 fix (2026-08-12): LLM 未返回 position_name 时回退到 JD 标题（管线 import 已传
 # job_title），不再落 "Unknown Position" 占位符 —— 该占位符曾产生 103 条幻影关系
 # 污染 PG SSOT 且无图对应（双库不一致根因之一）。
    position_name = str(data.get("position_name") or job_title or "").strip()
    # 2026-08-30 (Lane2 根因修复): 入库名清洗 —— LLM 抽取名可能携带 JD 头部
    # 符号残留(如 ".AI开发实习生"), ASCII 排序置顶放大显眼度。
    from app.core.extraction.industry_gate import normalize_position_name

    position_name = normalize_position_name(position_name) or position_name.strip()
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
        status="completed")
    session.add(record)
    await session.flush()

 # 2026-08-21 (debug: 抽取质量门禁): 非岗位内容不落 Position/Skill。
 # 论坛问答/教程/新闻标题被爬虫以 job_title 入库，原实现直接抽成岗位 →
 # 审核队列与图谱被垃圾灌满（本 debug session 根因 A）。门禁只在
 # 内容明显非岗位时拦截（零 LLM 成本启发式），真 JD 不受影响。
    from app.config import settings as _settings
    from app.core.extraction.job_content_guard import job_reject_reason

    if getattr(_settings, "extraction_skip_non_job", True):
        reason = job_reject_reason(jd_content, job_title)
        if reason:
            logger.warning(
                "job-content gate: skip non-job extraction title={!r} reason={}",
                position_name[:60], reason,
            )
            # 保留审计痕迹（JDExtractionRecord 已建）；不建 PositionRecord/SkillRecord
            data = dict(data or {})
            data["skipped_reason"] = f"non_job:{reason}"
            record.extracted_skills = data
            await session.flush()
            return record, "NON_JOB", {}

    position = await _upsert_position(
        session,
        position_name,
        source_run_id=source_run_id,
        name_cn=data.get("name_cn"),  #: I18N-01 翻译结果持久化
        industry=data.get("industry") or data.get("industry_zh"),  #: 2026-08-28 行业分类入库
    )
    if position is None:
        # 非 IT 岗位门禁拦截（销售/HR/财务等）— 保留抽取记录审计，不建岗位
        data = dict(data or {})
        data["skipped_reason"] = "non_it"
        record.extracted_skills = data
        await session.flush()
        return record, "NON_IT", {}
    skill_ids: dict[str, str] = {}
    for requirement_type, entries in (
        ("required", data.get("required_skills", [])),
        ("preferred", data.get("preferred_skills", []))):
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
                confidence)

 # 2026-08-28 (debug: 空技能岗位): 首轮抽取无技能时标记 quality_hint 供后续重试，
    # 但岗位仍正常建（不删数据/不阻断其他字段）。
    if not skill_ids:
        quality = dict(data)
        quality["quality_hint"] = "no_skills"
        record.extracted_skills = quality
        await session.flush()

 # R5 根治 (2026-08-13): 抽取 evolves_to 后继岗位（职业演化目标）此前只写 Neo4j 图
 # （graph_writer name-MERGE 无 canonical_id）不落 PG → 产生被 EVOLVES_TO 引用的
 # 无记录图节点（孤儿）。现在一并落 PG（pending_review 待审核），graph_sync 的
 # 岗位自愈会补齐 canonical_id 链接——未来抽取不再产生岗位孤儿。
    for successor in data.get("evolves_to", []) or []:
        if isinstance(successor, dict):
            succ_name = str(successor.get("position") or successor.get("name") or "").strip()
        else:
            succ_name = str(successor).strip()
        if succ_name and succ_name != position_name:
            try:
                await _upsert_position(session, succ_name, source_run_id=source_run_id)
            except Exception as succ_exc:  # noqa: BLE001 — 单条后继失败不阻断主写入
                logger.warning("evolves_to successor PG upsert failed for {!r}: {}", succ_name, succ_exc)

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

async def _position_is_approved(sessionmaker: Any, position_id: str) -> bool:
    """Check whether a PositionRecord has review_status='approved'.核验修复  闭环): 抽取即写图路径守 approved 门控——未审核岗位
    (pending_review) 不得进入图谱。审核通过后由 sync_approved_position_to_graph 补投影。
    """
    try:
        async with sessionmaker() as session:
            result = await session.execute(
                sa.select(PositionRecord.review_status).where(
                    PositionRecord.id == position_id
                )
            )
            return (result.scalar_one_or_none or "") == "approved"
    except Exception as exc:  # pragma: no cover - 查询失败 fail-closed 拒绝写图
        logger.warning("_position_is_approved query failed (fail-closed skip graph): {}", exc)
        return False

async def run_batch_extract_jd(
    jd_text: str,
    options: dict[str, Any] | None = None,
    *,
    job_title: str | None = None,
    source_run_id: uuid.UUID | None = None) -> dict[str, Any]:
    """Run extraction, persist it, and ingest the resulting triples into Neo4j. fix: wraps the Neo4j write in the graph-write outbox protocol
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
                sessionmaker, outbox_id, None, extraction_ids=[record.id])
        except StarMapError:
            raise
        except Exception as o_exc:  # pragma: no cover - outbox is best-effort
            logger.warning("run_batch_extract_jd outbox create failed (non-fatal): {}", o_exc)

        try:
 #核验修复 闭环): 抽取即写图路径也必须守 approved 门控。
 # 设计意图 : 新抽取默认 review_status='pending_review'，需人工审核
 # 后才进入图谱。run_batch_extract_jd 绕过 run_build_graph_from_extractions
 # 的 approved 过滤直接写图，是未审核岗位持续入图的根因——此处补查。
            graph_summary: dict[str, Any] = {"skipped": True, "reason": "position_not_approved"}
            if await _position_is_approved(sessionmaker, position_id):
                graph_summary = await write_single_extraction_to_graph(
                    result["data"],
                    canonical_ids={"position_id": position_id, "skills": skill_ids})
            try:
                await _ex._complete_outbox_record(
                    sessionmaker, outbox_id, int(graph_summary.get("triples_merged", 0)))
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
    canonical_ids: dict[str, Any] | None = None) -> dict[str, Any]:
    """Write a single extraction result to Neo4j.

    canonical_ids: {"position_id", "skills": {name: id}} from the PG persist
    step — threaded so graph nodes carry canonical_id at write time (C-1 根治).
    """
    config = GraphConfig()
    async with config.get_driver() as driver:
        summaries = await batch_write_extractions([extraction], driver, canonical_ids_list=[canonical_ids])
    return summaries[0] if summaries else {}

async def sync_approved_position_to_graph(position_name: str) -> dict[str, Any]:
    """审核即入图 ): 岗位审核通过后立即同步该岗位的抽取记录入图。

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
                        JDExtractionRecord.job_title == position_name)
                    .order_by(JDExtractionRecord.created_at.desc())
                    .limit(10)
                )
            ).scalars().all()
            extractions = [rec.to_extraction_payload() for rec in records]
            position_id = None
            name_cn_value: str | None = None
            # 中文化独立于抽取记录 —— 岗位缺中文名时无论有无抽取记录都补
            pos = (
                await session.execute(
                    sa.select(PositionRecord).where(PositionRecord.name == position_name)
                )
            ).scalars().first()
            if pos is not None:
                position_id = str(pos.id)
                # 2026-08-28 (批0 真相源): 隐藏岗位（no_skills/non_it）审核通过也不入图，
                # 与「空技能/非IT不进图」契约一致（六入口收敛 is_graph_eligible 语义）。
                if pos.quality_hint in ("no_skills", "non_it"):
                    logger.info(
                        "sync_approved_position_to_graph skip (hidden): '{}' quality_hint={}",
                        position_name[:60], pos.quality_hint,
                    )
                    return {}
                if not (pos.name_cn or "").strip():
                    name_cn = await _translate_position_name(position_name)
                    if name_cn:
                        pos.name_cn = name_cn
                        name_cn_value = name_cn
                        await session.flush()
 # fix: session 无 autocommit，flush 后必须 commit 否则回滚
                        await session.commit()
                else:
                    name_cn_value = pos.name_cn
 #: 翻译结果回传 extraction payload → Neo4j 节点同步 name_cn
            if name_cn_value:
                for payload in extractions:
                    payload["name_cn"] = name_cn_value

        config = GraphConfig()
        async with config.get_driver() as driver:
 #MERGE 键切为 canonical_id 后，这里必须解析技能
 # canonical_id（skills 不再传空 dict）——否则 merge_skill 缺 id 会 raise。
            skill_map: dict[str, str] = {}
            if position_id and extractions:
                try:
                    async with sessionmaker() as session:
                        skill_names = {
                            skill_entry_name(entry)
                            for payload in extractions
                            for entry in (payload.get("required_skills") or []) + (payload.get("preferred_skills") or [])
                        } - {""}
                        if skill_names:
                            skill_map = {
                                name: str(sid)
                                for name, sid in (
                                    await session.execute(
                                        sa.select(SkillRecord.name, SkillRecord.id).where(
                                            SkillRecord.name.in_(skill_names)
                                        )
                                    )
                                ).all()
                            }
                except Exception as sk_exc:  # noqa: BLE001 — 技能 id 解析失败不阻断
                    logger.warning(
                        "sync_approved_position_to_graph: skill canonical_id lookup failed (non-fatal): {}", sk_exc)
            canonical_ids_list: list[dict[str, Any] | None] | None = (
                [
                    {"position_id": position_id, "skills": dict(skill_map)}
                    for _ in extractions
                ]
                if position_id else None
            )
            summaries = await batch_write_extractions(
                extractions, driver, canonical_ids_list=canonical_ids_list)
 #: 无抽取记录时仍写岗位节点（审核即入图的最小单元），
 # 保证岗位在图中存在（后续抽取可 merge 补关系）
            if not extractions and position_id:
                from app.core.extraction.graph_writer import merge_position

                await merge_position(
                    driver,
                    {"name": position_name, "name_cn": name_cn_value or ""},
                    canonical_id=position_id)

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
    """LLM 翻译岗位名为中文（ 中文化）。失败静默返回 None（不阻断入图）。"""
    try:
        from app.core.extraction.llm_client import LLMClient
        from app.core.extraction.translation import has_cjk, translate_title_industry

        if has_cjk(position_name):
            return position_name
        llm = LLMClient
        translated = await translate_title_industry(llm, title=position_name)
        return translated.get("name_cn") or None
    except Exception as exc:  # noqa: BLE001 — 翻译失败不阻断审核闭环
        logger.warning("translate position name failed for {!r}: {}", position_name, exc)
        return None

async def run_build_graph_from_extractions(
    limit: int = 100,
    since: datetime | None = None) -> dict[str, Any]:
    """Load persisted extraction records and ingest their triples into Neo4j.数据审核闭环: 仅同步已审核通过 (approved) 的岗位对应的抽取记录。
    新抽取的数据默认 review_status='pending_review'，需人工审核后才进入图谱。 (增量): since 非空时只处理该时间点之后创建的抽取记录 —— graph_sync
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
                    JDExtractionRecord.job_title.in_(approved_positions))
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
                                name, single_sk_exc)
            await session.commit()
 # SSOT 可观测化: 失败技能列表写日志告警 (outbox 表 + 一致性告警由 services/pipeline_consistency.py 在阶段末调用)
            if failed_skills:
                logger.warning(
                    "stage3 skill_records upsert: {} failed (skills={})",
                    len(failed_skills), failed_skills[:10])
        except Exception as sk_exc:  # noqa: BLE001 — 技能入库失败不阻断图谱构建
            logger.warning("skill_records upsert failed (non-fatal): {}", sk_exc)
        config = GraphConfig()
        async with config.get_driver() as driver:
 #(checkpoint:decision): MERGE 键切为 canonical_id 后，
 # 这里必须预查 name → PG id 映射并补传 canonical_ids_list——否则
 # merge_position/merge_skill 缺 canonical_id 会 raise（不再静默孤儿）。
            canonical_ids_list: list[dict[str, Any] | None] | None = None
            try:
                async with sessionmaker() as session:
                    position_names = {
                        str(p.get("position_name") or p.get("job_title") or "").strip()
                        for p in extractions
                        if p
                    } - {""}
                    position_map: dict[str, str] = {}
                    if position_names:
                        position_map = {
                            name: str(pid)
                            for name, pid in (
                                await session.execute(
                                    sa.select(PositionRecord.name, PositionRecord.id).where(
                                        PositionRecord.name.in_(position_names)
                                    )
                                )
                            ).all()
                        }
                    skill_names: set[str] = set()
                    for payload in extractions:
                        for entry in (payload.get("required_skills") or []) + (payload.get("preferred_skills") or []):
                            name = skill_entry_name(entry)
                            if name:
                                skill_names.add(name)
                    skill_map: dict[str, str] = {}
                    if skill_names:
                        skill_map = {
                            name: str(sid)
                            for name, sid in (
                                await session.execute(
                                    sa.select(SkillRecord.name, SkillRecord.id).where(
                                        SkillRecord.name.in_(skill_names)
                                    )
                                )
                            ).all()
                        }
                canonical_ids_list = []
                for payload in extractions:
                    pname = str(payload.get("position_name") or payload.get("job_title") or "").strip()
                    cids: dict[str, Any] = {"position_id": position_map.get(pname), "skills": {}}
                    for entry in (payload.get("required_skills") or []) + (payload.get("preferred_skills") or []):
                        name = skill_entry_name(entry)
                        if name and name in skill_map:
                            cids["skills"][name] = skill_map[name]
                    canonical_ids_list.append(cids)
            except Exception as cid_exc:  # noqa: BLE001 — canonical_id 预查失败不阻断构建
                logger.warning(
                    "run_build_graph_from_extractions: canonical_id lookup failed (non-fatal): {}", cid_exc)
                canonical_ids_list = None
            summaries = await batch_write_extractions(
                extractions, driver, canonical_ids_list=canonical_ids_list)
 # P4a 根治 (R3): 补录覆盖全图谱——把图中存在但 PG 无记录的无标识技能
 # 回填 skill_records + 链接 canonical_id（幂等，每次 run 自愈历史缺口）。
 # 此前只回填当次 run 抽取载荷，历史 name-MERGE 技能永不回填（R3 根因）。
            try:
                from app.services.repair_engine import RepairEngine

                repair = RepairEngine(driver)
                heal = await repair.backfill_skill_records(session)
                if heal.get("backfilled") or heal.get("linked"):
                    logger.info(
                        "graph_sync: healed {} historical skills (backfilled={}, linked={})",
                        heal.get("backfilled", 0), heal.get("backfilled", 0), heal.get("linked", 0))
 # R5 根治: 同样自愈岗位——抽取 evolves_to 后继岗位只写图不落 PG 的
 # 历史缺口，回填 position_records（pending_review 待审核）+ 链接。
                pos_heal = await repair.backfill_position_records(session)
                if pos_heal.get("backfilled") or pos_heal.get("linked"):
                    logger.info(
                        "graph_sync: healed {} historical positions (backfilled={}, linked={})",
                        pos_heal.get("backfilled", 0), pos_heal.get("backfilled", 0), pos_heal.get("linked", 0))
            except Exception as heal_exc:  # noqa: BLE001 — 补录失败不阻断图谱构建
                logger.warning("graph_sync heal failed (non-fatal): {}", heal_exc)

        return {
            "status": "completed",
            "processed": len(extractions),
            "triples_merged": sum(int(s.get("triples_merged", 0)) for s in summaries),
            "relationships_touched": sum(int(s.get("relationships_touched", 0)) for s in summaries),
 # fix: 补 nodes_touched 汇总（graph_sync 读它展示"触及节点"，
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
                        })
                )
            await session.commit()

 # C-5 入口闭环: POST /evolution/analyze 与 6h beat 共用本入口 (celery_app.py:63-73).
 # SkillRecord 频次落库后追加完整演化管线 (snapshot → diff → trust → changelog →
 # 回写 / 一致性校验). 管线自身 fail-soft; 此处再兜一层防入口失败.
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
