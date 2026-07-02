"""Personalized learning path generation engine.

Builds ordered learning paths from match gap analysis by:
1. Constructing a prerequisite DAG from skill dependency data
2. Topologically sorting skills respecting prerequisite order
3. Estimating learning time per skill based on current/target proficiency
4. Allocating available weekly hours across the path
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from math import ceil
from typing import Any

from loguru import logger

# Proficiency level → numeric score (shared with match_service)
PROFICIENCY_SCORE: dict[str, float] = {"了解": 0.35, "熟悉": 0.65, "精通": 0.9}

# Base learning hours per skill at different gap levels
_BASE_HOURS: dict[str, float] = {
    "完全缺失": 40.0,
    "部分掌握": 20.0,
    "已掌握": 2.0,
}

# Default prerequisite relationships (same source as match_service.PREREQUISITE_MAP)
DEFAULT_PREREQUISITES: dict[str, list[str]] = {
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
    target_level: str = "熟悉",
    gap_level: str = "完全缺失",
) -> float:
    """Estimate learning hours for a single skill.

    Args:
        skill: Skill name.
        current_level: User's current proficiency (了解/熟悉/精通).
        target_level: Target proficiency level.
        gap_level: Gap level from match diagnosis.

    Returns:
        Estimated learning hours.
    """
    base = _BASE_HOURS.get(gap_level, 40.0)

    # Adjust based on proficiency gap
    current_score = PROFICIENCY_SCORE.get(current_level or "了解", 0.0)
    target_score = PROFICIENCY_SCORE.get(target_level, 0.65)
    proficiency_gap = max(0.0, target_score - current_score)

    # Scale hours by proficiency gap (0-1 range → 0.5x-1.5x multiplier)
    multiplier = 0.5 + proficiency_gap
    return round(base * multiplier, 1)


def build_prerequisite_graph(
    skills: list[str],
    extra_prerequisites: dict[str, list[str]] | None = None,
) -> dict[str, list[str]]:
    """Build a prerequisite DAG for the given skills.

    Combines default prerequisites with any DB-loaded extras,
    then filters to only include edges relevant to the given skill set.

    Args:
        skills: List of skill names to include in the graph.
        extra_prerequisites: Additional prerequisite mappings (e.g., from DB).

    Returns:
        Dict mapping each skill to its list of prerequisites (filtered to
        only include skills present in the input set).
    """
    skill_set = set(skills)

    # Merge prerequisite sources (extra takes precedence)
    all_prereqs: dict[str, list[str]] = dict(DEFAULT_PREREQUISITES)
    if extra_prerequisites:
        for skill, prereqs in extra_prerequisites.items():
            all_prereqs[skill] = prereqs

    graph: dict[str, list[str]] = {}
    for skill in skills:
        prereqs = all_prereqs.get(skill, [])
        # Only keep prerequisites that are in our skill set
        filtered = [p for p in prereqs if p in skill_set]
        graph[skill] = filtered

    return graph


def _topological_sort(graph: dict[str, list[str]]) -> list[str]:
    """Topological sort of the prerequisite DAG.

    Returns skills in learning order (prerequisites first).
    Raises ValueError if the graph contains cycles.
    """
    # Compute in-degrees
    in_degree: dict[str, int] = {skill: 0 for skill in graph}
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

    if len(order) != len(graph):
        logger.warning("Cycle detected in prerequisite graph — using fallback order")
        # Fallback: return all skills in original order
        return list(graph.keys())

    return order


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
        if skill_node.gap_level == "已掌握":
            continue

        if current_hours + skill_node.estimated_hours > phase_hours_budget and current_phase:
            phases.append({
                "phase": len(phases) + 1,
                "skills": [s.name for s in current_phase],
                "estimated_hours": round(current_hours, 1),
                "estimated_weeks": round(current_hours / weekly_hours, 1),
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
            "estimated_weeks": round(current_hours / weekly_hours, 1),
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

    # Step 2: Build prerequisite graph
    prereq_graph = build_prerequisite_graph(skill_names, prerequisites)

    # Step 3: Topological sort
    ordered_names = _topological_sort(prereq_graph)

    # Step 4: Build SkillNodes in topo order
    gap_map = {g["skill"]: g for g in match_gaps}
    skill_nodes: list[SkillNode] = []

    for name in ordered_names:
        gap = gap_map.get(name, {})
        gap_level = gap.get("gap_level", "完全缺失")
        importance = gap.get("importance", "required")
        current = current_proficiencies.get(name)
        target = gap.get("target_proficiency", "熟悉")

        hours = estimate_learning_time(
            skill=name,
            current_level=current,
            target_level=target,
            gap_level=gap_level,
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

    # Step 5: Calculate totals
    total_hours = sum(n.estimated_hours for n in skill_nodes if n.gap_level != "已掌握")
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
