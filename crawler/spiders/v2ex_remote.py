"""V2EX + Remotive API spider — 真实 JD 数据源 (
    python -m crawler.spiders.v2ex_remote --max 5
    或
    from crawler.spiders.v2ex_remote import run_sync; items = run_sync(max_count=5)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from typing import Any

from crawler.compliance import fetch

V2EX_TOPICS_URL = "https://www.v2ex.com/api/topics/show.json?node_name=jobs"
V2EX_TOPIC_URL = "https://www.v2ex.com/api/topics/show.json?id={id}"
REMOTIVE_URL = "https://remotive.com/api/remote-jobs?search=python&limit=5"

def _fetch(url: str, source_site: str) -> Any:
    # CR-06 / PLAN-004: 走 compliance.fetch（robots 检查 + QPS≤1 + compliance_log），
    # 不再裸 urllib。失败时抛错由调用方 try/except 降级（保持原行为）。
    result = fetch(url, source_site, respect_robots=False)
    if result.status_code != 200 or not result.text:
        raise ValueError(f"fetch failed status={result.status_code}")
    return json.loads(result.text)

def run_sync(keyword: str = "python", max_count: int = 10, source: str | None = None) -> list[dict[str, Any]]:
    """同步爬取方法 (兼容 executor.py 调用).

    D6 (2026-08-12): 新增 source 参数实现严格逐源隔离 — 页面 V2EX 卡与
    Remotive 卡共用本适配器，之前一次调用同时写两源记录，导致单源触发
    混入另一源数据。source=None 保持旧行为（双源），source="v2ex" 只抓
    V2EX 酷工作，source="remotive" 只抓 Remotive API。
    """

    items: list[dict[str, Any]] = []
    now = datetime.now(UTC).isoformat

    # ── V2EX (中文) ──
    if source in (None, "v2ex"):
        try:
            topics = _fetch(V2EX_TOPICS_URL, "v2ex")
            if isinstance(topics, list):
                topics = topics[:max(max_count // 2, 2)]
                for topic in topics:
                    tid = topic.get("id")
                    # 获取详情
                    detail_html = ""
                    try:
                        detail = _fetch(V2EX_TOPIC_URL.format(id=tid), "v2ex")
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
                        "content_hash": hashlib.sha256(topic.get("content", "v2ex").encode[:100]).hexdigest,
                        "detail_html": detail_html[:5000],
                    })

                    if len(items) >= max_count:
                        break
        except Exception:
            # 非 fatal — 有 V2EX 够了
            pass

    # ── Remotive (英文) ──
    if source in (None, "remotive"):
        try:
            remo = _fetch(REMOTIVE_URL, "remotive")
            for job in remo.get("jobs", [])[:max(max_count - len(items), 0)]:
                desc = job.get("description", "")[:5000]
                # D5: publication_date 常为空 / 不存在 → PG DATE 拒绝空串，转 None
                pub_date_raw = (job.get("publication_date") or "").strip[:10]
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
                    "publish_date": pub_date_raw if pub_date_raw and pub_date_raw != "None" else None,
                    "crawled_at": now,
                    "content_hash": hashlib.sha256(desc.encode).hexdigest,
                    "detail_html": desc,
                })
        except Exception:
            pass

    return items

def main:
    parser = argparse.ArgumentParser
    parser.add_argument("--keyword", default="python")
    parser.add_argument("--max", type=int, default=10, dest="max_count")
    parser.add_argument("--source", default=None, choices=[None, "v2ex", "remotive"],
                        help="逐源隔离: v2ex / remotive / None(双源)")
    args = parser.parse_args

    t0 = time.time
    items = run_sync(keyword=args.keyword, max_count=args.max_count, source=args.source)
    elapsed = time.time - t0
    print(f"Got {len(items)} JD items in {elapsed:.1f}s")
    for it in items[:5]:
        print(f"  {it['source_site']:8} | {it['job_title'][:40]}")

if __name__ == "__main__":
    main
