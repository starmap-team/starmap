"""BOSS 直聘爬虫（Playwright-stealth + 代理，反检测版）。

用法:
    # 直连
    python -m crawler.spiders.boss --max 10

    # 带代理
    PROXY_LIST=http://host:port python -m crawler.spiders.boss --max 10

    # 或指定单个代理
    python -m crawler.spiders.boss --max 10 --proxy http://host:port
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from crawler import config
from crawler.compliance import RateLimiter, get_proxy, stealth_check_robots, stealth_log_request
from crawler.dedup import hex64, simhash
from crawler.pipelines.clean import clean_html, extract_job_title
from crawler.pipelines.items import JdItem
from crawler.stealth import StealthConfig, create_stealth_context, stealth_goto

log = logging.getLogger(__name__)

# BOSS 直聘搜索 URL
SEARCH_URL = "https://www.zhipin.com/web/geek/job?query={kw}&city=100010000"


async def fetch_one(
    url: str,
    source_site: str = "bosszhipin",
    limiter: RateLimiter | None = None,
    config_: StealthConfig | None = None,
) -> dict | None:
    """用 Playwright-stealth 抓单个详情页。"""
    limiter = limiter or RateLimiter(min_interval=3.0)
    limiter.wait()

    p, browser, ctx = None, None, None
    try:
        p, browser, ctx = await create_stealth_context(config_)
        stealth_check_robots(url)
        page, status = await stealth_goto(ctx, url, timeout=20000)
        if status != 200 or not page:
            log.warning("BOSS 详情非 200 %s", url)
            stealth_log_request(source_site, url, response_code=status)
            return None

        # 等待内容渲染
        try:
            await page.wait_for_selector("div.job-detail, div.job-sec-text", timeout=10000)
        except Exception:
            pass

        html = await page.content()
        stealth_log_request(source_site, url, response_code=status, response_bytes=len(html))
        await page.close()
    except Exception as e:  # noqa: BLE001
        log.warning("BOSS 抓取异常 %s: %s", url, e)
        return None
    finally:
        if browser:
            await browser.close()
        if p:
            await p.stop()

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


async def run_boss(
    keyword: str,
    max_count: int = 100,
    proxy: str | None = None,
) -> list[dict]:
    """公开列表页 + 详情页（Playwright-stealth 反检测版）。"""
    search_url = SEARCH_URL.format(kw=keyword)
    log.info("BOSS 搜索: %s", search_url)

    proxy_user = None
    proxy_pass = None
    if proxy and "@" in proxy:
        # 解析 http://user:pass@host:port
        parts = proxy.split("@")
        auth = parts[0].replace("http://", "").replace("https://", "")
        if ":" in auth:
            proxy_user, proxy_pass = auth.split(":", 1)
        proxy = parts[1] if len(parts) > 1 else proxy
        if not proxy.startswith("http"):
            proxy = f"http://{proxy}"

    cfg = StealthConfig(
        proxy=proxy or get_proxy(),
        proxy_user=proxy_user,
        proxy_pass=proxy_pass,
    )

    p, browser, ctx = None, None, None
    try:
        p, browser, ctx = await create_stealth_context(cfg)
        stealth_check_robots(search_url)
        page, status = await stealth_goto(ctx, search_url, timeout=30000, wait_until="domcontentloaded")

        if not page:
            log.warning("BOSS 列表页加载失败")
            stealth_log_request("bosszhipin", search_url, response_code=status)
            return []

        # 等待职位列表渲染
        try:
            await page.wait_for_selector("div.job-list-box li.job-card-wrapper", timeout=15000)
        except Exception:
            log.warning("BOSS 列表未渲染，尝试直接提取")

        # 抓详情链接
        hrefs = await page.eval_on_selector_all(
            "a[href*='/job_detail/']",
            "els => els.slice(0, 20).map(e => e.href)",
        )
        log.info("BOSS 列表拿到 %d 个详情链接", len(hrefs))
        await page.close()
    except Exception as e:  # noqa: BLE001
        log.warning("BOSS 列表抓取失败: %s", e)
        hrefs = []
    finally:
        if browser:
            await browser.close()
        if p:
            await p.stop()

    # 抓详情
    results: list[dict] = []
    for href in hrefs:
        if len(results) >= max_count:
            break
        item = await fetch_one(href, config_=cfg)
        if item:
            results.append(item)
    return results


def run_sync(keyword: str = "python", max_count: int = 100, proxy: str | None = None) -> list[dict]:
    return asyncio.run(run_boss(keyword, max_count, proxy))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BOSS 直聘爬虫 (Playwright-stealth)")
    parser.add_argument("--keyword", default="python", help="搜索关键词")
    parser.add_argument("--max", type=int, default=10, help="最多抓取条数")
    parser.add_argument("--proxy", help="代理地址 (http://user:pass@host:port)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    items = run_sync(args.keyword, args.max, args.proxy)
    print(json.dumps(items, ensure_ascii=False, indent=2))
