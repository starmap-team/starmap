"""增量爬取 CLI 入口。

Issue #36 — 阶段3 数据增量更新管道。

用法:
 python -m crawler.scripts.run_incremental crawl --source v2ex --max 50
 python -m crawler.scripts.run_incremental crawl --source all --max 100 --skip-existing
 python -m crawler.scripts.run_incremental report
 python -m crawler.scripts.run_incremental report --source v2ex

2026-08-05（）：源清单改为真实开放源 v2ex/arbeitnow/jobicy/weworkremotely，
移除 lagou/51job/bosszhipin 死引用（对应 spider 模块不存在）。
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve.parent.parent.parent))

from crawler.persistence import dao
from crawler.persistence.models import JdStatus
from crawler.pipelines.incremental import check_incremental
from crawler.pipelines.quality_report import (
 format_report_text,
 generate_quality_report,
)

logging.basicConfig(
 level=logging.INFO,
 format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("incremental")

def _spider_registry -> dict:
 """真实开放源注册表（：移除指向不存在模块的死引用）。"""
 from crawler.spiders import arbeitnow, jobicy, juejin, remoteok, weworkremotely
 from crawler.spiders.v2ex_remote import run_sync as v2ex_sync

 return {
 "v2ex": v2ex_sync,
 "arbeitnow": arbeitnow.run_sync,
 "jobicy": jobicy.run_sync,
 "weworkremotely": weworkremotely.run_sync,
 "juejin": juejin.run_sync, # : 非结构化源 (sitemap)
 "remoteok": remoteok.run_sync, # : 英文 JD 源 (API)
 }

_OPEN_SOURCES = ("v2ex", "arbeitnow", "jobicy", "weworkremotely", "juejin", "remoteok")

def _crawl_site(site: str, max_count: int) -> list[dict]:
 """爬取单个站点，返回 item 列表（不入库）。"""
 fn = _spider_registry.get(site)
 if fn is None:
 log.warning("未知或已下线的源: %s（可选: %s）", site, ", ".join(_OPEN_SOURCES))
 return []
 return [dict(it) for it in fn(keyword="python", max_count=max_count)]

def cmd_incremental(args: argparse.Namespace) -> None:
 """增量爬取：爬取 → 差分过滤 → 入库。"""
 sites = list(_OPEN_SOURCES) if args.source == "all" else [args.source]

 for site in sites:
 log.info("=== 增量爬取 %s (max=%d) ===", site, args.max)

 # 爬取
 items = _crawl_site(site, args.max)
 log.info("爬取到 %d 条", len(items))

 if not items:
 log.warning("%s 无数据", site)
 continue

 # 增量过滤
 filtered, stats = check_incremental(
 items,
 source_site=site,
 skip_existing_urls=args.skip_existing,
 simhash_threshold=args.simhash_threshold,
 )

 # 入库过滤后的记录
 inserted = 0
 for rec in filtered:
 rec.setdefault("status", JdStatus.raw)
 r = dao.upsert_jd(rec)
 if r == "inserted":
 inserted += 1

 log.info(
 "%s 结果: 爬取=%d URL重复=%d 内容重复=%d 入库=%d",
 site, stats.total, stats.url_duplicate,
 stats.content_near_duplicate, inserted,
 )

def cmd_report(args: argparse.Namespace) -> None:
 """生成数据质量报告。"""
 source = args.source if args.source != "all" else None
 report = generate_quality_report(source_site=source)
 print(format_report_text(report))

 if args.json:
 print(json.dumps({
 "total": report.total,
 "unique_urls": report.unique_urls,
 "unique_hashes": report.unique_hashes,
 "dedup_rate": report.dedup_rate,
 "by_source": report.by_source,
 "by_status": report.by_status,
 "by_date": report.by_date,
 }, ensure_ascii=False, indent=2))

def main -> None:
 p = argparse.ArgumentParser(prog="run_incremental", description="增量爬取 + 质量报告")
 sub = p.add_subparsers(dest="cmd", required=True)

 # 增量爬取
 sp_crawl = sub.add_parser("crawl", help="增量爬取（差分去重后入库）")
 sp_crawl.add_argument("--source", default="all", choices=[*_OPEN_SOURCES, "all"])
 sp_crawl.add_argument("--max", type=int, default=50, help="每站点最大爬取数")
 sp_crawl.add_argument("--skip-existing", action="store_true", default=True, help="跳过已入库 URL")
 sp_crawl.add_argument("--simhash-threshold", type=int, default=10, help="SimHash 近似阈值（计划 默认 10）")
 sp_crawl.set_defaults(func=cmd_incremental)

 # 质量报告
 sp_report = sub.add_parser("report", help="数据质量报告")
 sp_report.add_argument("--source", default="all", help="数据源过滤（source_site 字符串或 all）")
 sp_report.add_argument("--json", action="store_true", help="同时输出 JSON")
 sp_report.set_defaults(func=cmd_report)

 args = p.parse_args
 args.func(args)

if __name__ == "__main__":
 main
