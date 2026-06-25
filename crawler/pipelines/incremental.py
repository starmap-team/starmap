"""增量更新管道：差分检测 + URL 去重 + SimHash 近似去重。

Issue #36 — 阶段3 数据增量更新管道。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable

from sqlalchemy import select

from crawler.dedup import hex64, is_near_duplicate, simhash
from crawler.persistence.database import get_jd_raw_session
from crawler.persistence.models import JdRaw

log = logging.getLogger(__name__)


@dataclass
class IncrementalResult:
    """单次增量批次的统计结果。"""

    total: int = 0
    inserted: int = 0
    url_duplicate: int = 0
    content_near_duplicate: int = 0
    failed: int = 0
    skipped_urls: list[str] = field(default_factory=list)
    inserted_urls: list[str] = field(default_factory=list)


def get_existing_urls(source_site: str | None = None) -> set[str]:
    """查询已入库的 URL 集合，用于增量跳过。"""
    with get_jd_raw_session() as s:
        if source_site:
            rows = s.execute(
                select(JdRaw.source_url).where(JdRaw.source_site == source_site)
            ).all()
        else:
            rows = s.execute(select(JdRaw.source_url)).all()
    return {r[0] for r in rows}


def get_existing_hashes(source_site: str | None = None) -> dict[str, int]:
    """查询已入库的 content_hash → SimHash 映射，用于近似去重。

    返回 {content_hash_hex: simhash_int}。
    """
    with get_jd_raw_session() as s:
        if source_site:
            rows = s.execute(
                select(JdRaw.content_hash).where(JdRaw.source_site == source_site)
            ).all()
        else:
            rows = s.execute(select(JdRaw.content_hash)).all()
    result: dict[str, int] = {}
    for (h,) in rows:
        if h and len(h) >= 16:
            try:
                result[h] = int(h[:16], 16)
            except ValueError:
                continue
    return result


def check_incremental(
    records: Iterable[dict],
    *,
    source_site: str | None = None,
    skip_existing_urls: bool = True,
    simhash_threshold: int = 3,
) -> tuple[list[dict], IncrementalResult]:
    """对一批待入库记录做增量过滤。

    返回 (filtered_records, stats)。
    filtered_records 只包含通过 URL 去重 + SimHash 近似去重的记录。
    """
    stats = IncrementalResult()
    existing_urls: set[str] = set()
    existing_hashes: dict[str, int] = {}

    if skip_existing_urls:
        existing_urls = get_existing_urls(source_site)
        existing_hashes = get_existing_hashes(source_site)

    filtered: list[dict] = []
    batch_hashes: list[int] = []

    for rec in records:
        stats.total += 1
        url = rec.get("source_url", "")

        # URL 精确去重
        if url in existing_urls:
            stats.url_duplicate += 1
            stats.skipped_urls.append(url)
            continue

        # SimHash 近似去重
        text = rec.get("clean_text", "")
        if text:
            new_hash = simhash(text)
            # 对比已入库
            is_dup = False
            for old_hash in existing_hashes.values():
                if is_near_duplicate(new_hash, old_hash, threshold=simhash_threshold):
                    stats.content_near_duplicate += 1
                    stats.skipped_urls.append(url)
                    is_dup = True
                    break
            if is_dup:
                continue
            # 对比本批次内
            for bh in batch_hashes:
                if is_near_duplicate(new_hash, bh, threshold=simhash_threshold):
                    stats.content_near_duplicate += 1
                    stats.skipped_urls.append(url)
                    is_dup = True
                    break
            if is_dup:
                continue
            batch_hashes.append(new_hash)
            # 更新 content_hash
            rec["content_hash"] = hex64(new_hash)

        filtered.append(rec)
        stats.inserted += 1
        stats.inserted_urls.append(url)

    log.info(
        "[incremental] total=%d inserted=%d url_dup=%d content_dup=%d",
        stats.total,
        stats.inserted,
        stats.url_duplicate,
        stats.content_near_duplicate,
    )
    return filtered, stats


__all__ = [
    "IncrementalResult",
    "check_incremental",
    "get_existing_urls",
    "get_existing_hashes",
]
