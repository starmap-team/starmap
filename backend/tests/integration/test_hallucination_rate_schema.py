"""Phase 11 D-05: hallucination_rate 三段式契约 schema 集成测试。"""
from __future__ import annotations

from app.api.v1.quality import QualityDashboard, QualityReport
from app.schemas.quality import QualityDashboard as SchemaQualityDashboard


class TestHallucinationContractRoundTrip:
    """QualityDashboard schema 包含 hallucination_numerator/denominator/window_days 三段式。"""

    def test_internal_quality_dashboard_has_three_part_fields(self):
        dashboard = QualityDashboard(
            report=QualityReport(
                precision=0.85, recall=0.80, f1=0.82, warning_level="green", details=[]
            ),
            hallucination_numerator=2,
            hallucination_denominator=10,
            hallucination_window_days=30,
        )
        assert dashboard.hallucination_numerator == 2
        assert dashboard.hallucination_denominator == 10
        assert dashboard.hallucination_window_days == 30

    def test_exported_schema_alias_has_three_part_fields(self):
        """导出 schema 别名与内部一致（确保前后端契约同步）。"""
        exported = SchemaQualityDashboard(
            report=QualityReport(
                precision=0.85, recall=0.80, f1=0.82, warning_level="green", details=[]
            ),
        )
        assert hasattr(exported, "hallucination_numerator")
        assert hasattr(exported, "hallucination_denominator")
        assert hasattr(exported, "hallucination_window_days")

    def test_default_window_days_is_30(self):
        """窗口默认 30 天，匹配 CONTEXT D-05 统计窗口。"""
        dashboard = QualityDashboard(
            report=QualityReport(
                precision=0.85, recall=0.80, f1=0.82, warning_level="green", details=[]
            ),
        )
        assert dashboard.hallucination_window_days == 30

    def test_window_days_ge_1_validation(self):
        """window_days 必须 ≥ 1（防止前端除零）。"""
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            QualityDashboard(
                report=QualityReport(
                    precision=0.85, recall=0.80, f1=0.82, warning_level="green", details=[]
                ),
                hallucination_window_days=0,
            )
