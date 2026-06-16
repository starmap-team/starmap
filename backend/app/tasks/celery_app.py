"""Celery 基础配置。"""
from __future__ import annotations

from celery import Celery

from app.config import settings

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
