"""Playwright-stealth 封装：反检测浏览器指纹修补 + 代理支持。

所有需要用 Playwright 抓取的 spider 共用此模块。
"""
# 业务说明：本模块是 StarMap 爬虫系统的反检测浏览器封装层。
# 针对使用 JavaScript 渲染的现代招聘网站（如 BOSS 直聘），
# 普通 HTTP 请求无法获取完整页面内容，需要使用真实浏览器抓取。
# 但目标网站会检测自动化浏览器特征（如 navigator.webdriver），
# 因此需要 stealth 技术隐藏自动化痕迹，模拟真实用户行为。
from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Optional

from playwright.async_api import BrowserContext, Page, async_playwright
from playwright_stealth import Stealth

log = logging.getLogger(__name__)

# Chrome 启动参数：最关键的反检测 flag
# 业务说明：这些启动参数用于隐藏 Playwright/Chrome 的自动化特征，
# 使目标网站无法区分爬虫与真实浏览器。
# 技术说明：
#   --disable-blink-features=AutomationControlled: 移除 navigator.webdriver 标记
#   --headless=new: 使用新版 headless 模式，保留 GPU 渲染管道
#   --no-sandbox: 禁用沙箱（容器环境必需）
#   --disable-dev-shm-usage: 避免 /dev/shm 内存不足问题
#   --disable-infobars: 隐藏"Chrome 正受到自动测试软件控制"提示
#   --window-size=1920,1080: 设置标准桌面分辨率，避免无头模式默认小窗口被检测
_CHROME_ARGS = [
    "--disable-blink-features=AutomationControlled",  # 最高性价比单一修复
    "--headless=new",  # 新 headless，保留 GPU pipeline
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-infobars",
    "--window-size=1920,1080",
]

# 常见中文 User-Agent 池
# 业务说明：使用真实浏览器的 User-Agent，模拟中国用户的常见浏览器环境。
# 技术说明：包含 Windows、Mac、Linux 平台的 Chrome 和 Firefox，
# 随机选择可避免所有请求使用相同 UA 而被识别。
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
    # 业务说明：Stealth 爬虫的配置数据类，封装了浏览器启动所需的全部参数。
    # 技术说明：使用 dataclass 可简化配置管理，支持默认值的灵活覆盖。
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
    # 业务说明：创建并配置一个反检测的 Playwright 浏览器上下文。
    # 包含指纹修补、代理设置、语言环境配置等，使浏览器行为尽可能接近真实用户。
    # 技术说明：返回三元组 (playwright, browser, context)，调用方需负责资源释放。
    cfg = config or StealthConfig()

    p = await async_playwright().start()

    # 业务说明：合并默认反检测参数和用户自定义参数。
    launch_args = list(_CHROME_ARGS) + cfg.extra_args

    # 业务说明：配置代理设置，支持有密码认证的代理。
    # 技术说明：proxy_settings 字典会被传递给 Playwright 的 launch 方法。
    proxy_settings = None
    if cfg.proxy:
        proxy_settings = {"server": cfg.proxy}
        if cfg.proxy_user:
            proxy_settings["username"] = cfg.proxy_user
        if cfg.proxy_pass:
            proxy_settings["password"] = cfg.proxy_pass

    # 业务说明：启动 Chromium 浏览器，应用反检测启动参数和代理。
    browser = await p.chromium.launch(
        headless=cfg.headless,
        args=launch_args,
        proxy=proxy_settings,
    )

    # 业务说明：随机选择 User-Agent，未指定时从预定义池中选择。
    ua = cfg.user_agent or random.choice(_USER_AGENTS)

    # 业务说明：配置浏览器上下文，模拟中国用户的语言、时区等环境。
    # 技术说明：locale 和 timezone_id 的设置使 navigator.language 和
    # Intl.DateTimeFormat 等 API 返回中国用户预期的值。
    context = await browser.new_context(
        user_agent=ua,
        viewport={"width": cfg.viewport_width, "height": cfg.viewport_height},
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
        extra_http_headers={
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )

    # 业务说明：应用 playwright-stealth 补丁，进一步隐藏自动化特征。
    # 技术说明：Stealth 库会注入 JavaScript 代码覆盖 navigator.webdriver、
    # plugins、languages 等属性，使浏览器指纹更接近真实 Chrome。
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
    # 业务说明：在 stealth 浏览器上下文中访问指定 URL，返回页面对象和 HTTP 状态码。
    # 技术说明：wait_until="domcontentloaded" 表示等待 DOM 加载完成即可继续，
    # 比 "networkidle" 更快，适合不需要等待所有资源加载的场景。
    page = await context.new_page()
    try:
        resp = await page.goto(url, timeout=timeout, wait_until=wait_until)
        status = resp.status if resp else 0
        return page, status
    except Exception as e:
        # 业务说明：页面访问失败时记录警告，返回状态码 0 表示失败。
        # 不抛异常，避免单次失败影响整个抓取任务。
        log.warning("stealth_goto 失败 %s: %s", url, e)
        return page, 0
