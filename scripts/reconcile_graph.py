"""Reconcile Neo4j graph against PostgreSQL SSOT.

Architecture decision (Round 3): PG is the single source of truth.
Neo4j is a derived projection. This script deletes any Neo4j node whose
canonical_id no longer exists in PG, and back-fills PG nodes that are
missing from Neo4j.

This is the single command-line escape hatch for the orphaned-neighborhood
problem previously documented in QA reports (Neo4j had 17 stray
positions and 12 extra BELONGS_TO edges with no PG counterpart).

Usage:
    python scripts/reconcile_graph.py
    python scripts/reconcile_graph.py --dry-run         # only report
    python scripts/reconcile_graph.py --backfill        # also insert missing PG → Neo4j
    python scripts/reconcile_graph.py --json            # emit machine-readable report

Exit codes:
    0  success — orphans pruned (and backfill applied if requested)
    1  driver unavailable — PG or Neo4j not reachable; nothing changed
    2  unexpected error
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Make `app.*` importable when run from starmap root
BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("reconcile_graph")


async def _run(dry_run: bool, backfill: bool) -> dict:
    """Main reconciliation routine. Returns a structured report dict."""
    from sqlalchemy import select
    from app.config import settings
    from app.dependencies import get_session_factory, get_neo4j_driver
    from app.models.extraction_models import PositionRecord, SkillRecord
    from app.services.graph_projector import GraphProjector

    sf = get_session_factory()
    driver = None
    try:
        driver = get_neo4j_driver()
    except Exception as exc:  # noqa: BLE001
        logger.error("Neo4j driver unavailable: %s", exc)
        return {"status": "neo4j_unavailable", "error": str(exc)}

    if driver is None:
        logger.error("Neo4j driver is None — nothing to reconcile")
        return {"status": "neo4j_unavailable"}

    report: dict = {
        "status": "ok",
        "pg_counts": {},
        "neo4j_counts_before": {},
        "orphans_pruned": 0,
        "backfilled": 0,
        "dry_run": dry_run,
        "backfill_applied": backfill,
        "orphans_by_label": {},
    }

    async with sf() as session:
        projector = GraphProjector(driver)

        # 1. PG snapshot
        pos_rows = (await session.execute(select(PositionRecord.id, PositionRecord.name))).all()
        skill_rows = (await session.execute(select(SkillRecord.id, SkillRecord.name))).all()
        pg_pos_ids = {str(r[0]) for r in pos_rows}
        pg_skill_ids = {str(r[0]) for r in skill_rows}
        report["pg_counts"] = {
            "positions": len(pg_pos_ids),
            "skills": len(pg_skill_ids),
        }

        # 2. Neo4j snapshot — TWO passes.
        # Pass A: nodes WITH canonical_id (the new world)
        # Pass B: nodes WITHOUT canonical_id (legacy pre-Round-3 era). These
        #         can never be matched to PG by design; we treat them as
        #         orphans and prune them on a real run. This is the fix for
        #         the 16 legacy-position drift the QA report flagged.
        neo4j_ids: dict[str, set[str]] = {}
        legacy_orphans: dict[str, list[dict[str, Any]]] = {}
        async with driver.session() as n4j:
            for label in ("Position", "Skill"):
                # Pass A
                res_a = await n4j.run(
                    f"MATCH (n:{label}) WHERE n.canonical_id IS NOT NULL "
                    "RETURN n.canonical_id AS cid"
                )
                ids: set[str] = set()
                async for record in res_a:
                    cid = record.get("cid") if hasattr(record, "get") else record["cid"]
                    if cid:
                        ids.add(str(cid))
                neo4j_ids[label] = ids

                # Pass B
                res_b = await n4j.run(
                    f"MATCH (n:{label}) WHERE n.canonical_id IS NULL "
                    "RETURN n.name AS name, labels(n) AS labels LIMIT 5000"
                )
                legacy: list[dict[str, Any]] = []
                async for record in res_b:
                    name = record.get("name") if hasattr(record, "get") else record["name"]
                    legacy.append({"name": name})
                legacy_orphans[label] = legacy
        report["neo4j_counts_before"] = {
            "positions": len(neo4j_ids["Position"]),
            "skills": len(neo4j_ids["Skill"]),
            "legacy_positions_no_cid": len(legacy_orphans["Position"]),
            "legacy_skills_no_cid": len(legacy_orphans["Skill"]),
        }

        # 3. Compute orphans (canonical_id path)
        orphan_pos = neo4j_ids["Position"] - pg_pos_ids
        orphan_skill = neo4j_ids["Skill"] - pg_skill_ids
        report["orphans_by_label"] = {
            "Position": sorted(orphan_pos),
            "Skill": sorted(orphan_skill),
        }
        report["legacy_orphans"] = {
            label: [n["name"] for n in items] for label, items in legacy_orphans.items()
        }

        # 4. Prune orphans (unless dry-run)
        pruned_total = 0
        if not dry_run and (orphan_pos or orphan_skill or any(legacy_orphans.values())):
            async with driver.session() as n4j:
                # Canonical-id orphans
                for cid in orphan_pos:
                    await n4j.run(
                        "MATCH (n:Position {canonical_id: $cid}) DETACH DELETE n",
                        cid=cid,
                    )
                for cid in orphan_skill:
                    await n4j.run(
                        "MATCH (n:Skill {canonical_id: $cid}) DETACH DELETE n",
                        cid=cid,
                    )
                # Legacy orphans (no canonical_id) — match by name+labels
                for label, items in legacy_orphans.items():
                    for n in items:
                        if not n["name"]:
                            continue
                        await n4j.run(
                            f"MATCH (n:{label} {{name: $name}}) WHERE n.canonical_id IS NULL "
                            "DETACH DELETE n",
                            name=n["name"],
                        )
                pruned_total = len(orphan_pos) + len(orphan_skill) + sum(len(v) for v in legacy_orphans.values())
            report["orphans_pruned"] = pruned_total
            logger.info(
                "pruned %d orphans (canonical=Position:%d+Skill:%d, legacy=Position:%d+Skill:%d)",
                pruned_total,
                len(orphan_pos), len(orphan_skill),
                len(legacy_orphans["Position"]), len(legacy_orphans["Skill"]),
            )
        elif dry_run:
            logger.info(
                "dry-run: would prune %d canonical-id orphans + %d legacy-no-cid orphans",
                len(orphan_pos) + len(orphan_skill),
                sum(len(v) for v in legacy_orphans.values()),
            )

        # 5. Backfill missing PG → Neo4j (optional)
        if backfill:
            missing_pos = pg_pos_ids - neo4j_ids["Position"]
            missing_skill = pg_skill_ids - neo4j_ids["Skill"]

            positions = []
            if missing_pos:
                rows = (
                    await session.execute(
                        select(PositionRecord).where(
                            PositionRecord.id.in_([__import__("uuid").UUID(c) for c in missing_pos])
                        )
                    )
                ).scalars().all()
                positions = [
                    {
                        "canonical_id": str(p.id),
                        "name": p.name,
                        "name_cn": p.name_cn,
                        "industry": p.industry,
                        "description": p.description,
                    }
                    for p in rows
                ]
            skills = []
            if missing_skill:
                rows = (
                    await session.execute(
                        select(SkillRecord).where(
                            SkillRecord.id.in_([__import__("uuid").UUID(c) for c in missing_skill])
                        )
                    )
                ).scalars().all()
                skills = [
                    {
                        "canonical_id": str(s.id),
                        "name": s.name,
                        "category": s.category,
                        "source_count": s.source_count,
                    }
                    for s in rows
                ]

            if positions or skills:
                result = await projector.apply_batch(positions=positions, skills=skills)
                report["backfilled"] = result.nodes_upserted
                report["backfill_errors"] = result.errors
                logger.info("backfilled %d nodes", report["backfilled"])

            # 5b. Backfill REQUIRES edges (PG PositionSkillRelation → Neo4j)
            #     This closes the gap where nodes exist on both sides but the
            #     edges do not, which is the dominant cause of the "66 vs 527"
            #     REQUIRES count discrepancy the QA report flagged.
            try:
                from app.models.extraction_models import PositionSkillRelation
                rel_rows = (await session.execute(
                    select(
                        PositionRecord.id,
                        PositionRecord.name,
                        SkillRecord.id,
                        SkillRecord.name,
                        PositionSkillRelation.confidence,
                        PositionSkillRelation.level,
                    )
                    .join(PositionSkillRelation, PositionSkillRelation.position_id == PositionRecord.id)
                    .join(SkillRecord, SkillRecord.id == PositionSkillRelation.skill_id)
                )).all()

                if rel_rows:
                    edge_payload = [
                        {
                            "position_id": str(pos_id),
                            "skill_id": str(skill_id),
                            "level": rel_level or "熟悉",
                            "required": True,
                            "confidence": float(confidence or 1.0),
                        }
                        for pos_id, _pos_name, skill_id, _skill_name, confidence, rel_level in rel_rows
                    ]
                    edge_result = await projector.apply_relations(
                        edge_payload, rel_type="REQUIRES"
                    )
                    report["edges_backfilled"] = len(edge_payload)
                    report["edges_backfill_errors"] = edge_result.errors
                    logger.info("backfilled %d REQUIRES edges", len(edge_payload))
            except Exception as exc:
                logger.warning("REQUIRES edge backfill skipped: %s", exc)

    return report


def _print_human(report: dict) -> None:
    print("\n=== reconcile_graph report ===")
    for k, v in report.items():
        if k == "orphans_by_label":
            print(f"{k}:")
            for label, ids in v.items():
                print(f"  {label}: {len(ids)} orphans")
                for cid in ids[:5]:
                    print(f"    - {cid}")
                if len(ids) > 5:
                    print(f"    … +{len(ids) - 5} more")
        elif isinstance(v, list):
            print(f"{k}: {len(v)} items")
        else:
            print(f"{k}: {v}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile Neo4j vs PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    parser.add_argument("--backfill", action="store_true", help="Upsert missing PG nodes to Neo4j")
    parser.add_argument("--json", action="store_true", dest="as_json", help="JSON output")
    args = parser.parse_args()

    try:
        report = asyncio.run(_run(args.dry_run, args.backfill))
    except Exception as exc:  # noqa: BLE001
        logger.error("reconcile failed: %s", exc, exc_info=True)
        return 2

    if args.as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_human(report)

    return 0 if report.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())