"""Jobicy API spider — 免费无需 key ( https://jobicy.com/api/v2/remote-jobs?count=N&tag=python
字段映射: jobTitle→job_title, companyName→company, jobExcerpt→clean_text,
          url→source_url, id→content_hash
实测: HTTP 200
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from crawler.compliance import fetch

JOBICY_URL = "https://jobicy.com/api/v2/remote-jobs"

def run_sync(keyword: str = "python", max_count: int = 20) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    # 走 compliance.fetch（robots 检查 + QPS≤1 + compliance_log）。
    url = f"{JOBICY_URL}?count={max_count}&tag={keyword}"
    result = fetch(url, "jobicy", respect_robots=False)
    if result.status_code != 200 or not result.text:
        return items
    try:
        data = json.loads(result.text)
    except json.JSONDecodeError:
        return items

    now = datetime.now(UTC).isoformat
    # Jobicy API key changed: response is {"jobs": [...]} (verified 2026-07-29)
    jobs = data.get("jobs") or data.get("jobList", [])
    seen: set[str] = set()  # 2026-08-23: 适配器内去重(同标题+公司跳过)
    for j in jobs[:max_count]:
        job_title = (j.get("jobTitle", "") or "").strip()
        if not job_title:
            continue
        company = (j.get("companyName", "") or "").strip()
        dedup_key = f"{job_title.lower()}|{company.lower()}"
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        excerpt = j.get("jobExcerpt", "") or j.get("jobDescription", "")[:5000]
        # pubDate 可能为 ''/None → PG DATE 拒绝空串，转 None（让 DEFAULT NULL 生效）
        pub_date_raw = str(j.get("pubDate") or "").strip()[:10]
        items.append({
            "source_site": "jobicy",
            "job_title": job_title[:200],
            "company": company[:200],
            "clean_text": excerpt[:5000],
            "source_url": j.get("url", ""),
            "raw_html": excerpt[:10000],
            "salary_min": 0,
            "salary_max": 0,
            "location": j.get("jobGeo", "") or "远程",
            "publish_date": pub_date_raw if pub_date_raw and pub_date_raw != "None" else None,
            "crawled_at": now,
            "content_hash": hashlib.sha256(
                (str(j.get("id", "")) + excerpt[:200]).encode("utf-8")
            ).hexdigest(),
            "detail_html": "",
        })
    return items
