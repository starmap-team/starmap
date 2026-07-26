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
from app.exceptions import StarMapError
from app.db.session import get_async_engine
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
            skill_name = skill_entry_name(entry)
            if not skill_name:
                continue
            skill = await _upsert_skill(session, skill_name, skill_entry_category(entry, default="general"))
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
    except StarMapError:
        raise
    except Exception as exc:
        logger.warning("Failed to load source counts, continuing without them: {}", exc)
        return {}


async def run_batch_extract_jd(jd_text: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
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
                record = await persist_extraction_result(session, jd_text, result)

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
            graph_summary = await write_single_extraction_to_graph(result["data"])
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


async def write_single_extraction_to_graph(extraction: dict[str, Any]) -> dict[str, Any]:
    """Write a single extraction result to Neo4j."""
    config = GraphConfig()
    async with config.get_driver() as driver:
        summaries = await batch_write_extractions([extraction], driver)
    return summaries[0] if summaries else {}


async def run_build_graph_from_extractions(limit: int = 100) -> dict[str, Any]:
    """Load persisted extraction records and ingest their triples into Neo4j."""
    bounded_limit = max(1, min(int(limit), 1000))
    engine = get_async_engine()
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

        extractions = [record.to_extraction_payload() for record in rows]
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
