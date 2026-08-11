"""Phase 03 Plan 03 Task 3: stages/clean.py 阶段测试。

锁定 clean 阶段行为契约（成功/失败/状态置 cleaned）。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestExecuteClean:
    """execute_clean 行为契约。"""

    def test_marks_status_cleaned(self):
        """每条记录应被标记 status=cleaned（T5 修复）。"""
        from crawler.persistence.models import JdStatus

        from app.core.pipeline.stages.clean import execute_clean

        fake_session = MagicMock()
        fake_session.__enter__ = MagicMock(return_value=fake_session)
        fake_session.__exit__ = MagicMock(return_value=False)
        fake_jd = MagicMock(spec=["clean_text", "job_title", "status"])
        fake_jd.clean_text = " hello world "
        fake_jd.job_title = ""
        fake_jd.status = JdStatus.raw
        fake_query = MagicMock()
        fake_query.filter.return_value.all.return_value = [fake_jd]
        fake_session.query.return_value = fake_query

        with patch(
            "crawler.persistence.database.get_jd_raw_session",
            return_value=fake_session,
        ), patch(
            "app.core.pipeline.stages.clean.run_async",
        ):
            result = execute_clean("test-run-id")
        assert fake_jd.status == JdStatus.cleaned, (
            "execute_clean must set jd.status = JdStatus.cleaned (T5)"
        )
        assert result["records_processed"] == 1
        assert result["errors"] == []

    def test_empty_records_returns_zero(self):
        """无待清洗记录时返回 records_processed=0。"""
        from app.core.pipeline.stages.clean import execute_clean

        fake_session = MagicMock()
        fake_session.__enter__ = MagicMock(return_value=fake_session)
        fake_session.__exit__ = MagicMock(return_value=False)
        fake_query = MagicMock()
        fake_query.filter.return_value.all.return_value = []
        fake_session.query.return_value = fake_query

        with patch(
            "crawler.persistence.database.get_jd_raw_session",
            return_value=fake_session,
        ), patch(
            "app.core.pipeline.stages.clean.run_async",
        ):
            result = execute_clean("test-run-id")
        assert result["records_processed"] == 0
        assert result["errors"] == []

    def test_failure_returns_error(self):
        """session 查询失败时返回 errors 列表。"""
        from app.core.pipeline.stages.clean import execute_clean

        fake_session = MagicMock()
        fake_session.__enter__ = MagicMock(return_value=fake_session)
        fake_session.__exit__ = MagicMock(return_value=False)
        fake_session.query.side_effect = RuntimeError("DB exploded")

        with patch(
            "crawler.persistence.database.get_jd_raw_session",
            return_value=fake_session,
        ), patch(
            "app.core.pipeline.stages.clean.run_async",
        ):
            result = execute_clean("test-run-id")
        assert result["records_processed"] == 0
        assert any("DB exploded" in e for e in result["errors"])

    def test_pipeline_stage_error_reraised(self):
        """PipelineStageError 必须上抛，不能被吞。"""
        from app.core.pipeline.stages.clean import execute_clean
        from app.exceptions import PipelineStageError

        fake_session = MagicMock()
        fake_session.__enter__ = MagicMock(return_value=fake_session)
        fake_session.__exit__ = MagicMock(return_value=False)
        fake_session.query.side_effect = PipelineStageError("critical", stage="clean")

        with patch(
            "crawler.persistence.database.get_jd_raw_session",
            return_value=fake_session,
        ), patch(
            "app.core.pipeline.stages.clean.run_async",
        ):
            with pytest.raises(PipelineStageError):
                execute_clean("test-run-id")
