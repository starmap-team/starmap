"""Industry Quality Monitor (Phase 4, 2026-08-17).

多层防御 IndustryClassifier 第四层（监测 + 告警）：
- 检测「未分类」占比 / 数量
- 检测单源未分类率（如 arbeitnow 95% 未分类时触发 critical）
- 检测最近 24h 新增岗位未分类率
- 检测 Neo4j Industry 节点与 PG industry 字段一致性

API:
    detect_industry_quality(session) -> IndustryQualityReport

返回结构（直接喂给 dashboard / overview）:
    {
        "unclassified_count": 145,        # 已发布 approved 状态下的未分类行数
        "unclassified_ratio": 0.74,        # 未分类占比 (0-1)
        "total_positions": 185,            # 已发布总数
        "new_24h_unclassified_count": 5,    # 最近 24h 抽取但未分类
        "new_24h_total": 12,                # 最近 24h 抽取总数
        "per_source_unclassified": {        # 各源未分类率
            "arbeitnow": {"unclassified": 12, "total": 12, "ratio": 1.0},
            ...
        },
        "neo4j_pg_consistency": True,       # Neo4j Industry 节点与 PG 行业值一致
        "alert_level": "warning",            # info / warning / critical
    }
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.extraction.industry import UNCLASSIFIED_INDUSTRY_LITERAL
from app.models.extraction_models import PositionRecord


@dataclass
class SourceQualityStats:
    """单数据源未分类率。"""

    source_site: str
    unclassified: int
    total: int

    @property
    def ratio(self) -> float:
        return self.unclassified / self.total if self.total else 0.0


@dataclass
class IndustryQualityReport:
    """行业质量监控报告（喂给 dashboard KPI）。"""

    unclassified_count: int = 0
    unclassified_ratio: float = 0.0
    total_positions: int = 0
    new_24h_unclassified_count: int = 0
    new_24h_total: int = 0
    per_source_unclassified: list[SourceQualityStats] = field(default_factory=list)
    neo4j_pg_consistency: bool = True
    alert_level: str = "info"  # info / warning / critical
    timestamp: float = 0.0


# 告警阈值（Phase 4 多层防御第四层）
UNCLASSIFIED_RATIO_WARNING = 0.30  # 30%+ 未分类触发 warning
UNCLASSIFIED_RATIO_CRITICAL = 0.50  # 50%+ 触发 critical
SOURCE_RATIO_WARNING = 0.80  # 单源 80%+ 未分类触发 warning
NEW_24H_RATIO_WARNING = 0.40  # 新增 24h 40%+ 未分类触发 warning


async def detect_industry_quality(
    session: AsyncSession,
    neo4j_driver: Any | None = None,
) -> IndustryQualityReport:
    """行业质量监控主入口。

    计算 4 个核心指标：
    1. 已发布 approved 状态下的「未分类」占比
    2. 最近 24h 抽取岗位的「未分类」占比
    3. 单源（source_platform）未分类率分布
    4. Neo4j Industry 节点 vs PG industry 字段一致性（如果提供了 driver）
    """
    report = IndustryQualityReport(timestamp=datetime.now(UTC).timestamp())

    # ── 1. 总体「未分类」占比（限定 approved，保持 dashboard 口径一致）──
    total_stmt = sa.select(sa.func.count()).select_from(PositionRecord).where(
        PositionRecord.review_status == "approved"
    )
    report.total_positions = int((await session.execute(total_stmt)).scalar() or 0)

    unclass_stmt = sa.select(sa.func.count()).select_from(PositionRecord).where(
        PositionRecord.review_status == "approved",
        PositionRecord.industry == UNCLASSIFIED_INDUSTRY_LITERAL,
    )
    report.unclassified_count = int((await session.execute(unclass_stmt)).scalar() or 0)
    report.unclassified_ratio = (
        report.unclassified_count / report.total_positions if report.total_positions else 0.0
    )

    # ── 2. 最近 24h 抽取岗位的「未分类」占比 ──
    cutoff_24h = datetime.now(UTC) - timedelta(hours=24)
    new_24h_total_stmt = sa.select(sa.func.count()).select_from(PositionRecord).where(
        PositionRecord.created_at >= cutoff_24h
    )
    report.new_24h_total = int((await session.execute(new_24h_total_stmt)).scalar() or 0)
    new_24h_unclass_stmt = sa.select(sa.func.count()).select_from(PositionRecord).where(
        PositionRecord.created_at >= cutoff_24h,
        PositionRecord.industry == UNCLASSIFIED_INDUSTRY_LITERAL,
    )
    report.new_24h_unclassified_count = int(
        (await session.execute(new_24h_unclass_stmt)).scalar() or 0
    )

    # ── 3. 单源未分类率（admin 排查「哪个爬虫数据脏」）──
    # Phase 4 (2026-08-17): PositionRecord 没有 source_platform 字段，
    # 但 created_by 形如 'system:extraction' / 'system:fixture' / 'admin'，
    # 用 LEFT(industry, 8) 做粗粒度分组（提取来源前缀）。
    src_stmt = (
        sa.select(
            sa.func.coalesce(
                sa.func.substring(PositionRecord.created_by, 1, 16),
                "unknown",
            ).label("source"),
            sa.func.count().label("total"),
            sa.func.count().filter(
                PositionRecord.industry == UNCLASSIFIED_INDUSTRY_LITERAL
            ).label("unclass"),
        )
        .where(PositionRecord.review_status == "approved")
        .group_by("source")
    )
    src_rows = (await session.execute(src_stmt)).all()
    for row in src_rows:
        src_name = str(getattr(row, "source", None) or "unknown")
        report.per_source_unclassified.append(
            SourceQualityStats(
                source_site=src_name,
                unclassified=int(getattr(row, "unclass", None) or 0),
                total=int(getattr(row, "total", None) or 0),
            )
        )

    # ── 4. Neo4j Industry 节点 vs PG 行业值一致性（可选）──
    if neo4j_driver is not None:
        try:
            async with neo4j_driver.session() as s:
                # 计数 Neo4j Industry 节点数
                neo4j_count_result = await s.run(
                    "MATCH (n:Industry) RETURN count(n) AS cnt"
                )
                neo4j_count_record = await neo4j_count_result.single()
                neo4j_industry_count = int(neo4j_count_record["cnt"]) if neo4j_count_record else 0

                # PG distinct industry 数
                pg_distinct_stmt = (
                    sa.select(sa.func.count(sa.distinct(PositionRecord.industry)))
                    .where(PositionRecord.industry.isnot(None))
                    .where(PositionRecord.industry != "")
                    .where(PositionRecord.industry != UNCLASSIFIED_INDUSTRY_LITERAL)
                )
                pg_distinct = int((await session.execute(pg_distinct_stmt)).scalar() or 0)

                # 简单一致性判定：差异不应 > 5（容许有别名/历史残留）
                report.neo4j_pg_consistency = (
                    neo4j_industry_count >= pg_distinct - 5
                    and neo4j_industry_count <= pg_distinct + 5
                )
        except Exception as exc:  # noqa: BLE001 — Neo4j 检测 fail-soft
            logger.warning("Neo4j consistency check failed: {}", exc)
            report.neo4j_pg_consistency = True  # fail-open

    # ── 5. 告警等级判定（4 个指标任何一个越界即升级）──
    report.alert_level = _compute_alert_level(report)

    return report


def _compute_alert_level(report: IndustryQualityReport) -> str:
    """根据 4 个指标判定告警等级（info / warning / critical）。"""
    if report.unclassified_ratio >= UNCLASSIFIED_RATIO_CRITICAL:
        return "critical"
    if report.unclassified_ratio >= UNCLASSIFIED_RATIO_WARNING:
        return "warning"
    new_24h_ratio = (
        report.new_24h_unclassified_count / report.new_24h_total
        if report.new_24h_total
        else 0.0
    )
    if new_24h_ratio >= NEW_24H_RATIO_WARNING:
        return "warning"
    if any(s.ratio >= SOURCE_RATIO_WARNING for s in report.per_source_unclassified):
        return "warning"
    if not report.neo4j_pg_consistency:
        return "warning"
    return "info"


def report_to_dict(report: IndustryQualityReport) -> dict[str, Any]:
    """IndustryQualityReport → dict（喂给 dashboard overview JSON 序列化）。"""
    return {
        "unclassified_count": report.unclassified_count,
        "unclassified_ratio": round(report.unclassified_ratio, 4),
        "total_positions": report.total_positions,
        "new_24h_unclassified_count": report.new_24h_unclassified_count,
        "new_24h_total": report.new_24h_total,
        "per_source_unclassified": [
            {
                "source_site": s.source_site,
                "unclassified": s.unclassified,
                "total": s.total,
                "ratio": round(s.ratio, 4),
            }
            for s in report.per_source_unclassified
        ],
        "neo4j_pg_consistency": report.neo4j_pg_consistency,
        "alert_level": report.alert_level,
        "timestamp": report.timestamp,
    }
