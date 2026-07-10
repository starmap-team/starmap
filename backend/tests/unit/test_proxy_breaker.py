"""PIPE-02 D-02 验收：熔断行为契约。"""
import time

from crawler.middleware.proxy_middleware import (
    _BREAKER_STATE,
    FAIL_THRESHOLD,
    _parse_proxy,
    load_proxies,
    pick_proxy,
    record_proxy_failure,
    record_proxy_success,
    reset_for_tests,
)


def test_parse_proxy_basic():
    e = _parse_proxy("http://1.2.3.4:8080")
    assert e is not None
    assert e.host == "1.2.3.4"
    assert e.port == 8080
    assert e.scheme == "http"
    assert e.user is None and e.password is None


def test_parse_proxy_with_auth():
    e = _parse_proxy("http://user:pass@5.6.7.8:3128")
    assert e is not None
    assert e.host == "5.6.7.8"
    assert e.port == 3128
    assert e.user == "user"
    assert e.password == "pass"


def test_parse_proxy_invalid_returns_none():
    assert _parse_proxy("not-a-url") is None
    assert _parse_proxy("") is None
    assert _parse_proxy("http://no-port") is None


def test_pick_proxy_cycles(monkeypatch):
    """3 个代理池 — pick_proxy 6 次应轮询覆盖所有 3 个。"""
    reset_for_tests()
    monkeypatch.setenv("PROXY_LIST", "http://p1:8080,http://p2:8080,http://p3:8080")
    seen = set()
    for _ in range(6):
        p = pick_proxy()
        seen.add(p)
    assert seen == {"http://p1:8080", "http://p2:8080", "http://p3:8080"}


def test_breaker_opens_after_threshold(monkeypatch):
    """单代理触发 3 次失败后, pick_proxy 返回 None（直连 fallback）。"""
    reset_for_tests()
    monkeypatch.setenv("PROXY_LIST", "http://only:8080")
    proxy = pick_proxy()
    assert proxy == "http://only:8080"
    # 触发 3 次失败（达到 FAIL_THRESHOLD）
    for _ in range(FAIL_THRESHOLD):
        record_proxy_failure(proxy)
    # 冷却生效 — pick_proxy 应返回 None
    assert pick_proxy() is None


def test_success_resets_failure_count(monkeypatch):
    """2 次失败（未达阈值）+ 1 次成功 + 1 次失败 → 不触发冷却。"""
    reset_for_tests()
    monkeypatch.setenv("PROXY_LIST", "http://x:8080")
    proxy = pick_proxy()
    # 2 次失败
    record_proxy_failure(proxy)
    record_proxy_failure(proxy)
    # 1 次成功 — 重置计数器
    record_proxy_success(proxy)
    # 1 次失败 — 累计仅 1（远未达 3）
    record_proxy_failure(proxy)
    # 仍然可用
    assert pick_proxy() == proxy


def test_no_env_returns_none(monkeypatch):
    """PROXY_LIST 未设置 — pick_proxy 返回 None（直连 + WARN 日志）。"""
    reset_for_tests()
    monkeypatch.delenv("PROXY_LIST", raising=False)
    assert load_proxies() == []
    assert pick_proxy() is None


def test_partial_failure_does_not_open_breaker(monkeypatch):
    """2 次失败（< 阈值 3）后 pick_proxy 仍返回该代理。"""
    reset_for_tests()
    monkeypatch.setenv("PROXY_LIST", "http://only:8080")
    proxy = pick_proxy()
    assert proxy is not None
    record_proxy_failure(proxy)
    record_proxy_failure(proxy)
    breaker = _BREAKER_STATE.get(proxy)
    assert breaker is not None
    assert breaker.fail_count == 2
    assert breaker.cooldown_until == 0  # 仍未冷却
    assert breaker.is_open(time.monotonic()) is False
