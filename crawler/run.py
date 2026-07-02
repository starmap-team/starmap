"""R1 CLI 入口。

用法:
    python run.py init              # 建表
    python run.py lagou             # 跑拉勾（HTTP）
    python run.py lagou_stealth     # 跑拉勾（Playwright-stealth，反检测）
    python run.py 51job             # 跑前程无忧（HTTP）
    python run.py 51job_stealth     # 跑前程无忧（Playwright-stealth）
    python run.py bosszhipin        # 跑 BOSS（Playwright-stealth）
    python run.py apify_lagou       # 跑拉勾(Apify, 免费层)
    python run.py all               # 跑 3 个站点（HTTP 版）
    python run.py stealth_all       # 跑 3 个站点（stealth 版）
    python run.py stats             # 统计
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# 让脚本可独立运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler import config  # noqa: E402
from crawler.persistence import dao  # noqa: E402
from crawler.persistence.models import JdStatus  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("r1")


def cmd_init(_args):
    log.info("建表...")
    dao.init_schema()
    log.info("OK")


def cmd_stats(_args):
    log.info("统计 jd_raw ...")
    total = dao.count_jd()
    by_status = dao.count_by_status()
    print(json.dumps({"total": total, "by_status": by_status}, ensure_ascii=False, indent=2))


def _scrapy_settings() -> dict:
    """Scrapy 公共 settings（含入库 pipeline）。"""
    return {
        "USER_AGENT": config.USER_AGENTS[0],
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS": 1,
        "LOG_LEVEL": "INFO",
        "ITEM_PIPELINES": {
            "crawler.pipelines.storage.JdStoragePipeline": 300,
        },
    }


def cmd_crawl_lagou(args):
    from crawler.spiders.lagou import LagouSpider
    from scrapy.crawler import CrawlerProcess

    process = CrawlerProcess(settings=_scrapy_settings())
    process.crawl(LagouSpider, max_per_site=args.max)
    process.start()


def cmd_crawl_51job(args):
    from crawler.spiders.job51 import Job51Spider
    from scrapy.crawler import CrawlerProcess

    process = CrawlerProcess(settings=_scrapy_settings())
    process.crawl(Job51Spider, max_per_site=args.max)
    process.start()


def cmd_crawl_boss(args):
    from crawler.spiders.boss import run_sync
    items = run_sync(keyword=args.keyword or "python", max_count=args.max, proxy=args.proxy)
    log.info("BOSS 拿到 %d 条", len(items))
    inserted = 0
    for it in items:
        rec = {
            "source_site": it["source_site"],
            "source_url": it["source_url"],
            "raw_html": it["raw_html"],
            "clean_text": it["clean_text"],
            "job_title": it["job_title"],
            "company": it["company"],
            "salary_min": it["salary_min"],
            "salary_max": it["salary_max"],
            "location": it["location"],
            "publish_date": it["publish_date"],
            "content_hash": it["content_hash"],  # spider 已计算
            "status": JdStatus.raw,
        }
        r = dao.upsert_jd(rec)
        if r == "inserted":
            inserted += 1
    log.info("BOSS 入库 %d 条", inserted)


def cmd_crawl_lagou_stealth(args):
    from crawler.spiders.lagou_stealth import run_sync
    items = run_sync(keyword=args.keyword or "python", max_count=args.max, proxy=args.proxy)
    log.info("拉勾(stealth) 拿到 %d 条", len(items))
    inserted = 0
    for it in items:
        rec = {
            "source_site": it["source_site"],
            "source_url": it["source_url"],
            "raw_html": it["raw_html"],
            "clean_text": it["clean_text"],
            "job_title": it["job_title"],
            "company": it["company"],
            "salary_min": it["salary_min"],
            "salary_max": it["salary_max"],
            "location": it["location"],
            "publish_date": it["publish_date"],
            "content_hash": it["content_hash"],
            "status": JdStatus.raw,
        }
        r = dao.upsert_jd(rec)
        if r == "inserted":
            inserted += 1
    log.info("拉勾(stealth) 入库 %d 条", inserted)


def cmd_crawl_51job_stealth(args):
    from crawler.spiders.job51_stealth import run_sync
    items = run_sync(keyword=args.keyword or "python", max_count=args.max, proxy=args.proxy)
    log.info("51job(stealth) 拿到 %d 条", len(items))
    inserted = 0
    for it in items:
        rec = {
            "source_site": it["source_site"],
            "source_url": it["source_url"],
            "raw_html": it["raw_html"],
            "clean_text": it["clean_text"],
            "job_title": it["job_title"],
            "company": it["company"],
            "salary_min": it["salary_min"],
            "salary_max": it["salary_max"],
            "location": it["location"],
            "publish_date": it["publish_date"],
            "content_hash": it["content_hash"],
            "status": JdStatus.raw,
        }
        r = dao.upsert_jd(rec)
        if r == "inserted":
            inserted += 1
    log.info("51job(stealth) 入库 %d 条", inserted)


def cmd_apify_lagou(args):
    from crawler.scripts.apify_lagou import run_apify_lagou
    summary = run_apify_lagou(
        max_items=args.max,
        dry_run=args.dry_run,
    )
    log.info("Apify 拉勾: total=%d inserted=%d", summary.get("total", 0), summary.get("inserted", 0))


def cmd_apify_liepin(args):
    from crawler.scripts.apify_liepin import run_apify_liepin
    summary = run_apify_liepin(max_items=args.max, dry_run=args.dry_run, force_paid=args.force_paid)
    log.info('Apify liepin: total=%d inserted=%d', summary.get('total', 0), summary.get('inserted', 0))


def cmd_apify_zhaopin(args):
    from crawler.scripts.apify_zhaopin import run_apify_zhaopin
    summary = run_apify_zhaopin(max_items=args.max, dry_run=args.dry_run, force_paid=args.force_paid)
    log.info('Apify zhaopin: total=%d inserted=%d', summary.get('total', 0), summary.get('inserted', 0))


def _add_common_args(sp):
    """给 spider 子命令加通用参数。"""
    sp.add_argument("--max", type=int, default=config.MAX_PER_SITE)
    sp.add_argument("--keyword", default="python")
    sp.add_argument("--proxy", help="代理地址 (http://user:pass@host:port)")


def main():
    p = argparse.ArgumentParser(prog="r1-crawler")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="建 jd_raw / compliance_log 表")
    sub.add_parser("stats", help="统计 jd_raw")

    # HTTP 版 spider
    for site, fn in (("lagou", cmd_crawl_lagou), ("51job", cmd_crawl_51job)):
        sp = sub.add_parser(site, help=f"爬 {site} (HTTP)")
        _add_common_args(sp)
        sp.set_defaults(func=fn)

    # BOSS（已经是 Playwright）
    sp_boss = sub.add_parser("bosszhipin", help="爬 BOSS 直聘 (Playwright-stealth)")
    _add_common_args(sp_boss)
    sp_boss.set_defaults(func=cmd_crawl_boss)

    # Playwright-stealth 版
    for site, fn in (
        ("lagou_stealth", cmd_crawl_lagou_stealth),
        ("51job_stealth", cmd_crawl_51job_stealth),
    ):
        sp = sub.add_parser(site, help=f"爬 {site} (Playwright-stealth)")
        _add_common_args(sp)
        sp.set_defaults(func=fn)

    # all = HTTP 版 3 站点
    sp_all = sub.add_parser("all", help="跑 3 个站点 (HTTP)")
    _add_common_args(sp_all)
    sp_all.set_defaults(func=lambda a: (
        cmd_crawl_lagou(argparse.Namespace(max=a.max, keyword=a.keyword, proxy=None)),
        cmd_crawl_51job(argparse.Namespace(max=a.max, keyword=a.keyword, proxy=None)),
        cmd_crawl_boss(argparse.Namespace(max=a.max, keyword=a.keyword, proxy=None)),
    ))

    # stealth_all = stealth 版 3 站点
    sp_stealth_all = sub.add_parser("stealth_all", help="跑 3 个站点 (Playwright-stealth)")
    _add_common_args(sp_stealth_all)
    sp_stealth_all.set_defaults(func=lambda a: (
        cmd_crawl_lagou_stealth(argparse.Namespace(max=a.max, keyword=a.keyword, proxy=a.proxy)),
        cmd_crawl_51job_stealth(argparse.Namespace(max=a.max, keyword=a.keyword, proxy=a.proxy)),
        cmd_crawl_boss(argparse.Namespace(max=a.max, keyword=a.keyword, proxy=a.proxy)),
    ))

    # Apify 拉勾（自带住宅代理绕 WAF）
    sp_apify = sub.add_parser("apify_lagou", help="爬拉勾 (Apify，自带住宅代理)")
    sp_apify.add_argument("--max", type=int, default=10, help="最大抓取条数")
    sp_apify.add_argument("--dry-run", action="store_true", help="仅测试，不入库")
    sp_apify.set_defaults(func=cmd_apify_lagou)

    # Apify liepin
    sp_liepin = sub.add_parser('apify_liepin', help='liepin via Apify (paid)')
    sp_liepin.add_argument('--max', type=int, default=50)
    sp_liepin.add_argument('--dry-run', action='store_true')
    sp_liepin.add_argument('--force-paid', action='store_true')
    sp_liepin.set_defaults(func=cmd_apify_liepin)

    # Apify zhaopin
    sp_zhaopin = sub.add_parser('apify_zhaopin', help='zhaopin/51job via Apify (paid)')
    sp_zhaopin.add_argument('--max', type=int, default=100)
    sp_zhaopin.add_argument('--dry-run', action='store_true')
    sp_zhaopin.add_argument('--force-paid', action='store_true')
    sp_zhaopin.set_defaults(func=cmd_apify_zhaopin)

    args = p.parse_args()
    if args.cmd == "init":
        cmd_init(args)
    elif args.cmd == "stats":
        cmd_stats(args)
    elif hasattr(args, "func"):
        args.func(args)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
