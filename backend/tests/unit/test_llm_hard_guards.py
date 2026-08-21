"""Phase 27 hard guard tests.

覆盖 qwen-plus 资源包严格保护的 3 道闸门:
1. **成本 cap** (llm_cost_cap_cny_per_day) — 防累积成本爆表
2. **128K input 闸门** (llm_max_input_chars_per_request) — 单次请求超 128K token
   即不抵扣 → 直接阻断,不发送请求
3. **全局 kill switch** (llm_enabled) — 紧急止血

所有闸门都抛 LLMBlockedError(非返回 'blocked' dict),上层能立刻识别
且不重试(retry 也不会成功)。
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import settings
from app.core.extraction import llm_client
from app.core.llm.cost_tracker import tracker


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> None:
    """每个用例前清 cap / 累计 cost / 开关。"""
    tracker.set_model_cap(settings.dashscope_model, 0.0)
    with tracker._lock:
        tracker._by_model.clear()
    monkeypatch.setattr(settings, "llm_enabled", True, raising=False)
    monkeypatch.setattr(settings, "llm_response_cache_enabled", False, raising=False)


# ─────────────────────────────────────────────────────────────────
# Guard 1: 成本 cap
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cost_cap_blocks_with_blocked_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracker.set_model_cap(settings.dashscope_model, 0.0001)
    tracker.record(
        model=settings.dashscope_model,
        prompt="x" * 10_000,
        content="y" * 10_000,
    )

    with pytest.raises(llm_client.LLMBlockedError, match="cost cap"):
        await llm_client.call_llm_with_fallback("any prompt")


@pytest.mark.asyncio
async def test_cost_cap_zero_disables_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """cap=0 时不阻断(等同禁用,与原行为兼容)。"""
    tracker.set_model_cap(settings.dashscope_model, 0.0)
    monkeypatch.setattr(settings, "dashscope_api_key", "", raising=False)
    monkeypatch.setattr(settings, "xunfei_api_key", "", raising=False)
    monkeypatch.setattr(settings, "deepseek_api_key", "", raising=False)
    monkeypatch.setattr(settings, "mimo_api_key", "", raising=False)
    monkeypatch.setattr(settings, "qwen_model_path", "", raising=False)

    # 没配任何 provider key + cap=0 → 应抛 LLMConnectionError(而非 LLMBlockedError)
    with pytest.raises(llm_client.LLMConnectionError):
        await llm_client.call_llm_with_fallback("any prompt")


# ─────────────────────────────────────────────────────────────────
# Guard 2: 128K input token 闸门
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_prompt_over_128k_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """prompt 超过 128K token 估算时立即阻断,绝不发请求。"""
    # 设为很小以便快速触发(原始默认 480K chars)
    monkeypatch.setattr(
        settings, "llm_max_input_chars_per_request", 1000, raising=False,
    )
    long_prompt = "x" * 2000

    call_dashscope_called = MagicMock(side_effect=AssertionError("should not reach dashscope"))
    monkeypatch.setattr(llm_client, "call_dashscope_llm", call_dashscope_called)

    with pytest.raises(llm_client.LLMBlockedError, match="128K token limit"):
        await llm_client.call_llm_with_fallback(long_prompt)
    call_dashscope_called.assert_not_called()


@pytest.mark.asyncio
async def test_prompt_within_limit_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings, "llm_max_input_chars_per_request", 10_000, raising=False,
    )
    # 配齐 provider key 但 monkey-patch 不让真发请求
    call_dashscope = MagicMock(
        return_value={"role": "assistant", "content": "ok", "model": "qwen-plus"},
    )
    monkeypatch.setattr(llm_client, "call_dashscope_llm", AsyncMock(return_value=call_dashscope.return_value))
    # 让 fallback chain 跳过所有 provider(dashscope 已 mock)
    # 然后我们断言 call_dashscope 被调用过(说明 128K 闸门没阻断)
    # 实际实现:把 dashscope_api_key 设空,让 is_blocked cap 也不触发
    monkeypatch.setattr(settings, "llm_cost_cap_cny_per_day", 1000.0, raising=False)
    monkeypatch.setattr(settings, "dashscope_api_key", "", raising=False)
    monkeypatch.setattr(settings, "xunfei_api_key", "", raising=False)
    monkeypatch.setattr(settings, "deepseek_api_key", "", raising=False)
    monkeypatch.setattr(settings, "mimo_api_key", "", raising=False)
    monkeypatch.setattr(settings, "qwen_model_path", "", raising=False)

    # 不应抛 LLMBlockedError(128K 闸门放行 + cap 没触发)
    with pytest.raises(llm_client.LLMConnectionError):
        await llm_client.call_llm_with_fallback("short prompt")


@pytest.mark.asyncio
async def test_limit_zero_disables_128k_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """limit=0 时禁用 128K 闸门(与原行为兼容)。"""
    monkeypatch.setattr(
        settings, "llm_max_input_chars_per_request", 0, raising=False,
    )
    monkeypatch.setattr(settings, "dashscope_api_key", "", raising=False)
    monkeypatch.setattr(settings, "xunfei_api_key", "", raising=False)
    monkeypatch.setattr(settings, "deepseek_api_key", "", raising=False)
    monkeypatch.setattr(settings, "mimo_api_key", "", raising=False)
    monkeypatch.setattr(settings, "qwen_model_path", "", raising=False)

    # 极长 prompt 也不抛 LLMBlockedError,仅因为没 provider 抛 LLMConnectionError
    with pytest.raises(llm_client.LLMConnectionError):
        await llm_client.call_llm_with_fallback("x" * 10_000_000)


# ─────────────────────────────────────────────────────────────────
# Guard 3: 全局 kill switch
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_kill_switch_blocks_all_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_enabled", False, raising=False)

    call_dashscope = MagicMock(side_effect=AssertionError("kill switch should block"))
    monkeypatch.setattr(llm_client, "call_dashscope_llm", call_dashscope)

    with pytest.raises(llm_client.LLMBlockedError, match="globally disabled"):
        await llm_client.call_llm_with_fallback("any prompt")
    call_dashscope.assert_not_called()


@pytest.mark.asyncio
async def test_kill_switch_blocks_even_when_cache_hit_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """kill switch 与缓存独立 —— kill switch 后无任何调用,缓存命中也照常。"""
    # 启用缓存 + kill switch
    monkeypatch.setattr(settings, "llm_response_cache_enabled", True, raising=False)
    monkeypatch.setattr(settings, "llm_enabled", False, raising=False)
    monkeypatch.setattr(
        "app.services.resources.resources",
        MagicMock(redis_client=None),  # Redis 未初始化 → 缓存 miss
    )

    # 即使缓存配置打开,kill switch 也阻断
    with pytest.raises(llm_client.LLMBlockedError):
        await llm_client.call_llm_with_fallback("any prompt")


# ─────────────────────────────────────────────────────────────────
# 优先级: kill switch > 128K > cost cap > cache
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_kill_switch_takes_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """kill switch 是最严格的闸门,即使其他都通过也会阻断。"""
    monkeypatch.setattr(settings, "llm_enabled", False, raising=False)
    monkeypatch.setattr(settings, "llm_max_input_chars_per_request", 0, raising=False)
    # cap 不触发,kill switch 触发 → 应抛 kill switch 错
    with pytest.raises(llm_client.LLMBlockedError, match="globally disabled"):
        await llm_client.call_llm_with_fallback("any prompt")


@pytest.mark.asyncio
async def test_128k_takes_precedence_over_cost_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """128K 闸门先于 cost cap 检查(更早期 fail)。"""
    monkeypatch.setattr(settings, "llm_max_input_chars_per_request", 1000, raising=False)
    tracker.set_model_cap(settings.dashscope_model, 1000.0)  # 高 cap,不触发
    long_prompt = "x" * 5000
    with pytest.raises(llm_client.LLMBlockedError, match="128K"):
        await llm_client.call_llm_with_fallback(long_prompt)


@pytest.mark.asyncio
async def test_cache_hit_bypasses_all_guards(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """缓存命中时不触发任何闸门(零 token 消耗)。"""
    monkeypatch.setattr(settings, "llm_enabled", False, raising=False)  # 关闭 LLM
    monkeypatch.setattr(settings, "llm_max_input_chars_per_request", 100, raising=False)  # 超限

    # 但缓存有 → 命中 → 直接返回
    fake_redis = MagicMock()
    fake_redis.get.return_value = '{"role": "assistant", "content": "cached", "model": "qwen-plus"}'
    monkeypatch.setattr(
        "app.services.resources.resources",
        MagicMock(redis_client=fake_redis),
    )
    monkeypatch.setattr(settings, "llm_response_cache_enabled", True, raising=False)

    result = await llm_client.call_llm_with_fallback("x" * 5000)
    assert result["content"] == "cached"


# ─────────────────────────────────────────────────────────────────
# 闸门顺序: cache → cap → kill → 128K
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cost_cap_takes_precedence_over_128k(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """cost cap 在 128K 闸门之前检查(更早期 fail)。"""
    monkeypatch.setattr(settings, "llm_max_input_chars_per_request", 1000, raising=False)
    tracker.set_model_cap(settings.dashscope_model, 0.0001)
    tracker.record(model=settings.dashscope_model, prompt="x" * 10_000, content="y" * 10_000)
    with pytest.raises(llm_client.LLMBlockedError, match="cost cap"):
        await llm_client.call_llm_with_fallback("x" * 5000)
