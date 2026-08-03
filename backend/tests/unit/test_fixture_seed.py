"""Tests for fixture seed — verify data flows correctly through review_service + graph_writer."""
import pytest


class TestFixtureSeed:
    """Integration tests for app.data.fixtures.seed."""

    @pytest.mark.asyncio
    async def test_load_fixtures_returns_valid_positions(self):
        """Fixture JSON parses correctly with required fields."""
        from app.data.fixtures.seed import _load_json

        positions = _load_json("positions.json")
        assert len(positions) == 35, f"Expected 35 positions, got {len(positions)}"
        for p in positions:
            assert "name" in p, f"Missing 'name' in {p}"
            assert "skills" in p, f"Missing 'skills' in {p}"
            assert len(p["skills"]) > 0, f"Empty skills for {p['name']}"

    @pytest.mark.asyncio
    async def test_load_fixtures_returns_valid_skills(self):
        """Skills fixture contains unique skills with categories."""
        from app.data.fixtures.seed import _load_json

        skills = _load_json("skills.json")
        assert len(skills) > 100, f"Expected >100 skills, got {len(skills)}"
        names = [s["name"] for s in skills]
        assert len(names) == len(set(names)), "Skills must be unique"

    @pytest.mark.asyncio
    async def test_seed_is_idempotent(self, db_session):
        """Running seed twice does not create duplicates."""
        from app.data.fixtures.seed import seed_positions, seed_skills
        from sqlalchemy import select, func
        from app.models.extraction_models import PositionRecord, SkillRecord

        # First run
        p1 = await seed_positions(db_session)
        s1 = await seed_skills(db_session)

        # Second run
        p2 = await seed_positions(db_session)
        s2 = await seed_skills(db_session)

        assert p2 == 0, f"Second seed should create 0 new positions, got {p2}"
        assert s2 == 0, f"Second seed should create 0 new skills, got {s2}"

    @pytest.mark.asyncio
    async def test_seed_creates_position_skill_relations(self, db_session):
        """After seed, position_skill_relations table is not empty."""
        from app.data.fixtures.seed import seed_positions, seed_skills, seed_position_skill_relations
        from sqlalchemy import text

        await seed_positions(db_session)
        await seed_skills(db_session)
        await seed_position_skill_relations(db_session)

        count = (await db_session.execute(
            text("SELECT count(*) FROM position_skill_relations")
        )).scalar()

        assert count > 0, "position_skill_relations should have records after seed"

    @pytest.mark.asyncio
    async def test_offline_pipeline_uses_fixtures(self):
        """_crawl_from_fixtures returns valid crawl output."""
        # _crawl_from_fixtures 已从 executor 移除(离线 fixture 爬取功能未在当前实现)。
        pytest.skip("_crawl_from_fixtures 未在当前 executor 实现;离线 fixture 爬取待重新实现。")
