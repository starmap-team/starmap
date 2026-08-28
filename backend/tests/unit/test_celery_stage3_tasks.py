"""Stage 3 Celery task entrypoint tests."""
from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.tasks.celery_app import analyze_evolution_trends, batch_extract_jd, build_graph_from_extractions


def test_batch_extract_jd_runs_real_service_entrypoint(monkeypatch):
    service = Mock(return_value={"status": "completed", "extraction_id": "record-1"})
    runner = Mock(return_value={"status": "completed", "extraction_id": "record-1"})
    monkeypatch.setattr("app.tasks.celery_app.run_batch_extract_jd", service)
    monkeypatch.setattr("app.tasks.celery_app.run_async", runner)

    result = batch_extract_jd.run("岗位要求：Python", options={"normalize_skills_enabled": False})

    service.assert_called_once_with("岗位要求：Python", options={"normalize_skills_enabled": False})
    runner.assert_called_once_with(service.return_value)
    assert result["status"] == "completed"


def test_build_graph_from_extractions_runs_real_service_entrypoint(monkeypatch):
    service = Mock(return_value={"status": "completed", "processed": 2})
    runner = Mock(return_value={"status": "completed", "processed": 2})
    monkeypatch.setattr("app.tasks.celery_app.run_build_graph_from_extractions", service)
    monkeypatch.setattr("app.tasks.celery_app.run_async", runner)

    result = build_graph_from_extractions.run(50)

    service.assert_called_once_with(50)
    runner.assert_called_once_with(service.return_value)
    assert result["processed"] == 2


@pytest.mark.parametrize("days", [7, 90, 730])
def test_analyze_evolution_trends_runs_real_service_entrypoint(monkeypatch, days):
    service = Mock(return_value={"status": "completed", "days": days})
    runner = Mock(return_value={"status": "completed", "days": days})
    monkeypatch.setattr("app.tasks.celery_app.run_analyze_evolution_trends", service)
    monkeypatch.setattr("app.tasks.celery_app.run_async", runner)

    result = analyze_evolution_trends.run(days)

    service.assert_called_once_with(days)
    runner.assert_called_once_with(service.return_value)
    assert result["days"] == days


# ══════════════════════════════════════════════════════════════
# retry_no_skill_positions (批2 可持续, 2026-08-28)
# ══════════════════════════════════════════════════════════════


def test_retry_no_skill_positions_runs(monkeypatch):
    from app.tasks.celery_app import retry_no_skill_positions

    redis_mock = Mock()
    redis_mock.set = Mock(return_value=True)  # lock acquired
    redis_mock.delete = Mock()
    redis_cls = Mock()
    redis_cls.from_url = Mock(return_value=redis_mock)
    monkeypatch.setattr("redis.Redis", redis_cls)

    async def _inner(limit):
        return {"retried": 2, "success": 1, "failed": 1, "no_jd": 0}

    inner = Mock(side_effect=_inner)
    monkeypatch.setattr("app.tasks.celery_app._run_no_skill_retry", inner)

    result = retry_no_skill_positions.run(limit=10)

    assert result == {"retried": 2, "success": 1, "failed": 1, "no_jd": 0}
    inner.assert_called_once_with(10)
    redis_mock.delete.assert_called_once()


def test_retry_no_skill_positions_lock_held_skips(monkeypatch):
    from app.tasks.celery_app import retry_no_skill_positions

    redis_mock = Mock()
    redis_mock.set = Mock(return_value=False)  # lock already held
    redis_cls = Mock()
    redis_cls.from_url = Mock(return_value=redis_mock)
    monkeypatch.setattr("redis.Redis", redis_cls)

    inner = Mock()
    monkeypatch.setattr("app.tasks.celery_app._run_no_skill_retry", inner)

    result = retry_no_skill_positions.run(limit=10)

    assert result == {"skipped": 1}
    inner.assert_not_called()


def test_retry_no_skill_positions_redis_unavailable_still_runs(monkeypatch):
    from app.tasks.celery_app import retry_no_skill_positions

    def _raise(*args, **kwargs):
        raise RuntimeError("redis down")

    monkeypatch.setattr("redis.Redis", Mock(side_effect=_raise))

    async def _inner(limit):
        return {"retried": 0, "success": 0, "failed": 0, "no_jd": 0}

    inner = Mock(side_effect=_inner)
    monkeypatch.setattr("app.tasks.celery_app._run_no_skill_retry", inner)

    result = retry_no_skill_positions.run(limit=5)

    assert result == {"retried": 0, "success": 0, "failed": 0, "no_jd": 0}
    inner.assert_called_once()
