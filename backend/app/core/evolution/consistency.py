"""PG ↔ Neo4j REQUIRES-edge consistency check (D-07).

Compares ``position_skill_relations`` in PG with REQUIRES edges in Neo4j keyed
by canonical_id pair, including attribute-level comparison of
``requirement_type`` and ``confidence``. Purely read-only — this module only
issues SELECT / MATCH queries and never writes or repairs data (D-07: 不一致仅
告警不改数据).

The caller (evolution pipeline end) is responsible for surfacing the returned
report into ``summary["consistency"]`` and downgrading mismatches to warnings.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.extraction.graph_writer import GraphConfig
from app.models.extraction_models import PositionSkillRelation

# Read-only Cypher: mirrors backfill_graph_to_pg.py:40-49 — no MERGE/SET/CREATE.
_EDGE_QUERY = (
    "MATCH (p:Position)-[r:REQUIRES]->(sk:Skill) "
    "WHERE p.canonical_id IS NOT NULL AND sk.canonical_id IS NOT NULL "
    "RETURN p.canonical_id AS pcid, sk.canonical_id AS scid, "
    "r.confidence AS conf, r.requirement_type AS rt"
)


async def check_pg_neo4j_consistency(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, Any]:
    """Compare PG PSR rows against Neo4j REQUIRES edges.

    Returns ``{"status": "ok" | "mismatch" | "error", "pg_only": [...],
    "neo4j_only": [...], "attribute_mismatches": [...], "checked_at": iso}``.
    ``pg_only`` / ``neo4j_only`` are lists of ``{"position_id", "skill_id",
    "requirement_type"}`` (canonical_id strings + PSR/edge requirement type);
    ``attribute_mismatches`` additionally carry the two sides' ``confidence``.
    W4: 键为 (position_id, skill_id, requirement_type) —— required 与 preferred 可
    并存，不再按 (position_id, skill_id) 折叠导致漏报/误报。
    """
    checked_at = datetime.now(UTC).isoformat()
    report: dict[str, Any] = {
        "status": "ok",
        "pg_only": [],
        "neo4j_only": [],
        "attribute_mismatches": [],
        "checked_at": checked_at,
    }

    try:
        async with session_factory() as session:
            rows = (
                await session.execute(
                    sa.select(
                        PositionSkillRelation.position_id,
                        PositionSkillRelation.skill_id,
                        PositionSkillRelation.requirement_type,
                        PositionSkillRelation.confidence,
                    )
                )
            ).all()
 # W4: 键含 requirement_type —— 同一 (position, skill) 的 required 与 preferred
 # 行/边各自独立比较，互不折叠覆盖。
        pg_rels: dict[tuple[str, str, str], float] = {
            (str(position_id), str(skill_id), requirement_type): float(confidence or 0.0)
            for position_id, skill_id, requirement_type, confidence in rows
        }
    except Exception as exc:  # noqa: BLE001 — D-07 fail-soft, read failure is a report
        logger.warning("evolution consistency: PG read failed: {}", exc)
        report["status"] = "error"
        report["error"] = f"pg_read_failed: {type(exc).__name__}: {exc}"
        return report

    try:
        config = GraphConfig()
        async with config.get_driver() as driver:
            async with driver.session() as graph_session:
                records = await (await graph_session.run(_EDGE_QUERY)).data()
        neo_rels: dict[tuple[str, str, str], float] = {}
        for rec in records:
            rt = str(rec.get("rt") or "")
            key = (str(rec["pcid"]), str(rec["scid"]), rt)
            neo_rels[key] = float(rec.get("conf") or 0.0)
    except Exception as exc:  # noqa: BLE001 — D-07 fail-soft
        logger.warning("evolution consistency: Neo4j read failed: {}", exc)
        report["status"] = "error"
        report["error"] = f"neo4j_read_failed: {type(exc).__name__}: {exc}"
        return report

    for key, pg_conf in pg_rels.items():
        if key not in neo_rels:
            report["pg_only"].append(
                {"position_id": key[0], "skill_id": key[1], "requirement_type": key[2]}
            )
        elif neo_rels[key] != pg_conf:
            report["attribute_mismatches"].append(
                {
                    "position_id": key[0],
                    "skill_id": key[1],
                    "requirement_type": key[2],
                    "pg": {"requirement_type": key[2], "confidence": pg_conf},
                    "neo4j": {"requirement_type": key[2], "confidence": neo_rels[key]},
                }
            )
    for key in neo_rels:
        if key not in pg_rels:
            report["neo4j_only"].append(
                {"position_id": key[0], "skill_id": key[1], "requirement_type": key[2]}
            )

    if report["pg_only"] or report["neo4j_only"] or report["attribute_mismatches"]:
        report["status"] = "mismatch"
    return report
