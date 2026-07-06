"""Match Service — 图驱动匹配引擎：计算求职者技能与岗位要求的匹配度。

核心功能：
  从 Neo4j 加载岗位技能画像，与求职者技能进行多维度匹配评分，
  识别技能差距，生成个性化学习路径推荐。

匹配维度：
  - 精确匹配：技能名称完全一致
  - 模糊匹配：SequenceMatcher 字符串相似度
  - 向量匹配：ChromaDB 语义相似度（阈值 0.85）
  - 熟练度覆盖：求职者熟练度 / 岗位要求熟练度

业务价值：
  为求职者提供量化的岗位匹配度评估，识别技能短板，
  支撑个性化的学习路径规划和职业发展建议。
"""

from __future__ import annotations

import json
import time
from difflib import SequenceMatcher
from math import ceil
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from loguru import logger

from app.core.extraction.normalize import normalize_skill
from app.services.graph_service import fetch_position_graph

# 业务说明：技能熟练度量化映射表。将中文熟练度等级映射为 0-1 之间的数值，
# 用于计算求职者技能覆盖岗位要求的程度。"精通"=0.9,"熟悉"=0.65,"了解"=0.35。
# 技术说明：该映射直接影响匹配评分中的 proficiency_coverage 计算。
PROFICIENCY_SCORE = {"了解": 0.35, "熟悉": 0.65, "精通": 0.9}

# 业务说明：默认岗位必备技能基线数量（6项）。用于计算 CII（内容通胀指数），
# 识别岗位描述中技能要求是否过度膨胀。超过基线 1.2 倍时触发通胀修正。
# 技术说明：基线值 6.0 基于行业统计中位数设定，可通过配置动态调整。
DEFAULT_REQUIRED_SKILL_BASELINE = 6.0

# 业务说明：ChromaDB 语义相似度阈值（0.85）。当精确匹配和模糊匹配均失败时，
# 启用向量数据库进行语义级技能匹配。仅当相似度超过此阈值才认定为匹配成功。
# 技术说明：0.85 为经验阈值，平衡召回率与精确率，避免语义漂移导致的误匹配。
CHROMA_SIMILARITY_THRESHOLD = 0.85

PREREQUISITE_MAP: dict[str, list[str]] = {}

async def _load_prerequisite_map(driver: Any) -> None:
    """Load PREREQUISITE relationships from Neo4j into PREREQUISITE_MAP.

    Results are cached for 5 minutes to avoid repeated Neo4j queries.
    """
    # 业务说明：技能前置关系缓存加载。从 Neo4j 图数据库中一次性加载所有技能之间的
    # PREREQUISITE（前置依赖）关系，构建技能依赖有向图，供学习路径推荐时递归遍历。
    # 技术说明：采用 5 分钟 TTL 缓存策略，避免重复查询 Neo4j。全局变量 PREREQUISITE_MAP
    # 作为运行时缓存，首次加载后后续请求直接命中内存，降低图数据库查询压力。
    global PREREQUISITE_MAP, _PREREQ_CACHE_TS
    if driver is None:
        return

    # Cache TTL: 5 minutes
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


# ── Profile cache (5-minute TTL) ──
_PROFILE_CACHE: dict[str, dict[str, list[dict[str, str]]]] = {}
_PROFILE_CACHE_TS: float | None = None

_PREREQ_CACHE_TS: float | None = None
_MATCH_RESULTS: dict[str, dict[str, Any]] = {}
_MATCH_RESULTS_MAX_SIZE = 1000


# Common skill aliases — unified from normalize.py's SKILL_ALIAS (single source of truth)
# match_service.py no longer maintains its own alias table.
# _canonical_skill_name delegates to normalize_skill which uses the canonical SKILL_ALIAS.

# 业务说明：模糊匹配阈值（0.7）。当技能名称不完全一致时，
# 使用 SequenceMatcher 计算字符串相似度，超过此阈值视为潜在匹配。
# 技术说明：该阈值与 CHROMA_SIMILARITY_THRESHOLD 形成互补的匹配降级策略。
FUZZY_MATCH_THRESHOLD = 0.7


def _canonical_skill_name(name: str) -> str:
    """Canonicalize a skill name using the unified normalization pipeline.

    Delegates to normalize.py's normalize_skill (alias lookup).
    Falls back to the original name if no alias match found.
    """
    result = normalize_skill(name, use_vector=False)
    return (result.normalized or name.strip())


async def _load_target_profile(
    driver: Any,
    target_position: str,
    db_session: Any = None,
    repo: Any = None,
) -> dict[str, list[dict[str, str]]] | None:
    """Load target position skills from graph data sources.

    Priority: PositionRepository(batch+cache) → Neo4j graph
    Returns None if position is not found in any source.
    Results are cached for 5 minutes to avoid repeated queries.
    """
    # 业务说明：岗位技能画像双源加载策略。优先从 PositionRepository（关系型数据库）
    # 获取预聚合的岗位技能数据，命中失败时回退到 Neo4j 图数据库实时查询。
    # 该策略兼顾查询性能（Repo 缓存命中率高）与数据完整性（Neo4j 覆盖全量关系）。
    # 技术说明：采用 5 分钟 TTL 的内存缓存，过期后自动清空并重新加载。
    # Tier 1（PositionRepository）：批量加载+ORM 缓存，延迟最低，适合高频查询。
    # Tier 2（Neo4j）：图遍历查询，支持深度关联分析，适合冷数据或复杂关系场景。
    global _PROFILE_CACHE_TS

    # Check in-memory cache (5-minute TTL)
    now = time.monotonic()
    if _PROFILE_CACHE_TS is not None and (now - _PROFILE_CACHE_TS) < 300:
        cached = _PROFILE_CACHE.get(target_position)
        if cached is not None:
            logger.debug("[Match] Cache hit for \"{}\"", target_position)
            return cached
    else:
        # TTL expired — clear cache
        _PROFILE_CACHE.clear()
        _PROFILE_CACHE_TS = now

    # Tier 1: PositionRepository（批量加载+缓存，最快）
    if repo is not None:
        try:
            profile = await repo.get_position_profile(target_position)
            if profile and profile.required_skills:
                # 业务说明：保留 source_count 字段，供 CII 修正时识别核心硬技能
                # （proficiency="精通" 且 source_count>=30 的技能不应被 CII 降级）。
                result = {
                    "required": [
                        {"skill": s["name"], "category": s.get("category", "hard_skill"),
                         "proficiency": s.get("proficiency", "熟悉"),
                         "source_count": int(s.get("source_count", 0) or 0)}
                        for s in profile.required_skills
                    ],
                    "bonus": [
                        {"skill": s["name"], "category": s.get("category", "hard_skill"),
                         "proficiency": s.get("proficiency", "了解"),
                         "source_count": int(s.get("source_count", 0) or 0)}
                        for s in profile.bonus_skills
                    ],
                }
                logger.info(
                    "[Match] Loaded {} required + {} bonus skills from repo for \"{}\"",
                    len(result["required"]), len(result["bonus"]), target_position,
                )
                _PROFILE_CACHE[target_position] = result
                return result
        except Exception as exc:
            logger.debug("[Match] Repo lookup failed for \"{}\": {}", target_position, exc)

    # Tier 2: Neo4j 图查询
    # 业务说明：fetch_position_graph 返回扁平 SkillNode 字典（name/proficiency/importance 在顶层），
    # 而非嵌套在 properties 下。早期版本误从 item["properties"] 读取，导致 importance 恒为默认值，
    # 所有技能被错误归入必备项（加分项永远为空）。此处显式从两层回退读取以保证兼容性。
    if driver is not None:
        try:
            graph = await fetch_position_graph(driver, target_position, depth=3)
            if graph.get("skills"):
                required: list[dict[str, str]] = []
                bonus: list[dict[str, str]] = []
                for item in graph["skills"]:
                    # fetch_position_graph 的 _skill_item 返回扁平 dict；
                    # 兼容历史嵌套 properties 结构，两层回退读取。
                    props = item.get("properties", {})
                    skill_entry = {
                        "skill": props.get("name") or item.get("name", ""),
                        "category": props.get("category") or item.get("category", "hard_skill"),
                        "proficiency": props.get("proficiency") or item.get("proficiency", "熟悉"),
                        "source_count": int(props.get("source_count") or item.get("source_count", 0) or 0),
                    }
                    importance = props.get("importance") or item.get("importance", "required")
                    if importance == "bonus":
                        bonus.append(skill_entry)
                    else:
                        required.append(skill_entry)
                if required or bonus:
                    result = {"required": required, "bonus": bonus}
                    logger.info(
                        "[Match] Loaded {} required + {} bonus skills from graph for \"{}\"",
                        len(required), len(bonus), target_position,
                    )
                    _PROFILE_CACHE[target_position] = result
                    return result
        except Exception as exc:
            logger.warning("[Match] Graph lookup failed for \"{}\": {}", target_position, exc)

    # All graph data sources exhausted — position not found
    logger.warning("[Match] No profile found for \"{}\" from graph data sources", target_position)
    return None


def _semantic_similarity(left: str, right: str) -> float:
    # 业务说明：语义相似度计算。对两个技能名称进行规范化后比较，
    # 支持精确匹配（1.0）和模糊匹配（SequenceMatcher 字符串相似度）。
    # 当模糊匹配度超过 FUZZY_MATCH_THRESHOLD（0.7）时，返回实际相似度值，
    # 否则返回原始 ratio，供上层决策是否采纳为有效匹配。
    # 技术说明：先通过 _canonical_skill_name 统一别名（如 "JS"→"JavaScript"），
    # 再转小写后比较，确保大小写和别名不影响匹配结果。
    left_name = _canonical_skill_name(left).lower()
    right_name = _canonical_skill_name(right).lower()
    if left_name == right_name:
        return 1.0
    ratio = SequenceMatcher(a=left_name, b=right_name).ratio()
    # B16: Treat fuzzy match above threshold as strong match
    if ratio >= FUZZY_MATCH_THRESHOLD:
        return ratio
    return ratio


def _chroma_similarity(target_name: str, candidate_name: str) -> float | None:
    """Check semantic similarity via ChromaDB vector search.

    When exact string match fails, tries ChromaDB vector search.
    If similarity > CHROMA_SIMILARITY_THRESHOLD, returns the similarity score.
    Returns None if ChromaDB is unavailable or similarity is below threshold.

    Note: For batch matching, prefer ``_chroma_match_against_candidates`` which
    queries ChromaDB once per target and matches against all candidates, avoiding
    the O(target×candidate) call pattern that caused severe latency when the
    ChromaDB collection was unavailable.
    """
    # 业务说明：ChromaDB 向量语义匹配降级策略。当精确匹配和模糊匹配均失败时，
    # 启用向量数据库进行语义级匹配，识别技能名称不同但语义相近的情况
    # （如 "React.js" 与 "React" 或 "前端框架" 与 "React"）。
    # 技术说明：调用 normalize_by_vector 进行向量检索，返回标准化技能名。
    # 若返回的标准名与候选技能的规范名一致，则判定为语义匹配成功，
    # 返回固定阈值 CHROMA_SIMILARITY_THRESHOLD 作为匹配分数。
    # 异常时静默返回 None，避免向量服务故障影响主流程。
    try:
        from app.core.extraction.normalize import normalize_by_vector

        result = normalize_by_vector(
            target_name,
            chroma_client=None,
            threshold=CHROMA_SIMILARITY_THRESHOLD,
        )
        if result is not None:
            # normalize_by_vector returns the standard name; verify it matches candidate
            canonical_candidate = _canonical_skill_name(candidate_name)
            if result == canonical_candidate:
                return CHROMA_SIMILARITY_THRESHOLD
        return None
    except Exception:
        return None


def _chroma_match_against_candidates(
    target_name: str,
    candidate_canonical_names: set[str],
) -> float | None:
    """Query ChromaDB once for ``target_name`` and check against all candidates.

    业务说明：批量语义匹配优化版。对单个目标技能仅查询一次 ChromaDB，
    返回的标准名与候选技能集合做内存匹配，避免对每个候选技能单独查询。
    技术说明：将原 O(候选数) 次 ChromaDB 调用降为 O(1) 次，显著降低
    ChromaDB 不可用或延迟较高时的匹配耗时（原实现导致 /match/position 接口卡死）。
    若 ChromaDB 返回 None（不可用/无匹配），整体返回 None。

    Args:
        target_name: 目标技能的规范化名称。
        candidate_canonical_names: 候选技能的规范化名称集合（person_name_map 的键集合）。

    Returns:
        匹配成功返回 CHROMA_SIMILARITY_THRESHOLD，否则 None。
    """
    if not candidate_canonical_names:
        return None
    try:
        from app.core.extraction.normalize import normalize_by_vector

        result = normalize_by_vector(
            target_name,
            chroma_client=None,
            threshold=CHROMA_SIMILARITY_THRESHOLD,
        )
        if result is not None and result in candidate_canonical_names:
            return CHROMA_SIMILARITY_THRESHOLD
        return None
    except Exception:
        return None


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
    # 业务说明：构建求职者技能索引。将原始技能名称规范化后建立两级映射：
    # person_name_map 保存规范名→原始名的映射（用于模糊匹配时回查），
    # person_level_map 保存规范名→熟练度数值的映射（用于计算覆盖度）。
    # 技术说明：规范化通过 _canonical_skill_name 统一别名，熟练度通过 PROFICIENCY_SCORE 量化。
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
    # 候选技能的规范名集合，供 _chroma_match_against_candidates 一次性内存匹配使用，
    # 避免 _score_one 在嵌套循环中对每个候选技能单独查询 ChromaDB（性能优化）。
    candidate_canonical_set = set(person_level_map.keys())

    def _score_one(item: dict[str, str]) -> dict[str, Any]:
        """对单个目标技能评分（从 score_target:415-440 提取）。"""
        # 业务说明：单个技能的四维匹配评分算法。
        # 1) 精确匹配（exact）：技能规范名完全一致，权重最高（0.5）。
        # 2) 模糊匹配（fuzzy）：SequenceMatcher 字符串相似度≥阈值，权重 0.3。
        # 3) 向量匹配（chroma）：ChromaDB 语义相似度，权重折算后并入 fuzzy（0.9 折）。
        # 4) 熟练度覆盖（proficiency_coverage）：求职者熟练度/岗位要求熟练度，权重 0.35。
        # 最终分数 = recall_score × (0.65 + 0.35 × proficiency_coverage)，上限 1.0。
        # 技术说明：recall_score = 0.5×exact + 0.3×fuzzy + 0.2×best_semantic，
        # 确保即使 fuzzy 和 chroma 同时命中也不会过度加权。
        target_name = _canonical_skill_name(item["skill"])
        target_level = PROFICIENCY_SCORE.get(item.get("proficiency", "熟悉"), 0.65)
        exact = 1.0 if target_name in person_level_map else 0.0
        best_semantic = max(
            (_semantic_similarity(target_name, candidate) for candidate in person_name_map.values()),
            default=0.0,
        )
        # ChromaDB semantic fallback: when exact match fails, try vector similarity.
        # 优化：每个目标技能仅查询一次 ChromaDB，再与候选集合做内存匹配，
        # 避免原 O(候选数) 次查询导致的接口卡死问题。
        chroma_match = 0.0
        if exact == 0.0 and best_semantic < FUZZY_MATCH_THRESHOLD:
            chroma_sim = _chroma_match_against_candidates(target_name, candidate_canonical_set)
            if chroma_sim is not None and chroma_sim > chroma_match:
                chroma_match = chroma_sim
        fuzzy_match = 1.0 if best_semantic >= FUZZY_MATCH_THRESHOLD else best_semantic
        # ChromaDB match counts as a fuzzy match with reduced weight
        if chroma_match >= CHROMA_SIMILARITY_THRESHOLD and fuzzy_match < 1.0:
            fuzzy_match = max(fuzzy_match, chroma_match * 0.9)  # reduced weight for vector match
        recall_score = (0.5 * exact) + (0.3 * fuzzy_match) + (0.2 * best_semantic)
        user_level = person_level_map.get(target_name, 0.0)
        proficiency_coverage = min(1.0, user_level / target_level) if target_level else 1.0
        final_score = min(1.0, recall_score * (0.65 + (0.35 * proficiency_coverage)))

        # 业务说明：gap_level 分级判定。早期版本仅以 final_score >= 0.85 判为"已掌握"，
        # 但精确匹配（exact==1.0）的技能即使熟练度略低于岗位要求（如用户"了解" vs 岗位"熟悉"），
        # final_score 也会因熟练度惩罚降到 ~0.838，被错误归为"部分掌握"，
        # 导致 matched_skills 虚低、missing_required 虚高（即 B16 根因）。
        # 修复：精确命中即视为"已掌握"；模糊/语义命中按 final_score 分级。
        if exact == 1.0:
            gap_level = "已掌握"
        elif final_score >= 0.85:
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
    # 业务说明：CII（Content Inflation Index，内容通胀指数）修正。
    # 某些岗位描述存在技能要求过多的"通胀"现象（如要求 15 项必备技能），
    # 导致求职者匹配度被人为压低。通过 CII 识别并修正：
    # CII = 实际必备技能数 / DEFAULT_REQUIRED_SKILL_BASELINE（6.0）。
    # 当 CII > 1.2 且技能数 > 6 时，将多余的低优先级必备技能降级为加分项，
    # 使匹配评分更公平地反映核心技能覆盖度。
    # 技术说明：按熟练度要求从低到高排序，优先降级要求较低的技能（如"了解"级），
    # 保留高要求的硬核技能。同时对最终 required+bonus 集合做去重，
    # 避免同名技能（如 Docker）同时出现在必备与加分列表中导致响应数据重复。
    required = [dict(item, importance="required") for item in profile.get("required", [])]
    bonus = [dict(item, importance="bonus") for item in profile.get("bonus", [])]
    required_count = len(required)
    cii = (required_count / DEFAULT_REQUIRED_SKILL_BASELINE) if required_count else 1.0

    if cii <= 1.2 or required_count <= 6:
        # 即便不触发降级，也要保证 bonus 中没有与 required 同名的技能
        required_names = {item["skill"] for item in required}
        bonus = [item for item in bonus if item["skill"] not in required_names]
        return required, bonus, cii

    overflow = max(1, required_count - ceil(DEFAULT_REQUIRED_SKILL_BASELINE * 1.2))
    # 按 proficiency 从低到高排序，proficiency 相同则按 source_count 从低到高（数据支撑弱的优先降级）
    required.sort(key=lambda item: (
        PROFICIENCY_SCORE.get(item.get("proficiency", "熟悉"), 0.65),
        int(item.get("source_count", 0) or 0),
    ))
    downgraded = required[:overflow]
    kept = required[overflow:]
    # 业务说明：避免降级误伤核心硬技能。即便在降级队列中，
    # 若技能的 proficiency="精通" 且 source_count >= 30（数据强支撑），
    # 则视为核心硬技能，保留在 required 列表，避免核心能力被错误降级为加分项。
    safe_downgraded = []
    for item in downgraded:
        prof = item.get("proficiency", "")
        src = int(item.get("source_count", 0) or 0)
        if prof == "精通" and src >= 30:
            kept.append(item)  # 留在 required
            logger.debug(
                "[Match] Protected core skill '{}' from CII downgrade (prof={}, sources={})",
                item["skill"], prof, src,
            )
            continue
        item["importance"] = "bonus"
        item["inflation_adjusted"] = "true"
        safe_downgraded.append(item)
    downgraded = safe_downgraded
    # 合并 bonus（降级项 + 原始 bonus），然后按技能名去重，
    # 避免同一技能既出现在 kept(required) 又出现在 downgraded/bonus。
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


def _build_learning_path(skill_name: str, owned_skills: set[str]) -> list[str]:
    # 业务说明：递归构建技能学习路径。基于 PREREQUISITE_MAP 中的前置依赖关系，
    # 从目标技能出发递归遍历其所有前置技能，生成线性的学习顺序列表。
    # 仅包含求职者尚未掌握的技能，已掌握的技能自动过滤，避免重复学习建议。
    # 技术说明：使用深度优先递归（DFS）遍历依赖图，通过 seen 集合防止循环依赖导致的死循环。
    # 前置技能优先于目标技能加入列表，确保学习路径符合"先基础后进阶"的认知规律。
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
    # 业务说明：学习资源富集。在生成技能差距报告后，为每个缺失技能
    # 关联推荐的学习资源（课程、文档、教程等），将抽象的学习路径转化为可执行的学习计划。
    # 技术说明：通过 Neo4j 中 LearningResource 节点与 Skill 节点的 RECOMMENDED_FOR 关系
    # 进行批量查询，构建 skill→resources 映射字典，避免逐技能查询导致的 N+1 问题。
    # 若查询失败或无资源，保留原有的 prerequisite 路径作为兜底。
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
    # 业务说明：根据匹配分数和缺失必备技能数量，生成结构化的评估文本。
    # 当匹配分数≥0.8 且没有缺失必备技能时，判定为核心技能已覆盖；
    # 当匹配分数≥0.6 时，判定为基础能力可支撑转岗；
    # 否则判定为与目标岗位有明显差距。用于向求职者提供直观的匹配评估结论。
    if match_score >= 0.8 and missing_required == 0:
        return "核心技能已基本覆盖，补齐少量加分项即可进入强匹配区间。"
    if match_score >= 0.6:
        return "基础能力可支撑转岗或进阶，但仍需优先补齐关键缺口。"
    return "当前与目标岗位仍有明显差距，建议按学习路径分阶段补强。"


def _estimate_learning_time(gaps: list[dict[str, Any]]) -> str:
    # 业务说明：基于技能差距列表估算学习时长。核心逻辑：
    # 1) 必备技能基础耗时 3 周/项，加分技能 1.5 周/项；
    # 2) "部分掌握"的技能按 50% 折算，"已掌握"的技能仅计 0.5 周复习时间；
    # 3) 总时长≥12 周时转换为月数表示，否则以周为单位。
    # 该估算为粗略参考，实际学习时长因个人基础和学习强度而异。
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


async def save_match_result(session: Any, match_id: str, result: dict[str, Any]) -> None:
    """Persist a match result to the match_results table.

    Uses SQLAlchemy raw SQL with jsonb casts for insertion.
    Silently ignores duplicates (ON CONFLICT DO NOTHING).
    Also stores the result in the in-memory read-through cache.
    """
    # 业务说明：将匹配结果持久化到 PostgreSQL 关系型数据库。
    # 匹配结果包含匹配分数、已匹配技能、缺失技能、差距报告、学习路径等多维数据，
    # 以 JSONB 格式存储，兼顾结构化查询和灵活扩展。
    # 技术说明：使用 SQLAlchemy raw SQL 执行 INSERT，通过 CAST(... AS jsonb) 将 Python 字典
    # 转换为 PostgreSQL jsonb 类型。ON CONFLICT DO NOTHING 避免重复插入导致的异常。
    # 同时写入内存缓存 _MATCH_RESULTS，实现写入即缓存的 write-through 策略。
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
        logger.debug("[Match] Persisted result {} to PostgreSQL", match_id)
    except Exception as exc:
        logger.warning("[Match] Failed to persist result {}: {}", match_id, exc)


async def _get_pg_session() -> Any:
    """Get a short-lived PostgreSQL session from AppResources.

    Returns None if the sessionmaker is not initialized.
    """
    from app.services.resources import AppResources

    if AppResources.pg_sessionmaker is None:
        return None
    return AppResources.pg_sessionmaker()


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
    # 业务说明：核心匹配引擎入口。整体匹配流程如下：
    # 1) 加载技能前置依赖图（PREREQUISITE_MAP），用于后续学习路径构建；
    # 2) 加载目标岗位技能画像（双源策略：PositionRepository → Neo4j）；
    # 3) 应用 CII 通胀修正，识别并降级过度膨胀的必备技能；
    # 4) 对必备技能和加分技能分别调用 score_skill_match 进行多维匹配评分；
    # 5) 计算加权匹配分数（必备 70% + 加分 30%），生成差距报告；
    # 6) 生成学习路径推荐、整体评估文本、预估学习时长；
    # 7) 将结果写入内存缓存（LRU 淘汰）并持久化到 PostgreSQL。
    # 技术说明：必备技能和加分技能分别评分后合并，确保两类技能的重要性权重差异
    # 在最终分数中得到体现。内存缓存采用 FIFO 淘汰策略，上限 1000 条。
    await _load_prerequisite_map(driver)
    target_profile = await _load_target_profile(driver, target_position, db_session, repo=repo)
    if target_profile is None:
        raise HTTPException(
            status_code=404,
            detail=f"Position \"{target_position}\" not found in graph",
        )
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

    # 业务说明：合并后去重。即便 _apply_inflation_correction 已尽力去重，
    # 若上游图数据中同技能出现多条不同 node id 的边（直接 REQUIRES 多条），
    # 也可能在评分阶段产生重复项。此处做最终保险去重：
    # - 同名技能若同时出现在 required 与 bonus，优先保留 required（重要性更严格）。
    # - 分数取两者中较高者；gap_level 取较严格（已掌握 > 部分掌握 > 完全缺失）。
    required_skill_map: dict[str, dict[str, Any]] = {item["skill"]: item for item in evaluated_required}
    bonus_skill_map: dict[str, dict[str, Any]] = {item["skill"]: item for item in evaluated_bonus}
    merged_evaluated: list[dict[str, Any]] = []
    for skill, req_item in required_skill_map.items():
        if skill in bonus_skill_map:
            bon_item = bonus_skill_map[skill]
            # 保留 required 版本（重要性更严格），但取较高分数与较好 gap_level
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
    evaluated_bonus = [item for skill, item in bonus_skill_map.items() if skill not in required_skill_map]

    # Scoring: weighted average of required + bonus, with CII correction
    required_avg = sum(item["score"] for item in evaluated_required) / len(evaluated_required) if evaluated_required else 1.0
    bonus_avg = sum(item["score"] for item in evaluated_bonus) / len(evaluated_bonus) if evaluated_bonus else required_avg
    match_score = round(min(1.0, (required_avg * 0.7) + (bonus_avg * 0.3)), 4)

    matched_skills = [item["skill"] for item in merged_evaluated if item["gap_level"] == "已掌握"]
    missing_required = [item["skill"] for item in evaluated_required if item["gap_level"] != "已掌握"]
    missing_bonus = [item["skill"] for item in evaluated_bonus if item["gap_level"] != "已掌握"]
    gap_details = sorted(
        merged_evaluated,
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

    # Persist to PostgreSQL — use provided session, or acquire one from AppResources
    if db_session is not None:
        await save_match_result(db_session, match_id, result)
    else:
        session_ctx = await _get_pg_session()
        if session_ctx is not None:
            try:
                async with session_ctx as sess:
                    await save_match_result(sess, match_id, result)
            except Exception as exc:
                logger.warning("[Match] Failed to persist result {} via AppResources session: {}", match_id, exc)

    return result


async def get_match_result(match_id: str) -> dict[str, Any] | None:
    """Return a previously computed match result (memory first, DB fallback).

    Implements a read-through cache: when a result is found in PostgreSQL
    but not in the in-memory cache, it is loaded into the cache so that
    subsequent lookups hit the fast path.
    """
    # 业务说明：Read-Through 缓存模式实现。查询优先级：内存缓存 → PostgreSQL 数据库。
    # 当内存缓存命中时直接返回（微秒级延迟）；未命中时查询 PostgreSQL，
    # 若数据库中存在记录，则重建完整结果对象并回填到内存缓存，供后续请求快速访问。
    # 该模式显著降低热点数据的查询延迟，同时保证冷数据的可访问性。
    # 技术说明：从数据库重建结果时，需将 JSONB 字段解析为 Python 对象，
    # 并基于 gap_report 和 learning_path 重新生成 recommendations 列表。
    # 内存缓存上限 1000 条，超限时采用 FIFO 淘汰策略。
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
                    for gap, path in zip(skill_gap_detail, learning_paths, strict=False)
                    if gap.get("gap_level") != "已掌握"
                ] if skill_gap_detail else []

                reconstructed = {
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

                # Read-through: populate in-memory cache for future fast lookups
                _MATCH_RESULTS[match_id] = reconstructed
                if len(_MATCH_RESULTS) > _MATCH_RESULTS_MAX_SIZE:
                    excess = len(_MATCH_RESULTS) - _MATCH_RESULTS_MAX_SIZE
                    for old_key in list(_MATCH_RESULTS.keys())[:excess]:
                        del _MATCH_RESULTS[old_key]

                return reconstructed
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
    # 业务说明：批量匹配引擎。支持多份简历与多个岗位之间的交叉匹配，
    # 生成匹配结果列表、二维分数矩阵和汇总统计。适用于人才批量筛选、
    # 岗位推荐等场景。每个简历×岗位组合独立调用 run_match，失败时记录日志并返回 0 分，
    # 确保单条失败不影响整体批次。
    # 技术说明：外层循环遍历简历，内层循环遍历岗位，构建二维分数矩阵。
    # 汇总统计包括平均分、最高分、最低分，以及高/中/低匹配度分布计数。
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
    # 业务说明：岗位竞争力分析。从四个维度综合评估目标岗位的市场竞争难度：
    # 1) 技能数量维度：必备技能越多，竞争越激烈（满分 10 项，线性归一化）；
    # 2) 熟练度深度：岗位要求熟练度越高，入门门槛越高（取必备技能熟练度均值）；
    # 3) 前置依赖深度：技能的前置学习链越长，培养周期越长（取平均前置路径长度，满分 5 层）；
    # 4) CII 通胀指数：岗位要求膨胀程度越高，实际竞争越被低估（CII/1.5 归一化）。
    # 综合竞争力 = 技能数量×0.3 + 熟练度×0.3 + 前置深度×0.2 + CII×0.2，范围 0-1。
    # 技术说明：通过 _build_learning_path 计算每个技能的前置依赖链长度，
    # 识别瓶颈技能（前置链最长的前 5 项），为求职者提供竞争难度预警。
    await _load_prerequisite_map(driver)
    profile = await _load_target_profile(driver, target_position, db_session)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail=f"Position \"{target_position}\" not found in graph",
        )

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

