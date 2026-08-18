"""R1 CLI 入口。

用法:
 python run.py init # 建表
 python run.py stats # 统计
 python run.py apify_lagou # 跑拉勾 (Apify, 免费层)
 python run.py run-pipeline # 触发完整 pipeline（crawl 阶段跑真实开放源）

2026-08-05（ / CR-09）：删除指向不存在模块的死子命令
（lagou/51job/bosszhipin/lagou_stealth/51job_stealth/all/stealth_all）。
真实开放源（v2ex/arbeitnow/jobicy/weworkremotely）由 pipeline crawl 阶段
经 executor spider_registry 调度；国内站点真链路见计划书 / 。
"""
# 业务说明：本模块是 StarMap 爬虫系统的 CLI 入口和任务调度中心。
# 提供统一的命令行接口，支持初始化数据库、Apify 云抓取、流水线触发和数据统计。
# 技术说明：使用 argparse 构建命令行解析，支持子命令和参数传递。
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# 让脚本可独立运行
# 业务说明：将项目根目录加入 Python 路径，使脚本可以直接运行而不依赖包安装。
# 技术说明：sys.path.insert 确保导入 crawler 包时能找到正确的位置。
sys.path.insert(0, str(Path(__file__).resolve.parent.parent))

from crawler.persistence import dao
from crawler.pipeline_bridge import trigger_pipeline_run

# 业务说明：配置根日志记录器，设置日志级别和格式。
# 技术说明：format 包含时间戳、日志级别、记录器名称和消息内容。
logging.basicConfig(
 level=logging.INFO,
 format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("r1")

def cmd_init(_args):
 # 业务说明：初始化数据库表结构，创建 jd_raw 和 compliance_log 等必要表。
 # 首次部署或数据库 schema 变更后需要执行。
 log.info("建表...")
 dao.init_schema
 log.info("OK")

def cmd_stats(_args):
 # 业务说明：统计数据库中职位数据的总量和按状态分布情况。
 # 输出 JSON 格式结果，便于脚本化处理和监控。
 log.info("统计 jd_raw ...")
 total = dao.count_jd
 by_status = dao.count_by_status
 print(json.dumps({"total": total, "by_status": by_status}, ensure_ascii=False, indent=2))

def cmd_apify_lagou(args):
 # 业务说明：使用 Apify 云平台抓取拉勾网职位数据。
 # Apify 提供住宅代理和云基础设施，可绕过 WAF 限制，适合大规模抓取。
 # 技术说明：Apify 免费层有抓取量限制，付费层可解除限制。
 from crawler.scripts.apify_lagou import run_apify_lagou
 summary = run_apify_lagou(
 max_items=args.max,
 dry_run=args.dry_run)
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

def cmd_run_pipeline(args):
 """ (b): CLI 子命令触发一次完整 pipeline run."""
 # 业务说明：通过 pipeline_bridge 调用后端 executor.trigger_and_start，
 # 与 main API 等价的调用路径（CLI 与后端同进程内）。
 # 技术说明：trigger_pipeline_run 内部用 asyncio.run 跑异步 trigger_and_start，
 # 返回 0 / 1 作为子命令退出码（成功 / 失败）。
 log.info("CLI run-pipeline 触发: source=%s, limit=%s", args.source, args.limit)
 rc = trigger_pipeline_run(source=args.source, limit=args.limit)
 if rc != 0:
 log.error("Pipeline trigger 退出码 %d", rc)
 return rc

def main:
 # 业务说明：构建命令行参数解析器，注册所有子命令。
 # 技术说明：使用 argparse 的 subparsers 机制实现子命令路由。
 p = argparse.ArgumentParser(prog="r1-crawler")
 sub = p.add_subparsers(dest="cmd", required=True)

 # 业务说明：注册 init 子命令，用于初始化数据库表结构。
 sub.add_parser("init", help="建 jd_raw / compliance_log 表")
 # 业务说明：注册 stats 子命令，用于统计职位数据。
 sub.add_parser("stats", help="统计 jd_raw")

 # Apify 拉勾（免费层）
 # 业务说明：注册 Apify 云抓取命令，使用 Apify 的住宅代理绕过 WAF。
 sp_apify = sub.add_parser("apify_lagou", help="爬拉勾 (Apify，免费层 actor)")
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

 # (b): CLI 触发完整 pipeline run
 # 业务说明：注册 run-pipeline 子命令，触发一次完整流水线
 # (crawl → dedup → clean → extract → graph_sync)。
 # crawl 阶段按 DataSourceRecord 配置跑真实开放源（v2ex/arbeitnow/jobicy/weworkremotely）。
 sp_pipeline = sub.add_parser(
 "run-pipeline",
 help="触发一次完整 pipeline run（与 POST /api/v1/pipeline/trigger 等价）")
 sp_pipeline.add_argument(
 "--source", default="auto",
 choices=["auto", "v2ex", "arbeitnow", "jobicy", "weworkremotely"],
 help="爬取源标识（仅用于 run_type 标记；实际源由数据源配置决定）")
 sp_pipeline.add_argument(
 "--limit", type=int, default=20,
 help="最大抓取条数（信息性，调用透传给 trigger_and_start）")
 sp_pipeline.set_defaults(func=cmd_run_pipeline)

 # 业务说明：解析命令行参数并执行对应的处理函数。
 args = p.parse_args
 if args.cmd == "init":
 cmd_init(args)
 elif args.cmd == "stats":
 cmd_stats(args)
 elif hasattr(args, "func"):
 args.func(args)
 else:
 p.print_help

if __name__ == "__main__":
 main
