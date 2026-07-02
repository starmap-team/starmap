"""Tests for hallucination guard edge cases."""
from __future__ import annotations

from datetime import UTC, datetime

from app.core.evolution.hallucination_guard import HallucinationGuard


class TestComputeSpanWeeks:
    def test_normal_dates(self):
        """Test with proper datetime objects."""
        first = datetime(2026, 1, 1, tzinfo=UTC)
        last = datetime(2026, 2, 1, tzinfo=UTC)
        weeks = HallucinationGuard._compute_span_weeks(first, last)
        assert weeks > 0

    def test_returns_float(self):
        result = HallucinationGuard._compute_span_weeks(None, None)
        assert result == 0.0

    def test_edge_case_objects(self):
        """Test objects without timestamp attribute."""
        result = HallucinationGuard._compute_span_weeks("string", "string")
        assert result == 0.0
