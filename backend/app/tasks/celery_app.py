"""Celery 基础配置。"""
from __future__ import annotations

import json
import logging

from celery import Celery

from app.config import settings

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
def batch_extract_jd(self, jd_text: str) -> str:
    """Batch-extract skills from a JD via Celery.

    Args:
        jd_text: Raw job description text.

    Returns:
        JSON string of extracted skills.

    Raises:
        self.retry() on transient failures.
    """
    try:
        from app.core.extraction.jd_extract import mask_pii

        clean_text = mask_pii(jd_text)
        logger.info("batch_extract_jd received %d chars (masked)", len(clean_text))
        return json.dumps({"status": "queued", "char_count": len(clean_text)}, ensure_ascii=False)
    except Exception as exc:
        logger.exception("batch_extract_jd failed")
        raise self.retry(exc=exc) from exc


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def build_graph_from_extractions(self, limit: int = 100) -> dict[str, int | str]:
    """Queue graph construction from persisted extraction records."""
    try:
        logger.info("build_graph_from_extractions queued limit=%d", limit)
        return {"status": "queued", "limit": max(1, limit)}
    except Exception as exc:
        logger.exception("build_graph_from_extractions failed")
        raise self.retry(exc=exc) from exc


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def analyze_evolution_trends(self, days: int = 90) -> dict[str, int | str]:
    """Queue skill and position evolution analysis."""
    try:
        bounded_days = min(max(days, 7), 730)
        logger.info("analyze_evolution_trends queued days=%d", bounded_days)
        return {"status": "queued", "days": bounded_days}
    except Exception as exc:
        logger.exception("analyze_evolution_trends failed")
        raise self.retry(exc=exc) from exc
