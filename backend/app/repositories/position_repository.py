"""PositionRepository — 统一的岗位画像数据访问层。

替代 match_service._load_target_profile 的内联逻辑，
提供批量加载、缓存和数据质量统计。
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.pipeline.contracts import DataQualityStats, PositionProfile


class PositionRepository:
    """Neo4j 岗位画像数据访问层，支持批量加载和缓存。"""

    def __init__(self, driver: Any) -> None:
        self._driver = driver
        self._cache: dict[str, PositionProfile] = {}
        self._cache_loaded = False

    async def get_all_position_profiles(self) -> dict[str, PositionProfile]:
        """单次 Cypher 查询加载所有岗位画像。

        使用 COALESCE 处理可能缺失的属性，避免返回 null。
        结果缓存在内存中，后续调用直接返回缓存。
        """
        if self._cache_loaded:
            return self._cache

        query = """
        MATCH (p:Position)-[rel:REQUIRES]->(s:Skill)
        RETURN p.name AS pos_name,
               COALESCE(p.industry, '') AS industry,
               collect({
                   name: s.name,
                   category: COALESCE(s.category, 'hard_skill'),
                   proficiency: COALESCE(rel.level, '熟悉'),
                   is_required: COALESCE(rel.required, true)
               }) AS skills
        """
        try:
            async with self._driver.session() as session:
                result = await session.run(query)
                records = await result.data()

            for rec in records:
                pos_name = rec["pos_name"]
                skills = rec["skills"]
                required = [s for s in skills if s.get("is_required", True)]
                bonus = [s for s in skills if not s.get("is_required", True)]
                self._cache[pos_name] = PositionProfile(
                    name=pos_name,
                    industry=rec.get("industry", ""),
                    required_skills=required,
                    bonus_skills=bonus,
                )
            self._cache_loaded = True
            logger.info("[PositionRepository] Loaded {} position profiles from Neo4j", len(self._cache))
        except Exception as exc:
            logger.warning("[PositionRepository] Failed to load from Neo4j: {}", exc)

        return self._cache

    async def get_position_profile(self, name: str) -> PositionProfile | None:
        """单个岗位查询（带缓存）。"""
        if not self._cache_loaded:
            await self.get_all_position_profiles()
        return self._cache.get(name)

    async def get_data_quality_stats(self) -> DataQualityStats:
        """返回图谱数据质量统计。"""
        profiles = await self.get_all_position_profiles()
        total_positions = len(profiles)
        positions_with_skills = sum(1 for p in profiles.values() if len(p.required_skills) >= 3)
        total_skills_set: set[str] = set()
        for p in profiles.values():
            for s in p.required_skills + p.bonus_skills:
                total_skills_set.add(s["name"])

        # 查询 PREREQUISITE 关系数
        prerequisite_count = 0
        try:
            async with self._driver.session() as session:
                result = await session.run("MATCH ()-[r:PREREQUISITE]->() RETURN count(r) AS cnt")
                record = await result.single()
                if record:
                    prerequisite_count = record["cnt"]
        except Exception:
            pass

        return DataQualityStats(
            total_positions=total_positions,
            positions_with_skills=positions_with_skills,
            coverage_ratio=positions_with_skills / total_positions if total_positions else 0.0,
            total_skills=len(total_skills_set),
            skills_with_sources=0,  # 需要查询 source_count，暂用0
            skill_trust_ratio=0.0,
            prerequisite_count=prerequisite_count,
        )
