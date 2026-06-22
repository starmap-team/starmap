#!/usr/bin/env python3
"""用 Apify web-scraper 抓 BOSS 直聘真实数据"""
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

from apify_client import ApifyClient
from crawler.compliance import log_request, is_allowed
from crawler.dedup import hex64, simhash
from crawler.persistence import dao
from crawler.persistence.models import JdStatus
from crawler.pipelines.clean import clean_html

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")

# BOSS 直聘的 pageFunction
BOSS_PAGE_FUNCTION = """async function pageFunction(context) {
    const { page, request } = context;
    await page.waitForSelector('div.job-list-box li', {timeout: 15000}).catch(() => {});
    const items = await page.$$eval('li.job-card-wrapper', els => els.map(el => ({
        title: el.querySelector('.job-name')?.textContent?.trim() || '',
        company: el.querySelector('.company-name a')?.textContent?.trim() || '',
        url: el.querySelector('a.job-card-left')?.href || '',
        salary: el.querySelector('.salary')?.textContent?.trim() || '',
        city: el.querySelector('.job-area')?.textContent?.trim() || '',
        experience: el.querySelector('.tag-list li:first-child')?.textContent?.trim() || '',
        education: el.querySelector('.tag-list li:nth-child(2)')?.textContent?.trim() || '',
    })));
    return items;
}"""

# 51job 的 pageFunction
JOB51_PAGE_FUNCTION = """async function pageFunction(context) {
    const { page, request } = context;
    await page.waitForSelector('div.j_joblist', {timeout: 15000}).catch(() => {});
    const items = await page.$$eval('div.j_joblist a.jname', els => els.map(el => ({
        title: el.textContent?.trim() || '',
        url: el.href || '',
        company: el.closest('.j_joblist')?.querySelector('.cname a')?.textContent?.trim() || '',
        salary: el.closest('.j_joblist')?.querySelector('.sal')?.textContent?.trim() || '',
        city: el.closest('.j_joblist')?.querySelector('.d_at')?.textContent?.trim() || '',
    })));
    return items;
}"""


def run_web_scraper(urls, page_function, source_site, max_pages=5):
    """用 Apify web-scraper 抓取"""
    client = ApifyClient(APIFY_TOKEN)
    
    run_input = {
        "startUrls": [{"url": u} for u in urls],
        "maxPagesPerCrawl": max_pages,
        "pageFunction": page_function,
        "proxyConfiguration": {"useApifyProxy": True},
    }
    
    target_url = "https://www.apify.com/actor/apify/web-scraper"
    robots_ok = is_allowed(target_url)
    print(f"启动 web-scraper 抓 {source_site}...")
    run = client.actor("apify/web-scraper").call(run_input=run_input)
    
    dataset_id = run.get("defaultDatasetId")
    items = list(client.dataset(dataset_id).iterate_items())
    # 记录合规日志：每条 item 一次
    for item in items:
        item_url = item.get("url", target_url)
        log_request(source_site, item_url, robots_ok, "StarMap-Apify/1.0", 0.0, 200, len(json.dumps(item)))
    print(f"返回 {len(items)} 条")
    return items


def save_to_db(items, source_site):
    """入库"""
    inserted = 0
    skipped = 0
    failed = 0
    
    for item in items:
        try:
            title = item.get("title", "")
            company = item.get("company", "")
            url = item.get("url", "")
            salary = item.get("salary", "")
            city = item.get("city", "")
            experience = item.get("experience", "")
            education = item.get("education", "")
            
            if not title:
                skipped += 1
                continue
            
            # 构造 clean_text
            parts = [p for p in [title, company, education, experience, salary, city] if p]
            clean = " ".join(parts)
            if len(clean) < 30:
                skipped += 1
                continue
            
            rec = {
                "source_site": source_site,
                "source_url": url or f"apify://{source_site}/title/{hash(title) % 10**8}",
                "raw_html": "",
                "clean_text": clean,
                "job_title": title[:200],
                "company": company or None,
                "salary_min": None,
                "salary_max": None,
                "location": city or None,
                "publish_date": date.today(),
                "content_hash": hex64(simhash(clean)),
                "status": JdStatus.raw,
            }
            
            r = dao.upsert_jd(rec)
            if r == "inserted":
                inserted += 1
            elif r == "duplicate":
                skipped += 1
            else:
                failed += 1
        except Exception as e:
            print(f"处理失败: {e}")
            failed += 1
    
    print(f"{source_site}: inserted={inserted}, skipped={skipped}, failed={failed}")
    return inserted


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", choices=["boss", "51job", "both"], default="both")
    parser.add_argument("--max-pages", type=int, default=5)
    args = parser.parse_args()
    
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    
    if args.site in ("boss", "both"):
        boss_urls = [
            "https://www.zhipin.com/web/geek/job?query=python&city=100010000",
            "https://www.zhipin.com/web/geek/job?query=java&city=100010000",
            "https://www.zhipin.com/web/geek/job?query=golang&city=100010000",
        ]
        items = run_web_scraper(boss_urls, BOSS_PAGE_FUNCTION, "bosszhipin", args.max_pages)
        save_to_db(items, "bosszhipin")
    
    if args.site in ("51job", "both"):
        job51_urls = [
            "https://search.51job.com/list/000000,000000,0000,00,9,99,python,2,1.html",
            "https://search.51job.com/list/000000,000000,0000,00,9,99,java,2,1.html",
        ]
        items = run_web_scraper(job51_urls, JOB51_PAGE_FUNCTION, "51job", args.max_pages)
        save_to_db(items, "51job")
