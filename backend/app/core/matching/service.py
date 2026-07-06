"""精简后的 MatchService 模块。

使用模块化的组件替代原有的 monolithic 实现：
- MatchCache: 线程安全缓存
- scorer: 评分逻辑
- path_builder: 学习路径构建
"""

from __future__ import annotations

import json
from math import ceil
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from loguru import logger

from app.core.matching.cache import get_match_cache
from app.core.matching.scorer import score_skill_match
from app.services.graph_service import fetch_position_graph

# CII 基线
DEFAULT_REQUIRED_SKILL_BASELINE = 6.0

# 熟练度映射
PROFICIENCY_SCORE = {"了解": 0.35, "熟悉": 0.65, "精通": 0.9}


class MatchService:
    """图驱动匹配引擎：计算求职者技能与岗位要求的匹配度。

    使用模块化的组件替代全局状态，支持线程安全操作。
    """

    def __init__(self) -> None:
        """初始化 MatchService。"""
        self._cache = get_match_cache()

    async def _load_prerequisite_map(self, driver: Any) -> dict[str, list[str]]:
        """加载技能前置关系映射。"""
        # 先检查缓存
        cached = self._cache.get_prerequisite_map()
        if cached is not None:
            return cached

        prereq_map: dict[str, list[str]] = {}
        if driver is None:
            return prereq_map

        try:
            async with driver.session() as session:
                cypher = (
                    "MATCH (a:Skill)-[:PREREQUISITE]->(b:Skill) "
                    "RETURN a.name as src, b.name as tgt"
                )
                result = await session.run(cypher)
                async for rec in result:
                    src = rec["src"]
                    tgt = rec["tgt"]
                    if src not in prereq_map:
                        prereq_map[src] = []
                    if tgt not in prereq_map[src]:
                        prereq_map[src].append(tgt)
            self._cache.set_prerequisite_map(prereq_map)
            logger.info("[MatchService] Loaded {} prerequisite relations", len(prereq_map))
        except Exception as exc:
            logger.warning("[MatchService] Failed to load prerequisite map: {}", exc)

        return prereq_map

    async def _load_target_profile(
        self,
        driver: Any,
        target_position: str,
        db_session: Any = None,
        repo: Any = None,
    ) -> dict[str, list[dict[str, str]]] | None:
        """加载目标岗位技能画像。"""
        # 检查缓存
        cached = self._cache.get_profile(target_position)
        if cached is not None:
            return cached

        # 从数据库加载
        if repo is not None:
            try:
                profile = await repo.get_position_profile(target_position)
                if profile and profile.required_skills:
                    result = {
                        "required": [
                            {
                                "skill": s["name"],
                                "category": s.get("category", "hard_skill"),
                                "proficiency": s.get("proficiency", "熟悉"),
                                "source_count": int(s.get("source_count", 0) or 0),
                            }
                            for s in profile.required_skills
                        ],
                        "bonus": [
                            {
                                "skill": s["name"],
                                "category": s.get("category", "hard_skill"),
                                "proficiency": s.get("proficiency", "了解"),
                                "source_count": int(s.get("source_count", 0) or 0),
                            }
                            for s in profile.bonus_skills
                        ],
                    }
                    self._cache.set_profile(target_position, result)
                    return result
            except Exception as exc:
                logger.debug("[MatchService] Repo lookup failed: {}", exc)

        # 从 Neo4j 加载
        if driver is not None:
            try:
                graph = await fetch_position_graph(driver, target_position, depth=3)
                if graph.get("skills"):
                    required: list[dict[str, str]] = []
                    bonus: list[dict[str, str]] = []
                    for item in graph["skills"]:
                        props = item.get("properties", {})
                        skill_entry = {
                            "skill": props.get("name") or item.get("name", ""),
                            "category": props.get("category") or item.get("category", "hard_skill"),
                            "proficiency": props.get("proficiency") or item.get("proficiency", "熟悉"),
                            "source_count": str(int(props.get("source_count") or item.get("source_count", 0) or 0)),
                        }
                        importance = props.get("importance") or item.get("importance", "required")
                        if importance == "bonus":
                            bonus.append(skill_entry)
                        else:
                            required.append(skill_entry)
                    if required or bonus:
                        result = {"required": required, "bonus": bonus}
                        self._cache.set_profile(target_position, result)
                        return result
            except Exception as exc:
                logger.warning("[MatchService] Graph lookup failed: {}", exc)

        # 从 PostgreSQL position_records 回退
        if db_session is not None:
            try:
                from sqlalchemy import select

                from app.models.extraction_models import PositionRecord, PositionSkillRelation, SkillRecord

                pos_stmt = select(PositionRecord).where(PositionRecord.name == target_position)
                pos_row = (await db_session.execute(pos_stmt)).scalar_one_or_none()
                if pos_row is not None:
                    rel_stmt = (
                        select(PositionSkillRelation, SkillRecord)
                        .join(SkillRecord, PositionSkillRelation.skill_id == SkillRecord.id)
                        .where(PositionSkillRelation.position_id == pos_row.id)
                    )
                    rel_rows = (await db_session.execute(rel_stmt)).all()
                    required_db: list[dict[str, str]] = []
                    bonus_db: list[dict[str, str]] = []
                    for rel, skill in rel_rows:
                        entry = {
                            "skill": skill.name,
                            "category": skill.category or "hard_skill",
                            "proficiency": "熟悉",
                            "source_count": str(skill.source_count or 0),
                        }
                        if rel.requirement_type == "preferred":
                            bonus_db.append(entry)
                        else:
                            required_db.append(entry)
                    if required_db or bonus_db:
                        result = {"required": required_db, "bonus": bonus_db}
                        self._cache.set_profile(target_position, result)
                        return result
            except Exception as exc:
                logger.debug("[MatchService] DB fallback lookup failed: {}", exc)

        return None

    def _apply_inflation_correction(
        self, profile: dict[str, list[dict[str, str]]]
    ) -> tuple[list[dict[str, str]], list[dict[str, str]], float]:
        """应用 CII 通胀修正。"""
        required = [dict(item, importance="required") for item in profile.get("required", [])]
        bonus = [dict(item, importance="bonus") for item in profile.get("bonus", [])]
        required_count = len(required)
        cii = (required_count / DEFAULT_REQUIRED_SKILL_BASELINE) if required_count else 1.0

        if cii <= 1.2 or required_count <= 6:
            required_names = {item["skill"] for item in required}
            bonus = [item for item in bonus if item["skill"] not in required_names]
            return required, bonus, cii

        overflow = max(1, required_count - ceil(DEFAULT_REQUIRED_SKILL_BASELINE * 1.2))
        required.sort(key=lambda item: (
            PROFICIENCY_SCORE.get(item.get("proficiency", "熟悉"), 0.65),
            int(item.get("source_count", 0) or 0),
        ))
        downgraded = required[:overflow]
        kept = required[overflow:]

        safe_downgraded = []
        for item in downgraded:
            prof = item.get("proficiency", "")
            src = int(item.get("source_count", 0) or 0)
            if prof == "精通" and src >= 30:
                kept.append(item)
                continue
            item["importance"] = "bonus"
            item["inflation_adjusted"] = "true"
            safe_downgraded.append(item)
        downgraded = safe_downgraded

        merged_bonus = downgraded + bonus
        kept_names = {item["skill"] for item in kept}
        seen: set[str] = set()
        deduped_bonus: list[dict[str, str]] = []
        for item in merged_bonus:
            if item["skill"] in kept_names or item["skill"] in seen:
                continue
            seen.add(item["skill"])
            deduped_bonus.append(item)
        return kept, deduped_bonus, cii

    async def run_match(
        self,
        *,
        target_position: str,
        person_skills: list[dict[str, Any]],
        threshold: float = 0.6,
        driver: Any = None,
        db_session: Any = None,
        repo: Any = None,
    ) -> dict[str, Any]:
        """运行匹配引擎。"""
        await self._load_prerequisite_map(driver)
        target_profile = await self._load_target_profile(driver, target_position, db_session, repo)
        if target_profile is None:
            raise HTTPException(
                status_code=404,
                detail=f'Position "{target_position}" not found in graph',
            )

        required_skills, bonus_skills, cii = self._apply_inflation_correction(target_profile)

        required_result = score_skill_match(
            target_skills=required_skills, person_skills=person_skills, threshold=threshold
        )
        bonus_result = score_skill_match(
            target_skills=bonus_skills, person_skills=person_skills, threshold=threshold
        )

        evaluated_required: list[dict[str, Any]] = required_result["evaluated"]
        evaluated_bonus: list[dict[str, Any]] = bonus_result["evaluated"]

        # Merge and deduplicate
        required_skill_map: dict[str, dict[str, Any]] = {
            item["skill"]: item for item in evaluated_required
        }
        bonus_skill_map: dict[str, dict[str, Any]] = {
            item["skill"]: item for item in evaluated_bonus
        }

        merged_evaluated: list[dict[str, Any]] = []
        for skill, req_item in required_skill_map.items():
            if skill in bonus_skill_map:
                bon_item = bonus_skill_map[skill]
                merged_evaluated.append({
                    **req_item,
                    "score": max(req_item["score"], bon_item["score"]),
                    "gap_level": min(
                        [req_item["gap_level"], bon_item["gap_level"]],
                        key=lambda g: {"已掌握": 0, "部分掌握": 1, "完全缺失": 2}.get(g, 2),
                    ),
                })
            else:
                merged_evaluated.append(req_item)

        for skill, bon_item in bonus_skill_map.items():
            if skill not in required_skill_map:
                merged_evaluated.append(bon_item)

        evaluated_required = list(required_skill_map.values())
        evaluated_bonus = [
            item for skill, item in bonus_skill_map.items() if skill not in required_skill_map
        ]

        # Scoring
        required_avg = (
            sum(item["score"] for item in evaluated_required) / len(evaluated_required)
            if evaluated_required else 1.0
        )
        bonus_avg = (
            sum(item["score"] for item in evaluated_bonus) / len(evaluated_bonus)
            if evaluated_bonus else required_avg
        )
        match_score = round(min(1.0, (required_avg * 0.7) + (bonus_avg * 0.3)), 4)

        matched_skills = [
            item["skill"] for item in merged_evaluated if item["gap_level"] == "已掌握"
        ]
        missing_required = [
            item["skill"] for item in evaluated_required if item["gap_level"] != "已掌握"
        ]
        missing_bonus = [
            item["skill"] for item in evaluated_bonus if item["gap_level"] != "已掌握"
        ]
        gap_details = sorted(
            merged_evaluated,
            key=lambda item: (
                item["importance"] != "required",
                item["gap_level"] == "已掌握",
                item["skill"],
            ),
        )
        gap_skills = [item["skill"] for item in gap_details if item["gap_level"] != "已掌握"]

        # Build recommendations
        recommendations: list[str] = []
        for item in gap_details[:3]:
            if item["gap_level"] == "已掌握":
                continue
            path_preview = " -> ".join(item["learning_path"][:3])
            recommendations.append(f"优先补齐 {item['skill']}：{path_preview}")
        if cii > 1.2:
            recommendations.append("岗位要求存在通胀迹象，已将边缘必备项按加分项处理。")

        match_id = str(uuid4())
        result = {
            "match_id": match_id,
            "target_position": target_position,
            "match_score": match_score,
            "matched_skills": matched_skills,
            "gap_skills": gap_skills,
            "recommendations": recommendations,
            "missing_required": missing_required,
            "missing_bonus": missing_bonus,
            "skill_gap_detail": [
                {
                    "skill": item["skill"],
                    "importance": item["importance"],
                    "gap_level": item["gap_level"],
                    "learning_path": item["learning_path"],
                }
                for item in gap_details
            ],
            "overall_assessment": self._assessment_text(match_score, len(missing_required)),
            "estimated_learning_time": self._estimate_learning_time(gap_details),
        }

        # Cache result
        self._cache.set_match_result(match_id, result)

        # Persist to database
        if db_session is not None:
            await self._save_match_result(db_session, match_id, result)

        return result

    def _assessment_text(self, match_score: float, missing_required: int) -> str:
        """生成评估文本。"""
        if match_score >= 0.8 and missing_required == 0:
            return "核心技能已基本覆盖，补齐少量加分项即可进入强匹配区间。"
        if match_score >= 0.6:
            return "基础能力可支撑转岗或进阶，但仍需优先补齐关键缺口。"
        return "当前与目标岗位仍有明显差距，建议按学习路径分阶段补强。"

    def _estimate_learning_time(self, gaps: list[dict[str, Any]]) -> str:
        """估算学习时长。"""
        weeks = 0.0
        for gap in gaps:
            base = 3.0 if gap["importance"] == "required" else 1.5
            if gap["gap_level"] == "部分掌握":
                base *= 0.5
            elif gap["gap_level"] == "已掌握":
                base = 0.5
            weeks += base

        if weeks >= 12:
            months_low = max(1, int(weeks // 4))
            months_high = months_low + 1
            return f"{months_low}-{months_high}个月（兼职学习）"
        return f"{max(2, ceil(weeks))}-{max(3, ceil(weeks) + 1)}周（兼职学习）"

    async def _save_match_result(self, session: Any, match_id: str, result: dict[str, Any]) -> None:
        """保存匹配结果到数据库。"""
        try:
            from sqlalchemy import text as sa_text

            await session.execute(
                sa_text("""
                    INSERT INTO match_results (
                        match_id, target_position, match_score,
                        matched_skills, missing_required, missing_bonus,
                        gap_report, learning_path, cii, created_at
                    ) VALUES (
                        :match_id, :target_position, :match_score,
                        CAST(:matched_skills AS jsonb),
                        CAST(:missing_required AS jsonb),
                        CAST(:missing_bonus AS jsonb),
                        CAST(:gap_report AS jsonb),
                        CAST(:learning_path AS jsonb),
                        :cii, now()
                    )
                    ON CONFLICT (match_id) DO NOTHING
                """),
                {
                    "match_id": match_id,
                    "target_position": result.get("target_position", ""),
                    "match_score": result.get("match_score", 0.0),
                    "matched_skills": json.dumps(result.get("matched_skills", [])),
                    "missing_required": json.dumps(result.get("missing_required", [])),
                    "missing_bonus": json.dumps(result.get("missing_bonus", [])),
                    "gap_report": json.dumps(result.get("skill_gap_detail", [])),
                    "learning_path": json.dumps([
                        item.get("learning_path", [])
                        for item in result.get("skill_gap_detail", [])
                    ]),
                    "cii": result.get("cii", 1.0),
                },
            )
            await session.commit()
            logger.debug("[MatchService] Persisted result {} to PostgreSQL", match_id)
        except Exception as exc:
            logger.warning("[MatchService] Failed to persist result {}: {}", match_id, exc)
