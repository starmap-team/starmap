"""Stage 3 task services for extraction, graph ingestion, and evolution analysis."""
from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.extraction.graph_writer import GraphConfig, batch_write_extractions
from app.core.extraction.jd_extract import extract_from_jd, mask_pii
from app.models.extraction_models import (
    JDExtractionRecord,
    PositionRecord,
    PositionSkillRelation,
    SkillRecord,
)


def run_async(coro: Any) -> Any:
    """Run an async coroutine from a Celery worker process."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()


def _skill_name(entry: Any) -> str:
    if isinstance(entry, dict):
        return str(entry.get("name") or entry.get("skill") or "").strip()
    return str(entry).strip()


def _skill_category(entry: Any) -> str:
    if isinstance(entry, dict):
        return str(entry.get("category") or "general")
    return "general"


def _extraction_payload_from_record(record: JDExtractionRecord) -> dict[str, Any]:
    payload = dict(record.extracted_skills or {})
    payload.setdefault("position_name", record.job_title)
    payload.setdefault("experience_required", record.experience_years)
    payload.setdefault("education_required", record.education)
    return payload


def _confidence_from_result(result: dict[str, Any]) -> float:
    validation = result.get("validation") or {}
    return float(validation.get("confidence") or 0.85)


def _hallucination_score_from_result(result: dict[str, Any]) -> float | None:
    validation = result.get("validation") or {}
    if validation.get("is_valid", True):
        return 0.0
    confidence = float(validation.get("confidence") or 0.0)
    return round(1.0 - confidence, 4)


async def _upsert_position(session: AsyncSession, name: str) -> PositionRecord:
    existing = (
        await session.execute(sa.select(PositionRecord).where(PositionRecord.name == name))
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    record = PositionRecord(name=name)
    session.add(record)
    await session.flush()
    return record


async def _upsert_skill(session: AsyncSession, name: str, category: str) -> SkillRecord:
    existing = (
        await session.execute(sa.select(SkillRecord).where(SkillRecord.name == name))
    ).scalar_one_or_none()
    if existing is not None:
        existing.source_count += 1
        existing.category = existing.category or category
        return existing

    record = SkillRecord(name=name, category=category, source_count=1)
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
) -> JDExtractionRecord:
    """Persist a successful extraction and update relational evolution source tables."""
    data = extraction_result["data"]
    position_name = str(data.get("position_name") or "Unknown Position")
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

    position = await _upsert_position(session, position_name)
    for requirement_type, entries in (
        ("required", data.get("required_skills", [])),
        ("preferred", data.get("preferred_skills", [])),
    ):
        for entry in entries:
            skill_name = _skill_name(entry)
            if not skill_name:
                continue
            skill = await _upsert_skill(session, skill_name, _skill_category(entry))
            await _ensure_position_skill_relation(
                session,
                position.id,
                skill.id,
                requirement_type,
                confidence,
            )

    return record


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
    except Exception:
        logger.warning("Failed to load source counts, continuing without them")
        return {}


async def run_batch_extract_jd(jd_text: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run extraction, persist it, and ingest the resulting triples into Neo4j."""
    engine = create_async_engine(settings.postgres_uri, pool_pre_ping=True, future=True)
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
                record = await persist_extraction_result(session, jd_text, result)

        graph_summary = await write_single_extraction_to_graph(result["data"])
        return {
            "status": "completed",
            "extraction_id": str(record.id),
            "position_name": record.job_title,
            "required_skill_count": len(result["data"].get("required_skills", [])),
            "preferred_skill_count": len(result["data"].get("preferred_skills", [])),
            "graph": graph_summary,
        }
    finally:
        await engine.dispose()


async def write_single_extraction_to_graph(extraction: dict[str, Any]) -> dict[str, Any]:
    """Write a single extraction result to Neo4j."""
    config = GraphConfig()
    async with config.get_driver() as driver:
        summaries = await batch_write_extractions([extraction], driver)
    return summaries[0] if summaries else {}


async def run_build_graph_from_extractions(limit: int = 100) -> dict[str, Any]:
    """Load persisted extraction records and ingest their triples into Neo4j."""
    bounded_limit = max(1, min(int(limit), 1000))
    engine = create_async_engine(settings.postgres_uri, pool_pre_ping=True, future=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as session:
            rows = (
                await session.execute(
                    sa.select(JDExtractionRecord)
                    .where(JDExtractionRecord.status == "completed")
                    .order_by(JDExtractionRecord.created_at.desc())
                    .limit(bounded_limit)
                )
            ).scalars().all()

        extractions = [_extraction_payload_from_record(record) for record in rows]
        config = GraphConfig()
        async with config.get_driver() as driver:
            summaries = await batch_write_extractions(extractions, driver)

        return {
            "status": "completed",
            "processed": len(extractions),
            "triples_merged": sum(int(s.get("triples_merged", 0)) for s in summaries),
            "relationships_touched": sum(int(s.get("relationships_touched", 0)) for s in summaries),
        }
    finally:
        await engine.dispose()


async def run_analyze_evolution_trends(days: int = 90) -> dict[str, Any]:
    """Analyze recent extraction records and refresh skill source counts."""
    bounded_days = min(max(int(days), 7), 730)
    since = datetime.now(UTC) - timedelta(days=bounded_days)
    engine = create_async_engine(settings.postgres_uri, pool_pre_ping=True, future=True)
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
                payload = _extraction_payload_from_record(record)
                position_name = str(payload.get("position_name") or record.job_title)
                for entries in (payload.get("required_skills", []), payload.get("preferred_skills", [])):
                    for entry in entries or []:
                        skill_name = _skill_name(entry)
                        if not skill_name:
                            continue
                        skill_counts[skill_name] += 1
                        skill_categories.setdefault(skill_name, _skill_category(entry))
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
        }
    finally:
        await engine.dispose()
