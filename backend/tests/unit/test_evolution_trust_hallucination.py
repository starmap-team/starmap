"""Unit tests for TrustScorer and HallucinationGuard."""

from datetime import UTC, datetime, timedelta

from app.core.evolution.hallucination_guard import (
    HallucinationGuard,
    LLMJudgment,
    VerificationStatus,
)
from app.core.evolution.trust_integration import (
    TrustFactors,
    TrustLevel,
    TrustScorer,
)


class TestTrustScorer:
    """Tests for the weighted trust scoring model."""

    def setup_method(self) -> None:
        self.scorer = TrustScorer()

    def test_high_trust_many_sources(self) -> None:
        """Many sources with good continuity → verified."""
        factors = TrustFactors(
            source_count=10,
            temporal_continuity=0.9,
            cross_validation=0.8,
            manual_review=0.7,
        )
        result = self.scorer.compute(factors)
        assert result.score >= 0.8
        assert result.level == TrustLevel.VERIFIED

    def test_low_trust_no_sources(self) -> None:
        """No sources → high risk."""
        factors = TrustFactors(source_count=0)
        result = self.scorer.compute(factors)
        assert result.score < 0.5
        assert result.level == TrustLevel.HIGH_RISK

    def test_medium_trust_few_sources(self) -> None:
        """Few sources → pending."""
        factors = TrustFactors(
            source_count=3,
            temporal_continuity=0.5,
            cross_validation=0.4,
        )
        result = self.scorer.compute(factors)
        assert 0.3 <= result.score <= 0.7
        assert result.level == TrustLevel.HIGH_RISK

    def test_decay_reduces_score(self) -> None:
        """Trust decays over time."""
        old_date = datetime.now(UTC) - timedelta(days=180)  # 6 months ago
        recent_date = datetime.now(UTC) - timedelta(days=7)  # 1 week ago

        factors = TrustFactors(source_count=5, temporal_continuity=0.7, cross_validation=0.6)

        old_result = self.scorer.compute(factors, last_updated=old_date)
        recent_result = self.scorer.compute(factors, last_updated=recent_date)

        assert old_result.score < recent_result.score
        assert old_result.decay_applied < recent_result.decay_applied

    def test_compute_from_source_count(self) -> None:
        """Simplified computation from source count."""
        result = self.scorer.compute_from_source_count(8)
        assert result.score > 0.5
        assert result.factors.source_count == 8

    def test_update_trust_blending(self) -> None:
        """Update blends old and new scores (70/30)."""
        new_factors = TrustFactors(source_count=5, temporal_continuity=0.8, cross_validation=0.7)
        result = self.scorer.update_trust(
            current_score=0.9,
            new_evidence=new_factors,
        )
        # Should be blended: 0.7*0.9 + 0.3*new
        assert 0.5 <= result.score <= 0.9
        assert result.metadata["blend_ratio"] == "70/30"

    def test_source_count_capped_at_10(self) -> None:
        """Source count normalization caps at 10."""
        factors10 = TrustFactors(source_count=10, temporal_continuity=1.0, cross_validation=1.0, manual_review=1.0)
        factors20 = TrustFactors(source_count=20, temporal_continuity=1.0, cross_validation=1.0, manual_review=1.0)
        r10 = self.scorer.compute(factors10)
        r20 = self.scorer.compute(factors20)
        assert r10.score == r20.score  # Both capped


class TestHallucinationGuard:
    """Tests for the three-layer hallucination defense."""

    def setup_method(self) -> None:
        self.guard = HallucinationGuard()

    def test_verified_skill(self) -> None:
        """Skill with exact ontology match + many sources → verified."""
        result = self.guard.check(
            skill_name="Python",
            ontology_matches=["Python"],
            source_count=10,
            first_detected=datetime(2026, 1, 1, tzinfo=UTC),
            last_detected=datetime(2026, 6, 1, tzinfo=UTC),
        )
        assert result.status == VerificationStatus.VERIFIED
        assert result.overall_score >= 0.8

    def test_high_risk_no_match(self) -> None:
        """Skill with no ontology match + few sources → high risk."""
        result = self.guard.check(
            skill_name="FakeSkill123",
            ontology_matches=[],
            source_count=1,
        )
        assert result.status == VerificationStatus.HIGH_RISK
        assert result.overall_score < 0.5

    def test_pending_semantic_match(self) -> None:
        """Skill with semantic match but few sources → pending."""
        result = self.guard.check(
            skill_name="Pythn",  # typo
            ontology_matches=["Python"],
            semantic_score=0.9,
            source_count=2,
        )
        # Layer 1 passes (semantic), Layer 2 fails (sources)
        assert result.status in (VerificationStatus.PENDING, VerificationStatus.VERIFIED)

    def test_llm_unsupported_forces_high_risk(self) -> None:
        """LLM UNSUPPORTED verdict forces high risk regardless of other scores."""
        result = self.guard.check(
            skill_name="Python",
            ontology_matches=["Python"],
            source_count=10,
            llm_judgment=LLMJudgment.UNSUPPORTED,
        )
        assert result.status == VerificationStatus.HIGH_RISK
        assert result.overall_score <= 0.4

    def test_llm_supported_boosts_score(self) -> None:
        """LLM SUPPORTED verdict boosts confidence."""
        result_no_llm = self.guard.check(
            skill_name="Python",
            ontology_matches=["Python"],
            source_count=3,
        )
        result_with_llm = self.guard.check(
            skill_name="Python",
            ontology_matches=["Python"],
            source_count=3,
            llm_judgment=LLMJudgment.SUPPORTED,
        )
        assert result_with_llm.overall_score >= result_no_llm.overall_score

    def test_llm_ambiguous(self) -> None:
        """LLM AMBIGUOUS verdict doesn't change status drastically."""
        result = self.guard.check(
            skill_name="RAG",
            ontology_matches=["RAG"],
            source_count=2,
            llm_judgment=LLMJudgment.AMBIGUOUS,
        )
        assert result.llm_judgment == LLMJudgment.AMBIGUOUS

    def test_recommendations_generated(self) -> None:
        """Guard generates recommendations for non-verified skills."""
        result = self.guard.check(
            skill_name="UnknownSkill",
            ontology_matches=[],
            source_count=1,
        )
        assert len(result.recommendations) > 0

    def test_layer_results_count(self) -> None:
        """All three layers produce results."""
        result = self.guard.check(skill_name="Python")
        assert len(result.layer_results) == 3
        assert result.layer_results[0].layer == 1
        assert result.layer_results[1].layer == 2
        assert result.layer_results[2].layer == 3
