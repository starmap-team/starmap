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
