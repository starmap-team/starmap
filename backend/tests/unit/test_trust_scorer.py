"""TrustScorer unit tests — boundary values + factor weighting."""
from __future__ import annotations

import pytest

from app.core.evolution.diff_engine import ChangeType, EvolutionChange
from app.core.evolution.trust_scorer import TrustScorer, WEIGHT_SOURCE, WEIGHT_STABILITY, WEIGHT_TYPE


@pytest.fixture
def scorer():
    return TrustScorer()


def _change(ct: ChangeType, old_n: int = 0, new_n: int = 0) -> EvolutionChange:
    return EvolutionChange(
        skill_name="X",
        change_type=ct,
        old_proficiency=None,
        new_proficiency=None,
        old_requirement="required",
        new_requirement="required",
        mention_count_old=old_n,
        mention_count_new=new_n,
    )


class TestClamping:
    def test_zero_source_returns_low_score(self, scorer):
        trust, conf = scorer.score(_change(ChangeType.ADDED_REQUIRED, new_n=0), source_count=0)
        # With 0 sources and 0 new mentions, both factors collapse but type_factor=1.0
        # adds WEIGHT_TYPE * 1.0 = 0.2 → trust floor at 0.2
        assert 0.0 <= trust <= 1.0
        assert trust >= WEIGHT_TYPE  # type_factor alone

    def test_score_always_in_unit_interval(self, scorer):
        for ct in ChangeType:
            for source_count in (0, 1, 3, 10, 100):
                trust, conf = scorer.score(_change(ct, old_n=5, new_n=5), source_count)
                assert 0.0 <= trust <= 1.0, f"{ct.value} src={source_count} trust={trust}"
                assert 0.0 <= conf <= 1.0


class TestSourceFactor:
    def test_more_sources_higher_trust(self, scorer):
        change = _change(ChangeType.ADDED_REQUIRED, new_n=10)
        t1, _ = scorer.score(change, source_count=1)
        t5, _ = scorer.score(change, source_count=5)
        t10, _ = scorer.score(change, source_count=10)
        assert t1 < t5 < t10

    def test_saturation_at_10_sources(self, scorer):
        change = _change(ChangeType.ADDED_REQUIRED, new_n=10)
        t10, _ = scorer.score(change, source_count=10)
        t100, _ = scorer.score(change, source_count=100)
        # Should not exceed 1.0 even with absurd source counts
        assert t10 == t100 == 1.0


class TestTypeFactorRanking:
    """added_required should outrank retained which should outrank removed."""

    def test_added_required_beats_retained(self, scorer):
        ar = _change(ChangeType.ADDED_REQUIRED, new_n=5)
        rt = _change(ChangeType.RETAINED, old_n=5, new_n=5)
        t_ar, _ = scorer.score(ar, source_count=5)
        t_rt, _ = scorer.score(rt, source_count=5)
        assert t_ar > t_rt

    def test_removed_lowest_among_present_types(self, scorer):
        removed = _change(ChangeType.REMOVED, old_n=5)
        retained = _change(ChangeType.RETAINED, old_n=5, new_n=5)
        t_rm, _ = scorer.score(removed, source_count=5)
        t_rt, _ = scorer.score(retained, source_count=5)
        assert t_rm < t_rt


class TestStabilityFactor:
    def test_growing_skill_outweighs_vanishing(self, scorer):
        growing = _change(ChangeType.ADDED_REQUIRED, new_n=10)
        vanishing = _change(ChangeType.REMOVED, old_n=1)
        t_g, _ = scorer.score(growing, source_count=5)
        t_v, _ = scorer.score(vanishing, source_count=5)
        assert t_g > t_v