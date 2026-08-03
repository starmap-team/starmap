"""PathRecommender unit tests — pure Jaccard + top-K filtering."""
from __future__ import annotations

import pytest

from app.core.evolution.path_recommender import (
    DEFAULT_MIN_SIMILARITY,
    DEFAULT_TOP_K,
    MAX_POSITIONS,
    PathRecommender,
)


@pytest.fixture
def recommender():
    return PathRecommender()


class TestComputePairs:
    def test_identical_skill_sets_similarity_one(self, recommender):
        ps = {
            "A": {"Python", "Go", "Rust"},
            "B": {"Python", "Go", "Rust"},
        }
        pairs = recommender._compute_pairs(ps)
        assert len(pairs) == 2  # A→B and B→A
        assert all(p.similarity == 1.0 for p in pairs)

    def test_no_overlap_filtered(self, recommender):
        ps = {
            "Frontend": {"Vue", "React", "CSS"},
            "Backend": {"Python", "Go", "SQL"},
        }
        pairs = recommender._compute_pairs(ps)
        assert pairs == []

    def test_partial_overlap_jaccard_value(self, recommender):
        # overlap=2 (Python, SQL), union=5 → 0.4
        ps = {
            "Backend": {"Python", "SQL", "Linux"},
            "FullStack": {"Python", "SQL", "JS", "CSS"},
        }
        pairs = recommender._compute_pairs(ps)
        assert len(pairs) == 2
        assert pairs[0].similarity == pytest.approx(0.4, abs=1e-3)
        assert "Python" in pairs[0].skill_overlap
        # key_gaps for Backend→FullStack = skills target has but source doesn't
        backend_to_full = next(p for p in pairs if p.source_position == "Backend")
        assert set(backend_to_full.key_gaps) == {"JS", "CSS"}

    def test_min_similarity_threshold(self, recommender):
        # overlap=1, union=5 → 0.2 < default 0.3 → filtered
        ps = {
            "A": {"Python", "Go", "Rust", "Linux", "Docker"},
            "B": {"Python", "Vue", "React", "CSS", "HTML"},
        }
        pairs = recommender._compute_pairs(ps)
        assert pairs == []


class TestConfiguration:
    def test_default_constants(self):
        assert DEFAULT_MIN_SIMILARITY == 0.3
        assert DEFAULT_TOP_K == 50
        assert MAX_POSITIONS == 500

    def test_custom_thresholds_respected(self):
        r = PathRecommender(min_similarity=0.1, top_k=5)
        assert r.min_similarity == 0.1
        assert r.top_k == 5
        # Lower threshold → previously-filtered pair now included
        ps = {
            "A": {"Python", "Go", "Rust", "Linux", "Docker"},
            "B": {"Python", "Vue", "React", "CSS", "HTML"},
        }
        assert len(r._compute_pairs(ps)) == 2  # passes at 0.1 threshold


class TestSymmetry:
    def test_both_directions_emitted(self, recommender):
        ps = {
            "X": {"Python", "SQL"},
            "Y": {"Python", "SQL", "Docker"},
        }
        pairs = recommender._compute_pairs(ps)
        directions = {(p.source_position, p.target_position) for p in pairs}
        assert ("X", "Y") in directions
        assert ("Y", "X") in directions
        # key_gaps differ by direction
        x_to_y = next(p for p in pairs if p.source_position == "X")
        assert x_to_y.key_gaps == ["Docker"]
        y_to_x = next(p for p in pairs if p.source_position == "Y")
        assert y_to_x.key_gaps == []
