"""Tests for crawler/pipelines/quality_report.py."""
from __future__ import annotations

from crawler.pipelines.quality_report import QualityReport, format_report_text


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
