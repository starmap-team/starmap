"""Phase 03 Plan 03 Task 1: stages/timeseries.py 阶段测试。

锁定 timeseries 阶段行为契约（成功/失败路径）。
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.pipeline.stages.timeseries import execute_timeseries


class TestExecuteTimeseries:
    """execute_timeseries 行为契约。"""

    def test_returns_processed_count_on_success(self):
        """成功路径返回 windows_created 数。"""
        fake_result = {"windows_created": 7, "skills_updated": 42}

        async def _fake_refresh():  # noqa: D401
            return fake_result

        with patch(
            "app.core.pipeline.stages.timeseries._run_timeseries_refresh",
            _fake_refresh,
        ), patch(
            "app.core.pipeline.stages.timeseries.run_async",
            return_value=fake_result,
        ):
            result = execute_timeseries("test-run")
        assert result["records_processed"] == 7
        assert result["errors"] == []

    def test_returns_zero_processed_on_failure(self):
        """失败路径返回 errors 列表 + processed=0。"""
        async def _boom():  # noqa: D401
            raise RuntimeError("timeseries exploded")

        with patch(
            "app.core.pipeline.stages.timeseries._run_timeseries_refresh",
            _boom,
        ), patch(
            "app.core.pipeline.stages.timeseries.run_async",
            side_effect=RuntimeError("timeseries exploded"),
        ):
            result = execute_timeseries("test-run")
        assert result["records_processed"] == 0
        assert len(result["errors"]) == 1
        assert "timeseries exploded" in result["errors"][0]

    def test_pipeline_stage_error_reraised(self):
        """PipelineStageError 必须上抛，不能被吞。"""
        from app.exceptions import PipelineStageError

        with patch(
            "app.core.pipeline.stages.timeseries.run_async",
            side_effect=PipelineStageError("critical", stage="timeseries"),
        ):
            with pytest.raises(PipelineStageError):
                execute_timeseries("test-run")
