"""Scrapy Pipeline: 将 JdItem 入库 jd_raw。"""
from __future__ import annotations

import logging

from ..persistence import dao

log = logging.getLogger(__name__)


class JdStoragePipeline:
    """Scrapy Item Pipeline，把 JdItem 写入 PostgreSQL。"""

    def process_item(self, item, spider):
        rec = {
            "source_site": item.get("source_site"),
            "source_url": item.get("source_url"),
            "raw_html": item.get("raw_html"),
            "clean_text": item.get("clean_text"),
            "job_title": item.get("job_title"),
            "company": item.get("company"),
            "salary_min": item.get("salary_min"),
            "salary_max": item.get("salary_max"),
            "location": item.get("location"),
            "publish_date": item.get("publish_date"),
            "content_hash": item.get("content_hash"),
            "status": "raw",
        }
        result = dao.upsert_jd(rec)
        if result == "inserted":
            log.info("[storage] 入库 %s", item.get("source_url"))
        elif result == "duplicate":
            log.debug("[storage] 重复跳过 %s", item.get("source_url"))
        else:
            log.warning("[storage] 入库失败 %s", item.get("source_url"))
        return item
