"""Landing.jobs API spider — 免费无需 key ( https://landing.jobs/api/v1/jobs ).

字段映射: title→job_title, url→source_url, main_requirements+role_description→clean_text,
          id→content_hash, locations→location, gross_salary→salary
实测: HTTP 200, 50 条/请求, 欧洲技术岗位
"""
from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

from crawler.compliance import fetch

LANDING_URL = "https://landing.jobs/api/v1/jobs"
_HTML_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _strip_html(html: str) -> str:
    text = _HTML_TAG.sub(" ", html or "")
    return _WS.sub(" ", text).strip()


def run_sync(keyword: str = "", max_count: int = 20) -> list[dict[str, Any]]:
    """同步爬取 Landing.jobs 职位 (技术岗位, max_count 截断)。"""
    items: list[dict[str, Any]] = []
    now = datetime.now(UTC).isoformat()
    url = LANDING_URL + (f"?q={keyword}" if keyword else "")
    result = fetch(url, "landingjobs", respect_robots=False)
    if result.status_code != 200 or not result.text:
        return items
    try:
        import json
        data = json.loads(result.text)
    except (json.JSONDecodeError, ImportError):
        return items

    jobs = data if isinstance(data, list) else []
    for j in jobs[:max_count]:
        title = (j.get("title") or "").strip()
        if not title:
            continue
        req_text = _strip_html(j.get("main_requirements") or "")
        role_text = _strip_html(j.get("role_description") or "")
        description = f"{role_text} {req_text}".strip()[:5000]
        if len(description) < 20:
            continue
        locs = [
            f"{loc.get('city', '')} {loc.get('country_code', '')}".strip()
            for loc in (j.get("locations") or [])
        ]
        items.append({
            "source_site": "landingjobs",
            "job_title": title[:200],
            "company": (j.get("company_name") or "")[:200],
            "clean_text": description,
            "source_url": (j.get("url") or "")[:500],
            "raw_html": (j.get("main_requirements") or "")[:10000],
            "salary_min": int(j.get("gross_salary_low") or 0),
            "salary_max": int(j.get("gross_salary_high") or 0),
            "location": "、".join(locs)[:200] or "欧洲",
            "publish_date": str(j.get("published_at") or now)[:10],
            "content_hash": hashlib.sha256(
                f"{title}|{description[:300]}".encode()
            ).hexdigest(),
        })
    return items


__all__ = ["run_sync"]
