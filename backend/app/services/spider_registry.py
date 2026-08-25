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

# ---------------------------------------------------------------------------
# Platform → data_sources.name mapping (single source of truth)
# ---------------------------------------------------------------------------
# A1 fix (2026-08-20): spider_registry 注册的 platform key 与
# data_sources.name 的唯一映射。source_quality_sync / crawl / datasource API
# 统一从此处读取，不再各自维护硬编码映射。

PLATFORM_TO_SOURCE_NAME: dict[str, str] = {
    # 2026-08-20: 值对齐 data_sources.name 实际值（全小写 platform 名）。
    # 此前用显示名（'RemoteOK'/'Jobicy (远程)'）与 DB 不匹配 → sync_source_quality 跳统计。
    "arbeitnow": "arbeitnow",
    "jobicy": "jobicy",
    "remotive": "remotive",
    "v2ex": "v2ex",
    "weworkremotely": "weworkremotely",
    "juejin": "juejin",
    "remoteok": "remoteok",
    "themuse": "themuse",
    "landingjobs": "landingjobs",
    "manual": "手动导入",
    "boss": "Boss Zhipin",
}

# 平台中文显示名（数据源卡片/下拉用，2026-08-23 新增）
PLATFORM_DISPLAY_NAME: dict[str, str] = {
    "arbeitnow": "德国 Arbeitnow",
    "jobicy": "Jobicy 远程",
    "remotive": "Remotive 远程",
    "v2ex": "V2EX 酷工作",
    "weworkremotely": "WeWorkRemotely 远程",
    "juejin": "掘金技术社区",
    "remoteok": "RemoteOK 远程",
    "themuse": "The Muse 求职",
    "landingjobs": "Landing.jobs 欧洲",
    "manual": "手动导入",
    "boss": "BOSS 直聘",
}

# 非平台数据源中文显示名（系统源/占位源不匹配 platform key 时回退，2026-08-25）
SOURCE_DISPLAY_NAME: dict[str, str] = {
    "jd-manual": "手动 JD 导入",
    "manual-import": "手动导入",
    "seed-demo": "演示数据",
    "api-pipeline": "API 流水线",
    "llm-extract": "LLM 抽取",
    "csv-import": "CSV 导入",
    "test-source": "测试数据源",
    "bosszhipin": "BOSS 直聘",
    "v2ex-remote": "V2EX 远程",
}

# Reverse lookup: data_sources.name → platform key
_SOURCE_NAME_TO_PLATFORM: dict[str, str] = {v: k for k, v in PLATFORM_TO_SOURCE_NAME.items()}


def source_name_to_platform(source_name: str) -> str | None:
    """Return the platform key for a given data_sources.name, or None."""
    return _SOURCE_NAME_TO_PLATFORM.get(source_name)


def platform_to_source_name(platform: str) -> str | None:
    """Return the data_sources.name for a given platform key, or None."""
    return PLATFORM_TO_SOURCE_NAME.get(platform)


def build_spider_registry() -> dict[str, Callable[..., Any]]:
    """Build the live spider registry.

    D6 (2026-08-12): v2ex 与 remotive 共用 v2ex_remote.run_sync 但需严格逐源
    隔离 — 包一层闭包固定 source 参数，页面 V2EX 卡只写 v2ex、Remotive 卡只写
    remotive，不再一次调用混写两源。
    """
    from crawler.spiders import (
        arbeitnow,
        jobicy,
        juejin,
        landingjobs,
        remoteok,
        themuse,
        weworkremotely,
    )
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
        "themuse": themuse.run_sync,   # 2026-08-23: The Muse 免费 API
        "landingjobs": landingjobs.run_sync,  # 2026-08-23: Landing.jobs 欧洲
    }


def has_adapter(platform: str | None) -> bool:
    """Return True iff ``platform`` is a registered crawler platform."""
    if not platform:
        return False
    return platform in build_spider_registry()
