"""Cost tracker Phase 27 cap tests.

覆盖:
- 默认无 cap 时 is_blocked 始终 False。
- set_model_cap 后 is_blocked 在累计 cost>=cap 时变 True。
- record() 累计 cost 正确;summary() 含 caps 字段。
- 阻断状态时 call_llm_with_fallback 抛 LLMBlockedError(绝不返回 'blocked' dict)。
- response_cache 不缓存空 content 响应。
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.config import settings
from app.core.llm.cost_tracker import tracker


@pytest.fixture(autouse=True)
def _reset_tracker() -> None:
    """每个用例开始时清空 cap + 累计 cost。"""
    tracker.set_model_cap("qwen-plus", 0.0)
    with tracker._lock:
        tracker._by_model.clear()


@pytest.fixture
def fake_redis_fixture(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    fake = MagicMock(name="fake_redis")
    fake.get.return_value = None
    fake.set.return_value = True
    monkeypatch.setattr(
        "app.services.resources.resources",
        MagicMock(redis_client=fake),
    )
    monkeypatch.setattr(settings, "llm_response_cache_enabled", True, raising=False)
    return fake


# ─────────────────────────────────────────────────────────────────
# 基础 record / summary
# ─────────────────────────────────────────────────────────────────


def test_record_accumulates_cost() -> None:
    tracker.record(model="qwen-plus", prompt="abcd", content="efgh")
    summary = tracker.summary()
    assert "qwen-plus" in summary["by_model"]
    bucket = summary["by_model"]["qwen-plus"]
    assert bucket["calls"] == 1.0
    # "abcd" = 4 chars / 4 chars-per-token = 1 input_token
    assert bucket["input_tokens"] == 1.0
    # "efgh" = 4 chars / 4 chars-per-token = 1 output_token
    assert bucket["output_tokens"] == 1.0
    assert bucket["cost_cny"] > 0


def test_summary_includes_caps() -> None:
    tracker.set_model_cap("qwen-plus", 50.0)
    summary = tracker.summary()
    assert summary["caps"] == {"qwen-plus": 50.0}


def test_summary_caps_empty_when_unset() -> None:
    summary = tracker.summary()
    assert summary["caps"] == {}


# ─────────────────────────────────────────────────────────────────
# Cap 控制
# ─────────────────────────────────────────────────────────────────


def test_set_model_cap_zero_disables() -> None:
    tracker.set_model_cap("qwen-plus", 10.0)
    assert tracker.get_model_cap("qwen-plus") == 10.0
    tracker.set_model_cap("qwen-plus", 0.0)
    assert tracker.get_model_cap("qwen-plus") == 0.0


def test_is_blocked_false_when_no_cap() -> None:
    tracker.record(model="qwen-plus", prompt="x" * 1_000_000, content="x" * 1_000_000)
    assert tracker.is_blocked("qwen-plus") is False


def test_is_blocked_true_when_cost_exceeds_cap() -> None:
    tracker.set_model_cap("qwen-plus", 0.0001)
    tracker.record(model="qwen-plus", prompt="x" * 10_000, content="y" * 10_000)
    assert tracker.is_blocked("qwen-plus") is True


def test_record_blocks_further_calls_after_cap() -> None:
    """累计 cost 超过 cap 后,call_llm_with_fallback 应返回 blocked(已被
    test_call_llm_with_fallback_returns_blocked_when_capped 覆盖);此处验证
    record() 自身在 cap 触发后仍能正常累计 + is_blocked 持续为 True。
    """
    tracker.set_model_cap("qwen-plus", 0.0001)
    tracker.record(model="qwen-plus", prompt="x" * 10_000, content="y" * 10_000)
    assert tracker.is_blocked("qwen-plus") is True
    # 再 record 仍正常累计(不抛异常)
    tracker.record(model="qwen-plus", prompt="a", content="b")
    assert tracker.is_blocked("qwen-plus") is True


# ─────────────────────────────────────────────────────────────────
# 与 call_llm_with_fallback 集成
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_call_llm_with_fallback_returns_blocked_when_capped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """cap 触发时不再调任何 provider,抛 LLMBlockedError。"""
    from app.core.extraction import llm_client

    monkeypatch.setattr(settings, "llm_response_cache_enabled", False, raising=False)
    tracker.set_model_cap(settings.dashscope_model, 0.0001)
    tracker.record(
        model=settings.dashscope_model,
        prompt="x" * 10_000,
        content="y" * 10_000,
    )
    assert tracker.is_blocked(settings.dashscope_model)

    # 配齐 dashscope key 但 monkey-patch 后 provider 函数体不应执行
    monkeypatch.setattr(settings, "dashscope_api_key", "fake-key", raising=False)
    monkeypatch.setattr(settings, "xunfei_api_key", "", raising=False)
    monkeypatch.setattr(settings, "deepseek_api_key", "", raising=False)
    monkeypatch.setattr(settings, "mimo_api_key", "", raising=False)
    monkeypatch.setattr(settings, "qwen_model_path", "", raising=False)

    call_dashscope_called = MagicMock(side_effect=AssertionError("dashscope should not run"))
    monkeypatch.setattr(llm_client, "call_dashscope_llm", call_dashscope_called)

    with pytest.raises(llm_client.LLMBlockedError, match="cost cap"):
        await llm_client.call_llm_with_fallback("any prompt")
    call_dashscope_called.assert_not_called()


# ─────────────────────────────────────────────────────────────────
# response_cache 不缓存 blocked
# ─────────────────────────────────────────────────────────────────


def test_response_cache_skips_blocked_payload(fake_redis_fixture: MagicMock) -> None:
    from app.core.llm import response_cache as rc

    rc.response_cache.set(
        "qwen-plus",
        "p",
        {"role": "assistant", "content": "", "model": "blocked"},
    )
    fake_redis_fixture.set.assert_not_called()


def test_response_cache_skips_empty_content(fake_redis_fixture: MagicMock) -> None:
    from app.core.llm import response_cache as rc

    rc.response_cache.set(
        "qwen-plus",
        "p",
        {"role": "assistant", "content": "", "model": "qwen-plus"},
    )
    fake_redis_fixture.set.assert_not_called()
