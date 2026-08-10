"""推荐引擎 — 基于求职者技能画像推荐匹配岗位。

使用 PositionRepository 批量加载岗位画像，复用 score_skill_match 评分逻辑，
综合匹配度、可发展性和市场需求进行排序推荐。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from loguru import logger

from app.config import settings
from app.core.pipeline.sse.contracts import ExtractedSkill, PositionProfile
from app.exceptions import MatchingError, StarMapError
from app.repositories.position_repository import PositionRepository
from app.services.match_service import (
    PREREQUISITE_MAP,
    ensure_prerequisite_map,
    score_skill_match,
)


@dataclass
class Recommendation:
    """单个岗位推荐结果。

    Attributes:
        position: 岗位名称（对应 PositionProfile 中的键）。
        score: 综合得分 [0, 1]，由 match_score、developability、market_demand 加权得到。
        match_score: 技能匹配度分量 [0, 1]，基于 score_skill_match 对 required_skills 的评估均值。
        developability: 可发展性分量 [0, 1]，缺失技能中有学习路径的比例。
        market_demand: 市场需求分量 [0, 1]，来源于 PositionProfile.market_demand。
        match_detail: 来自 score_skill_match 的完整匹配详情（含 evaluated、missing 等字段）。
    """

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
        """初始化推荐引擎。

        Args:
            repo: 岗位数据仓库，用于加载所有岗位画像。
            scorer: 技能匹配评分函数（默认 score_skill_match）。
                    签名必须与 score_skill_match 兼容：
                    scorer(target_skills, person_skills, threshold) -> dict
        """
        self._repo = repo
        self._scorer = scorer or score_skill_match

    async def recommend(
        self,
        person_skills: list[ExtractedSkill],
        top_k: int = 10,
    ) -> list[Recommendation]:
        """基于求职者技能画像推荐 Top-K 岗位。

        评分公式：``score = match_score × 0.6 + developability × 0.3 + market_demand × 0.1``

        流程：
        1. 通过 PositionRepository 加载所有岗位画像。
        2. 对每个岗位，调用 scorer 计算技能匹配度（match_score）。
        3. 调用 _compute_developability 评估可发展性。
        4. 组合加权得分，按 score 降序排序，返回 Top-K。

        Args:
            person_skills: 求职者技能列表，每个技能含 name 和 proficiency。
            top_k: 返回的推荐数量上限，默认 10。

        Returns:
            按综合得分降序排列的推荐列表，最多 top_k 条。
            若无可用岗位画像，返回空列表。

        Raises:
            StarMapError: 仓库层或评分层返回的 StarMap 系统错误（透传）。
            MatchingError: 评分层返回的匹配逻辑错误（透传）。
        """
        # NEW-03: 确保前置关系已从 Neo4j 加载（developability 依赖，不可用时降级为空）
        await ensure_prerequisite_map()

        all_profiles = await self._repo.get_all_position_profiles()
        if not all_profiles:
            logger.warning("[Recommender] No position profiles available")
            return []

        # 转换为 score_skill_match 期望的格式（key="skill"）
        person_skill_dicts: list[dict[str, Any]] = [
            {"skill": s.name, "proficiency": s.proficiency} for s in person_skills
        ]

        scores: list[Recommendation] = []
        for name, profile in all_profiles.items():
            try:
                match_result = self._scorer(
                    target_skills=profile.required_skills,
                    person_skills=person_skill_dicts,
                    threshold=settings.match_threshold,
                )
                # 从 evaluated 列表计算匹配度均值
                evaluated = match_result.get("evaluated", [])
                match_score = sum(e["score"] for e in evaluated) / len(evaluated) if evaluated else 0.0

                developability = self._compute_developability(person_skills, profile)
                market_demand = profile.market_demand

                final_score = match_score * 0.6 + developability * 0.3 + market_demand * 0.1

                scores.append(
                    Recommendation(
                        position=name,
                        score=round(final_score, 4),
                        match_score=round(match_score, 4),
                        developability=round(developability, 4),
                        market_demand=round(market_demand, 4),
                        match_detail=match_result,
                    )
                )
            except StarMapError:
                raise
            except MatchingError:
                raise
            except Exception as exc:
                logger.exception("[Recommender] Failed to score {}: {}", name, exc)
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
        reachable = sum(1 for s in missing if any(prereq in owned for prereq in PREREQUISITE_MAP.get(s["name"], [])))
        return reachable / len(missing)
