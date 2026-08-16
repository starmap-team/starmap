"""D3 (2026-08-07): 数据源质量统计聚合回写 — 质量评估的真实来源。

背景: data_sources 的 avg_quality_score/valid_records/duplicate_rate 无任何
写入方 → 数据质量监控恒 0 且无过程。本模块从真实表聚合回写:
- jd_raw (真实采集数据, 按 source_site)
- data_source_metrics (每次爬取指标)

聚合口径 (诚实, 可解释):
- total_records   = jd_raw 按 source_site 计数
- valid_records   = jd_raw status='extracted' 计数 (已抽取 = 有效)
- avg_quality_score = extracted / (extracted + duplicate) (真实质量代理)
- duplicate_rate  = duplicate / (extracted + duplicate)
- last_crawl_at   = data_source_metrics 最新 started_at
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline_models import DataSourceRecord

# jd_raw.source_site → data_sources.name 映射 (缺失映射的源跳过)
_SITE_TO_SOURCE: dict[str, str] = {
    "arbeitnow": "Arbeitnow (远程)",
    "jobicy": "Jobicy (远程)",
    "remotive": "Remotive (远程)",
    "v2ex": "V2EX 酷工作",        # D6: 迁移 034 名称对齐 (原 "V2EX (远程)" 无匹配)
    "weworkremotely": "WeWorkRemotely (远程)",
    "juejin": "掘金技术社区",     # D6: 迁移 034 名称对齐 (原 "掘金" 无匹配)
    "remoteok": "RemoteOK",       # D6: 迁移 034 名称对齐 (原 "RemoteOK (远程)" 无匹配)
    "manual": "手动导入",
    "boss": "Boss Zhipin",
}


async def sync_source_quality(session: AsyncSession) -> dict[str, Any]:
    """从 jd_raw + data_source_metrics 聚合, 回写 data_sources 统计字段。

    Returns: {source_name: {"total_records": n, "valid_records": n, ...}}
    """
    # 1. jd_raw 按 source_site × status 计数
    raw_rows = (await session.execute(
        sa.text("SELECT source_site, status, COUNT(*) FROM jd_raw GROUP BY source_site, status")
    )).all()
    site_stats: dict[str, dict[str, int]] = {}
    for site, status, cnt in raw_rows:
        site_stats.setdefault(site, {"extracted": 0, "duplicate": 0, "raw": 0})
        status_str = str(status)
        if status_str in site_stats[site]:
            site_stats[site][status_str] += cnt
        else:
            site_stats[site][status_str] = cnt

    # 2a. jd_raw 每个 source_site 最新 crawled_at —— 真实采集时间（主来源）
    raw_last = (await session.execute(
        sa.text("SELECT source_site, MAX(crawled_at) FROM jd_raw GROUP BY source_site")
    )).all()
    last_crawl_by_site: dict[str, datetime] = {str(site): at for site, at in raw_last}

    # 2b. data_source_metrics 最新 started_at per source（补充来源）
    metric_rows = (await session.execute(
        sa.text("""
            SELECT m.source_id, MAX(m.started_at) AS last_at
            FROM data_source_metrics m GROUP BY m.source_id
        """)
    )).all()
    last_crawl_by_source: dict[str, datetime] = {str(sid): at for sid, at in metric_rows}

    # 3. 回写 data_sources
    updated: dict[str, Any] = {}
    for site, stats in site_stats.items():
        source_name = _SITE_TO_SOURCE.get(site)
        if not source_name:
            continue
        ds = (await session.execute(
            sa.select(DataSourceRecord).where(DataSourceRecord.name == source_name)
        )).scalar_one_or_none()
        if ds is None:
            continue
        extracted = stats.get("extracted", 0)
        duplicate = stats.get("duplicate", 0)
        total = extracted + duplicate + stats.get("raw", 0)
        quality = extracted / (extracted + duplicate) if (extracted + duplicate) > 0 else 0.0
        dup_rate = duplicate / (extracted + duplicate) if (extracted + duplicate) > 0 else 0.0
        ds.total_records = total
        ds.valid_records = extracted
        ds.avg_quality_score = round(quality, 4)
        ds.duplicate_rate = round(dup_rate, 4)
        # last_crawl_at = 「上次爬取尝试时间」语义：优先 data_source_metrics
        # （/crawl-source 与 sync 端点每次爬取都写一条，started_at=爬取时刻）——
        # 这样即使本次全部是 duplicate（平台暂无新职位）卡片也能反映"刚刚爬过"。
        # jd_raw.MAX(crawled_at) 是「数据新鲜度」（最后一条新数据），不是爬取时刻，
        # 仅在无 metrics（历史源）时兜底。
        metric_last = last_crawl_by_source.get(str(ds.id))
        if metric_last:
            ds.last_crawl_at = metric_last
        else:
            site_last = last_crawl_by_site.get(site)
            if site_last:
                ds.last_crawl_at = site_last
        updated[source_name] = {
            "total_records": total, "valid_records": extracted,
            "avg_quality_score": round(quality, 4), "duplicate_rate": round(dup_rate, 4),
        }
    # P0-2 (2026-08-15): 对 jd_raw 无行的 crawler/api/rss 活动源归零记录数。
    # 这些源的 total/valid 可能是 seed 合成值（seed_pipeline_data: 50+hash%200），
    # 不反映真实采集；sync 是唯一回写方，此前因 _SITE_TO_SOURCE 无映射而永不清零。
    # avg_quality_score 保留（属配置权威度，非测量值）。
    active_crawlers = (await session.execute(
        sa.select(DataSourceRecord).where(
            DataSourceRecord.status == "active",
            DataSourceRecord.source_type.in_(["crawler", "api", "rss"]),
        )
    )).scalars().all()
    for ds in active_crawlers:
        platform = (ds.config or {}).get("platform") or (ds.config or {}).get("source_site")
        has_real_rows = bool(platform) and platform in site_stats
        if has_real_rows or (ds.total_records == 0 and ds.valid_records == 0):
            continue
        ds.total_records = 0
        ds.valid_records = 0
        updated[ds.name] = {
            "total_records": 0, "valid_records": 0,
            "avg_quality_score": ds.avg_quality_score,
            "duplicate_rate": ds.duplicate_rate,
            "zeroed": True,
        }
    await session.commit()
    return updated
