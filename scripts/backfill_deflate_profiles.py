"""治理现有膨胀岗位画像（backfill）— 与写入门禁配套。

写入门禁（ingestion_gate）只拦新写入；存量岗位已膨胀（后端工程师 15 个
required 含 Axon/Ktor 等跨 JD 噪声）。本脚本对 approved 岗位中 required
技能数 > 上限 的岗位，按 source_count 降序保留核心技能，其余降级 preferred，
并同步 Neo4j（REQUIRES 边 required=True → False，保持双库一致）。

用法:
    cd backend
    poetry run python ../scripts/backfill_deflate_profiles.py [--cap 7] [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.extraction.ingestion_gate import DEFAULT_REQUIRED_CAP
from app.db.session import get_async_engine
from app.models.extraction_models import PositionRecord, PositionSkillRelation, SkillRecord
from app.services.resources import init_resources


async def collect_inflated(session_maker, cap: int) -> list[tuple[str, list[tuple[str, int]]]]:
    """找 required 技能数 > cap 的 approved 岗位，返回 [(岗位, [(技能, source_count)])]。"""
    async with session_maker() as session:
        rows = (
            await session.execute(
                select(
                    PositionRecord.name,
                    SkillRecord.name.label("skill_name"),
                    SkillRecord.source_count,
                )
                .select_from(PositionSkillRelation)
                .join(PositionRecord, PositionRecord.id == PositionSkillRelation.position_id)
                .join(SkillRecord, SkillRecord.id == PositionSkillRelation.skill_id)
                .where(PositionRecord.review_status == "approved")
                .where(PositionSkillRelation.requirement_type == "required")
                .order_by(PositionRecord.name, SkillRecord.source_count.desc())
            )
        ).all()
    grouped: dict[str, list[tuple[str, int]]] = {}
    for name, skill_name, source_count in rows:
        grouped.setdefault(name, []).append((skill_name, int(source_count or 0)))
    return [(name, skills) for name, skills in grouped.items() if len(skills) > cap]


async def deflate(session_maker, cap: int, dry_run: bool) -> None:
    inflated = await collect_inflated(session_maker, cap)
    if not inflated:
        print("[deflate] 无 required > {} 的岗位，跳过".format(cap))
        return
    print(f"[deflate] 发现 {len(inflated)} 个 required 超 {cap} 的岗位" + ("（dry-run）" if dry_run else ""))

    async with session_maker() as session:
        for pos_name, skills in inflated:
            keep = skills[:cap]  # source_count 降序已排序，保留前 cap 个
            demote = skills[cap:]
            if dry_run:
                print(f"  [dry] {pos_name}: {len(skills)} required → 保留 {len(keep)} 降级 {len(demote)}")
                continue
            # 降级：把 required 关系改为 preferred
            pos = (
                await session.execute(
                    select(PositionRecord).where(PositionRecord.name == pos_name)
                )
            ).scalar_one_or_none()
            if pos is None:
                continue
            demote_names = [s for s, _ in demote]
            if demote_names:
                await session.execute(
                    PositionSkillRelation.__table__.update()
                    .where(PositionSkillRelation.position_id == pos.id)
                    .where(PositionSkillRelation.requirement_type == "required")
                    .where(PositionSkillRelation.skill_id.in_(
                        select(SkillRecord.id).where(SkillRecord.name.in_(demote_names))
                    ))
                    .values(requirement_type="preferred")
                )
            print(f"  ✓ {pos_name}: {len(skills)} → 保留 {len(keep)} required, 降级 {len(demote)} → preferred")
        await session.commit()

    # 同步 Neo4j：REQUIRES 边 required=True → False（保持双库一致，匹配从 Neo4j 读画像）
    if not dry_run:
        try:
            res = await init_resources()
            driver = res.neo4j_driver
            if driver is not None:
                async with driver.session() as neo_session:
                    for pos_name, skills in inflated:
                        demote_names = [s for s, _ in skills[DEFAULT_REQUIRED_CAP:]]
                        if not demote_names:
                            continue
                        await neo_session.run(
                            "MATCH (p:Position {name: $pos})-[r:REQUIRES]->(s:Skill) "
                            "WHERE s.name IN $skills SET r.required = false",
                            pos=pos_name,
                            skills=demote_names,
                        )
                    print(f"[deflate] Neo4j 同步完成：{len(inflated)} 个岗位的降级边已更新")
                await res.close()
        except Exception as exc:  # noqa: BLE001 — Neo4j 同步失败不阻断 PG 治理
            print(f"[deflate] Neo4j 同步失败（PG 已治理，需手工补同步）: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="治理膨胀岗位画像（required 超上限降级）")
    parser.add_argument("--cap", type=int, default=DEFAULT_REQUIRED_CAP, help="required 上限")
    parser.add_argument("--dry-run", action="store_true", help="只报告不改库")
    args = parser.parse_args()

    async def _run() -> None:
        engine = get_async_engine()
        sm = async_sessionmaker(engine, expire_on_commit=False)
        try:
            await deflate(sm, args.cap, args.dry_run)
        finally:
            await engine.dispose()

    asyncio.run(_run())


if __name__ == "__main__":
    main()