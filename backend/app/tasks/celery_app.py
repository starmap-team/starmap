"""Celery task entrypoints for extraction, graph building, and evolution analysis."""
from __future__ import annotations

import logging
from typing import Any

from celery import Celery

from app.config import settings
from app.tasks.stage3_services import (
    run_analyze_evolution_trends,
    run_async,
    run_batch_extract_jd,
    run_build_graph_from_extractions,
)

logger = logging.getLogger(__name__)

celery_app = Celery(
    "starmap",
    broker=settings.redis_uri,
    backend=settings.redis_uri,
)
celery_app.conf.update(
    task_default_queue="starmap",
    task_track_started=True,
    timezone="Asia/Shanghai",
    enable_utc=False,
)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def batch_extract_jd(self, jd_text: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Batch-extract skills from a JD via Celery.

    Args:
        jd_text: Raw job description text.

    Returns:
        Extraction, persistence, and graph-ingestion summary.

    Raises:
        self.retry() on transient failures.
    """
    try:
        logger.info("batch_extract_jd started chars=%d", len(jd_text))
        return run_async(run_batch_extract_jd(jd_text, options=options))
    except Exception as exc:
        logger.exception("batch_extract_jd failed")
        raise self.retry(exc=exc) from exc


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def build_graph_from_extractions(self, limit: int = 100) -> dict[str, Any]:
    """Build Neo4j graph triples from persisted extraction records."""
    try:
        logger.info("build_graph_from_extractions started limit=%d", limit)
        return run_async(run_build_graph_from_extractions(limit))
    except Exception as exc:
        logger.exception("build_graph_from_extractions failed")
        raise self.retry(exc=exc) from exc


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def analyze_evolution_trends(self, days: int = 90) -> dict[str, Any]:
    """Analyze skill and position evolution from recent extraction records."""
    try:
        logger.info("analyze_evolution_trends started days=%d", days)
        return run_async(run_analyze_evolution_trends(days))
    except Exception as exc:
        logger.exception("analyze_evolution_trends failed")
        raise self.retry(exc=exc) from exc
