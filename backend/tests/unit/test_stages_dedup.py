"""Phase 03 Plan 03 Task 2: stages/dedup.py 阶段测试。

锁定 dedup 阶段行为契约（成功/失败/空输入）。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestExecuteDedup:
    """execute_dedup 行为契约。"""

    def test_empty_records_returns_zero(self):
        """无待去重记录时返回 records_processed=0。"""
        from app.core.pipeline.stages.dedup import execute_dedup

        # Mock session context manager; JdRaw query returns []
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
            "app.core.pipeline.stages.dedup.run_async",
        ):
            result = execute_dedup("test-run")
        assert result["records_processed"] == 0
        assert result["duplicates_found"] == 0
        assert result["errors"] == []

    def test_dedup_source_after_call(self):
        """dedup 完成后调用 _update_source_after_dedup。"""
        from app.core.pipeline.stages.dedup import execute_dedup

        # Mock session with one JD record
        fake_session = MagicMock()
        fake_session.__enter__ = MagicMock(return_value=fake_session)
        fake_session.__exit__ = MagicMock(return_value=False)
        fake_jd = MagicMock()
        fake_jd.clean_text = "hello world"
        fake_query = MagicMock()
        fake_query.filter.return_value.all.return_value = [fake_jd]
        fake_session.query.return_value = fake_query

        # dedup_service returns same list as input (no dup)
        async def _fake_dedup(records, **_):  # noqa: ARG001
            return records, []

        with patch(
            "crawler.persistence.database.get_jd_raw_session",
            return_value=fake_session,
        ), patch(
            "app.services.dedup_service.dedup_jd_records",
            _fake_dedup,
        ), patch(
            "app.core.pipeline.stages.dedup.run_async",
            side_effect=lambda c: None,
        ), patch(
            "app.core.pipeline.stages.dedup._update_source_after_dedup",
        ) as mock_update:
            result = execute_dedup("test-run-id")
        assert result["records_processed"] == 1
        assert result["duplicates_found"] == 0
        mock_update.assert_called_once()

    def test_marks_duplicates_status(self):
        """dedup_service 返回的重复记录应被标记 status=duplicate。"""
        from crawler.persistence.models import JdStatus

        from app.core.pipeline.stages.dedup import execute_dedup

        fake_session = MagicMock()
        fake_session.__enter__ = MagicMock(return_value=fake_session)
        fake_session.__exit__ = MagicMock(return_value=False)
        # 使用 spec=['clean_text', 'status'] 让 MagicMock 接受属性赋值
        keep = MagicMock(spec=["clean_text", "status"])
        keep.clean_text = "unique"
        keep.status = JdStatus.raw
        dup = MagicMock(spec=["clean_text", "status"])
        dup.clean_text = "dup"
        dup.status = JdStatus.raw
        fake_query = MagicMock()
        fake_query.filter.return_value.all.return_value = [keep, dup]
        fake_session.query.return_value = fake_query

        async def _fake_dedup(records, **_):  # noqa: ARG001
            return [keep], [dup]

        # 模拟 publish_stage_progress 异步调用：第3次调用触发 dedup_jd_records
        # (call 1 = start publish; call 2 = loading publish; call 3 = dedup)
        n = {"i": 0}

        def _run_async_dispatch(_coro):
            n["i"] += 1
            return ([keep], [dup]) if n["i"] == 3 else None

        with patch(
            "crawler.persistence.database.get_jd_raw_session",
            return_value=fake_session,
        ), patch(
            "app.services.dedup_service.dedup_jd_records",
            _fake_dedup,
        ), patch(
            "app.core.pipeline.stages.dedup.run_async",
            side_effect=_run_async_dispatch,
        ), patch(
            "app.core.pipeline.stages.dedup._update_source_after_dedup",
        ):
            result = execute_dedup("test-run-id")
        assert dup.status == JdStatus.duplicate, f"expected duplicate, got {dup.status}"
        assert result["duplicates_found"] == 1
