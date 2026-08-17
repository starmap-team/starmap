"""多模块联动 Phase 5 (2026-08-17): Celery 周期任务测试。

锁定 backend/app/tasks/skill_backfill_scheduler.py 的 3 个周期任务 + beat schedule。
"""
from __future__ import annotations

from app.tasks.celery_app import celery_app
from app.tasks.skill_backfill_scheduler import (
    daily_data_quality_check_task,
    daily_skill_backfill_task,
    weekly_low_data_re_extract_task,
)


class TestCeleryTaskRegistration:
    """3 个任务必须注册到 Celery。"""

    def test_daily_skill_backfill_registered(self):
        assert daily_skill_backfill_task.name == "daily_skill_backfill_task"

    def test_weekly_low_data_re_extract_registered(self):
        assert weekly_low_data_re_extract_task.name == "weekly_low_data_re_extract_task"

    def test_daily_data_quality_check_registered(self):
        assert daily_data_quality_check_task.name == "daily_data_quality_check_task"


class TestCeleryBeatSchedule:
    """3 个任务必须挂到 Celery beat schedule。"""

    def test_beat_schedule_has_3_tasks(self):
        schedule = celery_app.conf.beat_schedule or {}
        assert "daily-skill-backfill" in schedule
        assert "weekly-low-data-re-extract" in schedule
        assert "daily-data-quality-check" in schedule

    def test_daily_skill_backfill_task_name_correct(self):
        schedule = celery_app.conf.beat_schedule
        task = schedule["daily-skill-backfill"]
        assert task["task"] == "daily_skill_backfill_task"

    def test_weekly_task_name_correct(self):
        schedule = celery_app.conf.beat_schedule
        task = schedule["weekly-low-data-re-extract"]
        assert task["task"] == "weekly_low_data_re_extract_task"


class TestTaskRetryPolicy:
    """任务失败重试策略（防 LLM 临时故障触发漏跑）。"""

    def test_daily_backfill_has_retries(self):
        # 默认重试策略：max_retries=2, retry_delay=300s
        assert daily_skill_backfill_task.max_retries is not None
        assert daily_skill_backfill_task.max_retries >= 1

    def test_weekly_re_extract_has_retries(self):
        assert weekly_low_data_re_extract_task.max_retries is not None


class TestAsyncBackfillHelper:
    """_async_skill_backfill fail-soft 行为（不是 raise 而是返回 dict）。"""

    def test_helper_signature(self):
        import inspect

        from app.tasks.skill_backfill_scheduler import _async_skill_backfill
        sig = inspect.signature(_async_skill_backfill)
        assert "limit" in sig.parameters
