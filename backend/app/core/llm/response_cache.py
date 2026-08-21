"""LLM response cache — Redis-backed, cross-process, opt-in.

Phase 27 (qwen-plus resource pack tuning, 2026-08-20): 相同 (model, prompt)
的 LLM 响应按 sha256 缓存到 Redis,跨 Celery worker / API 进程共享,eval 续跑
与 reseed 场景下命中率 50%+。Redis 故障时优雅降级,不影响 LLM 调用。

设计要点:
- 命名空间 `llm:resp:{model}:{sha256(prompt)}`,避免与现有 `dashboard:*` / `resume-extract:*`
  / `pipeline:*` / `ab:*` 冲突 (resources.py:58 + 完整 cache key 列表见
  services/resume_service.py:18 + dashboard_service.py:36 等)。
- 优雅降级:任何 Redis 异常仅 warning 日志,调用直接 fall-through,
  与 resume_service._read_resume_cache (services/resume_service.py:159) 同模式。
- 单进程配置:不持有连接,直接复用全局 redis_client
  (services/resources.py:58, decode_responses=True)。
- TTL 默认 7 天 (eval/reseed 续跑覆盖即可)。

2026-08-21 修复: resources.redis_client 是 `redis.asyncio.Redis`(异步客户端),
其 get/set 是协程 —— 此前同步调用返回未 await 的 coroutine,get 永远 miss
(set 写入也从没生效),且每个调用泄漏一个 "coroutine was never awaited"
RuntimeWarning。改为在调用方已运行的 event loop 上 `asyncio.run_coroutine_threadsafe`
等待结果;无可用 loop 时静默降级为 miss(保持 graceful degradation 承诺)。

不做的事:
- 不缓存 `model="blocked"` / `content=""` 的阻断响应(避免污染后续正常调用)。
- 不主动 invalidate (prompt-template 改版由调用方用版本前缀区分或自然 TTL 过期)。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

from loguru import logger

from app.config import settings

CACHE_PREFIX = "llm:resp:"
DEFAULT_TTL_SECONDS = 7 * 24 * 3600  # 7 天


def make_cache_key(model: str, prompt: str) -> str:
    """Cache key = `{prefix}{model}:{sha256(prompt)}`.

    模型名参与 key:不同模型的响应不可互换 (qwen-plus vs qwen2.5:7b 不同)。
    """
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    return f"{CACHE_PREFIX}{model}:{prompt_hash}"


def _run_in_loop(coro: Any, timeout: float = 2.0) -> Any:
    """在调用方 event loop 上同步等待一个协程的结果。

    兼容三种上下文:
    - 已在运行 loop 的线程(async 上下文/Celery task): thread-safe 提交 + 等待。
    - 无 loop 的同步上下文: 临时 loop run_until_complete(兼容测试)。
    - 非协程入参(测试 mock 直接返回值的 redis_client): 原样返回。
    任何异常/超时 → 返回 None(graceful degradation)。
    """
    if not asyncio.iscoroutine(coro):
        # 测试/降级路径:mock 的 redis.get() 直接返回值而非协程
        return coro
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        try:
            return asyncio.run(asyncio.wait_for(coro, timeout=timeout))
        except Exception:  # noqa: BLE001
            return None
    if loop.is_running():
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        try:
            return future.result(timeout=timeout)
        except Exception:  # noqa: BLE001
            future.cancel()
            return None
    try:
        return asyncio.run(asyncio.wait_for(coro, timeout=timeout))
    except Exception:  # noqa: BLE001
        return None


class LLMResponseCache:
    """Module-level helper; instantiating is cheap and stateless."""

    def __init__(self) -> None:
        self._ttl: int = DEFAULT_TTL_SECONDS

    def configure_ttl(self, ttl_seconds: int) -> None:
        """Override default TTL (used by settings-driven config)."""
        self._ttl = max(ttl_seconds, 60)

    def get(self, model: str, prompt: str) -> dict[str, Any] | None:
        """Read cached response. Returns dict or None on miss / Redis fault.

        Never raises; Redis errors logged at warning and treated as miss.
        同步入口：用于无 event loop 的上下文（测试）。async 上下文请用 aget
        （否则 run_coroutine_threadsafe 会因 loop 被当前协程占用而超时）。
        """
        if not settings.llm_response_cache_enabled:
            return None
        try:
            from app.services.resources import resources

            redis = resources.redis_client
            if redis is None:
                return None
            key = make_cache_key(model, prompt)
            raw = _run_in_loop(redis.get(key))
            return self._decode(raw)
        except Exception as exc:  # noqa: BLE001 — graceful degradation
            logger.warning("LLM response cache GET fault (fall-through): {}", exc)
            return None

    async def aget(self, model: str, prompt: str) -> dict[str, Any] | None:
        """Async read: 在调用方 event loop 上直接 await Redis（推荐路径）。

        2026-08-21: call_llm_with_fallback 在 celery worker 的 loop 内运行，
        同步 get() 的 run_coroutine_threadsafe 会死锁（loop 被当前协程占用）→
        每次调用白等 2s 超时且永远 miss。改用本方法 await 即可正确命中。
        """
        if not settings.llm_response_cache_enabled:
            return None
        try:
            from app.services.resources import resources

            redis = resources.redis_client
            if redis is None:
                return None
            key = make_cache_key(model, prompt)
            raw = redis.get(key)
            if asyncio.iscoroutine(raw):
                raw = await raw
            return self._decode(raw)
        except Exception as exc:  # noqa: BLE001 — graceful degradation
            logger.warning("LLM response cache GET fault (fall-through): {}", exc)
            return None

    @staticmethod
    def _decode(raw: Any) -> dict[str, Any] | None:
        if not raw:
            return None
        try:
            data = json.loads(raw)
            # 容错:任何结构性缺失都视为 miss
            if not isinstance(data, dict) or "content" not in data:
                return None
            return data
        except (TypeError, ValueError):
            return None

    def set(self, model: str, prompt: str, response: dict[str, Any]) -> None:
        """Write response to cache. No-op on Redis fault or empty content.

        不缓存空 content (parse_llm_json_response 失败的脏响应) 与 model="blocked"
        (cost cap 触发的阻断响应),避免污染后续命中。
        同步入口：用于无 event loop 的上下文（测试）。async 上下文请用 aset。
        """
        if not settings.llm_response_cache_enabled:
            return
        content = response.get("content")
        model_name = response.get("model", "")
        if not content or model_name == "blocked":
            return
        try:
            from app.services.resources import resources

            redis = resources.redis_client
            if redis is None:
                return
            key = make_cache_key(model, prompt)
            ttl = self._ttl if self._ttl > 0 else DEFAULT_TTL_SECONDS
            _run_in_loop(redis.set(key, json.dumps(response, ensure_ascii=False, default=str), ex=ttl))
        except Exception as exc:  # noqa: BLE001 — graceful degradation
            logger.warning("LLM response cache SET fault (ignored): {}", exc)

    async def aset(self, model: str, prompt: str, response: dict[str, Any]) -> None:
        """Async write: 在调用方 event loop 上直接 await Redis（推荐路径）。"""
        if not settings.llm_response_cache_enabled:
            return
        content = response.get("content")
        model_name = response.get("model", "")
        if not content or model_name == "blocked":
            return
        try:
            from app.services.resources import resources

            redis = resources.redis_client
            if redis is None:
                return
            key = make_cache_key(model, prompt)
            ttl = self._ttl if self._ttl > 0 else DEFAULT_TTL_SECONDS
            result = redis.set(key, json.dumps(response, ensure_ascii=False, default=str), ex=ttl)
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:  # noqa: BLE001 — graceful degradation
            logger.warning("LLM response cache SET fault (ignored): {}", exc)


# 模块级单例 (类似 cost_tracker.tracker)
response_cache = LLMResponseCache()
