"""Evolution orchestrator unit tests — month iterator + summary shape.

The full ``run_evolution_pipeline`` touches the DB, so we test only the
pure helpers here. Integration is covered by stage 5 E2E.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.evolution.orchestrator import _month_iter


class TestMonthIter:
    def test_returns_chronological_order(self):
        months = _month_iter(3, datetime(2026, 7, 24, tzinfo=UTC))
        assert [m.strftime("%Y-%m") for m in months] == [
            "2026-04", "2026-05", "2026-06", "2026-07",
        ]

    def test_handles_year_boundary(self):
        months = _month_iter(2, datetime(2026, 2, 15, tzinfo=UTC))
        assert [m.strftime("%Y-%m") for m in months] == ["2025-12", "2026-01", "2026-02"]

    def test_includes_current_month_as_last(self):
        months = _month_iter(0, datetime(2026, 7, 4, tzinfo=UTC))
        assert len(months) == 1
        assert months[0] == datetime(2026, 7, 1, tzinfo=UTC)

    def test_naive_input_treated_as_utc(self):
        months = _month_iter(1, datetime(2026, 7, 4))
        assert all(m.tzinfo == UTC for m in months)


class TestPipelineCallable:
    def test_run_evolution_pipeline_importable_and_callable(self):
        from app.core.evolution.orchestrator import run_evolution_pipeline
        assert callable(run_evolution_pipeline)

    def test_process_single_position_importable(self):
        from app.core.evolution.orchestrator import _process_single_position
        assert callable(_process_single_position)

    def test_diff_and_persist_importable(self):
        from app.core.evolution.orchestrator import _diff_and_persist
        assert callable(_diff_and_persist)


class TestEvolutionPipelineError:
    def test_importable(self):
        from app.core.evolution.orchestrator import EvolutionPipelineError
        assert EvolutionPipelineError is not None

    def test_is_exception_subclass(self):
        from app.core.evolution.orchestrator import EvolutionPipelineError
        assert issubclass(EvolutionPipelineError, Exception)

    def test_constructor_with_message(self):
        from app.core.evolution.orchestrator import EvolutionPipelineError
        err = EvolutionPipelineError("something went wrong")
        assert str(err) == "something went wrong"
        assert err.message == "something went wrong"
        assert err.step == ""

    def test_constructor_with_step(self):
        from app.core.evolution.orchestrator import EvolutionPipelineError
        err = EvolutionPipelineError("snapshot failed", step="snapshot")
        assert err.step == "snapshot"
        assert "snapshot failed" in str(err)

    def test_caught_as_exception(self):
        from app.core.evolution.orchestrator import EvolutionPipelineError
        try:
            raise EvolutionPipelineError("test error", step="diff")
        except EvolutionPipelineError as e:
            assert e.step == "diff"
            assert e.message == "test error"