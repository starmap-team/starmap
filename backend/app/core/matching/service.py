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

from loguru import logger

from app.config import settings
from app.core.constants import (
    DEFAULT_PROFICIENCY,
    GAP_LEVEL_MASTERED,
    GAP_LEVEL_MISSING,
    GAP_LEVEL_PARTIAL,
    LOW_PROFICIENCY,
)
from app.core.matching.cache import get_match_cache
from app.core.matching.constants import PROFICIENCY_SCORE
from app.core.matching.path_builder import build_learning_path
from app.core.matching.scorer import score_skill_match
from app.exceptions import MatchingError, StarMapError
from app.services.graph_service import fetch_position_graph

# CII 基线
DEFAULT_REQUIRED_SKILL_BASELINE = 6.0


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
        except StarMapError:
            raise
        except Exception as exc:
            # M3: Neo4j 不可用时降级返回空映射,不阻断匹配主流程。
            logger.warning("[MatchService] Prerequisite map load failed, degrading to empty: {}", exc)
            return {}

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
                                "proficiency": s.get("proficiency", DEFAULT_PROFICIENCY),
                                "source_count": int(s.get("source_count", 0) or 0),
                            }
                            for s in profile.required_skills
                        ],
                        "bonus": [
                            {
                                "skill": s["name"],
                                "category": s.get("category", "hard_skill"),
                                "proficiency": s.get("proficiency", LOW_PROFICIENCY),
                                "source_count": int(s.get("source_count", 0) or 0),
                            }
                            for s in profile.bonus_skills
                        ],
                    }
                    self._cache.set_profile(target_position, result)
                    return result
            except StarMapError:
                raise
            except Exception as exc:
                logger.exception("Matching service error: {}", exc)
                raise MatchingError(str(exc)) from exc

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
                            "proficiency": props.get("proficiency") or item.get("proficiency", DEFAULT_PROFICIENCY),
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
            except StarMapError:
                raise
            except Exception as exc:
                # M3: Neo4j 不可用时降级返回 None,不阻断匹配主流程。
                logger.warning("[MatchService] Neo4j profile load failed, degrading to None: {}", exc)
                return None

        return None

    def _apply_inflation_correction(
        self, profile: dict[str, list[dict[str, str]]]
    ) -> tuple[list[dict[str, str]], list[dict[str, str]], float]:
        """应用 CII 通胀修正。"""
        required = [dict(item, importance="required") for item in profile.get("required", [])]
        bonus = [dict(item, importance="bonus") for item in profile.get("bonus", [])]
        required_count = len(required)
        # fix (M13): required=0 时 CII=0 表示"无明确必备要求"，
        # 原逻辑 1.0 会被前端误读为"无通胀→匹配度可信"，实际是"无量化基准"。
        cii = 0.0 if required_count == 0 else (required_count / DEFAULT_REQUIRED_SKILL_BASELINE)

        if cii <= 1.2 or required_count <= 6:
            required_names = {item["skill"] for item in required}
            bonus = [item for item in bonus if item["skill"] not in required_names]
            return required, bonus, cii

        overflow = max(1, required_count - ceil(DEFAULT_REQUIRED_SKILL_BASELINE * 1.2))
        required.sort(key=lambda item: (
            PROFICIENCY_SCORE.get(item.get("proficiency", DEFAULT_PROFICIENCY), PROFICIENCY_SCORE[DEFAULT_PROFICIENCY]),
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
        threshold: float = settings.match_threshold,
        driver: Any = None,
        db_session: Any = None,
        repo: Any = None,
    ) -> dict[str, Any]:
        """运行匹配引擎。"""
        prereq_map = await self._load_prerequisite_map(driver)
        target_profile = await self._load_target_profile(driver, target_position, db_session, repo)
        if target_profile is None:
            # M2（Phase 13 强制规范）：区分“岗位不存在”与“岗位存在但暂无技能画像”。
            # 后者返回 200 + 0 分 + note，而非 404（not-found 仅用于真不存在）。
            if await self._position_exists(driver, target_position, db_session):
                result: dict[str, Any] = {
                    "match_id": str(uuid4()),
                    "target_position": target_position,
                    "cii": None,
                    "match_score": 0.0,
                    "matched_skills": [],
                    "gap_skills": [],
                    "recommendations": [],
                    "missing_required": [],
                    "missing_bonus": [],
                    "skill_gap_detail": [],
                    "overall_assessment": "该岗位在图谱中存在，但暂无技能画像（无 REQUIRES 关系），无法计算匹配度与差距。",
                    "estimated_learning_time": "",
                    "note": "岗位存在但无技能画像：请先为该岗位补充技能要求（pipeline 抽取或人工维护），再行匹配。",
                }
                # ponytail: 无画像结果也落库，避免 cache 淘汰后 GET /match/result/{id} 404
                if db_session is not None:
                    await self._save_match_result(db_session, result["match_id"], result)
                return result
            from app.exceptions import PositionNotFoundError
            raise PositionNotFoundError(target_position)

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
                        key=lambda g: {GAP_LEVEL_MASTERED: 0, GAP_LEVEL_PARTIAL: 1, GAP_LEVEL_MISSING: 2}.get(g, 2),
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
            item["skill"] for item in merged_evaluated if item["gap_level"] == GAP_LEVEL_MASTERED
        ]
        missing_required = [
            item["skill"] for item in evaluated_required if item["gap_level"] != GAP_LEVEL_MASTERED
        ]
        missing_bonus = [
            item["skill"] for item in evaluated_bonus if item["gap_level"] != GAP_LEVEL_MASTERED
        ]
        gap_details = sorted(
            merged_evaluated,
            key=lambda item: (
                item["importance"] != "required",
                item["gap_level"] == GAP_LEVEL_MASTERED,
                item["skill"],
            ),
        )
        gap_skills = [item["skill"] for item in gap_details if item["gap_level"] != GAP_LEVEL_MASTERED]

        # ponytail: 真实先修链 —— path_builder 此前是死代码，prereq_map 已加载但从未被消费；
        # 这里按"未掌握技能 → 前置依赖"生成学习路径，已掌握技能路径置空
        owned_skills = {s.get("name", "").strip() for s in person_skills if s.get("name")}
        for item in gap_details:
            item["learning_path"] = (
                []
                if item["gap_level"] == GAP_LEVEL_MASTERED
                else build_learning_path(item["skill"], owned_skills, prereq_map)
            )

        # Build recommendations
        recommendations: list[str] = []
        for item in gap_details[:3]:
            if item["gap_level"] == GAP_LEVEL_MASTERED:
                continue
            path_preview = " -> ".join(item["learning_path"][:3])
            recommendations.append(f"优先补齐 {item['skill']}：{path_preview}")
        if cii > 1.2:
            recommendations.append("岗位要求存在通胀迹象，已将边缘必备项按加分项处理。")

        match_id = str(uuid4())
        result = {
            "match_id": match_id,
            "target_position": target_position,
            # fix: 把已计算的 cii 纳入响应体（_save_match_result 第 428 行的 result.get("cii", 1.0) 也会读到真实值）
            "cii": round(cii, 3),
            "match_score": match_score,
            # D-01: 分数拆解 — 暴露评分构成（required_avg×0.7 + bonus_avg×0.3），前端可展示
            "score_breakdown": {
                "required_avg": round(required_avg, 4),
                "bonus_avg": round(bonus_avg, 4),
                "weight_required": 0.7,
                "weight_bonus": 0.3,
                "inflated": cii > 1.2,
            },
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
                    # P4 fix (Phase 24 求职者分析): 补 score 字段——前端差距表
                    # Math.round(row.score*100) 依赖它，缺失时显示 "NaN%"。
                    "score": round(item.get("score", 0.0), 4),
                }
                for item in gap_details
            ],
            "overall_assessment": self._assessment_text(match_score, len(missing_required)),
            "estimated_learning_time": self._estimate_learning_time(gap_details),
        }

        # D6 fix: compute trust_score from Neo4j Skill.trust_score over matched_skills
        # via the shared metrics module. The MIN of matched_skills' trust is the
        # bottleneck — a single low-trust matched skill degrades the overall
        # trustworthiness. Routes through app.core.metrics to keep the formula
        # consistent with anything else computing per-skill trust.
        try:
            from app.core.metrics import match_trust_score  # noqa: PLC0415
            result["trust_score"] = await match_trust_score(matched_skills)
        except Exception as exc:  # noqa: BLE001
            from loguru import logger
            logger.warning("run_match trust_score lookup failed: {}", exc)
            result["trust_score"] = None

        # Cache result
        self._cache.set_match_result(match_id, result)

        # Persist to database
        if db_session is not None:
            await self._save_match_result(db_session, match_id, result)

        return result

    async def _position_exists(self, driver: Any, name: str, db_session: Any) -> bool:
        """M2 辅助：判断岗位是否“存在”（PG 或 Neo4j 有节点），与“有技能画像”区分。"""
        if db_session is not None:
            try:
                from sqlalchemy import select as _sel

                from app.models.extraction_models import PositionRecord as _PR  # noqa: N814

                row = (
                    await db_session.execute(_sel(_PR.id).where(_PR.name == name).limit(1))
                ).scalar_one_or_none()
                if row is not None:
                    return True
            except Exception:
                pass
        if driver is not None:
            try:
                async with driver.session() as _s:
                    _r = await _s.run(
                        "MATCH (p:Position {name:$n}) RETURN 1 AS x LIMIT 1", n=name
                    )
                    if (await _r.single()) is not None:
                        return True
            except Exception:
                pass
        return False

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
            # ponytail: .get 兜底 —— gap_report 回读数据（历史/精简记录）可能缺 importance
            base = 3.0 if gap.get("importance", "required") == "required" else 1.5
            if gap.get("gap_level") == GAP_LEVEL_PARTIAL:
                base *= 0.5
            elif gap.get("gap_level") == GAP_LEVEL_MASTERED:
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
        except StarMapError:
            raise
        except Exception as exc:
            # M3: 结果持久化是非关键副作用,匹配本身已成功;落库失败只记录,
            # 不让一次保存失败回滚整次匹配。
            logger.warning("[MatchService] Failed to persist result {}: {}", match_id, exc)
