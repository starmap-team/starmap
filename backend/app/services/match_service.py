"""Match Service — 图驱动匹配引擎（向后兼容包装器）。

此模块现在作为 app.core.matching 的向后兼容包装器。
新代码应直接使用 app.core.matching 中的组件。

核心功能：
  从 Neo4j 加载岗位技能画像，与求职者技能进行多维度匹配评分，
  识别技能差距，生成个性化学习路径推荐。
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from neo4j.exceptions import Neo4jError
from sqlalchemy.exc import SQLAlchemyError

# 从新的模块化组件导入
from app.config import settings
from app.core.constants import (
    DEFAULT_PROFICIENCY,
    DIFFICULTY_HIGH,
    DIFFICULTY_LOW,
    DIFFICULTY_MEDIUM,
    GAP_LEVEL_MASTERED,
)
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
from app.exceptions import StarMapError

# 为了保持向后兼容，保留原有的全局变量
PREREQUISITE_MAP: dict[str, list[str]] = {}
_PREREQUISITE_LOADED = False


async def ensure_prerequisite_map(driver: Any = None) -> dict[str, list[str]]:
    """从 Neo4j 幂等加载技能前置关系到 PREREQUISITE_MAP（原地填充）。

    NEW-03 修复：该字典此前恒空且无加载方，导致学习推荐 prerequisites 恒空、
    recommendation_service developability 恒 0.5。所有消费方（learning/
    learning_service/recommendation_service）import 的是同一 dict 对象，
    原地填充即可一处修复全链路。Neo4j 不可用时降级为空映射，不阻断业务。
    """
    global _PREREQUISITE_LOADED
    if _PREREQUISITE_LOADED or PREREQUISITE_MAP:
        return PREREQUISITE_MAP
    if driver is None:
        from app.services.resources import resources as app_resources

        driver = app_resources.neo4j_driver
    if driver is None:
        return PREREQUISITE_MAP
    try:
        async with driver.session() as session:
            result = await session.run(
                "MATCH (a:Skill)-[:PREREQUISITE]->(b:Skill) "
                "RETURN a.name AS src, b.name AS tgt"
            )
            async for rec in result:
                src, tgt = rec["src"], rec["tgt"]
                PREREQUISITE_MAP.setdefault(src, [])
                if tgt not in PREREQUISITE_MAP[src]:
                    PREREQUISITE_MAP[src].append(tgt)
        _PREREQUISITE_LOADED = True
        logger.info(
            "[match_service] Loaded {} prerequisite relations", len(PREREQUISITE_MAP)
        )
    except StarMapError:
        raise
    except Exception as exc:  # noqa: BLE001 — 加载失败降级为空映射
        logger.warning(
            "[match_service] Prerequisite map load failed, degrading to empty: {}", exc
        )
    return PREREQUISITE_MAP


# 创建全局 MatchService 实例
_match_service = MatchService()


# 向后兼容的函数
async def run_match(
    *,
    target_position: str,
    person_skills: list[dict[str, Any]],
    threshold: float = settings.match_threshold,
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
                gap_report = row.gap_report or []
                missing_required = row.missing_required or []
                result = {
                    "match_id": row.match_id,
                    "target_position": row.target_position,
                    "match_score": row.match_score,
                    "matched_skills": row.matched_skills or [],
                    "missing_required": missing_required,
                    "missing_bonus": row.missing_bonus or [],
                    "skill_gap_detail": gap_report,
                    "cii": row.cii,
                }
                # D6 fix: compute trust_score from Neo4j Skill.trust_score over matched_skills.
                # Routes through the shared metrics module so the formula is identical
                # to anything else computing per-skill trust.
                from app.core.metrics import match_trust_score  # noqa: PLC0415
                result["trust_score"] = await match_trust_score(row.matched_skills or [])
                # D-01: 分数组件（required_avg/bonus_avg）未持久化，PG 兜底无法重建 →
                # 显式 None（与 live POST 响应区分：cache/实时命中才带 score_breakdown）
                result["score_breakdown"] = None
                # ponytail: PG 兜底与 POST 响应字段对齐 —— 缺失字段在此重建/派生，
                # 避免同一 match_id 因 cache 状态返回不同结构
                result["gap_skills"] = [
                    g["skill"] for g in gap_report if g.get("gap_level") != GAP_LEVEL_MASTERED
                ]
                if row.cii is None and row.match_score == 0 and not gap_report:
                    result["recommendations"] = []
                    result["overall_assessment"] = "该岗位在图谱中存在，但暂无技能画像（无 REQUIRES 关系），无法计算匹配度与差距。"
                    result["estimated_learning_time"] = ""
                    result["note"] = "岗位存在但无技能画像：请先为该岗位补充技能要求，再行匹配。"
                else:
                    result["recommendations"] = []
                    for item in gap_report[:3]:
                        if item.get("gap_level") == GAP_LEVEL_MASTERED:
                            continue
                        path_preview = " -> ".join(item.get("learning_path", [])[:3])
                        result["recommendations"].append(f"优先补齐 {item.get('skill', '')}：{path_preview}")
                    result["overall_assessment"] = _match_service._assessment_text(row.match_score, len(missing_required))
                    result["estimated_learning_time"] = _match_service._estimate_learning_time(gap_report)
                    result["note"] = None
                _match_service._cache.set_match_result(match_id, result)
                return result
        except StarMapError:
            raise
        except SQLAlchemyError as exc:
            from loguru import logger
            logger.exception("[get_match_result] DB fallback failed: {}", exc)
            return None
        except Exception as exc:
            from loguru import logger
            logger.exception("[get_match_result] Unexpected error: {}", exc)
            return None

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
    except StarMapError:
        raise
    except (Neo4jError, SQLAlchemyError) as exc:
        from loguru import logger
        logger.exception("[Match] Failed to load learning resources: {}", exc)
    except Exception as exc:
        from loguru import logger
        logger.exception("[Match] Unexpected error loading learning resources: {}", exc)

    for gap in gap_details:
        skill = gap.get("skill", "")
        gap["learning_resources"] = resource_map.get(skill, [])

    return gap_details


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
        from app.exceptions import PositionNotFoundError
        raise PositionNotFoundError(target_position)

    required_skills = profile.get("required", [])
    bonus_skills = profile.get("bonus", [])
    all_skills = required_skills + bonus_skills

    skill_count_score = min(1.0, len(required_skills) / 10.0)
    proficiency_scores = [
        PROFICIENCY_SCORE.get(s.get("proficiency", DEFAULT_PROFICIENCY), 0.65)
        for s in required_skills
    ]
    avg_proficiency = sum(proficiency_scores) / len(proficiency_scores) if proficiency_scores else 0.5

    # ponytail: 真实先修链 —— 原实现 depth 恒 1、learning_path 恒 [skill]（虚构）；
    # 复用 ensure_prerequisite_map + build_learning_path 计算真实前置深度
    prereq_map = await ensure_prerequisite_map(driver)
    total_prereq_depth = 0
    skill_prereq_details: list[dict[str, Any]] = []
    for skill_data in all_skills:
        skill_name = skill_data["skill"]
        path = build_learning_path(skill_name, set(), prereq_map)
        depth = len(path)
        total_prereq_depth += depth
        skill_prereq_details.append({
            "skill": skill_name,
            "prerequisite_depth": depth,
            "learning_path": path,
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
        difficulty = DIFFICULTY_HIGH
        description = "该岗位竞争激烈，需要广泛且深入的技能储备"
    elif competitiveness >= 0.5:
        difficulty = DIFFICULTY_MEDIUM
        description = "该岗位有一定竞争性，需要扎实的核心技能"
    else:
        difficulty = DIFFICULTY_LOW
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
    "compute_competitiveness",
    "PROFICIENCY_SCORE",
    "DEFAULT_REQUIRED_SKILL_BASELINE",
    "CHROMA_SIMILARITY_THRESHOLD",
    "FUZZY_MATCH_THRESHOLD",
    "PREREQUISITE_MAP",
]
