"""Tests for learning path engine."""
from __future__ import annotations

import pytest

from app.core.learning.path_engine import (
    PROFICIENCY_SCORE,
    LearningPath,
    SkillNode,
    _build_phases,
    _topological_sort,
    build_prerequisite_graph,
    estimate_learning_time,
)


class TestProficiencyScore:
    def test_known_levels(self):
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
    def test_empty_skills(self):
        graph = build_prerequisite_graph([])
        assert graph == {}

    def test_known_prerequisite(self):
        graph = build_prerequisite_graph(["Python", "NumPy"])
        assert "NumPy" in graph
        assert "Python" in graph
        assert graph["NumPy"] == ["Python"]

    def test_extra_prerequisites_override(self):
        graph = build_prerequisite_graph(
            ["Python", "Custom"],
            extra_prerequisites={"Custom": ["Python"]},
        )
        assert graph["Custom"] == ["Python"]

    def test_filters_unrelated_prerequisites(self):
        graph = build_prerequisite_graph(["Python"])
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
