"""前程无忧爬虫（Playwright-stealth 反检测版）。

51job 使用阿里云 WAF + SPA 渲染，纯 HTTP 方式容易被拦。
本模块用 Playwright-stealth + 代理绕过 WAF。

用法:
    # 带代理（推荐）
    PROXY_LIST=http://host:port python -m crawler.spiders.job51_stealth --max 10
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

SEARCH_URL = "https://search.51job.com/list/000000,000000,0000,00,9,99,{kw},2,{pn}.html"


async def fetch_detail(
    url: str,
    limiter: RateLimiter,
    cfg: StealthConfig,
) -> dict | None:
    """用 stealth 抓单个详情页。"""
    limiter.wait()

    p, browser, ctx = None, None, None
    try:
        p, browser, ctx = await create_stealth_context(cfg)
        stealth_check_robots(url)
        page, status = await stealth_goto(ctx, url, timeout=20000)
        if status != 200 or not page:
            log.warning("51job 详情失败 %s status=%d", url, status)
            stealth_log_request("51job", url, response_code=status)
            return None

        try:
            await page.wait_for_selector("div.job_msg, div.tCompany_main", timeout=10000)
        except Exception:
            pass

        html = await page.content()
        stealth_log_request("51job", url, response_code=status, response_bytes=len(html))
        await page.close()
    except Exception as e:  # noqa: BLE001
        log.warning("51job 详情异常 %s: %s", url, e)
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
        "source_site": "51job",
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


async def run_51job(
    keyword: str = "python",
    max_count: int = 100,
    proxy: str | None = None,
) -> list[dict]:
    """51job 列表 + 详情（Playwright-stealth 反检测版）。"""
    limiter = RateLimiter(min_interval=config.DEFAULT_SLEEP)

    proxy_user = None
    proxy_pass = None
    if proxy and "@" in proxy:
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

    all_links: list[str] = []
    p, browser, ctx = None, None, None
    try:
        p, browser, ctx = await create_stealth_context(cfg)

        for page_num in range(1, 6):
            if len(all_links) >= max_count:
                break

            url = SEARCH_URL.format(kw=keyword, pn=page_num)
            log.info("[51job] 第 %d 页: %s", page_num, url)

            stealth_check_robots(url)
            page, status = await stealth_goto(ctx, url, timeout=30000)
            if not page:
                stealth_log_request("51job", url, response_code=status)
                continue

            try:
                await page.wait_for_selector(
                    "div.j_joblist a.jname, a[href*='jobs.51job.com']",
                    timeout=15000,
                )
            except Exception:
                log.warning("[51job] 第 %d 页列表未渲染", page_num)
                await page.close()
                continue

            links = await page.eval_on_selector_all(
                "div.j_joblist a.jname, a[href*='jobs.51job.com']",
                "els => els.map(e => e.href)",
            )
            log.info("[51job] 第 %d 页拿到 %d 个链接", page_num, len(links))
            all_links.extend(links)
            await page.close()

            await asyncio.sleep(2)

    except Exception as e:  # noqa: BLE001
        log.warning("51job 列表抓取失败: %s", e)
    finally:
        if browser:
            await browser.close()
        if p:
            await p.stop()

    results: list[dict] = []
    for href in all_links[:max_count]:
        item = await fetch_detail(href, limiter, cfg)
        if item:
            results.append(item)

    return results


def run_sync(keyword: str = "python", max_count: int = 100, proxy: str | None = None) -> list[dict]:
    return asyncio.run(run_51job(keyword, max_count, proxy))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="51job 爬虫 (Playwright-stealth)")
    parser.add_argument("--keyword", default="python", help="搜索关键词")
    parser.add_argument("--max", type=int, default=10, help="最多抓取条数")
    parser.add_argument("--proxy", help="代理地址 (http://user:pass@host:port)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    items = run_sync(args.keyword, args.max, args.proxy)
    print(json.dumps(items, ensure_ascii=False, indent=2))
