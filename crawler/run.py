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
# 业务说明：本模块是 StarMap 爬虫系统的 CLI 入口和任务调度中心。
# 提供统一的命令行接口，支持初始化数据库、单站点抓取、批量抓取、
# Stealth 模式抓取、Apify 云抓取和数据统计等多种操作。
# 技术说明：使用 argparse 构建命令行解析，支持子命令和参数传递。
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# 让脚本可独立运行
# 业务说明：将项目根目录加入 Python 路径，使脚本可以直接运行而不依赖包安装。
# 技术说明：sys.path.insert 确保导入 crawler 包时能找到正确的位置。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler import config  # noqa: E402
from crawler.persistence import dao  # noqa: E402
from crawler.persistence.models import JdStatus  # noqa: E402

# 业务说明：配置根日志记录器，设置日志级别和格式。
# 技术说明：format 包含时间戳、日志级别、记录器名称和消息内容。
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("r1")


def cmd_init(_args):
    # 业务说明：初始化数据库表结构，创建 jd_raw 和 compliance_log 等必要表。
    # 首次部署或数据库 schema 变更后需要执行。
    log.info("建表...")
    dao.init_schema()
    log.info("OK")


def cmd_stats(_args):
    # 业务说明：统计数据库中职位数据的总量和按状态分布情况。
    # 输出 JSON 格式结果，便于脚本化处理和监控。
    log.info("统计 jd_raw ...")
    total = dao.count_jd()
    by_status = dao.count_by_status()
    print(json.dumps({"total": total, "by_status": by_status}, ensure_ascii=False, indent=2))


def _scrapy_settings() -> dict:
    """Scrapy 公共 settings（含入库 pipeline）。"""
    # 业务说明：生成 Scrapy 框架的公共配置字典，所有基于 Scrapy 的爬虫共用。
    # 技术说明：配置项说明：
    #   USER_AGENT: 默认 User-Agent
    #   ROBOTSTXT_OBEY: 是否遵守 robots.txt（True 表示遵守）
    #   DOWNLOAD_DELAY: 下载延迟（秒），控制请求频率
    #   CONCURRENT_REQUESTS: 并发请求数，设为 1 避免被封
    #   LOG_LEVEL: 日志级别
    #   ITEM_PIPELINES: 数据入库 pipeline，负责将抓取结果写入数据库
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
    # 业务说明：使用 Scrapy 框架抓取拉勾网职位数据（HTTP 模式）。
    # 技术说明：CrawlerProcess 是 Scrapy 的同步入口，会阻塞直到抓取完成。
    from crawler.spiders.lagou import LagouSpider
    from scrapy.crawler import CrawlerProcess

    process = CrawlerProcess(settings=_scrapy_settings())
    process.crawl(LagouSpider, max_per_site=args.max)
    process.start()


def cmd_crawl_51job(args):
    # 业务说明：使用 Scrapy 框架抓取前程无忧职位数据（HTTP 模式）。
    from crawler.spiders.job51 import Job51Spider
    from scrapy.crawler import CrawlerProcess

    process = CrawlerProcess(settings=_scrapy_settings())
    process.crawl(Job51Spider, max_per_site=args.max)
    process.start()


def cmd_crawl_boss(args):
    # 业务说明：使用 Playwright-stealth 模式抓取 BOSS 直聘职位数据。
    # BOSS 直聘有严格的反爬机制，必须使用浏览器模拟才能获取完整数据。
    # 技术说明：run_sync 为同步包装函数，内部启动异步 Playwright 浏览器。
    from crawler.spiders.boss import run_sync
    items = run_sync(keyword=args.keyword or "python", max_count=args.max, proxy=args.proxy)
    log.info("BOSS 拿到 %d 条", len(items))
    # 业务说明：将抓取结果写入数据库，使用 upsert（插入或更新）避免重复。
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
    # 业务说明：使用 Playwright-stealth 模式抓取拉勾网职位数据。
    # 适用于拉勾网反爬升级、HTTP 模式被封禁时的备选方案。
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
    # 业务说明：使用 Playwright-stealth 模式抓取前程无忧职位数据。
    # 适用于前程无忧反爬升级、HTTP 模式被封禁时的备选方案。
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
    # 业务说明：使用 Apify 云平台抓取拉勾网职位数据。
    # Apify 提供住宅代理和云基础设施，可绕过 WAF 限制，适合大规模抓取。
    # 技术说明：Apify 免费层有抓取量限制，付费层可解除限制。
    from crawler.scripts.apify_lagou import run_apify_lagou
    summary = run_apify_lagou(
        max_items=args.max,
        dry_run=args.dry_run,
    )
    log.info("Apify 拉勾: total=%d inserted=%d", summary.get("total", 0), summary.get("inserted", 0))


def cmd_apify_liepin(args):
    # 业务说明：使用 Apify 云平台抓取猎聘网职位数据（付费功能）。
    from crawler.scripts.apify_liepin import run_apify_liepin
    summary = run_apify_liepin(max_items=args.max, dry_run=args.dry_run, force_paid=args.force_paid)
    log.info('Apify liepin: total=%d inserted=%d', summary.get('total', 0), summary.get('inserted', 0))


def cmd_apify_zhaopin(args):
    # 业务说明：使用 Apify 云平台抓取智联招聘职位数据（付费功能）。
    from crawler.scripts.apify_zhaopin import run_apify_zhaopin
    summary = run_apify_zhaopin(max_items=args.max, dry_run=args.dry_run, force_paid=args.force_paid)
    log.info('Apify zhaopin: total=%d inserted=%d', summary.get('total', 0), summary.get('inserted', 0))


def _add_common_args(sp):
    """给 spider 子命令加通用参数。"""
    # 业务说明：为所有爬虫子命令添加通用参数，避免重复定义。
    # 参数说明：
    #   --max: 最大抓取数量，默认使用 config.MAX_PER_SITE
    #   --keyword: 搜索关键词，默认 "python"
    #   --proxy: 代理地址，格式为 http://user:pass@host:port
    sp.add_argument("--max", type=int, default=config.MAX_PER_SITE)
    sp.add_argument("--keyword", default="python")
    sp.add_argument("--proxy", help="代理地址 (http://user:pass@host:port)")


def main():
    # 业务说明：构建命令行参数解析器，注册所有子命令。
    # 技术说明：使用 argparse 的 subparsers 机制实现子命令路由。
    p = argparse.ArgumentParser(prog="r1-crawler")
    sub = p.add_subparsers(dest="cmd", required=True)

    # 业务说明：注册 init 子命令，用于初始化数据库表结构。
    sub.add_parser("init", help="建 jd_raw / compliance_log 表")
    # 业务说明：注册 stats 子命令，用于统计职位数据。
    sub.add_parser("stats", help="统计 jd_raw")

    # HTTP 版 spider
    # 业务说明：注册基于 Scrapy 的 HTTP 模式爬虫命令。
    for site, fn in (("lagou", cmd_crawl_lagou), ("51job", cmd_crawl_51job)):
        sp = sub.add_parser(site, help=f"爬 {site} (HTTP)")
        _add_common_args(sp)
        sp.set_defaults(func=fn)

    # BOSS（已经是 Playwright）
    # 业务说明：BOSS 直聘必须使用 Playwright-stealth 模式，单独注册。
    sp_boss = sub.add_parser("bosszhipin", help="爬 BOSS 直聘 (Playwright-stealth)")
    _add_common_args(sp_boss)
    sp_boss.set_defaults(func=cmd_crawl_boss)

    # Playwright-stealth 版
    # 业务说明：注册反检测浏览器模式的爬虫命令，适用于反爬严格的站点。
    for site, fn in (
        ("lagou_stealth", cmd_crawl_lagou_stealth),
        ("51job_stealth", cmd_crawl_51job_stealth),
    ):
        sp = sub.add_parser(site, help=f"爬 {site} (Playwright-stealth)")
        _add_common_args(sp)
        sp.set_defaults(func=fn)

    # all = HTTP 版 3 站点
    # 业务说明：批量执行 HTTP 模式的 3 个站点抓取，依次执行而非并行。
    # 技术说明：使用 lambda 依次调用 3 个命令函数，注意这不是真正的并行执行。
    sp_all = sub.add_parser("all", help="跑 3 个站点 (HTTP)")
    _add_common_args(sp_all)
    sp_all.set_defaults(func=lambda a: (
        cmd_crawl_lagou(argparse.Namespace(max=a.max, keyword=a.keyword, proxy=None)),
        cmd_crawl_51job(argparse.Namespace(max=a.max, keyword=a.keyword, proxy=None)),
        cmd_crawl_boss(argparse.Namespace(max=a.max, keyword=a.keyword, proxy=None)),
    ))

    # stealth_all = stealth 版 3 站点
    # 业务说明：批量执行 Stealth 模式的 3 个站点抓取。
    sp_stealth_all = sub.add_parser("stealth_all", help="跑 3 个站点 (Playwright-stealth)")
    _add_common_args(sp_stealth_all)
    sp_stealth_all.set_defaults(func=lambda a: (
        cmd_crawl_lagou_stealth(argparse.Namespace(max=a.max, keyword=a.keyword, proxy=a.proxy)),
        cmd_crawl_51job_stealth(argparse.Namespace(max=a.max, keyword=a.keyword, proxy=a.proxy)),
        cmd_crawl_boss(argparse.Namespace(max=a.max, keyword=a.keyword, proxy=a.proxy)),
    ))

    # Apify 拉勾（自带住宅代理绕 WAF）
    # 业务说明：注册 Apify 云抓取命令，使用 Apify 的住宅代理绕过 WAF。
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

    # 业务说明：解析命令行参数并执行对应的处理函数。
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
