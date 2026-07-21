"""V2EX + Remotive API spider — 真实 JD 数据源 (Phase 3.8.10 Pony).

V2EX API 免费无需认证, 返回中文招聘数据.
Remotive API 免费无需认证, 返回英文远程职位.

用法:
    python -m crawler.spiders.v2ex_remote --max 5
    或
    from crawler.spiders.v2ex_remote import run_sync; items = run_sync(max_count=5)
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime, UTC
from typing import Any

import urllib.request
import json
import hashlib


V2EX_TOPICS_URL = "https://www.v2ex.com/api/topics/show.json?node_name=jobs"
V2EX_TOPIC_URL = "https://www.v2ex.com/api/topics/show.json?id={id}"
REMOTIVE_URL = "https://remotive.com/api/remote-jobs?search=python&limit=5"

_HEADERS = {"User-Agent": "StarMap/1.0 (+https://github.com/starmap)"}


def _fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def run_sync(keyword: str = "python", max_count: int = 10) -> list[dict[str, Any]]:
    """同步爬取方法 (兼容 executor.py 调用)."""

    items: list[dict[str, Any]] = []
    now = datetime.now(UTC).isoformat()

    # ── V2EX (中文) ──
    try:
        topics = _fetch(V2EX_TOPICS_URL)
        if isinstance(topics, list):
            topics = topics[:max(max_count // 2, 2)]
            for topic in topics:
                tid = topic.get("id")
                # 获取详情
                detail_html = ""
                try:
                    detail = _fetch(V2EX_TOPIC_URL.format(id=tid))
                    if isinstance(detail, list) and detail:
                        detail_html = detail[0].get("content_rendered", "") or detail[0].get("content", "")
                except Exception:
                    pass

                items.append({
                    "source_site": "v2ex",
                    "clean_text": topic.get("content_rendered", "")[:5000] or topic.get("content", "")[:5000],
                    "source_url": topic.get("url", f"https://www.v2ex.com/t/{tid}"),
                    "raw_html": topic.get("content_rendered", "")[:10000],
                    "job_title": topic.get("title", "未知职位")[:200],
                    "company": "V2EX",
                    "salary_min": 0,
                    "salary_max": 0,
                    "location": "远程/未指定",
                    "publish_date": datetime.fromtimestamp(topic.get("created", 0), UTC).strftime("%Y-%m-%d"),
                    "crawled_at": now,
                    "content_hash": hashlib.sha256(topic.get("content", "v2ex").encode()[:100]).hexdigest(),
                    "detail_html": detail_html[:5000],
                })

                if len(items) >= max_count:
                    break
    except Exception as e:
        # 非 fatal — 有 V2EX 够了
        pass

    # ── Remotive (英文) ──
    try:
        remo = _fetch(REMOTIVE_URL)
        for job in remo.get("jobs", [])[:max(max_count - len(items), 0)]:
            desc = job.get("description", "")[:5000]
            items.append({
                "source_site": "remotive",
                    "clean_text": desc,
                "source_url": job.get("url", ""),
                "raw_html": desc,
                "job_title": job.get("title", "未知")[:200],
                "company": job.get("company_name", "未知"),
                "salary_min": 0,
                "salary_max": 0,
                "location": job.get("candidate_required_location", "Remote"),
                "publish_date": job.get("publication_date", ""),
                "crawled_at": now,
                "content_hash": hashlib.sha256(desc.encode()).hexdigest(),
                "detail_html": desc,
            })
    except Exception:
        pass

    return items


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", default="python")
    parser.add_argument("--max", type=int, default=10, dest="max_count")
    args = parser.parse_args()

    t0 = time.time()
    items = run_sync(keyword=args.keyword, max_count=args.max_count)
    elapsed = time.time() - t0
    print(f"Got {len(items)} JD items in {elapsed:.1f}s")
    for it in items[:5]:
        print(f"  {it['source_site']:8} | {it['job_title'][:40]}")


if __name__ == "__main__":
    main()
