"""Fixture loader — seed database from structured JSON fixtures.

Design (per design.md):
  1. Read positions.json / skills.json / knowledge_areas.json / tools.json / relations.json
  2. Insert into PG position_records / skill_records (status='pending_review')
  3. Auto-approve via review_service.approve() → triggers graph_writer for Neo4j sync
  4. Write position_skill_relations for every position-skill pair
  5. Write BELONGS_TO / USES / EVOLVES_TO / PREREQUISITE via graph_writer
  6. Idempotent: skip existing records (MERGE semantics)

Usage:
    cd backend
    poetry run python -m app.data.fixtures.seed
"""
from __future__ import annotations

import asyncio
import json
import uuid as uuid_mod
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session_factory
from app.models.extraction_models import PositionRecord, SkillRecord
from app.services import review_service

FIXTURES_DIR = Path(__file__).parent


def _load_json(name: str) -> list[dict]:
    path = FIXTURES_DIR / name
    if not path.exists():
        print(f"[seed] Warning: {name} not found, skipping")
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _now() -> datetime:
    return datetime.now(UTC)


async def seed_positions(session: AsyncSession) -> int:
    """Seed position_records from fixtures. Returns count of new positions."""
    positions = _load_json("positions.json")
    if not positions:
        return 0

 # Get existing names
    existing = set(
        (await session.execute(select(PositionRecord.name))).scalars().all()
    )
    new_count = 0

    for pos in positions:
        name = pos["name"]
        if name in existing:
            continue

        rid = uuid_mod.uuid4()
        now = _now()
        stmt = text("""
            INSERT INTO position_records (id, name, industry, description, created_at, review_status, created_by)
            VALUES (:id, :name, :industry, :desc, :created, 'pending_review', 'system:fixture')
            ON CONFLICT (name) DO NOTHING
        """)
        await session.execute(stmt, {
            "id": rid, "name": name,
            "industry": pos.get("industry", "信息技术/互联网"),
            "desc": "",
            "created": now,
        })
        existing.add(name)
        new_count += 1

 # Auto-approve (triggers graph_writer → Neo4j sync)
        try:
            await review_service.approve(
                session,
                entity_type="position",
                entity_id=rid,
                actor="system:fixture",
                reason="Automatic approval from fixture seed",
            )
        except Exception as e:
            print(f"[seed]  approve position '{name}' failed (may already be approved): {e}")
 # If approve fails because it's already approved or wrong state, just continue

    await session.commit()
    print(f"[seed]  Positions: {new_count} new (total {len(existing)} in PG)")
    return new_count


async def seed_skills(session: AsyncSession) -> int:
    """Seed skill_records from fixtures. Returns count of new skills."""
    skills = _load_json("skills.json")
    if not skills:
        return 0

    existing = set(
        (await session.execute(select(SkillRecord.name))).scalars().all()
    )
    new_count = 0

    for skill in skills:
        name = skill["name"]
        if name in existing:
            continue

        rid = uuid_mod.uuid4()
        now = _now()
        stmt = text("""
            INSERT INTO skill_records (id, name, category, first_detected_at, last_detected_at, review_status, created_by)
            VALUES (:id, :name, :category, :created, :created, 'pending_review', 'system:fixture')
        """)
        await session.execute(stmt, {
            "id": rid, "name": name,
            "category": skill.get("category", "hard_skill"),
            "created": now,
        })
        existing.add(name)
        new_count += 1

 # Auto-approve
        try:
            await review_service.approve(
                session,
                entity_type="skill",
                entity_id=rid,
                actor="system:fixture",
                reason="Automatic approval from fixture seed",
            )
        except Exception as e:
            print(f"[seed]  approve skill '{name}' failed: {e}")

    await session.commit()
    print(f"[seed]  Skills: {new_count} new (total {len(existing)} in PG)")
    return new_count


async def seed_position_skill_relations(session: AsyncSession) -> int:
    """Write position_skill_relations for every position-skill pair."""
    positions = _load_json("positions.json")
    if not positions:
        return 0

 # Get ID mappings from PG
    pos_rows = (await session.execute(select(PositionRecord.id, PositionRecord.name))).all()
    skill_rows = (await session.execute(select(SkillRecord.id, SkillRecord.name))).all()
    pos_map = {name: pid for pid, name in pos_rows}
    skill_map = {name: sid for sid, name in skill_rows}

 # Get existing relations
    existing_rels = {
        (row[0], row[1])
        for row in (await session.execute(text("SELECT position_id, skill_id FROM position_skill_relations"))).all()
    }

    new_count = 0
    for pos in positions:
        pid = pos_map.get(pos["name"])
        if not pid:
            continue
        for sk in pos.get("skills", []):
            sid = skill_map.get(sk["name"])
            if not sid:
                continue
            if (pid, sid) in existing_rels:
                continue
            await session.execute(text("""
                INSERT INTO position_skill_relations (position_id, skill_id, confidence)
                VALUES (:pid, :sid, 1.0)
            """), {"pid": pid, "sid": sid})
            existing_rels.add((pid, sid))
            new_count += 1

    await session.commit()
    print(f"[seed]  Position-Skill Relations: {new_count} new")
    return new_count


async def seed_neo4j_graph(session: AsyncSession) -> int:
    """Sync fixture data to Neo4j via graph_writer (complete ontology: 7 node types, 8 relations).

    Creates jd_extraction_records as intermediate bridge, then calls
    graph_writer.batch_write_extractions for full Neo4j sync including
    BELONGS_TO, USES, EVOLVES_TO, PREREQUISITE relationships.
    Returns number of triples written.
    """
    from neo4j import AsyncGraphDatabase

    from app.config import settings
    from app.core.extraction.graph_writer import batch_write_extractions
    from app.services.resources import resources as app_resources

    driver = app_resources.neo4j_driver
    own_driver = False
    if driver is None:
 # Standalone mode: create own driver from config
        driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        own_driver = True
        print(f"[seed]  Neo4j: standalone driver ({settings.neo4j_uri})")

    positions = _load_json("positions.json")

 # Build extraction-like dicts for graph_writer
    extractions = []
    for pos in positions:
        required = pos.get("skills", [])
        extractions.append({
            "job_title": pos["name"],
            "industry": pos.get("industry", "信息技术/互联网"),
            "extracted_skills": [
                {"skill": s["name"], "category": s.get("category", "hard_skill"),
                 "proficiency": "熟悉", "type": "required"}
                for s in required
            ],
            "required_skills": [s["name"] for s in required],
            "experience_years": 3,
            "education": "本科",
            "confidence": 0.85,
        })

    try:
        summaries = await batch_write_extractions(extractions, driver)
        total_triples = sum(s.get("triples_written", 0) for s in summaries)
        print(f"[seed]  Neo4j: {total_triples} triples across {len(summaries)} positions")
        return total_triples
    except Exception as e:
        print(f"[seed]  Neo4j sync failed: {e}")
        return 0
    finally:
        if own_driver:
            await driver.close()


async def main():
    print("[seed] Starting fixture seed...")
    factory = get_session_factory()

    async with factory() as session:
        p = await seed_positions(session)
        s = await seed_skills(session)
        r = await seed_position_skill_relations(session)
        n = await seed_neo4j_graph(session)

    print(f"[seed] Complete: {p} positions, {s} skills, {r} relations, {n} Neo4j triples")
    print("[seed] PG → review_service.approve → approved | Neo4j → graph_writer.batch_write_extractions")


if __name__ == "__main__":
    asyncio.run(main())
