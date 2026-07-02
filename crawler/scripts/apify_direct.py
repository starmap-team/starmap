#!/usr/bin/env python3
"""Apify multi-platform job scraper (agentx/all-jobs-scraper).

Free actor that scrapes LinkedIn, Indeed, SAP, Freelancer, Talent.com.
Usage:
    $env:APIFY_TOKEN = "your_token"
    python crawler/scripts/apify_direct.py --max 120 --country "China"
    python crawler/scripts/apify_direct.py --max 30 --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from crawler.compliance import is_allowed, log_request
from crawler.dedup import hex64, simhash
from crawler.pipelines.clean import clean_html
from crawler.persistence import dao
from crawler.persistence.models import JdStatus

log = logging.getLogger(__name__)

_COMPLIANCE_UA = "StarMap-Apify/1.0 (compliance-audit)"
ACTOR_ID = "agentx/all-jobs-scraper"


def _extract_str(val, fallback=""):
    """Extract string from possibly-nested dict or plain string."""
    if val is None:
        return fallback
    if isinstance(val, dict):
        # Location dicts: {"raw": "...", "locality": "...", "region": "...", "country": "..."}
        return val.get("raw", val.get("name", val.get("title", str(val))))
    if isinstance(val, list):
        return ", ".join(str(v) for v in val[:3])
    return str(val)[:100]  # Truncate to VARCHAR(100) limit


def _extract_location(item):
    """Extract location string, handling nested dicts from LinkedIn/Indeed."""
    loc = item.get("location") or item.get("city") or item.get("workCity")
    if loc is None:
        return None
    if isinstance(loc, dict):
        # Prefer: raw > locality + country > name > str
        raw = loc.get("raw", "")
        if raw:
            return str(raw)[:100]
        parts = [loc.get("locality", ""), loc.get("region", ""), loc.get("country", "")]
        result = ", ".join(p for p in parts if p)
        return result[:100] if result else str(loc)[:100]
    if isinstance(loc, list):
        return ", ".join(str(v) for v in loc[:3])[:100]
    return str(loc)[:100]


def run_apify_direct(
    max_items: int = 120,
    keyword: str = "python developer",
    country: str = "China",
    dry_run: bool = False,
) -> dict:
    from apify_client import ApifyClient

    token = os.getenv("APIFY_TOKEN")
    if not token:
        log.error("APIFY_TOKEN not set")
        return {"total": 0, "inserted": 0, "failed": 0, "error": "missing APIFY_TOKEN"}

    log.info("Calling Actor: %s | keyword=%s | country=%s | max=%d", ACTOR_ID, keyword, country, max_items)

    client = ApifyClient(token)
    run_input = {"keyword": keyword, "country": country, "max_results": max_items}

    try:
        run = client.actor(ACTOR_ID).call(run_input=run_input)
    except Exception as e:
        log.error("Actor call failed: %s", e)
        return {"total": 0, "inserted": 0, "failed": 0, "error": str(e)}

    status = run.status if hasattr(run, "status") else run.get("status", "")
    if status != "SUCCEEDED":
        return {"total": 0, "inserted": 0, "failed": 0, "error": f"Actor status: {status}"}

    ds_id = run.default_dataset_id if hasattr(run, "default_dataset_id") else run.get("defaultDatasetId")
    items = list(client.dataset(ds_id).iterate_items())
    log.info("Apify returned %d items", len(items))

    log_request(source_site="multi", target_url=f"apify://actor/{ACTOR_ID}/dataset/{ds_id}",
                robots_allowed=True, user_agent=_COMPLIANCE_UA, qps=0.0, response_code=200,
                response_bytes=len(json.dumps(items, ensure_ascii=False).encode()))

    if dry_run:
        for item in items[:5]:
            log.info(json.dumps(item, ensure_ascii=False, indent=2)[:500])
        return {"total": len(items), "inserted": 0, "failed": 0, "skipped": 0}

    inserted = failed = skipped = 0
    for item in items:
        try:
            platform = _extract_str(item.get("platform") or item.get("source") or "unknown")
            platform_map = {
                "linkedin": "linkedin", "LinkedIn": "linkedin",
                "indeed": "indeed", "Indeed": "indeed",
                "SAP": "sap", "sap": "sap",
                "Freelancer.com": "freelancer", "freelancer": "freelancer",
                "Talent.com": "talent", "talent": "talent",
                "USAJOBS": "usajobs",
            }
            source_site = platform_map.get(platform, platform.lower().replace(" ", "_").replace(".com", ""))

            title = _extract_str(item.get("title") or item.get("jobTitle") or item.get("job_name"))
            company = _extract_str(item.get("company") or item.get("companyName") or item.get("organization"))
            description = item.get("description") or item.get("jobDesc") or ""
            url = item.get("platform_url") or item.get("url") or item.get("official_url") or ""
            location = _extract_location(item)
            salary = item.get("salary") or item.get("salaryDesc") or ""

            if not title and not description:
                skipped += 1
                continue

            if not url or not url.strip():
                url = f"apify://{source_site}/{ds_id}/title/{hash(title) % 10**8}"

            robots_ok = is_allowed(url, _COMPLIANCE_UA)
            log_request(source_site=source_site, target_url=url, robots_allowed=robots_ok,
                        user_agent=_COMPLIANCE_UA, qps=0.0, response_code=200,
                        response_bytes=len(description.encode()) if description else 0)

            clean = clean_html(description) if description else ""
            if not clean or len(clean) < 30:
                parts = [p for p in [title, company, location or "", str(salary)] if p]
                clean = " ".join(parts)
                if len(clean) < 20:
                    skipped += 1
                    continue

            salary_min = salary_max = None
            if salary:
                nums = re.findall(r"(\d+)", str(salary))
                if len(nums) >= 2:
                    salary_min = int(nums[0]) * 1000
                    salary_max = int(nums[1]) * 1000

            rec = {
                "source_site": source_site,
                "source_url": url[:2000],  # source_url is TEXT, no limit issue
                "raw_html": description,
                "clean_text": clean,
                "job_title": title[:200],
                "company": (company or None),
                "salary_min": salary_min,
                "salary_max": salary_max,
                "location": location,
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
            log.warning("Item failed: %s", e)
            failed += 1

    summary = {"total": len(items), "inserted": inserted, "failed": failed, "skipped": skipped}
    log.info("Multi-platform crawl done: %s", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Apify multi-platform job scraper")
    parser.add_argument("--max", type=int, default=120)
    parser.add_argument("--keyword", default="python developer")
    parser.add_argument("--country", default="China")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    summary = run_apify_direct(max_items=args.max, keyword=args.keyword, country=args.country, dry_run=args.dry_run)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
