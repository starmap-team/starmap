"""CONCERN 2.4 (Phase 24): Celery task_failure signal wiring tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from celery import signals


class TestTaskFailureSignal:
    """Verify task_failure signal is connected to the audit handler."""

    def test_handler_is_connected(self) -> None:
        """task_failure signal 必须连接 _on_task_failure。"""
        from app.tasks import celery_app as celery_module

        # 守卫属性设在 Celery 实例上（celery_module.celery_app），非模块
        instance = celery_module.celery_app
        assert getattr(instance, "task_failure_handler_registered", False) is True

        # 信号接收器列表应包含我们的 handler
        receivers = signals.task_failure.receivers
        handler_names = []
        for receiver in receivers:
            ref = receiver[1]
            func = ref() if callable(ref) else ref
            if func is not None:
                handler_names.append(getattr(func, "__name__", str(func)))
        assert any("_on_task_failure" in n for n in handler_names), (
            f"task_failure handler not connected, receivers={handler_names}"
        )

    def test_handler_writes_audit_on_failure(self) -> None:
        """_on_task_failure 触发时写 audit_events (CELERY_TASK_FAILURE)。

        2026-08-21: celery 5.6 信号只传 (task_id, exception, sender, ...)，
        无 task_name —— handler 从 sender.name 解析。这里按真实信号形状调用。
        """
        from app.tasks.celery_app import _on_task_failure

        class _FakeSender:
            name = "app.tasks.celery_app.batch_extract_jd"

        # handler 内部 lazy import `from app.utils.audit import audit_log`——
        # patch 源模块目标（`from X import y` 在 import 时读取 X.y，patch 生效）
        with patch("app.utils.audit.audit_log") as mock_audit:
            _on_task_failure(
                task_id="test-task-1",
                exception=RuntimeError("boom"),
                sender=_FakeSender(),
            )
            assert mock_audit.called, "audit_log 必须被调用"
            entry = mock_audit.call_args.args[0]
            assert entry.event.value == "celery_task_failure"
            assert "batch_extract_jd" in entry.action

    def test_handler_survives_audit_failure(self) -> None:
        """audit 写失败不阻断 handler（fail-soft）。"""
        from app.tasks.celery_app import _on_task_failure

        with (
            patch("app.utils.audit.audit_log", side_effect=RuntimeError("audit down")),
            patch("app.tasks.celery_app.logger"),
        ):
            # 由于 handler 内部 lazy import 会重新绑定，这里 patch 真实目标后
            # 通过模块级 reimport 强制走真实路径不可行；直接调用确认不抛。
            _on_task_failure(
                task_id="x",
                exception=ValueError("e"),
                sender=MagicMock(name="fake-sender"),
            )
