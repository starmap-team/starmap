"""Integration test — evolution pipeline full chain (real PG + real/local Neo4j).

C-5 入口闭环端到端：快照 → diff → trust → changelog 落库 → D-04 回写
position_skill_relations → D-04 尾句 Neo4j 增量投影 → D-07 一致性校验。

NOTE: 本文件在 tests/integration/ 下，pytest 默认 addopts 含
``--ignore=tests/integration``，需 ``-o addopts=""`` 运行（真实 DB + Neo4j）。

测试使用唯一岗位名/技能名，避免污染真实数据；结束后清理本测试创建的行与图谱节点。
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa

from app.core.evolution.orchestrator import run_evolution_pipeline
from app.core.extraction.graph_writer import GraphConfig
from app.db.session import get_async_engine
from app.models.evolution_models import EvolutionChangelog, EvolutionSnapshot
from app.models.extraction_models import (
    JDExtractionRecord,
    PositionRecord,
    PositionSkillRelation,
    SkillRecord,
)

TEST_POSITION = f"IT_EvolIntegration_{uuid.uuid4().hex[:8]}"
OLD_SKILL = f"EvolOld_{uuid.uuid4().hex[:8]}"
NEW_SKILL = f"EvolNew_{uuid.uuid4().hex[:8]}"


def _month_starts(ref: datetime) -> tuple[datetime, datetime]:
    """Return (prev_month_start, current_month_start) in UTC."""
    current_start = datetime(ref.year, ref.month, 1, tzinfo=UTC)
    if ref.month == 1:
        prev_start = datetime(ref.year - 1, 12, 1, tzinfo=UTC)
    else:
        prev_start = datetime(ref.year, ref.month - 1, 1, tzinfo=UTC)
    return prev_start, current_start


def _make_jd(position: str, skills: list[str], created_at: datetime) -> JDExtractionRecord:
    return JDExtractionRecord(
        jd_content="integration test JD",
        job_title=position,
        extracted_skills={
            "position_name": position,
            "required_skills": [{"name": s, "category": "general"} for s in skills],
            "preferred_skills": [],
        },
        status="completed",
        confidence=0.9,
        created_at=created_at,
    )


@pytest.fixture
async def pipeline_env():
    """Seed a unique test position + Neo4j nodes, run the pipeline, yield summary.

    Old month: OLD_SKILL (3 JD). Current month: OLD_SKILL + NEW_SKILL (5 JD).
    Diff yields ``added_required`` for NEW_SKILL with source_count=5 →
    trust ≈ 0.85 ≥ 0.6 → written back to PSR and projected to Neo4j.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker

    engine = get_async_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    prev_start, current_start = _month_starts(now)

    position_id: uuid.UUID | None = None
    new_skill_id: uuid.UUID | None = None
    try:
        async with sessionmaker() as session:
            # PositionRecord so write-back can resolve position_id (D-08: real row, not fabricated)
            pos_row = PositionRecord(name=TEST_POSITION, created_by="system:itest")
            session.add(pos_row)
            await session.flush()
            position_id = pos_row.id

            # Pre-create the new skill record so its id is deterministic for the Neo4j node.
            skill_row = SkillRecord(name=NEW_SKILL, category="general", source_count=1, created_by="system:itest")
            session.add(skill_row)
            await session.flush()
            new_skill_id = skill_row.id

            # Old month records (created_at in prev month)
            for _ in range(3):
                session.add(_make_jd(TEST_POSITION, [OLD_SKILL], prev_start + timedelta(days=10)))
            # Current month records (created_at now)
            for _ in range(5):
                session.add(_make_jd(TEST_POSITION, [OLD_SKILL, NEW_SKILL], now))
            await session.commit()

        # Neo4j nodes must exist with canonical_id before projection MATCH can resolve them.
        config = GraphConfig()
        async with config.get_driver() as driver:
            async with driver.session() as session:
                await session.run(
                    "MERGE (p:Position {name: $name}) SET p.canonical_id = $cid",
                    name=TEST_POSITION, cid=str(position_id),
                )
                await session.run(
                    "MERGE (s:Skill {name: $name}) SET s.canonical_id = $cid",
                    name=NEW_SKILL, cid=str(new_skill_id),
                )
                await session.run(
                    "MERGE (s:Skill {name: $name}) SET s.canonical_id = $cid",
                    name=OLD_SKILL, cid=str(uuid.uuid4()),
                )

        summary = await run_evolution_pipeline(months_back=2)
        yield summary, position_id, new_skill_id
    finally:
        # Cleanup PG rows created by this test + the pipeline for this position.
        async with sessionmaker() as session:
            await session.execute(
                sa.delete(EvolutionChangelog).where(EvolutionChangelog.position_name == TEST_POSITION)
            )
            await session.execute(
                sa.delete(JDExtractionRecord).where(JDExtractionRecord.job_title == TEST_POSITION)
            )
            await session.execute(sa.delete(EvolutionSnapshot).where(EvolutionSnapshot.position_name == TEST_POSITION))
            if position_id is not None:
                await session.execute(
                    sa.delete(PositionSkillRelation).where(PositionSkillRelation.position_id == position_id)
                )
            await session.execute(sa.delete(PositionRecord).where(PositionRecord.name == TEST_POSITION))
            await session.execute(sa.delete(SkillRecord).where(SkillRecord.name.in_([NEW_SKILL, OLD_SKILL])))
            await session.commit()
        # Cleanup Neo4j nodes/edges for the test position + skills.
        config = GraphConfig()
        async with config.get_driver() as driver:
            async with driver.session() as session:
                await session.run(
                    "MATCH (p:Position {name: $name}) DETACH DELETE p",
                    name=TEST_POSITION,
                )
                for skill_name in (NEW_SKILL, OLD_SKILL):
                    await session.run(
                        "MATCH (s:Skill {name: $name}) DETACH DELETE s",
                        name=skill_name,
                    )
        await engine.dispose()


@pytest.mark.asyncio
async def test_pipeline_full_chain_write_back_and_projection(pipeline_env):
    """全链：changelog 生成、trust≥0.6 added_required 回写 PSR、Neo4j 边可见、consistency 存在。"""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    summary, position_id, new_skill_id = pipeline_env
    assert position_id is not None
    assert new_skill_id is not None

    sessionmaker = async_sessionmaker(get_async_engine(), expire_on_commit=False)
    async with sessionmaker() as session:
        # 1) changelog row for NEW_SKILL added_required must exist + written_back=True
        row = (
            await session.execute(
                sa.select(EvolutionChangelog).where(
                    EvolutionChangelog.position_name == TEST_POSITION,
                    EvolutionChangelog.skill_name == NEW_SKILL,
                    EvolutionChangelog.change_type == "added_required",
                )
            )
        ).scalars().first()
        assert row is not None, "expected an added_required changelog row for the new skill"
        assert row.trust_score >= 0.6, f"trust_score={row.trust_score} must be >= 0.6"
        assert row.written_back is True, "written_back must be True after successful write-back"

        # 2) PSR row must exist with requirement_type='required'
        psr = (
            await session.execute(
                sa.select(PositionSkillRelation).where(
                    PositionSkillRelation.position_id == position_id,
                    PositionSkillRelation.skill_id == new_skill_id,
                )
            )
        ).scalars().first()
        assert psr is not None, "expected a position_skill_relations row after write-back"
        assert psr.requirement_type == "required"

    # 3) REQUIRES edge must be visible in Neo4j after projection (D-04 尾句闭环)
    config = GraphConfig()
    async with config.get_driver() as driver:
        async with driver.session() as session:
            record = await (
                await session.run(
                    "MATCH (p:Position {canonical_id: $pid})-[r:REQUIRES]->(s:Skill {canonical_id: $sid}) "
                    "RETURN r.requirement_type AS rt",
                    pid=str(position_id), sid=str(new_skill_id),
                )
            ).single()
    assert record is not None, "REQUIRES edge must exist in Neo4j after projection"
    assert record["rt"] == "required"

    # 4) summary must carry the consistency key (D-07)
    assert "consistency" in summary, "summary must contain the consistency key"
    assert summary["consistency"]["status"] in ("ok", "mismatch", "error")
    assert "checked_at" in summary["consistency"]


@pytest.mark.asyncio
async def test_pipeline_summary_shape(pipeline_env):
    """Summary 携带管线关键计数与 warnings 列表。"""
    summary, _, _ = pipeline_env
    assert summary["changelogs_written"] >= 1
    assert isinstance(summary["warnings"], list)
    assert "graph_projected_edges" in summary
    assert "completed_at" in summary
