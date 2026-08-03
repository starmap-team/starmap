"""Coverage boost tests for PositionRepository — pure/cache paths."""

from __future__ import annotations

import pytest

from app.core.pipeline.sse.contracts import DataQualityStats, PositionProfile
from app.repositories.position_repository import PositionRepository


class TestPositionRepositoryInit:
    def test_init_defaults(self):
        repo = PositionRepository(driver=None)
        assert repo._cache == {}
        assert repo._cache_loaded is False


class TestGetAllProfilesWithNoneDriver:
    @pytest.mark.asyncio
    async def test_returns_empty_on_none_driver(self):
        repo = PositionRepository(driver=None)
        result = await repo.get_all_position_profiles()
        assert result == {}
        # cache stays unloaded because driver raised exception
        assert repo._cache_loaded is False


class TestGetPositionProfileFromCache:
    @pytest.mark.asyncio
    async def test_cache_hit(self):
        repo = PositionRepository(driver=None)
        repo._cache_loaded = True
        repo._cache["Backend Engineer"] = PositionProfile(
            name="Backend Engineer",
            industry="IT",
            required_skills=[{"name": "Python", "category": "hard_skill"}],
        )
        result = await repo.get_position_profile("Backend Engineer")
        assert result is not None
        assert result.name == "Backend Engineer"

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        repo = PositionRepository(driver=None)
        repo._cache_loaded = True
        result = await repo.get_position_profile("Nonexistent")
        assert result is None


class TestDataQualityStatsEmpty:
    @pytest.mark.asyncio
    async def test_empty_cache_stats(self):
        repo = PositionRepository(driver=None)
        repo._cache_loaded = True
        repo._cache = {}
        stats = await repo.get_data_quality_stats()
        assert isinstance(stats, DataQualityStats)
        assert stats.total_positions == 0
        assert stats.coverage_ratio == 0.0
        assert stats.total_skills == 0

    @pytest.mark.asyncio
    async def test_stats_with_profiles(self):
        repo = PositionRepository(driver=None)
        repo._cache_loaded = True
        repo._cache["Dev"] = PositionProfile(
            name="Dev",
            industry="IT",
            required_skills=[
                {"name": "Python", "category": "hard_skill"},
                {"name": "SQL", "category": "hard_skill"},
                {"name": "Docker", "category": "hard_skill"},
            ],
        )
        stats = await repo.get_data_quality_stats()
        assert stats.total_positions == 1
        assert stats.positions_with_skills == 1
        assert stats.coverage_ratio == 1.0
        assert stats.total_skills == 3
