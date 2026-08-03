"""WeWorkRemotely RSS spider — 免费无需 key (Phase 15-01).

端点: https://weworkremotely.com/categories/remote-programming-jobs.rss
字段映射: title→job_title (格式 "Company: Position"), link→source_url,
          description→clean_text, pubDate→publish_date
实测: HTTP 200, RSS XML 格式
"""
from __future__ import annotations

import hashlib
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any

WWR_RSS = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
_HEADERS = {"User-Agent": "StarMap/1.0 (+https://github.com/starmap)"}


def run_sync(keyword: str = "", max_count: int = 20) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    try:
        req = urllib.request.Request(WWR_RSS, headers=_HEADERS)
        xml_data = urllib.request.urlopen(req, timeout=15).read()
    except Exception:
        return items

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return items

    now = datetime.now(UTC).isoformat()
    for item in root.findall(".//item")[:max_count]:
        title_text = item.findtext("title", "") or ""
        link = item.findtext("link", "") or ""
        desc = item.findtext("description", "") or ""
        pub_date = item.findtext("pubDate", "") or ""

        # WWR title 格式: "Company: Position" 或 "Company: Position (Category)"
        if ":" in title_text:
            parts = title_text.split(":", 1)
            company = parts[0].strip()
            position = parts[1].strip()
        else:
            company = ""
            position = title_text.strip()

        items.append({
            "source_site": "weworkremotely",
            "job_title": position[:200],
            "company": company[:200],
            "clean_text": desc[:5000],
            "source_url": link[:500],
            "raw_html": desc[:10000],
            "salary_min": 0,
            "salary_max": 0,
            "location": "远程",
            "publish_date": pub_date[:10] if pub_date else now[:10],
            "crawled_at": now,
            "content_hash": hashlib.sha256(
                (link + title_text).encode("utf-8")
            ).hexdigest(),
            "detail_html": "",
        })
    return items