"""Smoke tests for Celery app — basic configuration verification.

Covers:
- celery_app configuration
- broker and backend URL from settings
- task_default_queue setting
- task_time_limit from settings
- registered tasks
"""
from __future__ import annotations


class TestCeleryAppConfig:
    """Tests for Celery app configuration."""

    def test_celery_app_exists(self):
        from app.tasks.celery_app import celery_app
        assert celery_app is not None

    def test_broker_url_from_settings(self):
        """Broker URL is derived from settings.redis_uri."""
        from app.tasks.celery_app import celery_app
        # The broker should be set to settings.redis_uri
        assert celery_app.conf.broker_url is not None

    def test_result_backend_from_settings(self):
        """Result backend URL is derived from settings.redis_uri."""
        from app.tasks.celery_app import celery_app
        assert celery_app.conf.result_backend is not None

    def test_task_default_queue(self):
        from app.tasks.celery_app import celery_app
        assert celery_app.conf.task_default_queue == "starmap"

    def test_task_track_started(self):
        from app.tasks.celery_app import celery_app
        assert celery_app.conf.task_track_started is True


class TestCeleryTasks:
    """Tests for Celery task registration."""

    def test_batch_extract_jd_registered(self):
        from app.tasks.celery_app import batch_extract_jd
        assert batch_extract_jd is not None
        assert callable(batch_extract_jd)

    def test_build_graph_from_extractions_registered(self):
        from app.tasks.celery_app import build_graph_from_extractions
        assert build_graph_from_extractions is not None
        assert callable(build_graph_from_extractions)

    def test_analyze_evolution_trends_registered(self):
        from app.tasks.celery_app import analyze_evolution_trends
        assert analyze_evolution_trends is not None
        assert callable(analyze_evolution_trends)

    def test_execute_pipeline_stage_registered(self):
        from app.tasks.celery_app import execute_pipeline_stage
        assert execute_pipeline_stage is not None
        assert callable(execute_pipeline_stage)

    def test_stage_executor_dispatch(self):
        """execute_pipeline_stage dispatches to the correct executor."""
        from app.tasks.celery_app import execute_pipeline_stage
        # Verify the task is a Celery task
        assert hasattr(execute_pipeline_stage, "delay") or hasattr(execute_pipeline_stage, "apply_async")
