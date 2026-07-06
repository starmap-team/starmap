"""Tests for trust integration and path recommender edge cases."""
from __future__ import annotations

from datetime import datetime

from app.core.evolution.path_recommender import PathRecommender
from app.core.evolution.trust_integration import TrustFactors, TrustScorer


class TestTrustIntegration:
    """Test edge cases in TrustScorer."""

    def test_score_without_tzinfo(self):
        """Test that a datetime without tzinfo gets converted."""
        scorer = TrustScorer()
        factors = TrustFactors(
            source_count=10,
            temporal_continuity=0.8,
            cross_validation=0.7,
            manual_review=0.0,
        )
        # last_updated without tzinfo
        result = scorer.compute(
            factors,
            last_updated=datetime(2026, 1, 1),  # no tzinfo
        )
        assert result.score >= 0

    def test_score_with_none_last_updated(self):
        """Test that None last_updated doesn't cause issues."""
        scorer = TrustScorer()
        factors = TrustFactors(
            source_count=5,
            temporal_continuity=0.5,
            cross_validation=0.5,
            manual_review=0.0,
        )
        result = scorer.compute(factors, last_updated=None)
        assert 0 <= result.score <= 1

    def test_classify_edge_cases(self):
        """Test the trust level classification."""
        scorer = TrustScorer()
        # Test with various factor combinations
        high = scorer.compute(TrustFactors(source_count=100, temporal_continuity=0.9, cross_validation=0.9, manual_review=1.0))
        assert high.score > 0.5

        low = scorer.compute(TrustFactors(source_count=0, temporal_continuity=0.0, cross_validation=0.0, manual_review=0.0))
        assert low.score <= 0.5


class TestPathRecommender:
    def test_compute_similarity_empty(self):
        """Test similarity computation with empty sets."""
        recommender = PathRecommender()
        similarity, overlap = recommender.compute_similarity(set(), set())
        assert similarity == 0.0
        assert overlap == []

    def test_compute_similarity_identical(self):
        recommender = PathRecommender()
        similarity, overlap = recommender.compute_similarity({"Python"}, {"Python"})
        assert similarity == 1.0
        assert "Python" in overlap

    def test_compute_similarity_no_overlap(self):
        recommender = PathRecommender()
        similarity, _ = recommender.compute_similarity({"Python"}, {"Java"})
        assert similarity == 0.0

    def test_compute_similarity_partial(self):
        recommender = PathRecommender()
        similarity, overlap = recommender.compute_similarity({"Python", "SQL"}, {"Python", "Java"})
        assert 0 < similarity < 1.0
        assert "Python" in overlap

    def test_find_paths_with_low_evidence(self):
        """Test that paths with evidence below MIN_EVIDENCE are filtered out."""
        recommender = PathRecommender()
        # Same skill sets -> similarity = 0.75 (above MIN_SIMILARITY=0.6)
        skills = {
            "Junior Dev": {"Python", "SQL", "Docker"},
            "Senior Dev": {"Python", "SQL", "Docker", "Kubernetes"},
        }
        # Set evidence for BOTH directions below threshold
        report = recommender.find_paths(
            skills,
            evidence_counts={
                "Junior Dev->Senior Dev": 0,
                "Senior Dev->Junior Dev": 0,
            },
        )
        # With 0 evidence and MIN_EVIDENCE=1, all paths should be filtered
        assert len(report.paths) == 0

    def test_find_paths_with_sufficient_evidence(self):
        """Test paths are discovered when evidence threshold is met."""
        recommender = PathRecommender()
        skills = {
            "Junior Dev": {"Python", "SQL", "Docker"},
            "Senior Dev": {"Python", "SQL", "Docker", "Kubernetes"},
        }
        report = recommender.find_paths(
            skills,
            evidence_counts={
                "Junior Dev->Senior Dev": 3,
                "Senior Dev->Junior Dev": 3,
            },
        )
        # With enough evidence and good similarity, paths should be found
        assert len(report.paths) > 0
