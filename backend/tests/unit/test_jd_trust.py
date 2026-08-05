"""PLAN-012: §7.1 JD 级 4 因子信任度模型测试。"""

from __future__ import annotations

import pytest

from app.core.trust.jd_trust import (
    DEFAULT_WEIGHTS,
    authority_score,
    consistency_score,
    grid_search_weights,
    independence_score,
    timeliness_score,
    trust_score,
)


class TestAuthority:
    def test_source_type_table(self) -> None:
        assert authority_score("enterprise") == 0.9
        assert authority_score("platform") == 0.7
        assert authority_score("aggregator") == 0.5
        assert authority_score("social") == 0.3

    def test_unknown_type_neutral(self) -> None:
        assert authority_score("mystery") == 0.5
        assert authority_score("") == 0.5


class TestTimeliness:
    def test_recent_jd_scores_high(self) -> None:
        from datetime import UTC, datetime
        now = datetime(2026, 8, 5, tzinfo=UTC)
        assert timeliness_score("2026-08-01T00:00:00+00:00", now) > 0.9

    def test_six_months_approaches_zero(self) -> None:
        from datetime import UTC, datetime
        now = datetime(2026, 8, 5, tzinfo=UTC)
        assert timeliness_score("2026-02-05T00:00:00+00:00", now) < 0.2

    def test_missing_or_invalid_date_zero(self) -> None:
        assert timeliness_score(None) == 0.0
        assert timeliness_score("not-a-date") == 0.0


class TestIndependence:
    def test_no_same_source_scores_independent(self) -> None:
        assert independence_score(None) == 1.0
        assert independence_score([]) == 1.0

    def test_high_similarity_penalizes(self) -> None:
        assert independence_score([0.9, 0.3]) == 0.1  # 1 - 0.9

    def test_low_similarity_scores_high(self) -> None:
        assert independence_score([0.1, 0.2]) == 0.8


class TestConsistency:
    def test_ratio_of_cross_validated(self) -> None:
        assert consistency_score(6, 10) == 0.6

    def test_zero_total_returns_zero(self) -> None:
        assert consistency_score(0, 0) == 0.0

    def test_cross_validated_capped_at_total(self) -> None:
        assert consistency_score(12, 10) == 1.0


class TestTrustScore:
    def test_default_weights_blend(self) -> None:
        # enterprise + 近期 + 独立 + 全交叉 → 接近满分
        out = trust_score({
            "source_type": "enterprise",
            "publish_date": "2026-08-01T00:00:00+00:00",
            "sim_scores": [0.05],
            "cross_validated_skills": 10,
            "total_skills": 10,
        })
        assert out["trust_score"] > 0.9
        assert out["factors"]["authority"] == 0.9

    def test_low_evidence_scores_low(self) -> None:
        # social + 过期 + 高抄袭 + 零交叉 → 低分
        out = trust_score({
            "source_type": "social",
            "publish_date": "2025-01-01T00:00:00+00:00",
            "sim_scores": [0.95],
            "cross_validated_skills": 0,
            "total_skills": 8,
        })
        assert out["trust_score"] < 0.5

    def test_missing_fields_graceful(self) -> None:
        out = trust_score({})
        assert 0.0 <= out["trust_score"] <= 1.0
        assert out["factors"]["authority"] == 0.5  # 未知来源中立

    def test_custom_weights_override(self) -> None:
        out = trust_score({"source_type": "platform"}, weights={"authority": 0.5, "timeliness": 0.0, "independence": 0.0, "consistency": 0.5})
        assert out["trust_score"] == pytest.approx(0.7 * 0.5 + 0.0 * 0.2 + 1.0 * 0.0 + 0.0 * 0.5)

    def test_default_weights_sum_to_one(self) -> None:
        assert sum(DEFAULT_WEIGHTS.values()) == 1.0


class TestGridSearchWeights:
    def test_finds_weight_combo_matching_human_labels(self) -> None:
        """合成数据: 高信任 JD 全部高因子 → 各权重组合都相关, 网格必须返回合法组合。"""
        samples = [
            {"source_type": "enterprise", "publish_date": "2026-08-01T00:00:00+00:00",
             "sim_scores": [0.1], "cross_validated_skills": 8, "total_skills": 8},
            {"source_type": "social", "publish_date": "2025-06-01T00:00:00+00:00",
             "sim_scores": [0.9], "cross_validated_skills": 1, "total_skills": 8},
            {"source_type": "platform", "publish_date": "2026-05-01T00:00:00+00:00",
             "sim_scores": [0.4], "cross_validated_skills": 5, "total_skills": 10},
        ]
        labels = [95.0, 20.0, 60.0]
        out = grid_search_weights(samples, labels)
        assert out["pearson"] > 0.9  # 单调对应
        assert sum(out["weights"].values()) == pytest.approx(1.0)
        assert out["combos_evaluated"] > 0

    def test_empty_samples_returns_defaults(self) -> None:
        out = grid_search_weights([], [])
        assert out["weights"] == DEFAULT_WEIGHTS
