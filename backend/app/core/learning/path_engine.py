"""Learning Path Engine — 个性化学习路径生成引擎。

核心流程：
1. 从技能依赖数据构建前置条件 DAG（有向无环图）
2. 拓扑排序技能，确保前置技能优先学习
3. 基于当前/目标熟练度估算每个技能的学习时长
4. 按可用周学时分配学习路径

业务价值：
  根据用户技能差距诊断，生成个性化的学习路径和阶段性学习计划，
  帮助用户系统性地补齐技能短板，实现从当前能力到目标岗位的有序进阶。
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from math import ceil
from typing import Any

from loguru import logger

from app.core.constants import (
    DEFAULT_PROFICIENCY,
    GAP_LEVEL_MASTERED,
    GAP_LEVEL_MISSING,
    GAP_LEVEL_PARTIAL,
    LOW_PROFICIENCY,
)
from app.core.matching.constants import PROFICIENCY_SCORE
from app.exceptions import StarMapError

# Base learning hours per skill at different gap levels
_BASE_HOURS: dict[str, float] = {
    GAP_LEVEL_MISSING: 40.0,
    GAP_LEVEL_PARTIAL: 20.0,
    GAP_LEVEL_MASTERED: 2.0,
}

# Fallback prerequisite relationships (used when Neo4j is unavailable)
_FALLBACK_PREREQUISITES: dict[str, list[str]] = {
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
    "Deep Learning": ["Machine Learning", "Python"],
    "PyTorch": ["Python", "Deep Learning"],
    "TensorFlow": ["Python", "Deep Learning"],
    "NLP": ["Machine Learning", "Python"],
    "scikit-learn": ["Python", "Machine Learning"],
    "LangChain": ["Python", "LLM"],
    "LLM": ["Machine Learning", "Python"],
}


# ---------------------------------------------------------------------------
# Neo4j data loaders with TTL cache
# ---------------------------------------------------------------------------

_CACHE_TTL_SECONDS: float = 300.0  # 5 minutes

# Cache state: (timestamp, cache_key, data)
_prereqs_cache: tuple[float, dict[str, list[str]]] | None = None
_skill_hours_cache: tuple[float, frozenset[str], dict[str, float]] | None = None


async def _load_prerequisites_from_neo4j() -> dict[str, list[str]]:
    """Load PREREQUISITE relationships from Neo4j Skill nodes.

    Results are cached for 5 minutes to avoid hammering Neo4j on every call.

    Returns a dict mapping each skill to its list of prerequisite skills.
    Returns empty dict if Neo4j is unavailable, so callers fall back to
    ``_FALLBACK_PREREQUISITES``.
    """
    global _prereqs_cache

    # Return cached result if still valid
    if _prereqs_cache is not None:
        cached_at, cached_data = _prereqs_cache
        if time.monotonic() - cached_at < _CACHE_TTL_SECONDS:
            return cached_data

    from app.services.resources import resources

    driver = resources.neo4j_driver
    if driver is None:
        logger.debug("Neo4j driver not available — skipping prerequisite load")
        return {}

    try:
        prereqs: dict[str, list[str]] = {}
        async with driver.session() as session:
            cypher = (
                "MATCH (a:Skill)-[:PREREQUISITE]->(b:Skill) "
                "RETURN a.name AS src, b.name AS tgt"
            )
            result = await session.run(cypher)
            async for rec in result:
                src = rec["src"]
                tgt = rec["tgt"]
                if src not in prereqs:
                    prereqs[src] = []
                if tgt not in prereqs[src]:
                    prereqs[src].append(tgt)
        logger.debug("Loaded {} prerequisite rules from Neo4j", len(prereqs))
        _prereqs_cache = (time.monotonic(), prereqs)
        return prereqs
    except StarMapError:
        raise
    except Exception as exc:
        # M3: Neo4j 不可用时降级返回空映射,不阻断学习路径主流程;域异常仍向上抛。
        # 契约:test_neo4j_error_returns_empty。
        logger.warning("Learning path Neo4j load failed, degrading to empty: {}", exc)
        return {}


async def _load_skill_hours_from_neo4j(
    skill_names: set[str],
) -> dict[str, float]:
    """Load ``learning_hours`` from Neo4j Skill nodes.

    Results are cached for 5 minutes.  The cache key is the *sorted* set of
    requested skill names; a different set triggers a fresh query.

    Args:
        skill_names: Set of skill names to look up.

    Returns:
        Dict mapping skill name → learning hours.  Empty if Neo4j is
        unavailable or no Skill nodes carry that property.
    """
    global _skill_hours_cache

    # Return cached result if still valid and the skill set matches
    cache_key = frozenset(skill_names)
    if _skill_hours_cache is not None:
        cached_at, cached_key, cached_data = _skill_hours_cache
        if cached_key == cache_key and time.monotonic() - cached_at < _CACHE_TTL_SECONDS:
            return cached_data

    from app.services.resources import resources

    driver = resources.neo4j_driver
    if driver is None or not skill_names:
        return {}

    try:
        hours_map: dict[str, float] = {}
        async with driver.session() as session:
            cypher = (
                "MATCH (s:Skill) WHERE s.name IN $names "
                "RETURN s.name AS name, "
                "       COALESCE(s.learning_hours, s.base_hours, NULL) AS hours"
            )
            result = await session.run(cypher, names=list(skill_names))
            async for rec in result:
                name = rec["name"]
                h = rec.get("hours")
                if h is not None:
                    hours_map[name] = float(h)
        logger.debug(
            "Loaded learning hours for {}/{} skills from Neo4j",
            len(hours_map), len(skill_names),
        )
        _skill_hours_cache = (time.monotonic(), cache_key, hours_map)
        return hours_map
    except StarMapError:
        raise
    except Exception as exc:
        # M3: Neo4j 不可用时降级返回空映射,不阻断学习路径主流程;域异常仍向上抛。
        # 契约:test_neo4j_error_returns_empty。
        logger.warning("Learning path Neo4j load failed, degrading to empty: {}", exc)
        return {}


@dataclass
class SkillNode:
    """A skill in the learning path with time estimates."""

    name: str
    importance: str  # required | bonus
    gap_level: str  # 完全缺失 | 部分掌握 | 已掌握
    current_proficiency: str | None = None
    target_proficiency: str | None = None
    estimated_hours: float = 0.0
    prerequisites: list[str] = field(default_factory=list)
    learning_path: list[str] = field(default_factory=list)
    order: int = 0


@dataclass
class LearningPath:
    """A complete ordered learning path with time estimates."""

    skills: list[SkillNode]
    total_hours: float = 0.0
    total_weeks: float = 0.0
    weekly_hours: float = 10.0
    phase_count: int = 0
    phases: list[dict[str, Any]] = field(default_factory=list)


def estimate_learning_time(
    skill: str,
    current_level: str | None = None,
    target_level: str = DEFAULT_PROFICIENCY,
    gap_level: str = GAP_LEVEL_MISSING,
    skill_hours_map: dict[str, float] | None = None,
) -> float:
    """Estimate learning hours for a single skill.

    Args:
        skill: Skill name.
        current_level: User's current proficiency (了解/熟悉/精通).
        target_level: Target proficiency level.
        gap_level: Gap level from match diagnosis.
        skill_hours_map: Optional per-skill base hours loaded from Neo4j.
            When provided for the given skill, that value is used as the
            base instead of the gap-level-based ``_BASE_HOURS`` dict.

    Returns:
        Estimated learning hours.
    """
    # 1) Per-skill base hours from Neo4j (most accurate)
    if skill_hours_map and skill in skill_hours_map:
        base = skill_hours_map[skill]
    # 2) Fallback to gap-level-based dict
    else:
        base = _BASE_HOURS.get(gap_level, 40.0)

    # Adjust based on proficiency gap
    current_score = PROFICIENCY_SCORE.get(current_level or LOW_PROFICIENCY, 0.0)
    target_score = PROFICIENCY_SCORE.get(target_level, 0.65)
    proficiency_gap = max(0.0, target_score - current_score)

    # Scale hours by proficiency gap (0-1 range → 0.5x-1.5x multiplier)
    multiplier = 0.5 + proficiency_gap
    return round(base * multiplier, 1)


async def build_prerequisite_graph(
    skills: list[str],
    extra_prerequisites: dict[str, list[str]] | None = None,
) -> dict[str, list[str]]:
    """Build a prerequisite DAG for the given skills.

    Attempts to load prerequisite relationships from Neo4j first;
    falls back to ``_FALLBACK_PREREQUISITES`` when Neo4j is unavailable.
    Any caller-supplied ``extra_prerequisites`` are layered on top.

    Args:
        skills: List of skill names to include in the graph.
        extra_prerequisites: Additional prerequisite mappings (e.g., from DB).

    Returns:
        Dict mapping each skill to its list of prerequisites (filtered to
        only include skills present in the input set).
    """
    skill_set = set(skills)

    # 1) Try Neo4j first
    neo4j_prereqs = await _load_prerequisites_from_neo4j()

    # 2) Merge: Neo4j as primary, fallback for anything Neo4j doesn't cover
    all_prereqs: dict[str, list[str]] = (
        neo4j_prereqs if neo4j_prereqs else dict(_FALLBACK_PREREQUISITES)
    )

    # 3) Caller-supplied extras take highest precedence
    if extra_prerequisites:
        for skill, prereqs in extra_prerequisites.items():
            all_prereqs[skill] = prereqs

    # 4) Filter to only include skills in our set
    graph: dict[str, list[str]] = {}
    for skill in skills:
        prereqs = all_prereqs.get(skill, [])
        filtered = [p for p in prereqs if p in skill_set]
        graph[skill] = filtered

    return graph


def _topological_sort(graph: dict[str, list[str]]) -> list[str]:
    """Topological sort of the prerequisite DAG.

    Returns skills in learning order (prerequisites first).
    BL-04: If the graph contains cycles, use SCC (Tarjan's algorithm)
    to compress cyclic nodes into super-nodes, then topologically sort
    the compressed DAG instead of falling back to arbitrary order.
    """
    # Compute in-degrees
    in_degree: dict[str, int] = dict.fromkeys(graph, 0)
    dependents: dict[str, list[str]] = defaultdict(list)

    for skill, prereqs in graph.items():
        for prereq in prereqs:
            if prereq in graph:
                dependents[prereq].append(skill)
                in_degree[skill] = in_degree.get(skill, 0) + 1

    # BFS from zero in-degree nodes
    queue: deque[str] = deque(
        skill for skill, deg in in_degree.items() if deg == 0
    )
    order: list[str] = []

    while queue:
        current = queue.popleft()
        order.append(current)
        for dependent in dependents.get(current, []):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(order) == len(graph):
        return order

    # BL-04: Cycle detected — use Tarjan's SCC to compress cycles
    logger.warning("Cycle detected in prerequisite graph — using SCC compression")
    sccs = _tarjan_scc(graph)
    # Build compressed graph: each SCC becomes a single node
    node_to_scc: dict[str, int] = {}
    for idx, scc in enumerate(sccs):
        for node in scc:
            node_to_scc[node] = idx

    compressed: dict[int, set[int]] = defaultdict(set)
    for skill, prereqs in graph.items():
        s = node_to_scc[skill]
        for prereq in prereqs:
            if prereq in node_to_scc:
                p = node_to_scc[prereq]
                if p != s:
                    compressed[p].add(s)

    # Topological sort of compressed graph (Kahn's algorithm)
    comp_in_degree: dict[int, int] = defaultdict(int)
    all_sccs = set(range(len(sccs)))
    for _s, deps in compressed.items():
        for d in deps:
            comp_in_degree[d] += 1

    comp_queue: deque[int] = deque(
        s for s in all_sccs if comp_in_degree.get(s, 0) == 0
    )
    scc_order: list[int] = []
    while comp_queue:
        s = comp_queue.popleft()
        scc_order.append(s)
        for d in compressed.get(s, set()):
            comp_in_degree[d] -= 1
            if comp_in_degree[d] == 0:
                comp_queue.append(d)

    # Flatten SCC order back to skill order
    result: list[str] = []
    for scc_idx in scc_order:
        result.extend(sccs[scc_idx])
    return result


def _tarjan_scc(graph: dict[str, list[str]]) -> list[list[str]]:
    """Tarjan's algorithm for finding strongly connected components.

    Returns SCCs in reverse topological order (sinks first).
    BL-04: Used to compress cycles in prerequisite graphs.
    """
    index_counter = [0]
    stack: list[str] = []
    on_stack: set[str] = set()
    index: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    sccs: list[list[str]] = []

    def strongconnect(v: str) -> None:
        index[v] = lowlink[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack.add(v)

        for w in graph.get(v, []):
            if w not in graph:
                continue  # skip nodes not in our set
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], index[w])

        if lowlink[v] == index[v]:
            scc: list[str] = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                scc.append(w)
                if w == v:
                    break
            sccs.append(scc)

    for v in graph:
        if v not in index:
            strongconnect(v)

    return sccs


def _build_phases(
    ordered_skills: list[SkillNode],
    weekly_hours: float,
) -> list[dict[str, Any]]:
    """Group skills into learning phases based on prerequisites and time.

    Each phase contains skills that can be studied in parallel (their
    prerequisites are all in earlier phases).
    """
    phases: list[dict[str, Any]] = []
    current_phase: list[SkillNode] = []
    current_hours = 0.0
    phase_hours_budget = weekly_hours * 2  # ~2 weeks per phase

    for skill_node in ordered_skills:
        if skill_node.gap_level == GAP_LEVEL_MASTERED:
            continue

        if current_hours + skill_node.estimated_hours > phase_hours_budget and current_phase:
            phases.append({
                "phase": len(phases) + 1,
                "skills": [s.name for s in current_phase],
                "estimated_hours": round(current_hours, 1),
                "estimated_weeks": round(current_hours / weekly_hours, 1) if weekly_hours else 0,
            })
            current_phase = []
            current_hours = 0.0

        current_phase.append(skill_node)
        current_hours += skill_node.estimated_hours

    # Flush remaining
    if current_phase:
        phases.append({
            "phase": len(phases) + 1,
            "skills": [s.name for s in current_phase],
            "estimated_hours": round(current_hours, 1),
            "estimated_weeks": round(current_hours / weekly_hours, 1) if weekly_hours else 0,
        })

    return phases


async def generate_learning_path(
    match_gaps: list[dict[str, Any]],
    prerequisites: dict[str, list[str]] | None = None,
    available_time: float = 10.0,
    current_proficiencies: dict[str, str] | None = None,
) -> LearningPath:
    """Generate a personalized learning path from match diagnosis gaps.

    Args:
        match_gaps: List of skill gap dicts from match diagnosis, each with:
            - skill: str
            - importance: str (required|bonus)
            - gap_level: str (完全缺失|部分掌握|已掌握)
            - learning_path: list[str] (prerequisite chain)
        prerequisites: Optional extra prerequisite mappings from DB.
        available_time: Weekly hours available for learning (default: 10).
        current_proficiencies: Optional map of skill → current proficiency level.

    Returns:
        A LearningPath with topologically ordered skills, time estimates,
        and phase breakdown.
    """
    if not match_gaps:
        return LearningPath(skills=[], phases=[])

    current_proficiencies = current_proficiencies or {}

    # Step 1: Build skill list with time estimates
    skill_names = [g["skill"] for g in match_gaps]

    # Step 2: Load per-skill learning hours from Neo4j (best-effort)
    skill_hours_map = await _load_skill_hours_from_neo4j(set(skill_names))

    # Step 3: Build prerequisite graph (Neo4j → fallback → extras)
    prereq_graph = await build_prerequisite_graph(skill_names, prerequisites)

    # Step 4: Topological sort
    ordered_names = _topological_sort(prereq_graph)

    # Step 5: Build SkillNodes in topo order
    gap_map = {g["skill"]: g for g in match_gaps}
    skill_nodes: list[SkillNode] = []

    for name in ordered_names:
        gap = gap_map.get(name, {})
        gap_level = gap.get("gap_level", "完全缺失")
        importance = gap.get("importance", "required")
        current = current_proficiencies.get(name)
        target = gap.get("target_proficiency", DEFAULT_PROFICIENCY)

        hours = estimate_learning_time(
            skill=name,
            current_level=current,
            target_level=target,
            gap_level=gap_level,
            skill_hours_map=skill_hours_map,
        )

        node = SkillNode(
            name=name,
            importance=importance,
            gap_level=gap_level,
            current_proficiency=current,
            target_proficiency=target,
            estimated_hours=hours,
            prerequisites=prereq_graph.get(name, []),
            learning_path=gap.get("learning_path", []),
        )
        skill_nodes.append(node)

    # Assign order indices
    for i, node in enumerate(skill_nodes):
        node.order = i

    # Step 6: Calculate totals
    total_hours = sum(n.estimated_hours for n in skill_nodes if n.gap_level != GAP_LEVEL_MASTERED)
    total_weeks = ceil(total_hours / available_time) if available_time > 0 else 0

    # Step 6: Build phases
    phases = _build_phases(skill_nodes, available_time)

    path = LearningPath(
        skills=skill_nodes,
        total_hours=round(total_hours, 1),
        total_weeks=total_weeks,
        weekly_hours=available_time,
        phase_count=len(phases),
        phases=phases,
    )

    logger.info(
        "Generated learning path: {} skills, {} phases, {:.0f}h total (~{} weeks @ {:.0f}h/wk)",
        len(skill_nodes), len(phases), total_hours, total_weeks, available_time,
    )

    return path
