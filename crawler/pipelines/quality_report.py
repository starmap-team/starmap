"""数据质量报告：去重率、来源分布、时间分布统计。

Issue #36 — 阶段3 数据增量更新管道。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from sqlalchemy import func, select

from crawler.persistence.database import get_jd_raw_session
from crawler.persistence.models import JdRaw

log = logging.getLogger(__name__)


@dataclass
class QualityReport:
    """数据质量报告。"""

    total: int = 0
    by_source: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)
    by_date: dict[str, int] = field(default_factory=dict)
    dedup_rate: float = 0.0
    unique_urls: int = 0
    unique_hashes: int = 0


def generate_quality_report(source_site: str | None = None) -> QualityReport:
    """生成数据质量报告。"""
    report = QualityReport()

    with get_jd_raw_session() as s:
        # 构建基础过滤条件
        base_filter = []
        if source_site:
            base_filter.append(JdRaw.source_site == source_site)

        # 总量
        total_q = select(func.count(JdRaw.id))
        if base_filter:
            total_q = total_q.where(*base_filter)
        report.total = s.scalar(total_q) or 0

        # 来源分布
        src_q = select(JdRaw.source_site, func.count(JdRaw.id)).group_by(JdRaw.source_site)
        if base_filter:
            src_q = src_q.where(*base_filter)
        for site, cnt in s.execute(src_q).all():
            report.by_source[site] = cnt

        # 状态分布
        stat_q = select(JdRaw.status, func.count(JdRaw.id)).group_by(JdRaw.status)
        if base_filter:
            stat_q = stat_q.where(*base_filter)
        for status, cnt in s.execute(stat_q).all():
            report.by_status[str(status)] = cnt

        # 时间分布（按日期）
        date_col = func.date(JdRaw.crawled_at)
        date_q = select(date_col, func.count(JdRaw.id)).group_by(date_col).order_by(date_col)
        if base_filter:
            date_q = date_q.where(*base_filter)
        for d, cnt in s.execute(date_q).all():
            key = str(d) if d else "unknown"
            report.by_date[key] = cnt

        # URL 去重率
        url_q = select(func.count(func.distinct(JdRaw.source_url)))
        if base_filter:
            url_q = url_q.where(*base_filter)
        report.unique_urls = s.scalar(url_q) or 0

        # Hash 去重率
        hash_q = select(func.count(func.distinct(JdRaw.content_hash)))
        if base_filter:
            hash_q = hash_q.where(*base_filter)
        report.unique_hashes = s.scalar(hash_q) or 0

    if report.total > 0:
        report.dedup_rate = round(1.0 - report.unique_hashes / report.total, 4)

    log.info(
        "[quality] total=%d unique_urls=%d unique_hashes=%d dedup_rate=%.2f%%",
        report.total,
        report.unique_urls,
        report.unique_hashes,
        report.dedup_rate * 100,
    )
    return report


def format_report_text(report: QualityReport) -> str:
    """格式化报告为可读文本。"""
    lines = [
        "=" * 50,
        "StarMap 数据质量报告",
        "=" * 50,
        f"总量: {report.total} 条",
        f"唯一 URL: {report.unique_urls}",
        f"唯一 Hash: {report.unique_hashes}",
        f"近似重复率: {report.dedup_rate * 100:.1f}%",
        "",
        "--- 来源分布 ---",
    ]
    for site, cnt in sorted(report.by_source.items()):
        pct = cnt / report.total * 100 if report.total else 0
        lines.append(f"  {site:20s} {cnt:5d} ({pct:.1f}%)")

    lines.append("")
    lines.append("--- 状态分布 ---")
    for status, cnt in sorted(report.by_status.items()):
        lines.append(f"  {status:20s} {cnt:5d}")

    lines.append("")
    lines.append("--- 时间分布 ---")
    for d, cnt in sorted(report.by_date.items()):
        lines.append(f"  {d:20s} {cnt:5d}")

    lines.append("=" * 50)
    return "\n".join(lines)


__all__ = ["QualityReport", "generate_quality_report", "format_report_text"]
