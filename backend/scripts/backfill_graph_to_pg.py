"""One-shot backfill: PG ← Neo4j missing skills & REQUIRES edges.

漂移根因（stage3_services.run_batch_extract_jd:294-298）：技能落 PG 是 non-fatal，
失败仅告警、图谱写入继续 → Neo4j 有、PG 没有。本脚本把 PG 缺失的
SkillRecord（canonical_id 恢复原 id）与 PositionSkillRelation 回填，
使两库节点/边对齐，图谱数据零丢失。

方向：PG ← Neo4j（Neo4j 为图谱真源；PG 主数据补全）。
D-08 附加段：4 个无 canonical_id 的 Position（算法专家/技术总监/架构师/
Brandschutztechniker）先在 PG 建 PositionRecord（created_by="system:backfill"），
再补 Neo4j Position.canonical_id = PG id，使两侧一致并可参与演化回写解析。

用法：poetry run python -m scripts.backfill_graph_to_pg
"""
from __future__ import annotations

import asyncio
import sys
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

sys.path.insert(0, ".")

from app.core.extraction.graph_writer import GraphConfig  # noqa: E402
from app.db.session import get_async_engine  # noqa: E402
from app.models.extraction_models import PositionRecord, PositionSkillRelation, SkillRecord  # noqa: E402

# D-08: 4 个无 canonical_id 的 Position（无法参与演化回写解析，静默跳过）。
# Brandschutztechniker 在 Neo4j 中的实际节点名为 "Brandschutztechniker/-in"
# （精确名节点不存在；其中一条已带 canonical_id，一条为 NULL），此处用实际节点名。
D08_POSITION_NAMES = ["算法专家", "技术总监", "架构师", "Brandschutztechniker/-in"]


async def main() -> None:
    engine = get_async_engine()
    async with engine.begin() as conn:
        pg_skill_ids = {str(r[0]) for r in (await conn.execute(select(SkillRecord.id))).all()}
        pg_skill_names = {r[0] for r in (await conn.execute(select(SkillRecord.name))).all()}
        pg_pos_ids = {str(r[0]) for r in (await conn.execute(select(PositionRecord.id))).all()}

    config = GraphConfig()
    async with config.get_driver() as driver:
        async with driver.session() as s:
            skills = await (await s.run(
                "MATCH (sk:Skill) WHERE sk.canonical_id IS NOT NULL "
                "RETURN sk.canonical_id AS cid, sk.name AS name, sk.category AS cat, sk.source_count AS sc"
            )).data()
            edges = await (await s.run(
                "MATCH (p:Position)-[r:REQUIRES]->(sk:Skill) "
                "WHERE p.canonical_id IS NOT NULL AND sk.canonical_id IS NOT NULL "
                "RETURN p.canonical_id AS pcid, sk.canonical_id AS scid, "
                "r.confidence AS conf, r.requirement_type AS rt"
            )).data()

    async with engine.begin() as conn:
        # 1) 技能回填：PG 缺 id 或缺 name 的 Skill 直接插入（保留原 canonical_id）
        new_skills = []
        for sk in skills:
            cid, name = str(sk["cid"]), sk["name"]
            if not name or cid in pg_skill_ids or name in pg_skill_names:
                continue
            new_skills.append({
                "id": UUID(cid),
                "name": name,
                "category": sk.get("cat") or "general",
                "source_count": int(sk.get("sc") or 0),
                "review_status": "approved",
            })
        if new_skills:
            await conn.execute(
                pg_insert(SkillRecord)
                .values(new_skills)
                .on_conflict_do_nothing(index_elements=[SkillRecord.name])
            )
        # 刷新 PG 技能 id（供边回填 FK 检查）
        pg_skill_ids = {str(r[0]) for r in (await conn.execute(select(SkillRecord.id))).all()}

        # 2) REQUIRES 边回填：两端均在 PG 且该 (position, skill) 对缺失
        pg_rel_keys = {
            (str(r[0]), str(r[1]))
            for r in (await conn.execute(select(PositionSkillRelation.position_id, PositionSkillRelation.skill_id))).all()
        }
        new_rels = []
        for e in edges:
            pid, sid = str(e["pcid"]), str(e["scid"])
            if pid not in pg_pos_ids or sid not in pg_skill_ids or (pid, sid) in pg_rel_keys:
                continue
            new_rels.append({
                "position_id": UUID(pid),
                "skill_id": UUID(sid),
                "requirement_type": e.get("rt") or "required",
                "confidence": float(e.get("conf") or 1.0),
            })
        if new_rels:
            await conn.execute(pg_insert(PositionSkillRelation).values(new_rels))

    print(f"backfilled_skills={len(new_skills)} backfilled_edges={len(new_rels)}")

    # 3) D-08：4 个无 canonical_id 岗位补齐（PG 建行 + Neo4j SET canonical_id）
    d08 = await backfill_position_canonical_ids()
    print(
        "d08_created_pg={} d08_set_neo4j={} d08_skipped={}".format(
            d08["created_pg"], d08["set_neo4j"], d08["skipped"]
        )
    )
    if d08["set_neo4j"]:
        # D-07: 一次性对账脚本不作自动调度，仅提示手动重投影
        print("D-08 hint: canonical_id 已补齐，如需从 PG 全量重投影请手动运行 phase5_rebuild_neo4j.py")
    await engine.dispose()


async def backfill_position_canonical_ids() -> dict[str, list[str]]:
    """D-08: 为 4 个无 canonical_id 的岗位补齐 PG PositionRecord + Neo4j canonical_id。

    PG 侧按 ``_upsert_position`` 同款模式建行（name, created_by="system:backfill"）取 id；
    Neo4j 侧 ``MATCH (p:Position {name: $name}) WHERE p.canonical_id IS NULL SET`` —
    幂等，已带 canonical_id 的节点跳过（Brandschutztechniker/-in 两条中仅补 NULL 的那条）。
    仅提示重跑重投影脚本，不在脚本内自动调度（D-07）。
    """
    engine = get_async_engine()
    config = GraphConfig()
    stats: dict[str, list[str]] = {"created_pg": [], "set_neo4j": [], "skipped": []}

    async with engine.begin() as conn:
        rows = (
            await conn.execute(
                select(PositionRecord.id, PositionRecord.name).where(
                    PositionRecord.name.in_(D08_POSITION_NAMES)
                )
            )
        ).all()
        name_to_id = {name: str(rid) for rid, name in rows}
        missing = [n for n in D08_POSITION_NAMES if n not in name_to_id]
        if missing:
            await conn.execute(
                pg_insert(PositionRecord)
                .values([{"name": n, "created_by": "system:backfill"} for n in missing])
                .on_conflict_do_nothing(index_elements=[PositionRecord.name])
            )
            stats["created_pg"] = missing
            rows = (
                await conn.execute(
                    select(PositionRecord.id, PositionRecord.name).where(
                        PositionRecord.name.in_(D08_POSITION_NAMES)
                    )
                )
            ).all()
            name_to_id = {name: str(rid) for rid, name in rows}

    async with config.get_driver() as driver:
        async with driver.session() as s:
            for name in D08_POSITION_NAMES:
                pid = name_to_id.get(name)
                if pid is None:
                    stats["skipped"].append(name)
                    continue
                rec = await s.run(
                    "MATCH (p:Position {name: $name}) WHERE p.canonical_id IS NULL "
                    "SET p.canonical_id = $pid RETURN p.name AS name, p.canonical_id AS cid",
                    name=name,
                    pid=pid,
                )
                if await rec.data():
                    stats["set_neo4j"].append(name)
    await engine.dispose()
    return stats


if __name__ == "__main__":
    asyncio.run(main())
