"""Coverage: core/trust/entity_trust.py — 实体信任四因子评分器 (Phase 19)。

验证 §6.2 四因子公式: T = 0.3·source + 0.3·extractor + 0.25·cross + 0.15·time
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.trust.entity_trust import TRUST_WEIGHTS, EntityTrustScorer

NOW = datetime.now(UTC)


def _scorer() -> EntityTrustScorer:
    return EntityTrustScorer()


class TestSourceDiversity:
    def test_zero_sources_zero(self) -> None:
        assert _scorer().source_diversity(0) == 0.0

    def test_sqrt_saturation_curve(self) -> None:
        s = _scorer()
        assert s.source_diversity(1) == pytest.approx(0.316, abs=0.001)  # sqrt(1/10)
        assert s.source_diversity(10) == 1.0  # 饱和
        assert s.source_diversity(50) == 1.0  # 超饱和仍封顶

    def test_monotonic_increasing(self) -> None:
        s = _scorer()
        assert s.source_diversity(3) > s.source_diversity(2)


class TestExtractorConf:
    def test_none_returns_neutral_05(self) -> None:
        assert _scorer().extractor_conf(None) == 0.5

    def test_clamps_range(self) -> None:
        s = _scorer()
        assert s.extractor_conf(1.5) == 1.0
        assert s.extractor_conf(-0.2) == 0.0
        assert s.extractor_conf(0.9) == 0.9


class TestCrossVerify:
    def test_verified_threshold(self) -> None:
        s = _scorer()
        assert s.cross_verify(0) == 0.0
        assert s.cross_verify(1) == 0.0
        assert s.cross_verify(2) == 1.0
        assert s.cross_verify(10) == 1.0


class TestTimeDecay:
    def test_recent_full_trust(self) -> None:
        assert _scorer().time_decay(NOW) == 1.0
        assert _scorer().time_decay(NOW - timedelta(days=29)) == 1.0

    def test_old_decays(self) -> None:
        old = NOW - timedelta(days=60)
        val = _scorer().time_decay(old)
        assert 0.0 < val < 1.0

    def test_naive_datetime_handled(self) -> None:
        naive = NOW.replace(tzinfo=None) - timedelta(days=5)
        assert _scorer().time_decay(naive) == 1.0  # 无时区也按近 30d 处理

    def test_none_zero(self) -> None:
        assert _scorer().time_decay(None) == 0.0


class TestScore:
    def test_high_confidence_multi_source(self) -> None:
        # source=10→1.0, conf=0.9, cross=1.0, time=1.0
        v = _scorer().score(10, 0.9, NOW)
        assert v == pytest.approx(0.3 + 0.3 * 0.9 + 0.25 + 0.15, abs=0.001)  # 0.97

    def test_low_confidence_single_source(self) -> None:
        # source=1→0.316, conf=0.3, cross=0.0, time=1.0
        v = _scorer().score(1, 0.3, NOW)
        expected = 0.3 * (1 / 10) ** 0.5 + 0.3 * 0.3 + 0.25 * 0.0 + 0.15 * 1.0
        assert v == pytest.approx(expected, abs=0.001)
        assert v < 0.5  # 单源低置信 → 低信任

    def test_all_missing_graceful(self) -> None:
        # source=0, conf=None, last=None → 0.3*0 + 0.3*0.5 + 0.25*0 + 0.15*0 = 0.15
        v = _scorer().score(0, None, None)
        assert v == pytest.approx(0.15, abs=0.001)

    def test_clamped_to_range(self) -> None:
        v = _scorer().score(999, 2.0, NOW)  # 全部超上限
        assert 0.0 <= v <= 1.0


def test_trust_weights_match_design_doc() -> None:
    """设计 §6.2 Golden Set 校准权重: w1=0.3/w2=0.3/w3=0.25/w4=0.15。"""
    assert TRUST_WEIGHTS == {
        "source_diversity": 0.3,
        "extractor_conf": 0.3,
        "cross_verify": 0.25,
        "time_decay": 0.15,
    }
