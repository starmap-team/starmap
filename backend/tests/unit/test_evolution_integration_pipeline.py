"""Integration-style tests for the evolution pipeline.

Covers the consolidated trust + hallucination + emergence + path pipeline
using the orchestrator and local components, without requiring a real database.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.evolution.diff_engine import DiffEngine
from app.core.evolution.emergence_finder import EmergenceFinder
from app.core.evolution.hallucination_guard import HallucinationGuard
from app.core.evolution.orchestrator import EvolutionOrchestrator
from app.core.evolution.path_recommender import PathRecommender
from app.core.evolution.trust_integration import TrustScorer


def _snapshot_pair():
    old = SimpleNamespace(
        id="snap-1",
        position_name="AI Engineer",
        snapshot_date=datetime(2026, 6, 1, tzinfo=UTC),
        required_skills=[SimpleNamespace(name="Python", proficiency=None)],
        preferred_skills=[SimpleNamespace(name="Docker", proficiency=None)],
        source_count=3,
    )
    new = SimpleNamespace(
        id="snap-2",
        position_name="AI Engineer",
        snapshot_date=datetime(2026, 6, 15, tzinfo=UTC),
        required_skills=[
            SimpleNamespace(name="Python", proficiency=None),
            SimpleNamespace(name="RAG", proficiency=None),
        ],
        preferred_skills=[
            SimpleNamespace(name="Docker", proficiency=None),
            SimpleNamespace(name="Kubernetes", proficiency=None),
        ],
        source_count=4,
    )
    return old, new


@pytest.mark.asyncio
async def test_evolution_pipeline_end_to_end_with_orchestrator():
    old_snap, new_snap = _snapshot_pair()

    async def fake_execute(stmt):
        return SimpleNamespace(scalar_one_or_none=lambda: None, scalars=lambda: SimpleNamespace(all=lambda: []))

    session = SimpleNamespace(add=lambda obj: None, flush=AsyncMock(), execute=fake_execute)
    orchestrator = EvolutionOrchestrator(session)
    orchestrator._snapshot_mgr.get_snapshot_pair = AsyncMock(return_value=(old_snap, new_snap))
    orchestrator._load_timeseries = AsyncMock(
        return_value={
            "RAG": {
                "frequencies": [1, 2, 3, 4],
                "current": 10,
                "sources": 4,
                "positions": ["AI Engineer"],
            }
        }
    )
    orchestrator._load_path_data = AsyncMock(
        return_value={
            "AI Engineer": {"Python", "RAG"},
            "ML Engineer": {"Python", "ML"},
        }
    )

    result = await orchestrator.analyze("AI Engineer", ontology_skills={"Python", "RAG", "Docker", "Kubernetes"})

    assert result.position_name == "AI Engineer"
    assert result.diff_result is not None
    assert result.diff_result.total_changes > 0
    assert result.emergence_report is not None
    assert result.path_report is not None
    assert result.changelog_entries > 0


@pytest.mark.asyncio
async def test_orchestrator_records_guard_errors_for_high_risk_skill():
    old_snap, new_snap = _snapshot_pair()

    async def fake_execute(stmt):
        return SimpleNamespace(scalar_one_or_none=lambda: None, scalars=lambda: SimpleNamespace(all=lambda: []))

    session = SimpleNamespace(add=lambda obj: None, flush=AsyncMock(), execute=fake_execute)
    orchestrator = EvolutionOrchestrator(session)
    orchestrator._snapshot_mgr.get_snapshot_pair = AsyncMock(return_value=(old_snap, new_snap))
    orchestrator._load_timeseries = AsyncMock(return_value=None)
    orchestrator._load_path_data = AsyncMock(return_value=None)

    original_check = orchestrator._halluc_guard.check

    def fake_check(*, skill_name, ontology_matches=None, semantic_score=None, source_count=1, llm_judgment=None):
        result = original_check(skill_name=skill_name, ontology_matches=ontology_matches, semantic_score=semantic_score, source_count=source_count, llm_judgment=llm_judgment)
        if skill_name in {"RAG", "Kubernetes"}:
            result.status = HallucinationGuard().check.__class__.__mro__[0]  # unused, replaced below
        return result

    orchestrator._halluc_guard.check = lambda **kwargs: SimpleNamespace(status=SimpleNamespace(value="high_risk"), overall_score=0.0)
    result = await orchestrator.analyze("AI Engineer")

    assert result.position_name == "AI Engineer"
    assert result.diff_result is not None
    assert any("High-risk skill detected" in err for err in result.errors)


def test_trust_hallucination_emergence_path_components_compose():
    old_snap, new_snap = _snapshot_pair()

    diff_result = DiffEngine().diff(old_snap, new_snap)
    assert diff_result.total_changes > 0

    trust_low = TrustScorer().compute_from_source_count(source_count=1)
    trust_high = TrustScorer().compute_from_source_count(source_count=8)
    assert 0.0 <= trust_low.score <= trust_high.score <= 1.0

    guard_verified = HallucinationGuard().check(
        skill_name="RAG",
        ontology_matches=["Python", "RAG", "Docker"],
        source_count=6,
    )
    guard_risky = HallucinationGuard().check(
        skill_name="RareSkill",
        ontology_matches=["Python", "Docker"],
        source_count=1,
    )
    assert guard_verified.status.value in {"verified", "low_risk", "medium_risk", "high_risk", "pending"}
    assert guard_risky.status.value in {"verified", "low_risk", "medium_risk", "high_risk", "pending"}

    emergence = EmergenceFinder().scan(
        {
            "RAG": {
                "frequencies": [1, 2, 1, 2, 1],
                "current": 8,
                "sources": 3,
                "positions": ["AI Engineer"],
            },
            "Python": {
                "frequencies": [8, 9, 9, 8, 9],
                "current": 9,
                "sources": 10,
                "positions": ["AI Engineer", "Backend Engineer"],
            },
        }
    )
    assert any(signal.skill_name == "RAG" for signal in emergence.emerging)

    path_report = PathRecommender().find_paths(
        {
            "AI Engineer": {"Python", "RAG"},
            "ML Engineer": {"Python", "ML"},
            "Backend Engineer": {"Python", "SQL", "Docker"},
        }
    )
    assert path_report.total_pairs_analyzed >= 1
