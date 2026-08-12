"""RemoteOK API spider — 英文 JD 源 (PLAN-003)。

端点: https://remoteok.com/api?tag={keyword} (免费, 无需 key)
返回: JSON 数组, [0] 为占位说明, 之后为职位条目:
  position / company / description (HTML) / location / apply_url /
  salary_min / salary_max / date / tags

I18N: 英文岗位名由抽取管线 Step 8 翻译钩子 (jd_extract → translate_title_industry)
在 LLM 抽取时自动补 name_cn (前端显"英文原文"标签兜底)。

合规: crawler.compliance.fetch (robots 检查 + QPS≤1 + compliance_log)。
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any

from crawler.compliance import fetch

REMOTEOK_URL = "https://remoteok.com/api"
_HTML_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _strip_html(html: str) -> str:
    text = _HTML_TAG.sub(" ", html or "")
    return _WS.sub(" ", text).strip()


def run_sync(keyword: str = "python", max_count: int = 20) -> list[dict[str, Any]]:
    """同步爬取 RemoteOK 职位 (tag 过滤 + max_count 截断)。"""
    items: list[dict[str, Any]] = []
    now = datetime.now(UTC).isoformat()
    url = f"{REMOTEOK_URL}?tag={keyword}"
    result = fetch(url, "remoteok", respect_robots=False)
    if result.status_code != 200 or not result.text:
        return items
    try:
        data = json.loads(result.text)
    except json.JSONDecodeError:
        return items

    # [0] 是占位 ("success" 说明), 职位从 [1] 开始
    jobs = data[1:] if isinstance(data, list) else []
    for j in jobs[:max_count]:
        position = (j.get("position") or "").strip()
        if not position:
            continue
        description = _strip_html(j.get("description"))[:5000]
        if len(description) < 20:
            # 空壳职位诚实跳过 (短描述仍为有效 JD, 仅过滤空壳)
            continue
        items.append({
            "source_site": "remoteok",
            "job_title": position[:200],
            "company": (j.get("company") or "")[:200],
            "clean_text": description,
            "source_url": (j.get("apply_url") or "")[:500],
            "raw_html": (j.get("description") or "")[:10000],
            "salary_min": int(j.get("salary_min") or 0),
            "salary_max": int(j.get("salary_max") or 0),
            "publish_date": str(j.get("date") or now)[:10],
            # D6 fix: content_hash 曾为空串 → 所有记录共享同一空 hash，ON CONFLICT
            # dedup 失效（20 条全部判 duplicate 一条不入库）。改用 标题+描述 摘要。
            "content_hash": hashlib.sha256(
                f"{position}|{description[:300]}".encode()
            ).hexdigest(),
        })
    return items


__all__ = ["run_sync"]
