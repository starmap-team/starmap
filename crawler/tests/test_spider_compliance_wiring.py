"""CR-06 / PLAN-004 回归：本地 spider 必须经由 crawler.compliance.fetch。

锁定合规接线——robots 检查 + QPS 限速 + compliance_log 全部在 compliance.fetch
内完成；spider 若绕过它直连（裸 urllib/httpx）即破坏 §15.3 合规承诺。
测试不触网：patch 各 spider 模块内的 fetch 引用。
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from crawler.spiders import arbeitnow, jobicy, weworkremotely


class _FakeFetchResult:
    def __init__(self, text: str = "", status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code
        self.bytes_count = len(text.encode()) if text else 0
        self.robots_allowed = True


def test_arbeitnow_routes_through_compliance(monkeypatch):
    calls: list[str] = []

    def _fake_fetch(url: str, source_site: str, **kw: Any) -> _FakeFetchResult:
        calls.append(source_site)
        return _FakeFetchResult(text=json.dumps({"data": []}), status_code=200)

    monkeypatch.setattr(arbeitnow, "fetch", _fake_fetch)
    items = arbeitnow.run_sync(max_count=3)
    assert items == []
    assert calls == ["arbeitnow"], "arbeitnow 必须经 compliance.fetch 抓取"


def test_jobicy_routes_through_compliance(monkeypatch):
    calls: list[str] = []

    def _fake_fetch(url: str, source_site: str, **kw: Any) -> _FakeFetchResult:
        calls.append(source_site)
        return _FakeFetchResult(text=json.dumps({"jobs": []}), status_code=200)

    monkeypatch.setattr(jobicy, "fetch", _fake_fetch)
    jobicy.run_sync(max_count=3)
    assert calls == ["jobicy"]


def test_weworkremotely_routes_through_compliance(monkeypatch):
    calls: list[str] = []
    rss = "<rss><channel></channel></rss>"

    def _fake_fetch(url: str, source_site: str, **kw: Any) -> _FakeFetchResult:
        calls.append(source_site)
        return _FakeFetchResult(text=rss, status_code=200)

    monkeypatch.setattr(weworkremotely, "fetch", _fake_fetch)
    weworkremotely.run_sync(max_count=3)
    assert calls == ["weworkremotely"]


@pytest.mark.parametrize("mod", [arbeitnow, jobicy, weworkremotely])
def test_non_200_returns_empty(monkeypatch, mod):
    """robots 拒绝/网络失败（status 0 或 403）→ 诚实返回空列表。"""
    monkeypatch.setattr(mod, "fetch", lambda url, s, **kw: _FakeFetchResult(text="", status_code=403))
    assert mod.run_sync(max_count=3) == []
