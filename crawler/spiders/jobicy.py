"""Jobicy API spider — 免费无需 key (Phase 15-01).

端点: https://jobicy.com/api/v2/remote-jobs?count=N&tag=python
字段映射: jobTitle→job_title, companyName→company, jobExcerpt→clean_text,
          url→source_url, id→content_hash
实测: HTTP 200
"""
from __future__ import annotations

import hashlib
import json
import urllib.request
from datetime import UTC, datetime
from typing import Any

JOBICY_URL = "https://jobicy.com/api/v2/remote-jobs"
_HEADERS = {"User-Agent": "StarMap/1.0 (+https://github.com/starmap)"}


def run_sync(keyword: str = "python", max_count: int = 20) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    try:
        url = f"{JOBICY_URL}?count={max_count}&tag={keyword}"
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        return items

    now = datetime.now(UTC).isoformat()
    # Jobicy API key changed: response is {"jobs": [...]} (verified 2026-07-29)
    jobs = data.get("jobs") or data.get("jobList", [])
    for j in jobs[:max_count]:
        excerpt = j.get("jobExcerpt", "") or j.get("jobDescription", "")[:5000]
        items.append({
            "source_site": "jobicy",
            "job_title": j.get("jobTitle", "")[:200],
            "company": j.get("companyName", ""),
            "clean_text": excerpt[:5000],
            "source_url": j.get("url", ""),
            "raw_html": excerpt[:10000],
            "salary_min": 0,
            "salary_max": 0,
            "location": j.get("jobGeo", "") or "远程",
            "publish_date": str(j.get("pubDate", ""))[:10] or now[:10],
            "crawled_at": now,
            "content_hash": hashlib.sha256(
                (str(j.get("id", "")) + excerpt[:200]).encode("utf-8")
            ).hexdigest(),
            "detail_html": "",
        })
    return items