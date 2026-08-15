"""Spider adapter registry — the single source of truth for which platforms
have a working crawler.

Layer boundary: API routes and services may import from here; ``core/`` may
import from here too (downward direction only — ``core/`` must never be
imported by ``api/`` or ``services/`` directly).

Extracted from ``core/pipeline/stages/crawl.py:build_spider_registry`` so
the API layer can answer "does this datasource have an adapter?" without
importing from core/.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


def build_spider_registry() -> dict[str, Callable[..., Any]]:
    """Build the live spider registry.

    D6 (2026-08-12): v2ex 与 remotive 共用 v2ex_remote.run_sync 但需严格逐源
    隔离 — 包一层闭包固定 source 参数，页面 V2EX 卡只写 v2ex、Remotive 卡只写
    remotive，不再一次调用混写两源。
    """
    from crawler.spiders import arbeitnow, jobicy, juejin, remoteok, weworkremotely
    from crawler.spiders.v2ex_remote import run_sync as v2ex_sync

    def _v2ex_only(keyword: str = "python", max_count: int = 10) -> list[dict[str, Any]]:
        return v2ex_sync(keyword=keyword, max_count=max_count, source="v2ex")

    def _remotive_only(keyword: str = "python", max_count: int = 10) -> list[dict[str, Any]]:
        return v2ex_sync(keyword=keyword, max_count=max_count, source="remotive")

    return {
        "v2ex": _v2ex_only,
        "remotive": _remotive_only,
        "arbeitnow": arbeitnow.run_sync,
        "jobicy": jobicy.run_sync,
        "weworkremotely": weworkremotely.run_sync,
        "juejin": juejin.run_sync,    # PLAN-002: D5 非结构化源 (技术博客)
        "remoteok": remoteok.run_sync,  # PLAN-003: 英文 JD 源
    }


def has_adapter(platform: str | None) -> bool:
    """Return True iff ``platform`` is a registered crawler platform."""
    if not platform:
        return False
    return platform in build_spider_registry()
