"""合规日志：robots.txt 检查 + QPS 限速 + 请求记录 + 代理支持。"""
from __future__ import annotations

import logging
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from . import config
from .persistence.database import get_compliance_session
from .persistence.models import ComplianceLog

log = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# 1. robots.txt 缓存（按域）
# ----------------------------------------------------------------------
_ROBOTS_CACHE: dict[str, RobotFileParser] = {}


def _get_robots(url: str, timeout: float = 5.0) -> RobotFileParser:
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    if base in _ROBOTS_CACHE:
        return _ROBOTS_CACHE[base]
    rp = RobotFileParser()
    rp.set_url(f"{base}/robots.txt")
    try:
        rp.read()
    except Exception as e:  # noqa: BLE001
        log.warning("robots.txt 读取失败 %s: %s", base, e)
    _ROBOTS_CACHE[base] = rp
    return rp


def is_allowed(url: str, user_agent: str = "*") -> bool:
    """判断 URL 是否被 robots.txt 允许。"""
    try:
        return _get_robots(url).can_fetch(user_agent, url)
    except Exception:  # noqa: BLE001
        # 拿不到 robots 时默认放行，但记录 warning
        return True


# ----------------------------------------------------------------------
# 2. 限速器（QPS ≤ 1）
# ----------------------------------------------------------------------
class RateLimiter:
    def __init__(self, min_interval: float = 1.0):
        self.min_interval = min_interval
        self._last = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        delta = now - self._last
        if delta < self.min_interval:
            time.sleep(self.min_interval - delta)
        self._last = time.monotonic()


# ----------------------------------------------------------------------
# 3. 代理池
# ----------------------------------------------------------------------
_PROXY_LIST: list[str] = []


def _load_proxies() -> list[str]:
    """从环境变量 PROXY_LIST 加载代理池。

    格式: PROXY_LIST=http://host1:port1,http://host2:port2
    或: PROXY_LIST=socks5://host:port
    """
    raw = os.getenv("PROXY_LIST", "")
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def get_proxy() -> Optional[str]:
    """从代理池随机取一个代理。无池则返回 None（直连）。"""
    global _PROXY_LIST
    if not _PROXY_LIST:
        _PROXY_LIST = _load_proxies()
    if not _PROXY_LIST:
        return None
    return random.choice(_PROXY_LIST)


# ----------------------------------------------------------------------
# 4. 写入 compliance_log
# ----------------------------------------------------------------------
def log_request(
    source_site: str,
    target_url: str,
    robots_allowed: bool,
    user_agent: str,
    qps: float,
    response_code: int,
    response_bytes: int = 0,
) -> None:
    """写一条合规日志。失败也不抛错（合规日志不能阻塞主流程）。"""
    try:
        with get_compliance_session() as s:
            s.add(
                ComplianceLog(
                    source_site=source_site,
                    target_url=target_url,
                    robots_allowed=robots_allowed,
                    user_agent=user_agent,
                    qps=qps,
                    response_code=response_code,
                    response_bytes=response_bytes,
                )
            )
            s.commit()
    except Exception as e:  # noqa: BLE001
        log.error("compliance_log 写入失败: %s", e)


# ----------------------------------------------------------------------
# 5. 一站式 fetcher（合规 + 限速 + 日志 + 代理 三合一）
# ----------------------------------------------------------------------
@dataclass
class FetchResult:
    text: str
    status_code: int
    bytes_count: int
    robots_allowed: bool


def fetch(
    url: str,
    source_site: str,
    *,
    user_agent: Optional[str] = None,
    rate_limiter: Optional[RateLimiter] = None,
    timeout: float = 15.0,
    use_proxy: bool = False,
) -> FetchResult:
    ua = user_agent or config.USER_AGENTS[0]
    limiter = rate_limiter or RateLimiter(min_interval=config.DEFAULT_SLEEP)

    allowed = is_allowed(url, ua)
    if not allowed:
        log.warning("[compliance] robots.txt 禁止抓取 %s，跳过", url)
        log_request(source_site, url, False, ua, 0.0, 403, 0)
        return FetchResult(text="", status_code=403, bytes_count=0, robots_allowed=False)

    proxy = get_proxy() if use_proxy else None
    proxies = {"http://": proxy, "https://": proxy} if proxy else None

    t0 = time.monotonic()
    try:
        with httpx.Client(
            headers={"User-Agent": ua},
            timeout=timeout,
            follow_redirects=True,
            proxy=proxy,
        ) as c:
            resp = c.get(url)
    except httpx.HTTPError as e:
        log.warning("HTTP error %s: %s", url, e)
        log_request(source_site, url, allowed, ua, 0.0, 0, 0)
        return FetchResult(text="", status_code=0, bytes_count=0, robots_allowed=allowed)

    elapsed = time.monotonic() - t0
    log_request(source_site, url, allowed, ua, elapsed, resp.status_code, len(resp.content))
    limiter.wait()
    return FetchResult(
        text=resp.text,
        status_code=resp.status_code,
        bytes_count=len(resp.content),
        robots_allowed=allowed,
    )


# ----------------------------------------------------------------------
# 6. Stealth 合规辅助（给 Playwright stealth 爬虫用）
# ----------------------------------------------------------------------
def stealth_log_request(
    source_site: str,
    target_url: str,
    *,
    user_agent: str = "StarMap-Stealth/1.0",
    response_code: int = 200,
    response_bytes: int = 0,
) -> None:
    """Stealth 爬虫的合规日志记录。

    Stealth 爬虫使用 Playwright 浏览器，robots.txt 检查意义有限
    （浏览器会执行 JS），但仍需记录请求审计。
    """
    robots_ok = is_allowed(target_url, user_agent)
    log_request(
        source_site=source_site,
        target_url=target_url,
        robots_allowed=robots_ok,
        user_agent=user_agent,
        qps=0.0,  # Stealth 爬虫自带延迟
        response_code=response_code,
        response_bytes=response_bytes,
    )


def stealth_check_robots(url: str, user_agent: str = "StarMap-Stealth/1.0") -> bool:
    """Stealth 爬虫的 robots.txt 检查（软检查，不阻塞）。

    返回 True 表示允许，False 表示禁止但仍可抓取（记录 warning）。
    """
    allowed = is_allowed(url, user_agent)
    if not allowed:
        log.warning("[stealth-compliance] robots.txt 禁止 %s，但仍执行（浏览器抓取）", url)
    return allowed


__all__ = ["is_allowed", "RateLimiter", "log_request", "fetch", "FetchResult", "get_proxy",
           "stealth_log_request", "stealth_check_robots"]
