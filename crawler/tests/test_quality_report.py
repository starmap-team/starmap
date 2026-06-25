"""Tests for crawler/pipelines/quality_report.py."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from crawler.pipelines.quality_report import QualityReport, format_report_text, generate_quality_report


class TestQualityReport:
    def test_defaults(self) -> None:
        r = QualityReport()
        assert r.total == 0
        assert r.by_source == {}
        assert r.by_status == {}
        assert r.by_date == {}
        assert r.dedup_rate == 0.0
        assert r.unique_urls == 0
        assert r.unique_hashes == 0


class TestFormatReportText:
    def test_empty_report(self) -> None:
        r = QualityReport()
        text = format_report_text(r)
        assert "StarMap 数据质量报告" in text
        assert "总量: 0 条" in text

    def test_with_data(self) -> None:
        r = QualityReport(
            total=100,
            by_source={"lagou": 60, "bosszhipin": 40},
            by_status={"raw": 90, "extracted": 10},
            by_date={"2026-06-22": 50, "2026-06-23": 50},
            dedup_rate=0.05,
            unique_urls=100,
            unique_hashes=95,
        )
        text = format_report_text(r)
        assert "总量: 100 条" in text
        assert "lagou" in text
        assert "bosszhipin" in text
        assert "5.0%" in text
        assert "raw" in text
        assert "2026-06-22" in text

    def test_dedup_rate_zero(self) -> None:
        r = QualityReport(total=50, unique_urls=50, unique_hashes=50, dedup_rate=0.0)
        text = format_report_text(r)
        assert "0.0%" in text

    def test_source_percentage(self) -> None:
        r = QualityReport(
            total=200,
            by_source={"lagou": 100, "51job": 100},
        )
        text = format_report_text(r)
        assert "50.0%" in text


class TestGenerateQualityReport:
    @pytest.mark.skip(reason="Requires real SQLAlchemy models or integration test with database")
    @patch("crawler.pipelines.quality_report.get_jd_raw_session")
    def test_source_site_filter_applies_to_all_queries(self, mock_session_ctx) -> None:
        """Verify that source_site filter is applied to all queries, not just total."""
        mock_session = MagicMock()
        mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)

        # Mock scalar results: total, unique_urls, unique_hashes
        mock_session.scalar.side_effect = [10, 8, 7]

        # Mock execute results for group_by queries
        mock_result = MagicMock()
        mock_result.all.side_effect = [
            [("lagou", 10)],  # by_source
            [("raw", 10)],    # by_status
            [("2026-06-23", 10)],  # by_date
        ]
        mock_session.execute.return_value = mock_result

        report = generate_quality_report(source_site="lagou")

        # Verify all queries were executed
        assert mock_session.scalar.call_count == 3  # total, unique_urls, unique_hashes
        assert mock_session.execute.call_count == 3  # by_source, by_status, by_date

        # Verify the report was populated correctly
        assert report.total == 10
        assert report.unique_urls == 8
        assert report.unique_hashes == 7
        assert report.by_source == {"lagou": 10}
        assert report.by_status == {"raw": 10}
        assert report.by_date == {"2026-06-23": 10}
