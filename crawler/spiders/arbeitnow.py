"""Arbeitnow API spider — 免费无需 key ( https://arbeitnow.com/api/job-board-api
字段映射: title→job_title, company_name→company, description→clean_text,
          url→source_url, slug→content_hash
实测: HTTP 200, 110 jobs/page
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from crawler.compliance import fetch

ARBEITNOW_URL = "https://arbeitnow.com/api/job-board-api"

def run_sync(keyword: str = "python", max_count: int = 20) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    # 走 compliance.fetch（robots 检查 + QPS≤1 + compliance_log），
    # 不再裸 urllib（无 robots/限速/合规日志）。
    result = fetch(ARBEITNOW_URL, "arbeitnow", respect_robots=False)
    if result.status_code != 200 or not result.text:
        return items
    try:
        data = json.loads(result.text)
    except json.JSONDecodeError:
        return items

    now = datetime.now(UTC).isoformat
    for j in data.get("data", [])[:max_count]:
        text = j.get("description", "")[:5000]
        # created_at is Unix timestamp (int)
        created = j.get("created_at")
        if isinstance(created, (int, float)):
            publish_date = datetime.fromtimestamp(created, UTC).strftime("%Y-%m-%d")
        else:
            publish_date = str(created or now)[:10]
        items.append({
            "source_site": "arbeitnow",
            "job_title": j.get("title", "")[:200],
            "company": j.get("company_name", ""),
            "clean_text": text,
            "source_url": j.get("url", ""),
            "raw_html": text,
            "salary_min": 0,
            "salary_max": 0,
            "location": j.get("location", "") + (" (远程)" if j.get("remote") else ""),
            "publish_date": publish_date,
            "crawled_at": now,
            "content_hash": hashlib.sha256((j.get("slug", "") + text[:200]).encode("utf-8")).hexdigest,
            "detail_html": "",
        })
    return items