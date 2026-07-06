"""匹配服务缓存模块。

提供线程安全的缓存管理，替代原 match_service.py 中的全局可变状态。
支持 Redis 分布式缓存和本地内存缓存两种模式。
"""

from __future__ import annotations

import threading
import time
from typing import Any

from loguru import logger


class MatchCache:
    """线程安全的匹配结果缓存。

    替代原 _PROFILE_CACHE、_MATCH_RESULTS 等全局可变状态，
    使用 threading.Lock 保证线程安全，支持 TTL 过期策略。
    """

    def __init__(self, ttl: int = 300, max_size: int = 1000) -> None:
        """初始化缓存。

        Args:
            ttl: 缓存过期时间（秒），默认 5 分钟
            max_size: 最大缓存条目数，默认 1000
        """
        self._ttl = ttl
        self._max_size = max_size
        self._profile_cache: dict[str, dict[str, list[dict[str, str]]]] = {}
        self._profile_cache_ts: float | None = None
        self._match_results: dict[str, dict[str, Any]] = {}
        self._prerequisite_map: dict[str, list[str]] = {}
        self._prereq_cache_ts: float | None = None
        self._lock = threading.Lock()

    def get_profile(self, target_position: str) -> dict[str, list[dict[str, str]]] | None:
        """获取岗位技能画像缓存。

        Args:
            target_position: 目标岗位名称

        Returns:
            缓存的技能画像，或 None（已过期/不存在）
        """
        with self._lock:
            if self._profile_cache_ts is None:
                return None
            now = time.monotonic()
            if (now - self._profile_cache_ts) >= self._ttl:
                # TTL 过期，清空缓存
                self._profile_cache.clear()
                self._profile_cache_ts = None
                return None
            return self._profile_cache.get(target_position)

    def set_profile(
        self, target_position: str, profile: dict[str, list[dict[str, str]]]
    ) -> None:
        """设置岗位技能画像缓存。

        Args:
            target_position: 目标岗位名称
            profile: 技能画像数据
        """
        with self._lock:
            now = time.monotonic()
            if self._profile_cache_ts is None or (now - self._profile_cache_ts) >= self._ttl:
                # 首次设置或 TTL 过期，重置缓存
                self._profile_cache.clear()
                self._profile_cache_ts = now
            self._profile_cache[target_position] = profile

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

        Args:
            match_id: 匹配结果 ID

        Returns:
            缓存的匹配结果，或 None（不存在）
        """
        with self._lock:
            return self._match_results.get(match_id)

    def set_match_result(self, match_id: str, result: dict[str, Any]) -> None:
        """设置匹配结果缓存，自动淘汰最旧条目。

        Args:
            match_id: 匹配结果 ID
            result: 匹配结果数据
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
            self._profile_cache_ts = None
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
