"""Lightweight matching engine used by the phase 4 APIs."""

from __future__ import annotations

from copy import deepcopy
from difflib import SequenceMatcher
from math import ceil
from typing import Any
from uuid import uuid4

from loguru import logger

from app.core.extraction.normalize import normalize_skill
from app.services.graph_service import fetch_position_graph

PROFICIENCY_SCORE = {"了解": 0.35, "熟悉": 0.65, "精通": 0.9}
DEFAULT_REQUIRED_SKILL_BASELINE = 6.0

POSITION_SKILL_PROFILES: dict[str, dict[str, list[dict[str, str]]]] = {
    "数据分析师": {
        "required": [
            {"skill": "Python", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "SQL", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Excel", "category": "tool", "proficiency": "精通"},
            {"skill": "统计学", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Pandas", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "数据可视化", "category": "hard_skill", "proficiency": "了解"},
        ],
        "bonus": [
            {"skill": "Tableau", "category": "tool", "proficiency": "了解"},
            {"skill": "Machine Learning", "category": "hard_skill", "proficiency": "了解"},
        ],
    },
    "前端开发工程师": {
        "required": [
            {"skill": "JavaScript", "category": "hard_skill", "proficiency": "精通"},
            {"skill": "Vue.js", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "CSS3", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "HTML5", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "TypeScript", "category": "hard_skill", "proficiency": "了解"},
        ],
        "bonus": [
            {"skill": "Node.js", "category": "hard_skill", "proficiency": "了解"},
            {"skill": "Webpack", "category": "tool", "proficiency": "了解"},
        ],
    },
    "后端开发工程师": {
        "required": [
            {"skill": "Python", "category": "hard_skill", "proficiency": "精通"},
            {"skill": "FastAPI", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "PostgreSQL", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Redis", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Docker", "category": "tool", "proficiency": "了解"},
            {"skill": "System Design", "category": "hard_skill", "proficiency": "了解"},
        ],
        "bonus": [
            {"skill": "Kubernetes", "category": "tool", "proficiency": "了解"},
            {"skill": "Microservices", "category": "hard_skill", "proficiency": "了解"},
        ],
    },
    "高级后端工程师": {
        "required": [
            {"skill": "Python", "category": "hard_skill", "proficiency": "精通"},
            {"skill": "FastAPI", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "PostgreSQL", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Redis", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Docker", "category": "tool", "proficiency": "熟悉"},
            {"skill": "System Design", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Kubernetes", "category": "tool", "proficiency": "了解"},
        ],
        "bonus": [
            {"skill": "Apache Kafka", "category": "hard_skill", "proficiency": "了解"},
            {"skill": "Microservices", "category": "hard_skill", "proficiency": "了解"},
        ],
    },
    "后端工程师": {
        "required": [
            {"skill": "Python", "category": "hard_skill", "proficiency": "精通"},
            {"skill": "FastAPI", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "PostgreSQL", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Redis", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Docker", "category": "tool", "proficiency": "了解"},
            {"skill": "REST API", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Git", "category": "tool", "proficiency": "熟悉"},
        ],
        "bonus": [
            {"skill": "Linux", "category": "tool", "proficiency": "了解"},
            {"skill": "Microservices", "category": "hard_skill", "proficiency": "了解"},
        ],
    },
    "前端工程师": {
        "required": [
            {"skill": "JavaScript", "category": "hard_skill", "proficiency": "精通"},
            {"skill": "Vue.js", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "HTML5", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "CSS3", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "TypeScript", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Git", "category": "tool", "proficiency": "熟悉"},
        ],
        "bonus": [
            {"skill": "Node.js", "category": "hard_skill", "proficiency": "了解"},
            {"skill": "Webpack", "category": "tool", "proficiency": "了解"},
        ],
    },
    "DevOps工程师": {
        "required": [
            {"skill": "Docker", "category": "tool", "proficiency": "精通"},
            {"skill": "Kubernetes", "category": "tool", "proficiency": "熟悉"},
            {"skill": "Linux", "category": "tool", "proficiency": "精通"},
            {"skill": "CI/CD", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "Terraform", "category": "tool", "proficiency": "熟悉"},
            {"skill": "Prometheus", "category": "tool", "proficiency": "了解"},
            {"skill": "Grafana", "category": "tool", "proficiency": "了解"},
        ],
        "bonus": [
            {"skill": "AWS", "category": "tool", "proficiency": "了解"},
            {"skill": "Ansible", "category": "tool", "proficiency": "了解"},
            {"skill": "Python", "category": "hard_skill", "proficiency": "熟悉"},
        ],
    },
    "AI工程师": {
        "required": [
            {"skill": "Python", "category": "hard_skill", "proficiency": "精通"},
            {"skill": "Machine Learning", "category": "hard_skill", "proficiency": "精通"},
            {"skill": "Deep Learning", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "PyTorch", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "TensorFlow", "category": "hard_skill", "proficiency": "了解"},
            {"skill": "NLP", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "scikit-learn", "category": "hard_skill", "proficiency": "熟悉"},
        ],
        "bonus": [
            {"skill": "LLM", "category": "hard_skill", "proficiency": "了解"},
            {"skill": "LangChain", "category": "hard_skill", "proficiency": "了解"},
            {"skill": "Docker", "category": "tool", "proficiency": "了解"},
        ],
    },
}

PREREQUISITE_MAP: dict[str, list[str]] = {
    "Pandas": ["Python", "NumPy"],
    "NumPy": ["Python"],
    "数据可视化": ["Python", "Pandas"],
    "Tableau": ["数据可视化"],
    "Machine Learning": ["Python", "统计学"],
    "统计学": ["Excel"],
    "Kubernetes": ["Docker", "Linux"],
    "Microservices": ["REST API", "Docker"],
    "System Design": ["REST API", "PostgreSQL"],
    "FastAPI": ["Python", "REST API"],
    "Redis": ["Python"],
    "PostgreSQL": ["SQL"],
    "Vue.js": ["HTML5", "CSS3", "JavaScript"],
    "TypeScript": ["JavaScript"],
    "Webpack": ["JavaScript"],
}

async def _load_prerequisite_map(driver: Any) -> None:
    """Load PREREQUISITE relationships from Neo4j into PREREQUISITE_MAP.

    Results are cached for 5 minutes to avoid repeated Neo4j queries.
    """
    global PREREQUISITE_MAP, _PREREQ_CACHE_TS
    if driver is None:
        return

    # Cache TTL: 5 minutes
    import time
    now = time.monotonic()
    if _PREREQ_CACHE_TS is not None and (now - _PREREQ_CACHE_TS) < 300:
        return  # Cache still valid

    try:
        async with driver.session() as session:
            cypher = "MATCH (a:Skill)-[:PREREQUISITE]->(b:Skill) RETURN a.name as src, b.name as tgt"
            result = await session.run(cypher)
            async for rec in result:
                src = _canonical_skill_name(rec["src"])
                tgt = _canonical_skill_name(rec["tgt"])
                if src not in PREREQUISITE_MAP:
                    PREREQUISITE_MAP[src] = []
                if tgt not in PREREQUISITE_MAP[src]:
                    PREREQUISITE_MAP[src].append(tgt)
        _PREREQ_CACHE_TS = now
    except Exception as exc:
        logger.warning("Failed to load PREREQUISITE map from Neo4j: {}", exc)


_PREREQ_CACHE_TS: float | None = None
_MATCH_RESULTS: dict[str, dict[str, Any]] = {}
_MATCH_RESULTS_MAX_SIZE = 1000


# Common skill aliases — unified from normalize.py's SKILL_ALIAS (single source of truth)
# match_service.py no longer maintains its own alias table.
# _canonical_skill_name delegates to normalize_skill which uses the canonical SKILL_ALIAS.

# Fuzzy match threshold (SequenceMatcher ratio)
FUZZY_MATCH_THRESHOLD = 0.7


def _canonical_skill_name(name: str) -> str:
    """Canonicalize a skill name using the unified normalization pipeline.

    Delegates to normalize.py's normalize_skill (alias lookup).
    Falls back to the original name if no alias match found.
    """
    result = normalize_skill(name, use_vector=False)
    return (result.normalized or name.strip())


def _position_key(target_position: str) -> str:
    return target_position.strip().lower().replace(" ", "")


def _fallback_profile(target_position: str) -> dict[str, list[dict[str, str]]]:
    target_key = _position_key(target_position)
    # Pass 1: exact match
    for position_name, profile in POSITION_SKILL_PROFILES.items():
        if _position_key(position_name) == target_key:
            return deepcopy(profile)
    # Pass 2: best fuzzy match (shortest name that contains target)
    best_match = None
    best_len = float("inf")
    for position_name, profile in POSITION_SKILL_PROFILES.items():
        position_key = _position_key(position_name)
        if target_key in position_key or position_key in target_key:
            if len(position_key) < best_len:
                best_len = len(position_key)
                best_match = profile
    if best_match:
        return deepcopy(best_match)

    return {
        "required": [
            {"skill": "Python", "category": "hard_skill", "proficiency": "熟悉"},
            {"skill": "SQL", "category": "hard_skill", "proficiency": "了解"},
        ],
        "bonus": [
            {"skill": "Docker", "category": "tool", "proficiency": "了解"},
        ],
    }


async def _load_target_profile(
    driver: Any,
    target_position: str,
    db_session: Any = None,
    repo: Any = None,
) -> dict[str, list[dict[str, str]]]:
    """Load target position skills with 4-tier fallback.

    优先级：PositionRepository(批量缓存) → Neo4j图查询 → PostgreSQL → 硬编码
    """
    # Tier 1: PositionRepository（批量加载+缓存，最快）
    if repo is not None:
        try:
            profile = await repo.get_position_profile(target_position)
            if profile and profile.required_skills:
                logger.info(
                    "[Match] Loaded {} required + {} bonus skills from repo for \"{}\"",
                    len(profile.required_skills), len(profile.bonus_skills), target_position,
                )
                return {
                    "required": [
                        {"skill": s["name"], "category": s.get("category", "hard_skill"),
                         "proficiency": s.get("proficiency", "熟悉")}
                        for s in profile.required_skills
                    ],
                    "bonus": [
                        {"skill": s["name"], "category": s.get("category", "hard_skill"),
                         "proficiency": s.get("proficiency", "了解")}
                        for s in profile.bonus_skills
                    ],
                }
        except Exception as exc:
            logger.debug("[Match] Repo lookup failed for \"{}\": {}", target_position, exc)

    # Tier 2: Neo4j 图查询
    if driver is not None:
        try:
            graph = await fetch_position_graph(driver, target_position, depth=3)
            if graph.get("skills"):
                required: list[dict[str, str]] = []
                bonus: list[dict[str, str]] = []
                for item in graph["skills"]:
                    props = item.get("properties", {})
                    skill_entry = {
                        "skill": props.get("name", item.get("name", "")),
                        "category": props.get("category", item.get("category", "hard_skill")),
                        "proficiency": props.get("proficiency", item.get("proficiency", "熟悉")),
                    }
                    importance = props.get("importance", "required")
                    if importance == "bonus":
                        bonus.append(skill_entry)
                    else:
                        required.append(skill_entry)
                if required or bonus:
                    logger.info(
                        "[Match] Loaded {} required + {} bonus skills from graph for \"{}\"",
                        len(required), len(bonus), target_position,
                    )
                    return {"required": required, "bonus": bonus}
        except Exception as exc:
            logger.warning("[Match] Graph lookup failed for \"{}\": {}", target_position, exc)

    # Fallback: try PostgreSQL
    if db_session is not None:
        try:
            import sqlalchemy as sa
            from app.models.extraction_models import PositionRecord, PositionSkillRelation, SkillRecord

            stmt = (
                sa.select(SkillRecord.name, SkillRecord.category, PositionSkillRelation.proficiency, PositionSkillRelation.importance)
                .select_from(PositionRecord)
                .join(PositionSkillRelation, PositionSkillRelation.position_id == PositionRecord.id)
                .join(SkillRecord, SkillRecord.id == PositionSkillRelation.skill_id)
                .where(PositionRecord.name == target_position)
            )
            rows = (await db_session.execute(stmt)).all()
            if rows:
                required = []
                bonus = []
                for name, category, proficiency, importance in rows:
                    entry = {
                        "skill": name,
                        "category": category or "hard_skill",
                        "proficiency": proficiency or "熟悉",
                    }
                    if importance == "bonus":
                        bonus.append(entry)
                    else:
                        required.append(entry)
                if required or bonus:
                    logger.info(
                        "[Match] Loaded {} required + {} bonus skills from PostgreSQL for \"{}\"",
                        len(required), len(bonus), target_position,
                    )
                    return {"required": required, "bonus": bonus}
        except Exception as exc:
            logger.warning("[Match] PostgreSQL lookup failed for \"{}\": {}", target_position, exc)

    # Fallback to hardcoded profiles
    logger.info("[Match] Using fallback profile for \"{}\"", target_position)
    return _fallback_profile(target_position)


def _semantic_similarity(left: str, right: str) -> float:
    left_name = _canonical_skill_name(left).lower()
    right_name = _canonical_skill_name(right).lower()
    if left_name == right_name:
        return 1.0
    ratio = SequenceMatcher(a=left_name, b=right_name).ratio()
    # B16: Treat fuzzy match above threshold as strong match
    if ratio >= FUZZY_MATCH_THRESHOLD:
        return ratio
    return ratio


def score_skill_match(
    *,
    target_skills: list[dict[str, str]],
    person_skills: list[dict[str, Any]],
    threshold: float = 0.6,
) -> dict[str, Any]:
    """独立的技能匹配评分函数，可被 recommendation_service 复用。

    从 run_match 中的 score_target 闭包提取而来，包含
    person_level_map / person_name_map 的构建逻辑。

    Args:
        target_skills: 目标岗位的技能列表，每项含 "skill", "importance", "proficiency" 键。
        person_skills: 求职者技能列表，每项含 "skill"(或"name") 和 "proficiency" 键。
        threshold: 匹配阈值，默认 0.6。

    Returns:
        含 evaluated_required, evaluated_bonus, match_score 等字段的字典。
    """
    # 构建求职者技能索引（从 run_match:401-411 提取）
    person_level_map: dict[str, float] = {}
    person_name_map: dict[str, str] = {}
    for item in person_skills:
        raw_name = str(item.get("name") or item.get("skill") or "").strip()
        if not raw_name:
            continue
        canonical = _canonical_skill_name(raw_name)
        person_name_map[canonical] = raw_name
        person_level_map[canonical] = PROFICIENCY_SCORE.get(str(item.get("proficiency", "熟悉")), 0.65)

    all_input_names = set(person_level_map)

    def _score_one(item: dict[str, str]) -> dict[str, Any]:
        """对单个目标技能评分（从 score_target:415-440 提取）。"""
        target_name = _canonical_skill_name(item["skill"])
        target_level = PROFICIENCY_SCORE.get(item.get("proficiency", "熟悉"), 0.65)
        exact = 1.0 if target_name in person_level_map else 0.0
        best_semantic = max(
            (_semantic_similarity(target_name, candidate) for candidate in person_name_map.values()),
            default=0.0,
        )
        fuzzy_match = 1.0 if best_semantic >= FUZZY_MATCH_THRESHOLD else best_semantic
        recall_score = (0.5 * exact) + (0.3 * fuzzy_match) + (0.2 * best_semantic)
        user_level = person_level_map.get(target_name, 0.0)
        proficiency_coverage = min(1.0, user_level / target_level) if target_level else 1.0
        final_score = min(1.0, recall_score * (0.65 + (0.35 * proficiency_coverage)))

        if final_score >= 0.85:
            gap_level = "已掌握"
        elif final_score >= threshold * 0.75:
            gap_level = "部分掌握"
        else:
            gap_level = "完全缺失"

        return {
            "skill": target_name,
            "importance": item["importance"],
            "gap_level": gap_level,
            "learning_path": _build_learning_path(target_name, all_input_names),
            "score": round(final_score, 4),
        }

    evaluated: list[dict[str, Any]] = []
    for item in target_skills:
        evaluated.append(_score_one(item))

    return {"evaluated": evaluated}


def _apply_inflation_correction(profile: dict[str, list[dict[str, str]]]) -> tuple[list[dict[str, str]], list[dict[str, str]], float]:
    required = [dict(item, importance="required") for item in profile.get("required", [])]
    bonus = [dict(item, importance="bonus") for item in profile.get("bonus", [])]
    required_count = len(required)
    cii = (required_count / DEFAULT_REQUIRED_SKILL_BASELINE) if required_count else 1.0

    if cii <= 1.2 or required_count <= 6:
        return required, bonus, cii

    overflow = max(1, required_count - ceil(DEFAULT_REQUIRED_SKILL_BASELINE * 1.2))
    required.sort(key=lambda item: PROFICIENCY_SCORE.get(item.get("proficiency", "熟悉"), 0.65))
    downgraded = required[:overflow]
    kept = required[overflow:]
    for item in downgraded:
        item["importance"] = "bonus"
        item["inflation_adjusted"] = "true"
    return kept, downgraded + bonus, cii


def _build_learning_path(skill_name: str, owned_skills: set[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()

    def visit(name: str) -> None:
        canonical = _canonical_skill_name(name)
        if canonical in seen:
            return
        seen.add(canonical)
        for prerequisite in PREREQUISITE_MAP.get(canonical, []):
            visit(prerequisite)
        if canonical not in owned_skills:
            ordered.append(canonical)

    visit(skill_name)
    return ordered or [_canonical_skill_name(skill_name)]


async def enrich_learning_paths(
    gap_details: list[dict[str, Any]],
    driver: Any,
) -> list[dict[str, Any]]:
    """为差距详情中的每个技能查询 LearningResource 并附加到结果。

    查询 Neo4j 中 RECOMMENDED_FOR 关系，为每个缺失技能关联学习资源。
    无资源时保留原有的 prerequisite 学习路径。
    """
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
        logger.info("[Match] Loaded learning resources for {} skills", len(resource_map))
    except Exception as exc:
        logger.warning("[Match] Failed to load learning resources: {}", exc)

    for gap in gap_details:
        skill = gap.get("skill", "")
        gap["learning_resources"] = resource_map.get(skill, [])

    return gap_details


def _assessment_text(match_score: float, missing_required: int) -> str:
    if match_score >= 0.8 and missing_required == 0:
        return "核心技能已基本覆盖，补齐少量加分项即可进入强匹配区间。"
    if match_score >= 0.6:
        return "基础能力可支撑转岗或进阶，但仍需优先补齐关键缺口。"
    return "当前与目标岗位仍有明显差距，建议按学习路径分阶段补强。"


def _estimate_learning_time(gaps: list[dict[str, Any]]) -> str:
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


async def run_match(
    *,
    target_position: str,
    person_skills: list[dict[str, Any]],
    threshold: float = 0.6,
    driver: Any = None,
    db_session: Any = None,
    repo: Any = None,
) -> dict[str, Any]:
    """Run the lightweight matching engine and store the result."""
    await _load_prerequisite_map(driver)
    target_profile = await _load_target_profile(driver, target_position, db_session, repo=repo)
    required_skills, bonus_skills, cii = _apply_inflation_correction(target_profile)

    # 使用独立的 score_skill_match 函数（从原 score_target 闭包提取）
    required_result = score_skill_match(
        target_skills=required_skills, person_skills=person_skills, threshold=threshold
    )
    bonus_result = score_skill_match(
        target_skills=bonus_skills, person_skills=person_skills, threshold=threshold
    )
    evaluated_required: list[dict[str, Any]] = required_result["evaluated"]
    evaluated_bonus: list[dict[str, Any]] = bonus_result["evaluated"]

    # Scoring: weighted average of required + bonus, with CII correction
    required_avg = sum(item["score"] for item in evaluated_required) / len(evaluated_required) if evaluated_required else 1.0
    bonus_avg = sum(item["score"] for item in evaluated_bonus) / len(evaluated_bonus) if evaluated_bonus else required_avg
    match_score = round(min(1.0, (required_avg * 0.7) + (bonus_avg * 0.3)), 4)

    matched_skills = [item["skill"] for item in evaluated_required + evaluated_bonus if item["gap_level"] == "已掌握"]
    missing_required = [item["skill"] for item in evaluated_required if item["gap_level"] != "已掌握"]
    missing_bonus = [item["skill"] for item in evaluated_bonus if item["gap_level"] != "已掌握"]
    gap_details = sorted(
        evaluated_required + evaluated_bonus,
        key=lambda item: (item["importance"] != "required", item["gap_level"] == "已掌握", item["skill"]),
    )
    gap_skills = [item["skill"] for item in gap_details if item["gap_level"] != "已掌握"]

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
        "overall_assessment": _assessment_text(match_score, len(missing_required)),
        "estimated_learning_time": _estimate_learning_time(gap_details),
    }
    _MATCH_RESULTS[match_id] = result
    # LRU eviction: remove oldest entries when cache exceeds max size
    if len(_MATCH_RESULTS) > _MATCH_RESULTS_MAX_SIZE:
        excess = len(_MATCH_RESULTS) - _MATCH_RESULTS_MAX_SIZE
        for old_key in list(_MATCH_RESULTS.keys())[:excess]:
            del _MATCH_RESULTS[old_key]
    return result


async def get_match_result(match_id: str) -> dict[str, Any] | None:
    """Return a previously computed match result (DB first, memory fallback)."""
    # Try in-memory cache first (fast path)
    if match_id in _MATCH_RESULTS:
        return _MATCH_RESULTS[match_id]

    # Try PostgreSQL
    from sqlalchemy import text

    from app.services.resources import AppResources

    try:
        async with AppResources.pg_sessionmaker() as session:
            row = await session.execute(
                text("SELECT * FROM match_results WHERE match_id = :match_id"),
                {"match_id": match_id},
            )
            db_result = row.mappings().first()
            if db_result:
                # gap_report is stored as JSON array of SkillGapDetail dicts
                raw_gap = db_result.get("gap_report", [])
                skill_gap_detail = list(raw_gap) if isinstance(raw_gap, (list, tuple)) else []

                # learning_path is stored as JSON array of arrays (one per gap item)
                # Flatten the first few learning paths into recommendations
                raw_lp = db_result.get("learning_path", [])
                learning_paths = list(raw_lp) if isinstance(raw_lp, (list, tuple)) else []
                recommendations = [
                    f"优先补齐 {gap.get('skill', '?')}：{' → '.join(path[:3])}"
                    for gap, path in zip(skill_gap_detail, learning_paths)
                    if gap.get("gap_level") != "已掌握"
                ] if skill_gap_detail else []

                return {
                    "match_id": db_result["match_id"],
                    "target_position": db_result["target_position"],
                    "match_score": db_result["match_score"],
                    "matched_skills": db_result["matched_skills"],
                    "missing_required": db_result["missing_required"],
                    "missing_bonus": db_result["missing_bonus"],
                    "skill_gap_detail": skill_gap_detail,
                    "recommendations": recommendations,
                    "cii": db_result.get("cii", 1.0),
                }
    except Exception:
        pass

    return None


async def run_batch_match(
    *,
    resumes: list[dict[str, Any]],
    positions: list[str],
    threshold: float = 0.6,
    driver: Any = None,
    db_session: Any = None,
) -> dict[str, Any]:
    """Run batch matching: multiple resumes × multiple positions.

    Args:
        resumes: List of resume dicts, each with:
            - resume_id: str
            - person_skills: list[dict]
        positions: List of target position names.
        threshold: Match threshold.
        driver: Neo4j driver.
        db_session: DB session.

    Returns:
        Dict with:
        - results: list of match results (resume_id × position pairs)
        - matrix: 2D score matrix (resumes × positions)
        - summary: aggregate statistics
    """
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
                logger.warning(
                    "Batch match failed for resume={} position={}: {}",
                    resume_id, position, exc,
                )
                row_scores.append(0.0)

        matrix.append(row_scores)

    # Summary statistics
    all_scores = [r.get("match_score", 0.0) for r in results]
    summary = {
        "total_pairs": len(results),
        "avg_score": round(sum(all_scores) / len(all_scores), 4) if all_scores else 0.0,
        "max_score": round(max(all_scores), 4) if all_scores else 0.0,
        "min_score": round(min(all_scores), 4) if all_scores else 0.0,
        "high_match_count": sum(1 for s in all_scores if s >= 0.7),
        "medium_match_count": sum(1 for s in all_scores if 0.4 <= s < 0.7),
        "low_match_count": sum(1 for s in all_scores if s < 0.4),
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
    """Compute market competitiveness analysis for a position.

    Analyzes the skill requirements, prerequisite depth, and market
    demand to provide a competitiveness score and breakdown.

    Args:
        target_position: Position name.
        driver: Neo4j driver.
        db_session: DB session.

    Returns:
        Dict with competitiveness analysis.
    """
    await _load_prerequisite_map(driver)
    profile = await _load_target_profile(driver, target_position, db_session)

    required_skills = profile.get("required", [])
    bonus_skills = profile.get("bonus", [])
    all_skills = required_skills + bonus_skills

    # Skill count competitiveness (more skills = harder to match)
    skill_count_score = min(1.0, len(required_skills) / 10.0)

    # Proficiency depth (higher proficiency requirements = harder)
    proficiency_scores = [
        PROFICIENCY_SCORE.get(s.get("proficiency", "熟悉"), 0.65)
        for s in required_skills
    ]
    avg_proficiency = sum(proficiency_scores) / len(proficiency_scores) if proficiency_scores else 0.5

    # Prerequisite depth (deeper chains = harder to learn)
    total_prereq_depth = 0
    skill_prereq_details: list[dict[str, Any]] = []
    for skill_data in all_skills:
        skill_name = _canonical_skill_name(skill_data["skill"])
        path = _build_learning_path(skill_name, set())
        depth = len(path)
        total_prereq_depth += depth
        skill_prereq_details.append({
            "skill": skill_name,
            "prerequisite_depth": depth,
            "learning_path": path,
        })

    avg_prereq_depth = (
        total_prereq_depth / len(all_skills) if all_skills else 0
    )

    # CII (Content Inflation Index)
    required_count = len(required_skills)
    cii = (required_count / DEFAULT_REQUIRED_SKILL_BASELINE) if required_count else 1.0

    # Overall competitiveness score (0-1, higher = more competitive)
    competitiveness = round(
        (skill_count_score * 0.3)
        + (avg_proficiency * 0.3)
        + (min(1.0, avg_prereq_depth / 5.0) * 0.2)
        + (min(1.0, cii / 1.5) * 0.2),
        3,
    )

    # Difficulty label
    if competitiveness >= 0.75:
        difficulty = "高"
        description = "该岗位竞争激烈，需要广泛且深入的技能储备"
    elif competitiveness >= 0.5:
        difficulty = "中"
        description = "该岗位有一定竞争性，需要扎实的核心技能"
    else:
        difficulty = "低"
        description = "该岗位入门门槛较低，适合快速入门"

    # Top bottleneck skills (deepest prerequisite chains)
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

