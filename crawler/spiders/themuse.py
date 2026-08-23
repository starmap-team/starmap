"""The Muse API spider — 免费无需 key ( https://www.themuse.com/api/public/jobs ).

字段映射: name→job_title, company.name→company, contents→clean_text,
          refs.landing_page→source_url, id→content_hash, locations→location
实测: HTTP 200, 6344 岗位, 318 页
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any

from crawler.compliance import fetch

MUSE_URL = "https://www.themuse.com/api/public/jobs"
_HTML_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _strip_html(html: str) -> str:
    text = _HTML_TAG.sub(" ", html or "")
    return _WS.sub(" ", text).strip()


def run_sync(keyword: str = "", max_count: int = 20) -> list[dict[str, Any]]:
    """同步爬取 The Muse 职位 (Remote 过滤 + max_count 截断)。"""
    items: list[dict[str, Any]] = []
    now = datetime.now(UTC).isoformat()
    params = ["page=1", "location=Remote", f"results_per_page={max(max_count, 5)}"]
    if keyword:
        params.append(f"search={keyword}")
    url = f"{MUSE_URL}?{'&'.join(params)}"
    result = fetch(url, "themuse", respect_robots=False)
    if result.status_code != 200 or not result.text:
        return items
    try:
        data = json.loads(result.text)
    except json.JSONDecodeError:
        return items

    jobs = data.get("results", []) if isinstance(data, dict) else []
    for j in jobs[:max_count]:
        name = (j.get("name") or "").strip()
        if not name:
            continue
        # contents 可能是 HTML 或纯文本
        contents = j.get("contents") or ""
        description = _strip_html(contents)[:5000]
        if len(description) < 20:
            continue
        locs = [loc.get("name", "") for loc in (j.get("locations") or [])]
        items.append({
            "source_site": "themuse",
            "job_title": name[:200],
            "company": (j.get("company") or {}).get("name", "")[:200],
            "clean_text": description,
            "source_url": ((j.get("refs") or {}).get("landing_page") or "")[:500],
            "raw_html": contents[:10000],
            "salary_min": 0,
            "salary_max": 0,
            "location": "、".join(locs)[:200] or "Remote",
            "publish_date": str(j.get("publication_date") or now)[:10],
            "content_hash": hashlib.sha256(
                f"{name}|{description[:300]}".encode()
            ).hexdigest(),
        })
    return items


__all__ = ["run_sync"]
