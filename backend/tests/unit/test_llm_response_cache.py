"""LLM response cache unit tests (Phase 27).

覆盖:
- Redis 命中:不调用 provider,直接返回缓存响应,且计入 cost tracker。
- Redis 未命中:set 后下次 get 命中。
- Redis 故障:GET/SET 抛异常 → 不传播,降级为未命中。
- 关闭开关 (settings.llm_response_cache_enabled=False):完全旁路。
- 空 content / model=blocked 响应:不被写入缓存。
- TTL 配置:configure_ttl 生效。
- cache key 唯一性:不同 prompt 或 model 互不影响。
- 与 call_llm_with_fallback 的端到端集成(monkey-patch redis_client)。
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.config import settings
from app.core.llm import response_cache as cache_mod


@pytest.fixture(autouse=True)
def _reset_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_response_cache_enabled", True, raising=False)


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Inject a fake redis_client into resources."""
    fake = MagicMock(name="fake_redis_client")
    fake.get.return_value = None  # default miss
    fake.set.return_value = True
    monkeypatch.setattr(
        "app.services.resources.resources",
        MagicMock(redis_client=fake),
    )
    return fake


# ─────────────────────────────────────────────────────────────────
# Key 生成
# ─────────────────────────────────────────────────────────────────


def test_make_cache_key_stable() -> None:
    k1 = cache_mod.make_cache_key("qwen-plus", "hello")
    k2 = cache_mod.make_cache_key("qwen-plus", "hello")
    assert k1 == k2


def test_make_cache_key_includes_model() -> None:
    a = cache_mod.make_cache_key("qwen-plus", "x")
    b = cache_mod.make_cache_key("qwen2.5:7b-fallback", "x")
    assert a != b


def test_make_cache_key_includes_prompt() -> None:
    a = cache_mod.make_cache_key("qwen-plus", "alpha")
    b = cache_mod.make_cache_key("qwen-plus", "beta")
    assert a != b


def test_make_cache_key_prefix() -> None:
    assert cache_mod.make_cache_key("m", "p").startswith(cache_mod.CACHE_PREFIX)


# ─────────────────────────────────────────────────────────────────
# 命中/未命中路径
# ─────────────────────────────────────────────────────────────────


def test_get_returns_none_when_disabled(monkeypatch: pytest.MonkeyPatch, fake_redis: MagicMock) -> None:
    monkeypatch.setattr(settings, "llm_response_cache_enabled", False, raising=False)
    fake_redis.get.return_value = '{"role": "assistant", "content": "x", "model": "qwen-plus"}'
    assert cache_mod.response_cache.get("qwen-plus", "p") is None
    fake_redis.get.assert_not_called()


def test_get_returns_none_when_redis_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.resources.resources",
        MagicMock(redis_client=None),
    )
    assert cache_mod.response_cache.get("qwen-plus", "p") is None


def test_get_returns_dict_on_hit(fake_redis: MagicMock) -> None:
    payload = '{"role": "assistant", "content": "cached", "model": "qwen-plus"}'
    fake_redis.get.return_value = payload
    result = cache_mod.response_cache.get("qwen-plus", "p")
    assert result == {"role": "assistant", "content": "cached", "model": "qwen-plus"}
    fake_redis.get.assert_called_once()


def test_get_returns_none_on_redis_exception(fake_redis: MagicMock) -> None:
    fake_redis.get.side_effect = ConnectionError("redis down")
    assert cache_mod.response_cache.get("qwen-plus", "p") is None  # 不传播


def test_get_returns_none_on_corrupt_payload(fake_redis: MagicMock) -> None:
    fake_redis.get.return_value = "not-json"
    assert cache_mod.response_cache.get("qwen-plus", "p") is None


def test_get_returns_none_on_missing_content_field(fake_redis: MagicMock) -> None:
    fake_redis.get.return_value = '{"role": "assistant", "model": "qwen-plus"}'
    assert cache_mod.response_cache.get("qwen-plus", "p") is None


# ─────────────────────────────────────────────────────────────────
# Set 路径
# ─────────────────────────────────────────────────────────────────


def test_set_writes_payload(fake_redis: MagicMock) -> None:
    resp = {"role": "assistant", "content": "ok", "model": "qwen-plus"}
    cache_mod.response_cache.set("qwen-plus", "p", resp)
    fake_redis.set.assert_called_once()
    call_kwargs = fake_redis.set.call_args.kwargs
    assert call_kwargs["ex"] == cache_mod.DEFAULT_TTL_SECONDS


def test_set_skips_when_disabled(monkeypatch: pytest.MonkeyPatch, fake_redis: MagicMock) -> None:
    monkeypatch.setattr(settings, "llm_response_cache_enabled", False, raising=False)
    cache_mod.response_cache.set("qwen-plus", "p", {"content": "ok", "model": "qwen-plus"})
    fake_redis.set.assert_not_called()


def test_set_skips_empty_content(fake_redis: MagicMock) -> None:
    cache_mod.response_cache.set("qwen-plus", "p", {"content": "", "model": "qwen-plus"})
    fake_redis.set.assert_not_called()


def test_set_skips_blocked_model(fake_redis: MagicMock) -> None:
    cache_mod.response_cache.set("qwen-plus", "p", {"content": "x", "model": "blocked"})
    fake_redis.set.assert_not_called()


def test_set_handles_redis_exception(fake_redis: MagicMock) -> None:
    fake_redis.set.side_effect = ConnectionError("redis down")
    cache_mod.response_cache.set("qwen-plus", "p", {"content": "ok", "model": "qwen-plus"})  # 不传播


def test_configure_ttl_overrides_default(fake_redis: MagicMock) -> None:
    cache_mod.response_cache.configure_ttl(3600)
    cache_mod.response_cache.set("qwen-plus", "p", {"content": "ok", "model": "qwen-plus"})
    assert fake_redis.set.call_args.kwargs["ex"] == 3600


def test_configure_ttl_floors_at_60(fake_redis: MagicMock) -> None:
    cache_mod.response_cache.configure_ttl(10)  # 太短
    cache_mod.response_cache.set("qwen-plus", "p", {"content": "ok", "model": "qwen-plus"})
    assert fake_redis.set.call_args.kwargs["ex"] == 60


# ─────────────────────────────────────────────────────────────────
# 端到端: call_llm_with_fallback + 缓存
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_call_llm_with_fallback_uses_cache_on_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """缓存命中时不应触发任何 provider 调用。"""
    from app.core.extraction import llm_client

    fake_redis = MagicMock()
    fake_redis.get.return_value = (
        '{"role": "assistant", "content": "{\\"position_name\\": \\"x\\"}", '
        '"model": "qwen-plus"}'
    )
    monkeypatch.setattr(
        "app.services.resources.resources",
        MagicMock(redis_client=fake_redis),
    )

    # 任何 provider 都不应被调用
    call_dashscope_called = MagicMock(side_effect=AssertionError("dashscope should not run"))
    monkeypatch.setattr(llm_client, "call_dashscope_llm", call_dashscope_called)

    result = await llm_client.call_llm_with_fallback("any prompt")
    assert result["content"] == '{"position_name": "x"}'
    assert result["model"] == "qwen-plus"
    call_dashscope_called.assert_not_called()


@pytest.mark.asyncio
async def test_call_llm_with_fallback_skips_cache_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """缓存关闭时走 fallback chain(已有行为不变)。"""
    from app.core.extraction import llm_client

    monkeypatch.setattr(settings, "llm_response_cache_enabled", False, raising=False)
    fake_redis = MagicMock()
    fake_redis.get.return_value = (
        '{"role": "assistant", "content": "should not be returned", '
        '"model": "qwen-plus"}'
    )
    monkeypatch.setattr(
        "app.services.resources.resources",
        MagicMock(redis_client=fake_redis),
    )

    # dashscope 没设 api_key → 跳过;ollama endpoint 没设 → 抛 LLMConnectionError
    monkeypatch.setattr(settings, "dashscope_api_key", "", raising=False)
    monkeypatch.setattr(settings, "qwen_model_path", "", raising=False)
    monkeypatch.setattr(settings, "xunfei_api_key", "", raising=False)
    monkeypatch.setattr(settings, "deepseek_api_key", "", raising=False)
    monkeypatch.setattr(settings, "mimo_api_key", "", raising=False)

    with pytest.raises(llm_client.LLMConnectionError):
        await llm_client.call_llm_with_fallback("any prompt")

    fake_redis.get.assert_not_called()


@pytest.mark.asyncio
async def test_call_llm_with_fallback_redis_failure_still_calls_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Redis GET 抛异常时不传播,继续走 fallback chain。"""
    from app.core.extraction import llm_client

    fake_redis = MagicMock()
    fake_redis.get.side_effect = ConnectionError("redis flap")
    fake_redis.set.return_value = True
    monkeypatch.setattr(
        "app.services.resources.resources",
        MagicMock(redis_client=fake_redis),
    )
    monkeypatch.setattr(settings, "dashscope_api_key", "", raising=False)
    monkeypatch.setattr(settings, "xunfei_api_key", "", raising=False)
    monkeypatch.setattr(settings, "deepseek_api_key", "", raising=False)
    monkeypatch.setattr(settings, "mimo_api_key", "", raising=False)
    monkeypatch.setattr(settings, "qwen_model_path", "", raising=False)

    with pytest.raises(llm_client.LLMConnectionError):
        await llm_client.call_llm_with_fallback("any prompt")
    # 调用方不应被 Redis 异常连累(进入 fallback chain 报"未配置 provider"错)


# ─────────────────────────────────────────────────────────────────
# 2026-08-21: _run_in_loop 兼容性 (异步客户端修复)
# ─────────────────────────────────────────────────────────────────


def test_run_in_loop_sync_context() -> None:
    """无 event loop 的同步上下文: asyncio.run 路径。"""

    async def _coro() -> str:
        return "ok"

    assert cache_mod._run_in_loop(_coro()) == "ok"


def test_run_in_loop_non_coroutine_passthrough() -> None:
    """非协程入参(mock 直接返回值)原样返回。"""
    assert cache_mod._run_in_loop("plain-value") == "plain-value"


def test_run_in_loop_coroutine_raising_returns_none() -> None:
    """协程抛异常 → 降级为 None,不传播。"""

    async def _bad() -> str:
        raise RuntimeError("boom")

    assert cache_mod._run_in_loop(_bad()) is None


@pytest.mark.asyncio
async def test_aget_hits_real_async_client() -> None:
    """aget 在 async 上下文 await 真实异步客户端(此前同步 get 死锁/永不命中)。"""


    payload = '{"role": "assistant", "content": "cached", "model": "qwen-plus"}'
    fake_redis = MagicMock()

    async def _get(_key: str) -> str:
        return payload

    fake_redis.get.side_effect = _get
    monkeypatch = __import__("pytest").MonkeyPatch()
    monkeypatch.setattr("app.services.resources.resources", MagicMock(redis_client=fake_redis))
    try:
        hit = await cache_mod.response_cache.aget("qwen-plus", "p")
        assert hit == {"role": "assistant", "content": "cached", "model": "qwen-plus"}
    finally:
        monkeypatch.undo()


@pytest.mark.asyncio
async def test_aset_awaits_real_async_client() -> None:
    """aset 在 async 上下文 await 真实异步客户端(同步 set 会泄漏协程)。"""

    fake_redis = MagicMock()

    async def _set(*_a: object, **_kw: object) -> bool:
        return True

    fake_redis.set.side_effect = _set
    monkeypatch = __import__("pytest").MonkeyPatch()
    monkeypatch.setattr("app.services.resources.resources", MagicMock(redis_client=fake_redis))
    try:
        await cache_mod.response_cache.aset(
            "qwen-plus", "p", {"role": "assistant", "content": "ok", "model": "qwen-plus"}
        )
        fake_redis.set.assert_called_once()
    finally:
        monkeypatch.undo()
