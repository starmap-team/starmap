"""推荐引擎 — 基于求职者技能画像推荐匹配岗位。

使用 PositionRepository 批量加载岗位画像，复用 score_skill_match 评分逻辑，
综合匹配度、可发展性和市场需求进行排序推荐。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from loguru import logger

from app.pipeline.contracts import ExtractedSkill, PositionProfile
from app.repositories.position_repository import PositionRepository
from app.services.match_service import PREREQUISITE_MAP, score_skill_match


@dataclass
class Recommendation:
    """单个岗位推荐结果。"""

    position: str
    score: float  # 综合得分 [0, 1]
    match_score: float  # 匹配度分量
    developability: float  # 可发展性分量
    market_demand: float  # 市场需求分量
    match_detail: dict[str, Any]  # 匹配详情（来自 score_skill_match）


class PositionRecommender:
    """岗位推荐引擎。

    评分公式：score = match_score × 0.6 + developability × 0.3 + market_demand × 0.1
    """

    def __init__(
        self,
        repo: PositionRepository,
        scorer: Callable[..., dict[str, Any]] | None = None,
    ) -> None:
        self._repo = repo
        self._scorer = scorer or score_skill_match

    async def recommend(
        self,
        person_skills: list[ExtractedSkill],
        top_k: int = 10,
    ) -> list[Recommendation]:
        """基于求职者技能画像推荐 Top-K 岗位。"""
        all_profiles = await self._repo.get_all_position_profiles()
        if not all_profiles:
            logger.warning("[Recommender] No position profiles available")
            return []

        # 转换为 score_skill_match 期望的格式（key="skill"）
        person_skill_dicts: list[dict[str, Any]] = [
            {"skill": s.name, "proficiency": s.proficiency}
            for s in person_skills
        ]

        scores: list[Recommendation] = []
        for name, profile in all_profiles.items():
            try:
                match_result = self._scorer(
                    target_skills=profile.required_skills,
                    person_skills=person_skill_dicts,
                    threshold=0.6,
                )
                # 从 evaluated 列表计算匹配度均值
                evaluated = match_result.get("evaluated", [])
                match_score = (
                    sum(e["score"] for e in evaluated) / len(evaluated)
                    if evaluated
                    else 0.0
                )

                developability = self._compute_developability(person_skills, profile)
                market_demand = profile.market_demand

                final_score = match_score * 0.6 + developability * 0.3 + market_demand * 0.1

                scores.append(Recommendation(
                    position=name,
                    score=round(final_score, 4),
                    match_score=round(match_score, 4),
                    developability=round(developability, 4),
                    market_demand=round(market_demand, 4),
                    match_detail=match_result,
                ))
            except Exception as exc:
                logger.debug("[Recommender] Failed to score {}: {}", name, exc)
                continue

        scores.sort(key=lambda r: r.score, reverse=True)
        return scores[:top_k]

    def _compute_developability(
        self,
        person_skills: list[ExtractedSkill],
        profile: PositionProfile,
    ) -> float:
        """计算技能可发展性：缺失技能中有多少可以通过学习路径弥补。

        算法：
        1. 找出 person 缺失的 required_skills
        2. 对每个缺失技能，检查 PREREQUISITE 图中是否有从已有技能到目标的学习路径
        3. 可发展性 = 有路径的缺失技能数 / 总缺失技能数
        4. 无 PREREQUISITE 数据时降级为 0.5（中性值）
        """
        owned = {s.name for s in person_skills}
        missing = [s for s in profile.required_skills if s["name"] not in owned]
        if not missing:
            return 1.0  # 无缺失，完美可发展性
        if not PREREQUISITE_MAP:
            return 0.5  # 无前置知识图数据，降级为中性值
        reachable = sum(
            1
            for s in missing
            if any(prereq in owned for prereq in PREREQUISITE_MAP.get(s["name"], []))
        )
        return reachable / len(missing)
