"""Tests for hallucination guard edge cases that trigger exception handlers."""
from __future__ import annotations

from app.core.evolution.hallucination_guard import HallucinationGuard


def test_compute_span_weeks_incompatible_types():
    """Test that incompatible objects in _compute_span_weeks are handled."""
    class X:
        def timestamp(self):
            return 1000.0

    # (last - first) with X objects will fail since X doesn't support subtraction
    result = HallucinationGuard._compute_span_weeks(X(), X())
    assert result == 0.0
