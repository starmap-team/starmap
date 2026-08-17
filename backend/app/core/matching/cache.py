"""匹配服务缓存模块。

提供线程安全的缓存管理，替代原 match_service.py 中的全局可变状态。
支持本地内存缓存模式（线程安全），Redis 分布式缓存可在此基础上扩展。

Cache key format:
    - profile cache:  "profile:{target_position}"   (e.g., "profile:senior_engineer")
    - prerequisite:   "prerequisite_map"             (single global key)
    - match result:   "match_result:{match_id}"      (e.g., "match_result:550e8400-e29b-...")

TTL values:
    - profile cache:     300s (5 min, default)  / configurable via __init__ ttl
    - prerequisite map:  300s (5 min, default)  / same ttl as profile cache
    - match results:     no TTL (FIFO eviction at max_size, default 1000 entries)

Invalidation strategy:
    - Per-key TTL for profile cache (avoids cache avalanche — BL-13):
      each key has its own timestamp; expired keys are removed individually.
    - Prerequisite map: single timestamp, full clear on expiry.
    - Match results: FIFO eviction when cache exceeds max_size; no proactive invalidation.
    - Manual: clear() drops all entries at once.

Cache backend:
    - In-process memory (dict + threading.Lock).
    - Designed so RedisCache can be swapped in behind the same interface
      (see match_service.py _PROFILE_CACHE/_MATCH_RESULTS migration notes).
"""

from __future__ import annotations

import threading
import time
from typing import Any

from loguru import logger


class MatchCache:
    """线程安全的本地内存缓存，用于匹配服务。

    替代原 _PROFILE_CACHE、_MATCH_RESULTS 等全局可变状态，
    使用 threading.Lock 保证线程安全，支持 TTL 过期策略和 FIFO 淘汰。

    Cache domains:
        - profile_cache: 岗位技能画像（per-key TTL，避免雪崩）
        - match_results: 匹配结果（FIFO 淘汰，无 TTL）
        - prerequisite_map: 技能前置关系（单 key TTL）

    Key format:  ``{domain}:{key}``
    Default TTL: 300s (5 min), configurable per instance.
    """

    def __init__(self, ttl: int = 300, max_size: int = 1000) -> None:
        """初始化缓存。

        Args:
            ttl: 缓存过期时间（秒），默认 300（5 分钟）。
                 适用于 profile_cache 和 prerequisite_map 两个域。
            max_size: 最大缓存条目数，默认 1000。
                      仅影响 match_results 域的 FIFO 淘汰阈值。
        """
        self._ttl = ttl
        self._max_size = max_size
 # BL-13: per-key TTL for profile cache (avoids cache avalanche)
        self._profile_cache: dict[str, dict[str, list[dict[str, str]]]] = {}
        self._profile_cache_ts: dict[str, float] = {}  # per-key timestamps
        self._match_results: dict[str, dict[str, Any]] = {}
        self._prerequisite_map: dict[str, list[str]] = {}
        self._prereq_cache_ts: float | None = None
        self._lock = threading.Lock()

    def get_profile(self, target_position: str) -> dict[str, list[dict[str, str]]] | None:
        """获取岗位技能画像缓存。

        每个 target_position 有独立的时间戳（per-key TTL），
        过期时仅移除该 key，避免缓存雪崩（BL-13）。

        Args:
            target_position: 目标岗位标识（如 "senior_engineer"）。

        Returns:
            缓存的技能画像字典（key=技能分类, value=技能列表），
            或 None（key 不存在或已过期）。
        """
        with self._lock:
            ts = self._profile_cache_ts.get(target_position)
            if ts is None:
                return None
            now = time.monotonic()
            if (now - ts) >= self._ttl:
 # Per-key TTL expired: remove only this key
                self._profile_cache.pop(target_position, None)
                self._profile_cache_ts.pop(target_position, None)
                return None
            return self._profile_cache.get(target_position)

    def set_profile(
        self, target_position: str, profile: dict[str, list[dict[str, str]]]
    ) -> None:
        """设置岗位技能画像缓存（BL-13: per-key TTL）。

        写入时刷新该 key 的时间戳，过期由 get_profile 按需惰性删除。

        Args:
            target_position: 目标岗位标识。
            profile: 技能画像数据，格式为 {分类名称: [{"name": str, "proficiency": str}, ...]}。
        """
        with self._lock:
            self._profile_cache[target_position] = profile
            self._profile_cache_ts[target_position] = time.monotonic()

    def get_prerequisite_map(self) -> dict[str, list[str]] | None:
        """获取技能前置关系缓存。

        Returns:
            缓存的前置关系映射，或 None（已过期/不存在）
        """
        with self._lock:
            if self._prereq_cache_ts is None:
                return None
            now = time.monotonic()
            if (now - self._prereq_cache_ts) >= self._ttl:
                self._prerequisite_map.clear()
                self._prereq_cache_ts = None
                return None
            return self._prerequisite_map.copy()

    def set_prerequisite_map(self, prereq_map: dict[str, list[str]]) -> None:
        """设置技能前置关系缓存。

        Args:
            prereq_map: 前置关系映射字典
        """
        with self._lock:
            self._prerequisite_map = prereq_map.copy()
            self._prereq_cache_ts = time.monotonic()

    def get_match_result(self, match_id: str) -> dict[str, Any] | None:
        """获取匹配结果缓存。

        匹配结果域无 TTL 过期，仅通过 FIFO 淘汰（set_match_result 时触发）。
        调用方应自行处理结果过期语义。

        Args:
            match_id: 匹配结果唯一标识。

        Returns:
            缓存的匹配结果字典，或 None（不存在）。
        """
        with self._lock:
            return self._match_results.get(match_id)

    def set_match_result(self, match_id: str, result: dict[str, Any]) -> None:
        """设置匹配结果缓存，超出容量时自动 FIFO 淘汰最旧条目。

        匹配结果域无 TTL：条目在被淘汰前一直有效。
        淘汰策略：FIFO（按插入顺序移除最旧条目），单次最多淘汰至 max_size - 1。

        Args:
            match_id: 匹配结果唯一标识。
            result: 匹配结果数据字典（任意 JSON 可序列化结构）。
        """
        with self._lock:
 # FIFO 淘汰：当缓存超过最大大小时，移除最旧的条目
            if len(self._match_results) >= self._max_size:
                excess = len(self._match_results) - self._max_size + 1
                for old_key in list(self._match_results.keys())[:excess]:
                    del self._match_results[old_key]
            self._match_results[match_id] = result

    def clear(self) -> None:
        """清空所有缓存。"""
        with self._lock:
            self._profile_cache.clear()
            self._profile_cache_ts.clear()
            self._match_results.clear()
            self._prerequisite_map.clear()
            self._prereq_cache_ts = None
            logger.info("[MatchCache] All caches cleared")


# 全局缓存实例（单例模式）
_match_cache_instance: MatchCache | None = None


def get_match_cache() -> MatchCache:
    """获取全局 MatchCache 单例实例。

    Returns:
        MatchCache 实例
    """
    global _match_cache_instance
    if _match_cache_instance is None:
        _match_cache_instance = MatchCache()
    return _match_cache_instance


def reset_match_cache() -> None:
    """重置全局缓存实例（主要用于测试）。"""
    global _match_cache_instance
    _match_cache_instance = None
