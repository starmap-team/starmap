"""PIPE-02: PROXY_LIST 代理池 + 失败熔断中间件 )

行为契约：
1. 解析 PROXY_LIST (逗号分隔 http://[user:pass@]host:port)
2. 每次请求前从池中按"轮询 + 熔断状态"选一个代理
3. 失败计数：最近 5 分钟内同代理累计 ≥3 次连接失败 → 进入 5 分钟冷却
4. 冷却结束后重新接受该代理
5. PROXY_LIST 未设置 / 全部代理冷却中 → 警告日志 + 直连（不阻断）

模块级 dict 存储熔断状态（_BREAKER_STATE），单进程足够；
cluster 部署推 v2.2 改 Redis (deferred)。
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from urllib.parse import urlparse

log = logging.getLogger(__name__)

@dataclass
class ProxyEntry:
    raw: str  # 原始 URL
    scheme: str  # http / https / socks5
    host: str
    port: int
    user: str | None
    password: str | None

    def to_playwright(self) -> str:
        """转 Playwright proxy server URL: http://[user:pass@]host:port"""
        auth = ""
        if self.user and self.password:
            auth = f"{self.user}:{self.password}@"
        return f"{self.scheme}://{auth}{self.host}:{self.port}"

@dataclass
class _Breaker:
    fail_window_start: float  # 窗口起点（monotonic time）
    fail_count: int
    cooldown_until: float  # 0 = 不在冷却

    def is_open(self, now: float) -> bool:
        return self.cooldown_until > now

_BREAKER_STATE: dict[str, _Breaker] = {}
_PROXY_ENTRIES: list[ProxyEntry] = []
_LAST_PROXY_INDEX: int = 0  # 轮询游标

WINDOW_SECONDS = 5 * 60  # 5 分钟窗口
COOLDOWN_SECONDS = 5 * 60  # 5 分钟冷却
FAIL_THRESHOLD = 3  # 窗口内 ≥3 失败 → 冷却

def _parse_proxy(raw: str) -> ProxyEntry | None:
    """解析 http://[user:pass@]host:port / socks5://host:port"""
    raw = raw.strip()
    if not raw:
        return None
    try:
        p = urlparse(raw)
        if not p.hostname or not p.port:
            return None
        return ProxyEntry(
            raw=raw,
            scheme=p.scheme or "http",
            host=p.hostname,
            port=p.port,
            user=p.username,
            password=p.password)
    except Exception:
        return None

def load_proxies() -> list[ProxyEntry]:
    """读 PROXY_LIST 环境变量并缓存到模块级变量。"""
    global _PROXY_ENTRIES
    raw = os.getenv("PROXY_LIST", "")
    out: list[ProxyEntry] = []
    for item in raw.split(","):
        entry = _parse_proxy(item)
        if entry:
            out.append(entry)
    _PROXY_ENTRIES = out
    return out

def pick_proxy() -> str | None:
    """轮询选择 — 跳过冷却中的代理；池空 / 全部冷却 → 返回 None（直连）。

    返回的是原始 URL（proxy_user / proxy_pass 解析由调用方做，与现有
    boss.py 行为一致）。
    """
    if not _PROXY_ENTRIES:
        load_proxies()
    if not _PROXY_ENTRIES:
        return None
    now = time.monotonic()
    # 至少轮询一圈找到第一个非冷却的代理
    global _LAST_PROXY_INDEX
    for _ in range(len(_PROXY_ENTRIES)):
        _LAST_PROXY_INDEX = (_LAST_PROXY_INDEX + 1) % len(_PROXY_ENTRIES)
        entry = _PROXY_ENTRIES[_LAST_PROXY_INDEX]
        breaker = _BREAKER_STATE.get(entry.raw)
        if breaker is None or not breaker.is_open(now):
            return entry.raw
    log.warning("All proxies in cooldown; falling back to direct connection")
    return None

def record_proxy_failure(proxy_raw: str) -> None:
    """记录一次失败。同一代理 5 分钟内累计 ≥3 → 触发 5 分钟冷却。"""
    global _BREAKER_STATE
    breaker = _BREAKER_STATE.get(proxy_raw)
    now = time.monotonic()
    if breaker is None:
        _BREAKER_STATE[proxy_raw] = _Breaker(
            fail_window_start=now, fail_count=1, cooldown_until=0)
        return
    # 窗口滑出（已超 5 分钟）→ 重置
    if now - breaker.fail_window_start > WINDOW_SECONDS:
        breaker.fail_window_start = now
        breaker.fail_count = 1
        return
    breaker.fail_count += 1
    if breaker.fail_count >= FAIL_THRESHOLD and breaker.cooldown_until <= now:
        breaker.cooldown_until = now + COOLDOWN_SECONDS
        log.warning(
            "Proxy %s hit %d failures in %ds, cooling down for %ds",
            proxy_raw, breaker.fail_count, WINDOW_SECONDS, COOLDOWN_SECONDS)

def record_proxy_success(proxy_raw: str) -> None:
    """成功调用 — 重置该代理的失败计数（但保留 cooldown_until 不变直到自然过期）。"""
    breaker = _BREAKER_STATE.get(proxy_raw)
    if breaker is not None:
        breaker.fail_count = 0
        breaker.fail_window_start = time.monotonic()

def reset_for_tests() -> None:
    """仅测试用 — 清空模块级熔断状态。

    使用 .clear 而非 `= []`/`= {}` 重绑，避免与 `from ... import _BREAKER_STATE`
    的本地引用脱钩 — 后者会在 import 时定下对象身份，后续重绑不会更新本地引用。
    """
    global _BREAKER_STATE, _PROXY_ENTRIES, _LAST_PROXY_INDEX
    _BREAKER_STATE.clear()
    _PROXY_ENTRIES.clear()
    _LAST_PROXY_INDEX = 0

__all__ = [
    "COOLDOWN_SECONDS",
    "FAIL_THRESHOLD",
    "WINDOW_SECONDS",
    "ProxyEntry",
    "_Breaker",
    "load_proxies",
    "pick_proxy",
    "record_proxy_failure",
    "record_proxy_success",
    "reset_for_tests",
]
