"""D5: compliance.fetch 瞬时网络/SSL 抖动重试测试。"""
from __future__ import annotations

import httpx
import pytest

from crawler.compliance import fetch


class _FakeCM:
    """httpx.Client 上下文管理器 fake：第一次抛 ConnectTimeout，第二次成功。"""

    def __init__(self) -> None:
        self.calls = 0

    def __enter__(self) -> "_FakeCM":
        return self

    def __exit__(self, *_: object) -> bool:
        return False

    def get(self, url: str) -> object:
        self.calls += 1
        if self.calls == 1:
            raise httpx.ConnectTimeout("handshake timed out")
        resp = httpx.Response(200, text='{"ok": true}')
        return resp


def test_fetch_retries_once_on_transient_ssl_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """首次 SSL 超时 → 自动重试一次 → 成功。"""
    fake = _FakeCM()
    monkeypatch.setattr(
        "crawler.compliance.httpx.Client",
        lambda **_: fake,  # noqa: ARG005
    )
    result = fetch("https://example.com/api", "test", respect_robots=False)
    assert result.status_code == 200
    assert result.text == '{"ok": true}'
    assert fake.calls == 2  # 确实重试了一次


def test_fetch_returns_empty_after_two_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """连续两次失败 → 返回 status_code=0 空结果（不抛异常）。"""

    class _AlwaysFail(_FakeCM):
        def get(self, url: str) -> object:
            raise httpx.ConnectTimeout("persistent timeout")

    monkeypatch.setattr(
        "crawler.compliance.httpx.Client",
        lambda **_: _AlwaysFail(),  # noqa: ARG005
    )
    result = fetch("https://example.com/api", "test", respect_robots=False)
    assert result.status_code == 0
    assert result.text == ""
