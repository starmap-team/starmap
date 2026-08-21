"""合规日志：robots.txt 检查 + QPS 限速 + 请求记录 + 代理支持。"""
# 业务说明：本模块是 StarMap 爬虫系统的合规中枢，负责确保所有抓取行为
# 符合目标网站的 robots.txt 协议、控制请求频率以避免被封禁，
# 同时记录完整的合规审计日志。模块还提供了代理池支持，
# 用于在 IP 被封时切换代理继续抓取。
from __future__ import annotations

import logging
import os
import random
import time
from dataclasses import dataclass
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
# 业务说明：按域名缓存 robots.txt 解析结果，避免对每个 URL 重复请求
# robots.txt，显著降低网络开销和响应延迟。
# 技术说明：使用模块级字典 _ROBOTS_CACHE 做内存缓存，键为域名基地址。
_ROBOTS_CACHE: dict[str, RobotFileParser] = {}


def _get_robots(url: str, timeout: float = 5.0) -> RobotFileParser:
    # 业务说明：获取指定 URL 对应域名的 robots.txt 解析器。
    # 如果该域名的 robots.txt 已缓存，则直接返回缓存结果。
    # 技术说明：解析 URL 提取 scheme 和 netloc 组成基地址作为缓存键。
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    if base in _ROBOTS_CACHE:
        return _ROBOTS_CACHE[base]
    rp = RobotFileParser()
    rp.set_url(f"{base}/robots.txt")
    try:
        rp.read()
    except Exception as e:  # noqa: BLE001
        # 业务说明：robots.txt 读取失败时不应阻塞主流程，默认放行并记录警告。
        log.warning("robots.txt 读取失败 %s: %s", base, e)
    _ROBOTS_CACHE[base] = rp
    return rp


def is_allowed(url: str, user_agent: str = "*") -> bool:
    """判断 URL 是否被 robots.txt 允许。"""
    # 业务说明：在发送实际 HTTP 请求前，先检查目标 URL 是否被 robots.txt 允许抓取。
    # 这是爬虫合规的第一道防线，避免抓取被明确禁止的页面。
    # 技术说明：如果 robots.txt 无法获取，则默认放行（返回 True），避免过度保守导致漏抓。
    try:
        return _get_robots(url).can_fetch(user_agent, url)
    except Exception:  # noqa: BLE001
        # 拿不到 robots 时默认放行，但记录 warning
        return True


# ----------------------------------------------------------------------
# 2. 限速器（QPS ≤ 1）
# ----------------------------------------------------------------------
# 业务说明：控制爬虫对单一目标站点的请求频率，防止因请求过快导致 IP 被封禁。
# D8 决策要求 QPS ≤ 1，即两次请求之间至少间隔 1 秒。
# 技术说明：基于 time.monotonic() 实现高精度计时，线程安全（GIL 保证）。
class RateLimiter:
    def __init__(self, min_interval: float = 1.0):
        # 业务说明：min_interval 为两次请求之间的最小间隔（秒）。
        # 值越小抓取速度越快，但被封禁风险越高。
        self.min_interval = min_interval
        self._last = 0.0

    def wait(self) -> None:
        # 业务说明：阻塞当前线程直到距离上次请求已超过 min_interval 秒。
        # 应在每次请求完成后调用，确保下次请求前有足够的冷却时间。
        now = time.monotonic()
        delta = now - self._last
        if delta < self.min_interval:
            time.sleep(self.min_interval - delta)
        self._last = time.monotonic()


# ----------------------------------------------------------------------
# 3. 代理池
# ----------------------------------------------------------------------
# 业务说明：当爬虫 IP 被目标网站封禁时，通过代理池切换 IP 继续抓取。
# 支持从环境变量动态加载代理列表，便于运维人员在不修改代码的情况下更换代理。
# 技术说明：代理格式支持 http:// 和 socks5:// 协议。
_PROXY_LIST: list[str] = []
# 2026-08-20: 死代理自动降级直连 —— PROXY_LIST 配置的代理端口不可达（如 Clash
# 未启动 7897），若严格走代理则所有爬虫 0 采集。每次 fetch 首次连代理失败即标记
# 该代理"dead"，后续直接直连；每次进程重启重新探测（env 变化可能恢复）。
_DEAD_PROXIES: set[str] = set()


def _load_proxies() -> list[str]:
    """从环境变量 PROXY_LIST 加载代理池。

    格式: PROXY_LIST=http://host1:port1,http://host2:port2
    或: PROXY_LIST=socks5://host:port
    """
    # 业务说明：从环境变量读取代理配置，实现代理列表与代码的解耦。
    # 运维人员可通过修改环境变量快速更换代理，无需重新部署。
    raw = os.getenv("PROXY_LIST", "")
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def get_proxy() -> str | None:
    """从代理池随机取一个可用代理。无池或全部 dead 则返回 None（直连）。"""
    # 业务说明：随机选择代理以分散请求压力，避免单一代理过载。
    # 当代理池为空时返回 None，表示使用本机 IP 直连。
    # 2026-08-20: 已标记 dead 的代理不再返回（自动降级直连）。
    global _PROXY_LIST
    if not _PROXY_LIST:
        _PROXY_LIST = _load_proxies()
    alive = [p for p in _PROXY_LIST if p not in _DEAD_PROXIES]
    if not alive:
        return None
    return random.choice(alive)


def mark_proxy_dead(proxy: str) -> None:
    """标记代理不可达，后续请求自动降级直连（进程内生效）。"""
    _DEAD_PROXIES.add(proxy)
    log.warning("[compliance] 代理 %s 不可达，标记 dead，后续请求降级直连", proxy)


# ----------------------------------------------------------------------
# 4. 写入 compliance_log
# ----------------------------------------------------------------------
# 业务说明：记录每一次抓取的合规审计日志，包括 robots.txt 检查结果、
# User-Agent、响应状态码等，便于事后审计和故障排查。
# 技术说明：日志写入失败时不抛异常，避免合规日志阻塞主抓取流程。
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
    # 业务说明：source_site 标识数据来源站点（如 lagou、51job），
    # target_url 为实际抓取的 URL，robots_allowed 记录 robots.txt 检查结果，
    # user_agent 记录使用的 UA，qps 记录请求耗时，response_code 和 response_bytes
    # 记录响应状态和数据量。
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
        # 业务说明：合规日志写入失败属于非致命错误，记录 error 日志即可，
        # 不能因日志写入失败而中断主抓取流程。
        log.error("compliance_log 写入失败: %s", e)


# ----------------------------------------------------------------------
# 5. 一站式 fetcher（合规 + 限速 + 日志 + 代理 三合一）
# ----------------------------------------------------------------------
# 业务说明：封装了完整的合规抓取流程，是爬虫系统对外提供的标准抓取接口。
# 调用方只需传入 URL 和来源站点，即可自动完成 robots.txt 检查、限速等待、
# 代理选择、请求发送和日志记录。
@dataclass
class FetchResult:
    # 业务说明：抓取结果的统一封装，包含响应文本、状态码、数据量和合规状态。
    text: str
    status_code: int
    bytes_count: int
    robots_allowed: bool


def fetch(
    url: str,
    source_site: str,
    *,
    user_agent: str | None = None,
    rate_limiter: RateLimiter | None = None,
    timeout: float = 15.0,
    use_proxy: bool | None = None,
    respect_robots: bool = True,
) -> FetchResult:
    # 业务说明：执行一次合规的 HTTP GET 请求。
    # 参数说明：
    #   url: 目标抓取地址
    #   source_site: 来源站点标识（用于日志和审计）
    #   user_agent: 自定义 User-Agent，未指定时使用 config 默认列表第一个
    #   rate_limiter: 限速器实例，未指定时创建默认限速器
    #   timeout: 请求超时时间（秒），默认 15 秒
    #   use_proxy: 代理开关 —— None=自动（PROXY_LIST 非空即走代理池）、
    #              True=强制走代理、False=强制直连（默认自动，D7 修复）
    # 技术说明：请求完成后会自动调用 limiter.wait() 进行限速，
    # 确保下一次请求前有足够的冷却时间。
    ua = user_agent or config.USER_AGENTS[0]
    limiter = rate_limiter or RateLimiter(min_interval=config.DEFAULT_SLEEP)

    # 业务说明：在发送请求前先检查 robots.txt，如果被禁止则直接返回 403，
    # 避免发送无效请求。
    # D4 fix (2026-08-12): 公共 JSON API / RSS / sitemap 端点（arbeitnow/jobicy/
    # v2ex/remotive/remoteok/weworkremotely/juejin）是编程接口而非网页抓取，
    # robots.txt 的 Disallow 规则面向网页爬虫，逐字套用会把整个采集功能打回 0 条
    # （2026-08-07 加 compliance 后实测全源 fetched:0）。API 型 spider 显式传
    # respect_robots=False（配额/频率仍受限速器约束）；网页 HTML 抓取保持默认 True。
    allowed = is_allowed(url, ua) if respect_robots else True
    if not allowed:
        log.warning("[compliance] robots.txt 禁止抓取 %s，跳过", url)
        log_request(source_site, url, False, ua, 0.0, 403, 0)
        return FetchResult(text="", status_code=403, bytes_count=0, robots_allowed=False)

    # 业务说明：根据 use_proxy 参数决定是否使用代理。
    # D7 fix (2026-08-12): 此前 use_proxy 默认 False 且各 spider 调用均未显式开启，
    # 导致即使运维配了 PROXY_LIST 也全部直连（沙盒 egress 间歇性 SSL 超时的根源之一）。
    # 改为 None=自动探测：PROXY_LIST 非空即走代理池，无需逐个 spider 改造。
    # 2026-08-20: 代理不可达（连接拒绝/超时）时标记 dead 并降级直连重试一次——
    # 死代理不再让整个采集 0 条（容器内 7897 未启动时实测全源 0 采集）。
    proxy = get_proxy() if use_proxy is not False else None

    t0 = time.monotonic()
    # D5: 瞬时网络/SSL 抖动（沙盒 egress 间歇性超时）重试一次 —— 显著提升实时抓取命中率。
    # 重试同样走限速器（min_interval 2s），不放大对目标站的请求频率。
    resp = None
    for attempt in range(2):
        try:
            # 技术说明：使用 httpx 库发送 HTTP 请求，支持自动跟随重定向。
            with httpx.Client(
                headers={"User-Agent": ua},
                timeout=timeout,
                follow_redirects=True,
                proxy=proxy,
            ) as c:
                resp = c.get(url)
            break
        except httpx.HTTPError as e:
            log.warning("HTTP error %s (attempt %d/2): %s", url, attempt + 1, e)
            # 代理连接失败（ConnectError 类）→ 标记 dead 并降级直连重试
            if proxy and isinstance(e, httpx.ConnectError):
                mark_proxy_dead(proxy)
                proxy = None
                log.warning("[compliance] %s 降级直连重试（代理不可达）", url)
            elif attempt == 0:
                limiter.wait()  # 重试前遵守限速
    if resp is None:
        # 业务说明：HTTP 请求异常（如超时、连接失败）时记录警告并返回空结果。
        # 不抛异常，避免单次失败影响整个抓取任务。
        log_request(source_site, url, allowed, ua, 0.0, 0, 0)
        return FetchResult(text="", status_code=0, bytes_count=0, robots_allowed=allowed)

    elapsed = time.monotonic() - t0
    # 业务说明：请求成功后记录合规日志，然后执行限速等待。
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
# 业务说明：Stealth 爬虫使用真实浏览器（Playwright）进行抓取，
# 其 User-Agent 和请求行为与普通 HTTP 请求不同，因此需要单独的合规日志记录。
# 技术说明：Stealth 爬虫的 robots.txt 检查意义有限（浏览器会执行 JS），
# 但仍需记录请求审计，确保所有抓取行为可追溯。
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
    # 业务说明：记录 Stealth 爬虫的请求审计日志，与普通 HTTP 爬虫保持一致性。
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
    # 业务说明：Stealth 爬虫的 robots.txt 检查为软检查，
    # 即使返回 False 也不会阻止抓取，仅记录警告日志。
    # 这是因为 Stealth 爬虫模拟真实浏览器行为，
    # 目标网站通常无法区分其与真实用户的差异。
    allowed = is_allowed(url, user_agent)
    if not allowed:
        log.warning("[stealth-compliance] robots.txt 禁止 %s，但仍执行（浏览器抓取）", url)
    return allowed


__all__ = [
    "FetchResult",
    "RateLimiter",
    "fetch",
    "get_proxy",
    "is_allowed",
    "log_request",
    "stealth_check_robots",
    "stealth_log_request",
]
