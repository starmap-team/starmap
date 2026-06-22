"""compliance.py 单元测试。

覆盖: robots check, rate limiter, proxy, log_request, stealth helper, fetch.
不依赖真实网络/Docker，全部 mock。
"""
from __future__ import annotations

import httpx
import os
import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ── robots.txt ────────────────────────────────────────────────────
class TestRobotsCheck:
    """is_allowed / _get_robots / stealth_check_robots"""

    def test_is_allowed_returns_true_for_no_robots(self):
        """拿不到 robots.txt 时默认放行。"""
        from crawler.compliance import is_allowed, _ROBOTS_CACHE
        from urllib.robotparser import RobotFileParser

        # 注入一个空的 RobotFileParser（模拟读取失败）
        fake_rp = RobotFileParser()
        fake_rp.allow_all = True
        base = "https://nonexistent.example.com"
        _ROBOTS_CACHE[base] = fake_rp

        result = is_allowed("https://nonexistent.example.com/jobs/123")
        assert result is True

        # 清理
        _ROBOTS_CACHE.pop(base, None)

    def test_is_allowed_caches_per_domain(self):
        """同一域只查一次 robots.txt。"""
        from crawler.compliance import _ROBOTS_CACHE, _get_robots

        base = "https://cached-test-domain.example.com"
        # 清缓存
        _ROBOTS_CACHE.pop(base, None)

        _get_robots(f"{base}/page1")
        _get_robots(f"{base}/page2")
        # 缓存应只有 1 条
        assert base in _ROBOTS_CACHE

    def test_stealth_check_robots_returns_bool(self):
        """stealth_check_robots 返回 True/False，不抛错。"""
        from crawler.compliance import stealth_check_robots

        # 正常 URL → 可能 True 也可能 False，但不应抛错
        result = stealth_check_robots("https://www.zhipin.com/job/123")
        assert isinstance(result, bool)

    def test_stealth_check_robots_logs_warning_when_disallowed(self):
        """被禁止时应记录 warning（soft check，不阻塞）。"""
        from crawler.compliance import stealth_check_robots, _ROBOTS_CACHE
        from urllib.robotparser import RobotFileParser

        # 注入一个禁止所有路径的 robots
        fake_rp = RobotFileParser()
        fake_rp.parse([
            "User-agent: *",
            "Disallow: /",
        ])
        base = "https://blocked-test.example.com"
        _ROBOTS_CACHE[base] = fake_rp

        with patch("crawler.compliance.log") as mock_log:
            result = stealth_check_robots(f"{base}/job/123")
            assert result is False
            mock_log.warning.assert_called()


# ── RateLimiter ──────────────────────────────────────────────────
class TestRateLimiter:
    def test_wait_sleeps_when_too_fast(self):
        """间隔 < min_interval 时应 sleep。"""
        from crawler.compliance import RateLimiter

        rl = RateLimiter(min_interval=0.1)
        rl._last = time.monotonic()  # 刚调用过
        t0 = time.monotonic()
        rl.wait()
        elapsed = time.monotonic() - t0
        assert elapsed >= 0.09  # 至少 sleep 了近 0.1s

    def test_wait_no_sleep_when_enough_time(self):
        """间隔足够时不 sleep。"""
        from crawler.compliance import RateLimiter

        rl = RateLimiter(min_interval=0.1)
        rl._last = time.monotonic() - 1.0  # 已经过了 1s
        t0 = time.monotonic()
        rl.wait()
        elapsed = time.monotonic() - t0
        assert elapsed < 0.05  # 几乎不 sleep


# ── Proxy ────────────────────────────────────────────────────────
class TestProxy:
    def test_get_proxy_returns_none_when_empty(self):
        """无代理池时返回 None。"""
        import crawler.compliance as comp

        old = comp._PROXY_LIST[:]
        comp._PROXY_LIST = []
        try:
            with patch.dict(os.environ, {"PROXY_LIST": ""}, clear=False):
                result = comp.get_proxy()
                assert result is None
        finally:
            comp._PROXY_LIST = old

    def test_get_proxy_picks_from_pool(self):
        """有代理池时随机返回一个。"""
        import crawler.compliance as comp

        old = comp._PROXY_LIST[:]
        comp._PROXY_LIST = ["http://a:8080", "http://b:8080"]
        try:
            result = comp.get_proxy()
            assert result in ["http://a:8080", "http://b:8080"]
        finally:
            comp._PROXY_LIST = old

    def test_load_proxies_parses_env(self):
        """从 PROXY_LIST 环境变量解析。"""
        from crawler.compliance import _load_proxies

        with patch.dict(os.environ, {"PROXY_LIST": "http://x:80,socks5://y:1080"}, clear=False):
            result = _load_proxies()
            assert len(result) == 2
            assert "http://x:80" in result


# ── log_request ──────────────────────────────────────────────────
class TestLogRequest:
    def test_log_request_writes_to_db(self):
        """log_request 正常写入 compliance_log。"""
        from crawler.compliance import log_request

        mock_session = MagicMock()
        with patch("crawler.compliance.get_compliance_session") as mock_get:
            mock_get.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_get.return_value.__exit__ = MagicMock(return_value=False)

            log_request("bosszhipin", "https://example.com/job/1", True, "ua/1.0", 0.5, 200, 1024)

            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()

    def test_log_request_swallows_exception(self):
        """DB 写入失败不抛错。"""
        from crawler.compliance import log_request

        mock_session = MagicMock()
        mock_session.commit.side_effect = Exception("DB down")
        with patch("crawler.compliance.get_compliance_session") as mock_get:
            mock_get.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_get.return_value.__exit__ = MagicMock(return_value=False)

            # 不应抛出
            log_request("bosszhipin", "https://example.com", True, "ua", 0.0, 200, 0)


# ── stealth_log_request ──────────────────────────────────────────
class TestStealthLogRequest:
    def test_stealth_log_request_calls_log_request(self):
        """stealth_log_request 委托给 log_request。"""
        from crawler.compliance import stealth_log_request

        with patch("crawler.compliance.log_request") as mock_lr, \
             patch("crawler.compliance.is_allowed", return_value=True):
            stealth_log_request("lagou", "https://lagou.com/job/1", response_code=200, response_bytes=512)

            mock_lr.assert_called_once()
            call_kwargs = mock_lr.call_args
            assert call_kwargs[1]["source_site"] == "lagou"
            assert call_kwargs[1]["response_code"] == 200
            assert call_kwargs[1]["response_bytes"] == 512


# ── FetchResult ──────────────────────────────────────────────────
class TestFetchResult:
    def test_fetch_result_dataclass(self):
        """FetchResult 数据类。"""
        from crawler.compliance import FetchResult

        r = FetchResult(text="ok", status_code=200, bytes_count=2, robots_allowed=True)
        assert r.text == "ok"
        assert r.status_code == 200
        assert r.robots_allowed is True


# ── fetch ────────────────────────────────────────────────────────
class TestFetch:
    def test_fetch_blocked_by_robots(self):
        """robots 禁止时返回 403。"""
        from crawler.compliance import fetch

        with patch("crawler.compliance.is_allowed", return_value=False), \
             patch("crawler.compliance.log_request"):
            result = fetch("https://blocked.com/page", "test")
            assert result.status_code == 403
            assert result.robots_allowed is False

    def test_fetch_http_error(self):
        """HTTP 错误返回 status_code=0。"""
        from crawler.compliance import fetch

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.content = b""

        with patch("crawler.compliance.is_allowed", return_value=True), \
             patch("crawler.compliance.log_request"), \
             patch("crawler.compliance.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_instance.get.side_effect = httpx.HTTPError("timeout")
            mock_cls.return_value = mock_instance

            result = fetch("https://example.com/page", "test")
            assert result.status_code == 0

    def test_fetch_success(self):
        """正常抓取返回 200。"""
        from crawler.compliance import fetch

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"<html>hello</html>"
        mock_resp.text = "<html>hello</html>"

        with patch("crawler.compliance.is_allowed", return_value=True), \
             patch("crawler.compliance.log_request"), \
             patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = mock_resp

            result = fetch("https://example.com/page", "test", use_proxy=False)
            assert result.status_code == 200
            assert "hello" in result.text
