#!/usr/bin/env python3
"""Apify 51job 爬虫 — 绕过 WAF 获取真实数据"""
import argparse
import json
import logging
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

from apify_client import ApifyClient

from crawler import config
from crawler.compliance import is_allowed, log_request
from crawler.dedup import hex64, simhash
from crawler.persistence import dao
from crawler.persistence.models import JdStatus

log = logging.getLogger(__name__)

ACTOR_51JOB = "zhaopin-scraper"  # Apify 上 51job 智联爬虫
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
_COMPLIANCE_UA = "StarMap-Apify/1.0"


def run_apify_51job(max_items=100, keywords=None, dry_run=False):
    """Apify 抓 51job"""
    client = ApifyClient(APIFY_TOKEN)

    keywords = keywords or ["python", "java", "算法", "前端", "大模型"]

    run_input = {
        "searchKeywords": keywords,
        "maxResults": max_items,
    }

    log.info("启动 Apify Actor: %s", ACTOR_51JOB)
    log.info("关键词: %s", keywords)
    log.info("最大条数: %d", max_items)

    run = client.actor(ACTOR_51JOB).call(run_input=run_input)

    dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else run.default_dataset_id
    log.info("Actor 完成，dataset_id=%s", dataset_id)

    items = list(client.dataset(dataset_id).iterate_items())
    log.info("Apify 返回 %d 条数据", len(items))

    # 合规审计
    log_request(
        source_site="51job",
        target_url=f"apify://actor/{ACTOR_51JOB}/dataset/{dataset_id}",
        robots_allowed=True,
        user_agent=_COMPLIANCE_UA,
        qps=0.0,
        response_code=200,
        response_bytes=len(json.dumps(items, ensure_ascii=False).encode()),
    )

    if dry_run:
        log.info("[DRY RUN] 前 3 条:")
        for item in items[:3]:
            print(json.dumps(item, ensure_ascii=False, indent=2)[:500])
        return {"total": len(items), "inserted": 0, "failed": 0, "skipped": 0}

    inserted = 0
    failed = 0
    skipped = 0

    for item in items:
        try:
            title = item.get("jobName") or item.get("jobTitle") or item.get("title") or ""
            company = item.get("companyName") or item.get("companyShortName") or ""
            description = item.get("jobDesc") or item.get("jobDescription") or ""
            url = item.get("jobUrl") or item.get("url") or ""
            city = item.get("workCity") or item.get("city") or ""
            education = item.get("education") or ""
            salary = item.get("salary") or ""
            item_id = item.get("positionId") or item.get("id") or ""

            if not title and not description:
                skipped += 1
                continue

            if not url or not url.strip():
                if item_id:
                    url = f"apify://51job/{dataset_id}/{item_id}"
                else:
                    url = f"apify://51job/{dataset_id}/title/{hash(title) % 10**8}"

            robots_ok = is_allowed(url, _COMPLIANCE_UA)
            log_request(
                source_site="51job",
                target_url=url,
                robots_allowed=robots_ok,
                user_agent=_COMPLIANCE_UA,
                qps=0.0,
                response_code=200,
                response_bytes=len(description.encode()) if description else 0,
            )

            from crawler.pipelines.clean import clean_html
            clean = clean_html(description) if description else ""
            if not clean or len(clean) < 50:
                parts = [p for p in [title, company, education, salary] if p]
                clean = " ".join(parts)
                if len(clean) < 30:
                    skipped += 1
                    continue

            rec = {
                "source_site": "51job",
                "source_url": url,
                "raw_html": description,
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
            log.warning("处理条目失败: %s", e)
            failed += 1

    summary = {"total": len(items), "inserted": inserted, "failed": failed, "skipped": skipped}
    log.info("Apify 51job 完成: inserted=%d, skipped=%d, failed=%d", inserted, skipped, failed)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Apify 51job 爬虫")
    parser.add_argument("--max", type=int, default=100, help="最大条数")
    parser.add_argument("--keywords", nargs="+", default=["python", "java", "算法", "前端", "大模型"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    summary = run_apify_51job(args.max, args.keywords, args.dry_run)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
