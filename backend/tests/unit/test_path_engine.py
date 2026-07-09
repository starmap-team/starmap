"""Tests for learning path engine."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.learning.path_engine import (
    LearningPath,
    SkillNode,
    _build_phases,
    _load_prerequisites_from_neo4j,
    _load_skill_hours_from_neo4j,
    _tarjan_scc,
    _topological_sort,
    build_prerequisite_graph,
    estimate_learning_time,
    generate_learning_path,
)


def _async_result(items: list):
    """Return a mock Neo4j result object that supports `async for rec in result`."""
    class _Result:
        def __init__(self, data):
            self._data = data
            self._idx = 0

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._idx >= len(self._data):
                raise StopAsyncIteration
            item = self._data[self._idx]
            self._idx += 1
            return item

    return _Result(items)


class TestProficiencyScore:
    def test_known_levels(self):
        from app.core.matching.constants import PROFICIENCY_SCORE
        assert PROFICIENCY_SCORE["了解"] == 0.35
        assert PROFICIENCY_SCORE["熟悉"] == 0.65
        assert PROFICIENCY_SCORE["精通"] == 0.9


class TestSkillNode:
    def test_creation(self):
        node = SkillNode(name="Python", importance="required", gap_level="完全缺失")
        assert node.name == "Python"
        assert node.estimated_hours == 0.0
        assert node.prerequisites == []

    def test_with_all_fields(self):
        node = SkillNode(
            name="Pandas",
            importance="required",
            gap_level="完全缺失",
            estimated_hours=40.0,
            prerequisites=["Python", "NumPy"],
        )
        assert node.name == "Pandas"
        assert len(node.prerequisites) == 2


class TestLearningPath:
    def test_defaults(self):
        path = LearningPath(skills=[])
        assert path.total_hours == 0.0
        assert path.weekly_hours == 10.0
        assert path.phases == []


class TestEstimateLearningTime:
    def test_complete_gap(self):
        hours = estimate_learning_time("Python", gap_level="完全缺失")
        assert hours > 0

    def test_partial_gap(self):
        hours_partial = estimate_learning_time("Python", gap_level="部分掌握")
        hours_full = estimate_learning_time("Python", gap_level="完全缺失")
        assert hours_partial < hours_full

    def test_mastered(self):
        hours = estimate_learning_time("Python", gap_level="已掌握")
        assert hours > 0
        assert hours < 10


class TestBuildPrerequisiteGraph:
    @pytest.mark.asyncio
    async def test_empty_skills(self):
        graph = await build_prerequisite_graph([])
        assert graph == {}

    @pytest.mark.asyncio
    async def test_known_prerequisite(self):
        graph = await build_prerequisite_graph(["Python", "NumPy"])
        assert "NumPy" in graph
        assert "Python" in graph
        assert graph["NumPy"] == ["Python"]

    @pytest.mark.asyncio
    async def test_extra_prerequisites_override(self):
        graph = await build_prerequisite_graph(
            ["Python", "Custom"],
            extra_prerequisites={"Custom": ["Python"]},
        )
        assert graph["Custom"] == ["Python"]

    @pytest.mark.asyncio
    async def test_filters_unrelated_prerequisites(self):
        graph = await build_prerequisite_graph(["Python"])
        # Pandas has prereqs but is not in the list
        assert "Pandas" not in graph


class TestTopologicalSort:
    def test_simple_order(self):
        graph = {"A": [], "B": ["A"], "C": ["B"]}
        order = _topological_sort(graph)
        assert order.index("A") < order.index("B")
        assert order.index("B") < order.index("C")

    def test_empty_graph(self):
        assert _topological_sort({}) == []

    def test_single_node(self):
        assert _topological_sort({"A": []}) == ["A"]

    def test_no_dependencies(self):
        order = _topological_sort({"A": [], "B": []})
        assert len(order) == 2

    def test_diamond_dependency(self):
        graph = {"A": [], "B": ["A"], "C": ["A"], "D": ["B", "C"]}
        order = _topological_sort(graph)
        assert order.index("A") < order.index("B")
        assert order.index("A") < order.index("C")
        assert order.index("B") < order.index("D")
        assert order.index("C") < order.index("D")


class TestBuildPhases:
    def test_empty_order(self):
        phases = _build_phases([], 10.0)
        assert phases == []

    def test_single_skill(self):
        skills = [SkillNode(name="Python", importance="required", gap_level="完全缺失")]
        phases = _build_phases(skills, 10.0)
        assert len(phases) == 1
        assert phases[0]["phase"] == 1
        assert "Python" in phases[0]["skills"]

    def test_sequential_dependencies(self):
        skills = [
            SkillNode(name="A", importance="required", gap_level="完全缺失"),
            SkillNode(name="B", importance="required", gap_level="完全缺失", prerequisites=["A"]),
            SkillNode(name="C", importance="required", gap_level="完全缺失", prerequisites=["B"]),
        ]
        phases = _build_phases(skills, 10.0)
        assert len(phases) >= 1
        # Skills should be distributed across phases based on time budget
        all_skills = []
        for p in phases:
            all_skills.extend(p["skills"])
        assert "A" in all_skills
        assert "B" in all_skills
        assert "C" in all_skills

    def test_skips_mastered_skills(self):
        skills = [
            SkillNode(name="Python", importance="required", gap_level="已掌握"),
            SkillNode(name="NumPy", importance="required", gap_level="完全缺失"),
        ]
        phases = _build_phases(skills, 10.0)
        phase_skills = []
        for p in phases:
            phase_skills.extend(p["skills"])
        assert "Python" not in phase_skills
        assert "NumPy" in phase_skills


# ---------------------------------------------------------------------------
# Tests for generate_learning_path
# ---------------------------------------------------------------------------
class TestGenerateLearningPath:
    @pytest.mark.asyncio
    async def test_empty_gaps(self):
        """Empty gaps returns empty learning path."""
        path = await generate_learning_path([])
        assert path.skills == []
        assert path.total_hours == 0.0

    @pytest.mark.asyncio
    async def test_single_gap(self):
        """Single gap returns a learning path with one skill."""
        gaps = [
            {"skill": "Python", "importance": "required", "gap_level": "完全缺失", "learning_path": ["Python"]},
        ]
        path = await generate_learning_path(gaps)
        assert len(path.skills) == 1
        assert path.skills[0].name == "Python"
        assert path.skills[0].gap_level == "完全缺失"
        assert path.total_hours > 0

    @pytest.mark.asyncio
    async def test_multiple_gaps_with_prerequisites(self):
        """Multiple gaps with prerequisites are ordered correctly."""
        gaps = [
            {"skill": "Pandas", "importance": "required", "gap_level": "完全缺失", "learning_path": ["Python", "NumPy", "Pandas"]},
            {"skill": "Python", "importance": "required", "gap_level": "完全缺失", "learning_path": ["Python"]},
            {"skill": "NumPy", "importance": "required", "gap_level": "完全缺失", "learning_path": ["Python", "NumPy"]},
        ]
        path = await generate_learning_path(gaps)
        skill_names = [s.name for s in path.skills]
        assert "Python" in skill_names
        assert "NumPy" in skill_names
        assert "Pandas" in skill_names
        # Python should come before NumPy, NumPy before Pandas
        assert skill_names.index("Python") < skill_names.index("NumPy")
        assert skill_names.index("NumPy") < skill_names.index("Pandas")

    @pytest.mark.asyncio
    async def test_mastered_skills_excluded_from_hours(self):
        """Mastered skills don't contribute to total hours."""
        gaps = [
            {"skill": "Python", "importance": "required", "gap_level": "已掌握", "learning_path": ["Python"]},
            {"skill": "NumPy", "importance": "required", "gap_level": "完全缺失", "learning_path": ["Python", "NumPy"]},
        ]
        path = await generate_learning_path(gaps)
        # NumPy contributes hours, Python doesn't (已掌握)
        assert path.total_hours > 0
        assert path.skills[0].name == "Python"  # still in the list
        assert path.skills[0].gap_level == "已掌握"

    @pytest.mark.asyncio
    async def test_with_extra_prerequisites(self):
        """Extra prerequisites override fallback prerequisites."""
        gaps = [
            {"skill": "Custom", "importance": "required", "gap_level": "完全缺失", "learning_path": ["Custom"]},
            {"skill": "Python", "importance": "required", "gap_level": "完全缺失", "learning_path": ["Python"]},
        ]
        path = await generate_learning_path(gaps, prerequisites={"Custom": ["Python"]})
        skill_names = [s.name for s in path.skills]
        assert skill_names.index("Python") < skill_names.index("Custom")


# ---------------------------------------------------------------------------
# Neo4j loader tests (mock driver)
# ---------------------------------------------------------------------------
class TestLoadPrerequisitesFromNeo4j:
    @pytest.mark.asyncio
    async def test_no_driver_returns_empty(self):
        """When Neo4j driver is None, returns empty dict."""
        with patch("app.core.learning.path_engine._prereqs_cache", None):
            with patch("app.services.resources.resources.neo4j_driver", None):
                result = await _load_prerequisites_from_neo4j()
        assert result == {}

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """Returns cached data when TTL hasn't expired."""
        cached_data = {"Python": ["SQL"]}
        with patch("app.core.learning.path_engine._prereqs_cache", (time.monotonic(), cached_data)):
            result = await _load_prerequisites_from_neo4j()
        assert result == cached_data

    @pytest.mark.asyncio
    async def test_cache_expired_queries_neo4j(self):
        """Expired cache triggers a fresh Neo4j query."""
        old_ts = time.monotonic() - 9999  # expired
        # Mock the Neo4j session to return data
        mock_result = _async_result([
            {"src": "Pandas", "tgt": "Python"},
            {"src": "Pandas", "tgt": "NumPy"},
        ])
        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_driver = MagicMock()
        mock_driver.session = MagicMock(return_value=mock_session)

        with patch("app.core.learning.path_engine._prereqs_cache", (old_ts, {})):
            with patch("app.services.resources.resources.neo4j_driver", mock_driver):
                result = await _load_prerequisites_from_neo4j()
        assert result == {"Pandas": ["Python", "NumPy"]}

    @pytest.mark.asyncio
    async def test_neo4j_error_returns_empty(self):
        """Neo4j query failure returns empty dict gracefully."""
        mock_driver = MagicMock()
        mock_session = AsyncMock()
        mock_session.run = AsyncMock(side_effect=Exception("connection lost"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_driver.session = MagicMock(return_value=mock_session)

        with patch("app.core.learning.path_engine._prereqs_cache", None):
            with patch("app.services.resources.resources.neo4j_driver", mock_driver):
                result = await _load_prerequisites_from_neo4j()
        assert result == {}

    @pytest.mark.asyncio
    async def test_dedup_prerequisites(self):
        """Duplicate prerequisite edges are deduped."""
        mock_result = _async_result([
            {"src": "ML", "tgt": "Python"},
            {"src": "ML", "tgt": "Python"},  # duplicate
        ])
        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_driver = MagicMock()
        mock_driver.session = MagicMock(return_value=mock_session)

        with patch("app.core.learning.path_engine._prereqs_cache", None):
            with patch("app.services.resources.resources.neo4j_driver", mock_driver):
                result = await _load_prerequisites_from_neo4j()
        assert result == {"ML": ["Python"]}  # no duplicate


class TestLoadSkillHoursFromNeo4j:
    @pytest.mark.asyncio
    async def test_empty_skill_set(self):
        """Empty skill set returns empty dict without querying."""
        result = await _load_skill_hours_from_neo4j(set())
        assert result == {}

    @pytest.mark.asyncio
    async def test_no_driver_returns_empty(self):
        """When Neo4j driver is None, returns empty dict."""
        with patch("app.core.learning.path_engine._skill_hours_cache", None):
            with patch("app.services.resources.resources.neo4j_driver", None):
                result = await _load_skill_hours_from_neo4j({"Python"})
        assert result == {}

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """Returns cached data when TTL and skill set match."""
        cache_key = frozenset({"Python"})
        cached_data = {"Python": 30.0}
        with patch("app.core.learning.path_engine._skill_hours_cache", (time.monotonic(), cache_key, cached_data)):
            result = await _load_skill_hours_from_neo4j({"Python"})
        assert result == cached_data

    @pytest.mark.asyncio
    async def test_cache_expired_queries_neo4j(self):
        """Expired cache triggers a fresh Neo4j query."""
        old_ts = time.monotonic() - 9999
        mock_result = _async_result([
            {"name": "Python", "hours": 35.0},
            {"name": "SQL", "hours": None},  # should be skipped
        ])
        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_driver = MagicMock()
        mock_driver.session = MagicMock(return_value=mock_session)

        with patch("app.core.learning.path_engine._skill_hours_cache", (old_ts, frozenset(), {})):
            with patch("app.services.resources.resources.neo4j_driver", mock_driver):
                result = await _load_skill_hours_from_neo4j({"Python", "SQL"})
        assert result == {"Python": 35.0}  # SQL skipped (hours=None)

    @pytest.mark.asyncio
    async def test_neo4j_error_returns_empty(self):
        """Neo4j query failure returns empty dict gracefully."""
        mock_driver = MagicMock()
        mock_session = AsyncMock()
        mock_session.run = AsyncMock(side_effect=Exception("timeout"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_driver.session = MagicMock(return_value=mock_session)

        with patch("app.core.learning.path_engine._skill_hours_cache", None):
            with patch("app.services.resources.resources.neo4j_driver", mock_driver):
                result = await _load_skill_hours_from_neo4j({"Python"})
        assert result == {}


# ---------------------------------------------------------------------------
# estimate_learning_time — skill_hours_map branch
# ---------------------------------------------------------------------------
class TestEstimateLearningTimeSkillHoursMap:
    def test_skill_hours_map_overrides_base(self):
        """When skill_hours_map has the skill, it overrides gap-level base."""
        hours_map = {"Python": 50.0}
        hours = estimate_learning_time(
            "Python", gap_level="完全缺失", skill_hours_map=hours_map,
        )
        # base=50, current=了解(0.35), target=熟悉(0.65), gap=0.3, mult=0.8
        assert hours == round(50.0 * 0.8, 1)

    def test_skill_hours_map_miss_falls_back(self):
        """When skill not in skill_hours_map, falls back to gap-level base."""
        hours = estimate_learning_time(
            "Rust", gap_level="完全缺失", skill_hours_map={"Python": 50.0},
        )
        # base=40 (完全缺失), current=了解(0.35), target=熟悉(0.65), mult=0.8
        assert hours == round(40.0 * 0.8, 1)

    def test_proficiency_gap_zero(self):
        """When current >= target, multiplier is 0.5 (minimum)."""
        hours = estimate_learning_time(
            "Python", current_level="精通", target_level="熟悉",
            gap_level="完全缺失",
        )
        # gap = max(0, 0.65-0.9) = 0, mult = 0.5
        assert hours == round(40.0 * 0.5, 1)

    def test_unknown_gap_level_defaults_40(self):
        """Unknown gap_level defaults to 40.0 base hours."""
        hours = estimate_learning_time("X", gap_level="未知")
        # base=40.0, current=了解(0.35), target=熟悉(0.65), mult=0.8
        assert hours == round(40.0 * 0.8, 1)


# ---------------------------------------------------------------------------
# Cycle detection & Tarjan SCC
# ---------------------------------------------------------------------------
class TestTopologicalSortCycles:
    def test_simple_cycle(self):
        """Two-node cycle is compressed and still returns all nodes."""
        graph = {"A": ["B"], "B": ["A"]}
        order = _topological_sort(graph)
        assert set(order) == {"A", "B"}

    def test_three_node_cycle(self):
        """Three-node cycle returns all nodes."""
        graph = {"A": ["B"], "B": ["C"], "C": ["A"]}
        order = _topological_sort(graph)
        assert set(order) == {"A", "B", "C"}

    def test_cycle_with_dangling(self):
        """Cycle with a non-cyclic node: non-cyclic node comes first."""
        graph = {"A": [], "B": ["C"], "C": ["B"]}  # B↔C cycle, A independent
        order = _topological_sort(graph)
        assert set(order) == {"A", "B", "C"}
        # A has no deps, should come before the cycle group
        assert order.index("A") < order.index("B") or order.index("A") < order.index("C")

    def test_two_cycles(self):
        """Two independent cycles both appear in output."""
        graph = {
            "A": ["B"], "B": ["A"],  # cycle 1
            "C": ["D"], "D": ["C"],  # cycle 2
        }
        order = _topological_sort(graph)
        assert set(order) == {"A", "B", "C", "D"}

    def test_cycle_depends_on_acyclic(self):
        """Cycle that depends on an acyclic node: acyclic node comes first."""
        # A→B→C→B (cycle B↔C), A is acyclic root
        graph = {"A": [], "B": ["A", "C"], "C": ["B"]}
        order = _topological_sort(graph)
        assert set(order) == {"A", "B", "C"}
        # A must come before B and C (A is a prereq of B)
        assert order.index("A") < order.index("B")
        assert order.index("A") < order.index("C")

    def test_two_sccs_with_cross_edge(self):
        """Two SCCs where one depends on the other: dependency SCC comes first."""
        # Cycle1: A↔B, Cycle2: C↔D, and C depends on A (cross-SCC edge)
        graph = {"A": ["B"], "B": ["A"], "C": ["D", "A"], "D": ["C"]}
        order = _topological_sort(graph)
        assert set(order) == {"A", "B", "C", "D"}
        # SCC {A,B} must come before SCC {C,D}
        ab = min(order.index("A"), order.index("B"))
        cd = min(order.index("C"), order.index("D"))
        assert ab < cd


class TestTarjanSCC:
    def test_no_cycles(self):
        """Acyclic graph: each node is its own SCC."""
        graph = {"A": ["B"], "B": ["C"], "C": []}
        sccs = _tarjan_scc(graph)
        # Each node in its own SCC
        assert len(sccs) == 3
        for scc in sccs:
            assert len(scc) == 1

    def test_two_node_cycle(self):
        """Two-node cycle forms one SCC."""
        graph = {"A": ["B"], "B": ["A"]}
        sccs = _tarjan_scc(graph)
        merged = [set(s) for s in sccs]
        assert {"A", "B"} in merged

    def test_self_loop(self):
        """Self-loop forms a single-node SCC."""
        graph = {"A": ["A"]}
        sccs = _tarjan_scc(graph)
        assert len(sccs) == 1
        assert set(sccs[0]) == {"A"}

    def test_disconnected_graph(self):
        """Disconnected nodes each form their own SCC."""
        graph = {"A": [], "B": [], "C": []}
        sccs = _tarjan_scc(graph)
        assert len(sccs) == 3

    def test_prereq_outside_graph_ignored(self):
        """Prerequisites referencing nodes not in the graph are skipped."""
        graph = {"A": ["Z"], "B": []}  # Z not in graph keys
        sccs = _tarjan_scc(graph)
        assert len(sccs) == 2  # A and B each their own SCC


# ---------------------------------------------------------------------------
# _build_phases edge cases
# ---------------------------------------------------------------------------
class TestBuildPhasesEdgeCases:
    def test_all_mastered(self):
        """All mastered skills produce no phases."""
        skills = [
            SkillNode(name="A", importance="required", gap_level="已掌握"),
            SkillNode(name="B", importance="required", gap_level="已掌握"),
        ]
        assert _build_phases(skills, 10.0) == []

    def test_phase_budget_split(self):
        """Skills exceeding budget are split into multiple phases."""
        skills = [
            SkillNode(name="A", importance="required", gap_level="完全缺失", estimated_hours=15.0),
            SkillNode(name="B", importance="required", gap_level="完全缺失", estimated_hours=15.0),
        ]
        phases = _build_phases(skills, 10.0)  # budget = 20h per phase
        # 15+15=30 > 20, so should split
        assert len(phases) == 2

    def test_phase_fields(self):
        """Each phase dict has required keys."""
        skills = [SkillNode(name="X", importance="required", gap_level="部分掌握", estimated_hours=5.0)]
        phases = _build_phases(skills, 10.0)
        assert len(phases) == 1
        p = phases[0]
        assert "phase" in p
        assert "skills" in p
        assert "estimated_hours" in p
        assert "estimated_weeks" in p


# ---------------------------------------------------------------------------
# generate_learning_path — additional edge cases
# ---------------------------------------------------------------------------
class TestGenerateLearningPathEdgeCases:
    @pytest.mark.asyncio
    async def test_available_time_zero(self):
        """Zero available time: total_weeks = 0 (ceil guard)."""
        gaps = [
            {"skill": "Python", "importance": "required", "gap_level": "完全缺失", "learning_path": ["Python"]},
        ]
        path = await generate_learning_path(gaps, available_time=0)
        assert path.total_weeks == 0

    @pytest.mark.asyncio
    async def test_current_proficiencies_applied(self):
        """Current proficiencies are passed through to SkillNode."""
        gaps = [
            {"skill": "Python", "importance": "required", "gap_level": "部分掌握", "learning_path": ["Python"]},
        ]
        path = await generate_learning_path(gaps, current_proficiencies={"Python": "熟悉"})
        assert path.skills[0].current_proficiency == "熟悉"

    @pytest.mark.asyncio
    async def test_skill_order_assigned(self):
        """Each SkillNode gets an order index."""
        gaps = [
            {"skill": "Python", "importance": "required", "gap_level": "完全缺失", "learning_path": ["Python"]},
            {"skill": "NumPy", "importance": "required", "gap_level": "完全缺失", "learning_path": ["Python", "NumPy"]},
        ]
        path = await generate_learning_path(gaps)
        orders = [s.order for s in path.skills]
        assert orders == sorted(orders)  # monotonically increasing

    @pytest.mark.asyncio
    async def test_phase_count_matches_phases_list(self):
        """phase_count equals len(phases)."""
        gaps = [
            {"skill": "Python", "importance": "required", "gap_level": "完全缺失", "learning_path": ["Python"]},
        ]
        path = await generate_learning_path(gaps)
        assert path.phase_count == len(path.phases)

    @pytest.mark.asyncio
    async def test_with_skill_hours_map_from_neo4j(self):
        """When Neo4j returns skill hours, they override gap-level base."""
        gaps = [
            {"skill": "Python", "importance": "required", "gap_level": "完全缺失", "learning_path": ["Python"]},
        ]
        # Mock _load_skill_hours_from_neo4j to return custom hours
        with patch("app.core.learning.path_engine._load_skill_hours_from_neo4j", AsyncMock(return_value={"Python": 60.0})):
            path = await generate_learning_path(gaps)
        # base=60, current=了解(0.35), target=熟悉(0.65), mult=0.8 → 48.0
        assert path.skills[0].estimated_hours == round(60.0 * 0.8, 1)
