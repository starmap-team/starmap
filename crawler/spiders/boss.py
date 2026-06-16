"""BOSS 直聘爬虫（Playwright 渲染，备用站点）。

⚠️ BOSS 反爬最强，2026 年 6 月可能要求登录或验证码。
本文件保留 PoC 代码，但 R1 在 M1 验收阶段**优先用 S1 拉勾 + S2 51job 各 100 条凑满 200 条**，
BOSS 仅作 fallback。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date

from .. import config
from ..compliance import RateLimiter
from ..dedup import hex64, simhash
from ..pipelines.clean import clean_html, extract_job_title
from ..pipelines.items import JdItem

log = logging.getLogger(__name__)


async def fetch_one(url: str, source_site: str = "bosszhipin", limiter: RateLimiter | None = None) -> dict | None:
    """用 Playwright 抓单个详情页，返回 item 字典。"""
    from playwright.async_api import async_playwright

    limiter = limiter or RateLimiter(min_interval=3.0)
    limiter.wait()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=config.USER_AGENTS[0],
            viewport={"width": 1280, "height": 800},
        )
        page = await ctx.new_page()
        try:
            resp = await page.goto(url, timeout=20000, wait_until="domcontentloaded")
            if not resp or resp.status != 200:
                log.warning("BOSS 详情非 200 %s", url)
                return None
            html = await page.content()
        except Exception as e:  # noqa: BLE001
            log.warning("BOSS 抓取异常 %s: %s", url, e)
            return None
        finally:
            await ctx.close()
            await browser.close()

    clean = clean_html(html)
    if len(clean) < 200:
        return None

    return {
        "source_site": source_site,
        "source_url": url,
        "raw_html": html,
        "clean_text": clean,
        "job_title": extract_job_title(html)[:200],
        "company": None,
        "salary_min": None,
        "salary_max": None,
        "location": None,
        "publish_date": date.today(),
        "content_hash": hex64(simhash(clean)),
    }


async def run_boss(keyword: str, max_count: int = 100) -> list[dict]:
    """公开列表页 + 详情页的简化版（PoC）。"""
    # 搜索 URL
    search_url = f"https://www.zhipin.com/web/geek/job?query={keyword}&city=100010000"
    log.info("BOSS 搜索: %s", search_url)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=config.USER_AGENTS[0])
        page = await ctx.new_page()
        try:
            await page.goto(search_url, timeout=30000, wait_until="networkidle")
            # 抓前 N 个详情链接
            hrefs = await page.eval_on_selector_all(
                "a[href*='/job_detail/']",
                "els => els.slice(0, 20).map(e => e.href)",
            )
        except Exception as e:  # noqa: BLE001
            log.warning("BOSS 列表抓取失败: %s", e)
            hrefs = []
        finally:
            await ctx.close()
            await browser.close()

    results: list[dict] = []
    for href in hrefs:
        if len(results) >= max_count:
            break
        item = await fetch_one(href)
        if item:
            results.append(item)
    return results


def run_sync(keyword: str = "python", max_count: int = 100) -> list[dict]:
    return asyncio.run(run_boss(keyword, max_count))


if __name__ == "__main__":
    import json, sys
    items = run_sync("python", 5)
    json.dump(items, sys.stdout, ensure_ascii=False, indent=2)
