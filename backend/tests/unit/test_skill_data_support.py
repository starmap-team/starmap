"""多模块联动 Phase 2 (2026-08-17): skill_data_support 服务测试。

锁定 backend/app/services/skill_data_support.py 的 3 维度评分 + 4 档分类 + dict 序列化。
"""
from __future__ import annotations

from app.services.skill_data_support import (
    FULL_COVERAGE_THRESHOLD,
    SCORE_FULL_COVERAGE,
    SCORE_PARTIAL_COVERAGE,
    SOURCE_RICHNESS_THRESHOLD,
    PositionDataSupport,
    _classify_tier,
    _compute_score,
    report_to_dict,
)


class TestScoreComputation:
    """3 维度加权得分: skill_count(0.5) + avg_confidence(0.3) + source_count(0.2)."""

    def test_zero_skills_zero_score(self):
        """0 技能 = 0.0."""
        assert _compute_score(0, 0.0, 0) == 0.0

    def test_full_coverage_max_score(self):
        """FULL_THRESHOLD 技能 + 1.0 confidence + SOURCE_THRESHOLD source = 1.0."""
        score = _compute_score(
            skill_count=FULL_COVERAGE_THRESHOLD,
            avg_confidence=1.0,
            max_source_count=SOURCE_RICHNESS_THRESHOLD,
        )
        # 0.5 (skill 5/5) + 0.3 (conf 1.0) + 0.2 (source 3/3) = 1.0
        assert score == 1.0

    def test_skill_count_capped_at_threshold(self):
        """skill_count 超过 FULL_THRESHOLD 也不超过 1.0."""
        score = _compute_score(100, 1.0, 10)
        # 0.5 + 0.3 + 0.2 = 1.0
        assert score == 1.0

    def test_only_skill_count(self):
        """只有技能数，conf=0/source=0 → 0.5."""
        assert _compute_score(3, 0.0, 0) == 0.5 * (3 / FULL_COVERAGE_THRESHOLD)

    def test_only_confidence(self):
        """只有 conf → 0.3."""
        assert _compute_score(0, 1.0, 0) == 0.3

    def test_mixed_3_skill_0_5_conf_1_source(self):
        """3 技能 / 0.5 conf / 1 source → 0.3 + 0.15 + 0.0667 ≈ 0.5167."""
        score = _compute_score(3, 0.5, 1)
        assert 0.5 <= score <= 0.55


class TestTierClassification:
    """4 档分类: no_data / low_data_support / partial_coverage / full_coverage."""

    def test_no_data_skill_count_zero(self):
        assert _classify_tier(0.0, 0) == "no_data"

    def test_no_data_with_some_score_still_no_data(self):
        """skill_count=0 即便 score 也不是 no_data."""
        assert _classify_tier(0.5, 0) == "no_data"

    def test_full_coverage_threshold(self):
        assert _classify_tier(SCORE_FULL_COVERAGE, 5) == "full_coverage"
        assert _classify_tier(0.95, 8) == "full_coverage"

    def test_partial_coverage_range(self):
        assert _classify_tier(SCORE_PARTIAL_COVERAGE, 4) == "partial_coverage"
        assert _classify_tier(0.5, 3) == "partial_coverage"

    def test_low_data_support_below_threshold(self):
        assert _classify_tier(0.39, 1) == "low_data_support"
        assert _classify_tier(0.1, 2) == "low_data_support"


class TestReportToDict:
    """DataSupportReport → dict 序列化 (dashboard JSON)。"""

    def test_dict_contains_all_fields(self):
        report = DataSupportReport(
            avg_score=0.65,
            total_positions=10,
            full_coverage_count=3,
            partial_coverage_count=4,
            low_data_support_count=2,
            no_data_count=1,
        )
        d = report_to_dict(report)
        assert d["avg_score"] == 0.65
        assert d["total_positions"] == 10
        assert d["full_coverage_count"] == 3
        assert d["partial_coverage_count"] == 4
        assert d["low_data_support_count"] == 2
        assert d["no_data_count"] == 1
        assert d["low_data_position_count"] == 0  # no low_data_positions set

    def test_dict_serializes_low_data_positions(self):
        pos = PositionDataSupport(
            position_id="p1", position_name="Test Job",
            skill_count=2, score=0.3, tier="low_data_support",
        )
        report = DataSupportReport(
            total_positions=1, low_data_support_count=1,
            low_data_positions=[pos],
        )
        d = report_to_dict(report)
        assert d["low_data_position_count"] == 1
        assert d["low_data_position_sample"][0]["position_name"] == "Test Job"
        assert d["low_data_position_sample"][0]["tier"] == "low_data_support"

    def test_dict_limits_sample_to_10(self):
        report = DataSupportReport(
            low_data_positions=[
                PositionDataSupport(position_id=f"p{i}", position_name=f"Job{i}", score=0.1, tier="low_data_support")
                for i in range(50)
            ],
        )
        d = report_to_dict(report)
        assert len(d["low_data_position_sample"]) == 10


# 局部导入以避免循环
from app.services.skill_data_support import DataSupportReport  # noqa: E402
