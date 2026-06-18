"""Apify 拉勾爬虫集成：调用 Apify Actor 抓取拉勾数据，入库 jd_raw。

用法:
    # 先设置 Apify API Token
    $env:APIFY_TOKEN='your_token_here'

    # 抓 10 条
    python crawler/scripts/apify_lagou.py --max 10

    # 抓 50 条，指定城市
    python crawler/scripts/apify_lagou.py --max 50 --cities beijing shanghai

    # 仅测试（不入库）
    python crawler/scripts/apify_lagou.py --max 5 --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from crawler.dedup import hex64, simhash
from crawler.pipelines.clean import clean_html, extract_job_title
from crawler.persistence import dao
from crawler.persistence.models import JdStatus

log = logging.getLogger(__name__)

# Apify Actor ID（拉勾技术岗位爬虫）
LAGOU_ACTOR = "logiover/lagou-tech-jobs-scraper"


def run_apify_lagou(
    max_items: int = 10,
    keywords: list[str] | None = None,
    cities: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """调用 Apify Actor 抓取拉勾数据。

    Returns:
        统计 dict {total, inserted, failed, skipped}
    """
    from apify_client import ApifyClient

    token = os.getenv("APIFY_TOKEN")
    if not token:
        log.error("未设置 APIFY_TOKEN 环境变量")
        log.error("请在 Apify Console (https://console.apify.com/account/integrations) 获取 token")
        return {"total": 0, "inserted": 0, "failed": 0, "error": "missing APIFY_TOKEN"}

    keywords = keywords or ["python", "java", "算法", "前端", "大模型"]
    cities = cities or ["beijing", "shanghai", "shenzhen"]

    log.info("调用 Apify Actor: %s", LAGOU_ACTOR)
    log.info("关键词: %s", keywords)
    log.info("城市: %s", cities)
    log.info("最大条数: %d", max_items)

    client = ApifyClient(token)

    run_input = {
        "keywords": keywords,
        "cities": cities,
        "expandFilters": True,
        "maxJobsTotal": max_items,
        "maxConcurrency": 3,
        "proxyConfiguration": {
            "useApifyProxy": True,
            "apifyProxyGroups": ["RESIDENTIAL"],
        },
        "requestDelay": 1000,
        "includeDescription": True,
    }

    try:
        log.info("Actor 启动中（可能需要几分钟）...")
        run = client.actor(LAGOU_ACTOR).call(run_input=run_input)
    except Exception as e:
        log.error("Apify Actor 调用失败: %s", e)
        return {"total": 0, "inserted": 0, "failed": 0, "error": str(e)}

    status = run.status if hasattr(run, "status") else run.get("status", "")
    if status != "SUCCEEDED":
        log.error("Apify Actor 运行失败: status=%s", status)
        return {"total": 0, "inserted": 0, "failed": 0, "error": f"Actor status: {status}"}

    # 获取结果
    dataset_id = run.default_dataset_id if hasattr(run, "default_dataset_id") else run["defaultDatasetId"]
    log.info("Actor 完成，dataset_id=%s，获取结果...", dataset_id)

    items = list(client.dataset(dataset_id).iterate_items())
    log.info("Apify 返回 %d 条数据", len(items))

    if dry_run:
        log.info("[DRY RUN] 不入库，打印前 3 条示例:")
        for item in items[:3]:
            log.info(json.dumps(item, ensure_ascii=False, indent=2)[:500])
        return {"total": len(items), "inserted": 0, "failed": 0, "skipped": 0}

    # 入库
    inserted = 0
    failed = 0
    skipped = 0

    for item in items:
        try:
            # 提取字段（Apify 返回的字段名）
            title = item.get("jobTitle") or item.get("title") or ""
            company = item.get("companyName") or item.get("companyShortName") or ""
            description = item.get("description") or item.get("jobDescription") or ""
            salary = item.get("salary") or ""
            location = item.get("city") or item.get("location") or ""
            url = item.get("jobUrl") or item.get("url") or item.get("link") or ""
            skills = item.get("skills") or ""
            education = item.get("education") or ""
            work_year = item.get("workYear") or ""

            if not title and not description:
                skipped += 1
                continue

            # 清洗 HTML
            clean = clean_html(description) if description else ""
            if not clean or len(clean) < 50:
                # Apify 列表接口不返回详情，用标题+技能+公司拼接
                parts = [p for p in [title, company, skills, education, work_year, salary] if p]
                clean = " ".join(parts)
                if len(clean) < 30:
                    skipped += 1
                    continue

            # 解析薪资（Apify 已提供 salaryMin/salaryMax，单位 k）
            salary_min = None
            salary_max = None
            if item.get("salaryMin"):
                salary_min = int(item["salaryMin"]) * 1000
            if item.get("salaryMax"):
                salary_max = int(item["salaryMax"]) * 1000
            elif salary:
                import re
                nums = re.findall(r"(\d+)", salary)
                if len(nums) >= 2:
                    salary_min = int(nums[0]) * 1000
                    salary_max = int(nums[1]) * 1000

            rec = {
                "source_site": "lagou",
                "source_url": url,
                "raw_html": description,
                "clean_text": clean,
                "job_title": title[:200],
                "company": company or None,
                "salary_min": salary_min,
                "salary_max": salary_max,
                "location": location or None,
                "publish_date": date.today(),
                "content_hash": hex64(simhash(clean)),
                "status": JdStatus.raw,
            }

            r = dao.upsert_jd(rec)
            if r == "inserted":
                inserted += 1
            elif r == "duplicate":
                skipped += 1  # 已存在，跳过
            else:
                failed += 1

        except Exception as e:
            log.warning("处理条目失败: %s", e)
            failed += 1

    summary = {"total": len(items), "inserted": inserted, "failed": failed, "skipped": skipped}
    log.info("=" * 50)
    log.info("Apify 拉勾爬取完成")
    log.info("  total:    %d", summary["total"])
    log.info("  inserted: %d", summary["inserted"])
    log.info("  failed:   %d", summary["failed"])
    log.info("  skipped:  %d", summary["skipped"])
    log.info("=" * 50)

    return summary


def main():
    parser = argparse.ArgumentParser(description="Apify 拉勾爬虫")
    parser.add_argument("--max", type=int, default=10, help="最大抓取条数")
    parser.add_argument("--keywords", nargs="+", default=["python", "java", "算法", "前端", "大模型"])
    parser.add_argument("--cities", nargs="+", default=["beijing", "shanghai", "shenzhen"])
    parser.add_argument("--dry-run", action="store_true", help="仅测试，不入库")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    summary = run_apify_lagou(
        max_items=args.max,
        keywords=args.keywords,
        cities=args.cities,
        dry_run=args.dry_run,
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
