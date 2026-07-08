"""Match Service — 图驱动匹配引擎（向后兼容包装器）。

此模块现在作为 app.core.matching 的向后兼容包装器。
新代码应直接使用 app.core.matching 中的组件。

核心功能：
  从 Neo4j 加载岗位技能画像，与求职者技能进行多维度匹配评分，
  识别技能差距，生成个性化学习路径推荐。
"""

from __future__ import annotations

from typing import Any

# 从新的模块化组件导入
from app.core.matching.cache import get_match_cache
from app.core.matching.path_builder import build_learning_path

# 向后兼容：导出原有的全局变量和函数
from app.core.matching.scorer import (
    CHROMA_SIMILARITY_THRESHOLD,
    FUZZY_MATCH_THRESHOLD,
    PROFICIENCY_SCORE,
    score_skill_match,
)
from app.core.matching.service import DEFAULT_REQUIRED_SKILL_BASELINE, MatchService

# 为了保持向后兼容，保留原有的全局变量
PREREQUISITE_MAP: dict[str, list[str]] = {}

# 创建全局 MatchService 实例
_match_service = MatchService()


# 向后兼容的函数
async def run_match(
    *,
    target_position: str,
    person_skills: list[dict[str, Any]],
    threshold: float = 0.6,
    driver: Any = None,
    db_session: Any = None,
    repo: Any = None,
) -> dict[str, Any]:
    """运行匹配引擎（向后兼容）。"""
    return await _match_service.run_match(
        target_position=target_position,
        person_skills=person_skills,
        threshold=threshold,
        driver=driver,
        db_session=db_session,
        repo=repo,
    )


async def get_match_result(match_id: str, db_session: Any = None) -> dict[str, Any] | None:
    """获取匹配结果（向后兼容，缓存 miss 回读 PostgreSQL）。"""
    cached = _match_service._cache.get_match_result(match_id)
    if cached is not None:
        return cached

    # Fallback: query PostgreSQL when cache miss
    if db_session is not None:
        try:
            from sqlalchemy import select

            from app.models.extraction_models import MatchResult

            row = (
                await db_session.execute(
                    select(MatchResult).where(MatchResult.match_id == match_id)
                )
            ).scalar_one_or_none()
            if row is not None:
                result = {
                    "match_id": row.match_id,
                    "target_position": row.target_position,
                    "match_score": row.match_score,
                    "matched_skills": row.matched_skills or [],
                    "missing_required": row.missing_required or [],
                    "missing_bonus": row.missing_bonus or [],
                    "skill_gap_detail": row.gap_report or [],
                    "learning_path": row.learning_path or [],
                    "cii": row.cii,
                }
                _match_service._cache.set_match_result(match_id, result)
                return result
        except Exception as exc:
            from loguru import logger
            logger.debug("[get_match_result] DB fallback failed: {}", exc)

    return None


async def enrich_learning_paths(
    gap_details: list[dict[str, Any]],
    driver: Any,
) -> list[dict[str, Any]]:
    """为差距详情中的每个技能查询 LearningResource 并附加到结果。"""
    if not driver or not gap_details:
        return gap_details

    resource_map: dict[str, list[dict[str, str]]] = {}
    try:
        async with driver.session() as session:
            result = await session.run(
                "MATCH (lr:LearningResource)-[:RECOMMENDED_FOR]->(s:Skill) "
                "RETURN s.name AS skill_name, lr.name AS resource_name, "
                "COALESCE(lr.url, '') AS url, COALESCE(lr.type, 'course') AS type"
            )
            records = await result.data()
            for rec in records:
                skill = rec["skill_name"]
                if skill not in resource_map:
                    resource_map[skill] = []
                resource_map[skill].append({
                    "name": rec["resource_name"],
                    "url": rec["url"],
                    "type": rec["type"],
                })
    except Exception as exc:
        from loguru import logger
        logger.warning("[Match] Failed to load learning resources: {}", exc)

    for gap in gap_details:
        skill = gap.get("skill", "")
        gap["learning_resources"] = resource_map.get(skill, [])

    return gap_details


async def run_batch_match(
    *,
    resumes: list[dict[str, Any]],
    positions: list[str],
    threshold: float = 0.6,
    driver: Any = None,
    db_session: Any = None,
) -> dict[str, Any]:
    """批量匹配（向后兼容）。"""
    results: list[dict[str, Any]] = []
    matrix: list[list[float]] = []

    for resume in resumes:
        resume_id = resume.get("resume_id", "unknown")
        person_skills = resume.get("person_skills", [])
        row_scores: list[float] = []

        for position in positions:
            try:
                result = await run_match(
                    target_position=position,
                    person_skills=person_skills,
                    threshold=threshold,
                    driver=driver,
                    db_session=db_session,
                )
                result["resume_id"] = resume_id
                results.append(result)
                row_scores.append(result.get("match_score", 0.0))
            except Exception as exc:
                from loguru import logger
                logger.warning(
                    "Batch match failed for resume={} position={}: {}",
                    resume_id, position, exc,
                )
                row_scores.append(0.0)

        matrix.append(row_scores)

    all_scores = [r.get("match_score", 0.0) for r in results]
    summary = {
        "total_pairs": len(results),
        "avg_score": round(sum(all_scores) / len(all_scores), 4) if all_scores else 0.0,
        "max_score": round(max(all_scores), 4) if all_scores else 0.0,
        "min_score": round(min(all_scores), 4) if all_scores else 0.0,
        "high_match_count": sum(1 for s in all_scores if s >= 0.75),
        "medium_match_count": sum(1 for s in all_scores if 0.5 <= s < 0.75),
        "low_match_count": sum(1 for s in all_scores if s < 0.5),
    }

    return {
        "results": results,
        "matrix": matrix,
        "summary": summary,
        "resume_ids": [r.get("resume_id", "unknown") for r in resumes],
        "positions": positions,
    }


async def compute_competitiveness(
    *,
    target_position: str,
    driver: Any = None,
    db_session: Any = None,
) -> dict[str, Any]:
    """计算岗位竞争力分析（向后兼容）。"""
    from app.core.matching.scorer import PROFICIENCY_SCORE
    from app.core.matching.service import DEFAULT_REQUIRED_SKILL_BASELINE

    profile = await _match_service._load_target_profile(driver, target_position, db_session)
    if profile is None:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail=f'Position "{target_position}" not found in graph',
        )

    required_skills = profile.get("required", [])
    bonus_skills = profile.get("bonus", [])
    all_skills = required_skills + bonus_skills

    skill_count_score = min(1.0, len(required_skills) / 10.0)
    proficiency_scores = [
        PROFICIENCY_SCORE.get(s.get("proficiency", "熟悉"), 0.65)
        for s in required_skills
    ]
    avg_proficiency = sum(proficiency_scores) / len(proficiency_scores) if proficiency_scores else 0.5

    total_prereq_depth = 0
    skill_prereq_details: list[dict[str, Any]] = []
    for skill_data in all_skills:
        skill_name = skill_data["skill"]
        depth = 1
        total_prereq_depth += depth
        skill_prereq_details.append({
            "skill": skill_name,
            "prerequisite_depth": depth,
            "learning_path": [skill_name],
        })

    avg_prereq_depth = total_prereq_depth / len(all_skills) if all_skills else 0

    required_count = len(required_skills)
    cii = (required_count / DEFAULT_REQUIRED_SKILL_BASELINE) if required_count else 1.0

    competitiveness = round(
        (skill_count_score * 0.3)
        + (avg_proficiency * 0.3)
        + (min(1.0, avg_prereq_depth / 5.0) * 0.2)
        + (min(1.0, cii / 1.5) * 0.2),
        3,
    )

    if competitiveness >= 0.75:
        difficulty = "高"
        description = "该岗位竞争激烈，需要广泛且深入的技能储备"
    elif competitiveness >= 0.5:
        difficulty = "中"
        description = "该岗位有一定竞争性，需要扎实的核心技能"
    else:
        difficulty = "低"
        description = "该岗位入门门槛较低，适合快速入门"

    bottleneck_skills = sorted(
        skill_prereq_details,
        key=lambda x: x["prerequisite_depth"],
        reverse=True,
    )[:5]

    return {
        "position": target_position,
        "competitiveness_score": competitiveness,
        "difficulty": difficulty,
        "description": description,
        "skill_count": len(all_skills),
        "required_count": len(required_skills),
        "bonus_count": len(bonus_skills),
        "avg_proficiency_level": round(avg_proficiency, 3),
        "avg_prerequisite_depth": round(avg_prereq_depth, 1),
        "cii": round(cii, 3),
        "bottleneck_skills": bottleneck_skills,
        "skill_details": skill_prereq_details,
    }


# 导出所有公共 API
__all__ = [
    "MatchService",
    "score_skill_match",
    "build_learning_path",
    "get_match_cache",
    "run_match",
    "get_match_result",
    "enrich_learning_paths",
    "run_batch_match",
    "compute_competitiveness",
    "PROFICIENCY_SCORE",
    "DEFAULT_REQUIRED_SKILL_BASELINE",
    "CHROMA_SIMILARITY_THRESHOLD",
    "FUZZY_MATCH_THRESHOLD",
    "PREREQUISITE_MAP",
]
