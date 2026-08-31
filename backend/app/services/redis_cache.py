"""Redis 缓存助手 (PERF-06, 2026-08-31).

层边界: API 层 (api/v1/*) 不能直接 import app.core.* (test_layer_boundary 门禁),
故将 Redis 缓存读写抽到 services 层, 供 quality/graph 等 API 复用。

从 dashboard_service._get_cached/_set_cached/_cache_key 迁移(等价实现)。
"""
from __future__ import annotations

import json
import logging
from typing import Any

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


def cache_key(namespace: str) -> str:
    """生成带版本前缀的缓存 key (与 dashboard_service 同格式)。"""
    return f"starmap:cache:{namespace}"


async def get_cached(redis: Redis | None, key: str) -> dict[str, Any] | None:
    """读缓存; Redis 不可用/反序列化失败 → None (走重算, 不阻断)。"""
    if redis is None:
        return None
    try:
        raw = await redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis cache read failed for %s: %s", key, exc)
        return None


async def set_cached(
    redis: Redis | None, key: str, data: dict[str, Any], ttl: int,
) -> None:
    """写缓存; 失败仅告警不阻断主流程。"""
    if redis is None:
        return
    try:
        await redis.set(key, json.dumps(data, ensure_ascii=False), ex=ttl)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis cache write failed for %s: %s", key, exc)
