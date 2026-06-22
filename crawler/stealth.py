"""Playwright-stealth 封装：反检测浏览器指纹修补 + 代理支持。

所有需要用 Playwright 抓取的 spider 共用此模块。
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Optional

from playwright.async_api import BrowserContext, Page, async_playwright
from playwright_stealth import Stealth

log = logging.getLogger(__name__)

# Chrome 启动参数：最关键的反检测 flag
_CHROME_ARGS = [
    "--disable-blink-features=AutomationControlled",  # 最高性价比单一修复
    "--headless=new",  # 新 headless，保留 GPU pipeline
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-infobars",
    "--window-size=1920,1080",
]

# 常见中文 User-Agent 池
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
]


@dataclass
class StealthConfig:
    """stealth 配置。"""
    proxy: Optional[str] = None  # "http://host:port" 或 "socks5://host:port"
    proxy_user: Optional[str] = None
    proxy_pass: Optional[str] = None
    user_agent: Optional[str] = None
    headless: bool = True
    extra_args: list[str] = field(default_factory=list)
    viewport_width: int = 1920
    viewport_height: int = 1080


async def create_stealth_context(
    config: Optional[StealthConfig] = None,
) -> tuple:
    """创建反检测浏览器上下文。

    Returns:
        (playwright_instance, browser, context) — 调用方负责关闭。
    """
    cfg = config or StealthConfig()

    p = await async_playwright().start()

    launch_args = list(_CHROME_ARGS) + cfg.extra_args

    proxy_settings = None
    if cfg.proxy:
        proxy_settings = {"server": cfg.proxy}
        if cfg.proxy_user:
            proxy_settings["username"] = cfg.proxy_user
        if cfg.proxy_pass:
            proxy_settings["password"] = cfg.proxy_pass

    browser = await p.chromium.launch(
        headless=cfg.headless,
        args=launch_args,
        proxy=proxy_settings,
    )

    ua = cfg.user_agent or random.choice(_USER_AGENTS)

    context = await browser.new_context(
        user_agent=ua,
        viewport={"width": cfg.viewport_width, "height": cfg.viewport_height},
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
        extra_http_headers={
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )

    # 应用 stealth 补丁
    stealth = Stealth()
    await stealth.apply_stealth_async(context)

    return p, browser, context


async def stealth_goto(
    context: BrowserContext,
    url: str,
    *,
    timeout: int = 30000,
    wait_until: str = "domcontentloaded",
) -> tuple[Optional[Page], int]:
    """用 stealth 上下文访问 URL，返回 (page, status_code)。

    调用方负责关闭 page。
    """
    page = await context.new_page()
    try:
        resp = await page.goto(url, timeout=timeout, wait_until=wait_until)
        status = resp.status if resp else 0
        return page, status
    except Exception as e:
        log.warning("stealth_goto 失败 %s: %s", url, e)
        return page, 0
