"""Real-time data quality monitoring.

Provides:
- Anomaly detection on incoming data volumes / quality scores
- Per-source and global quality scoring
- Alert generation when thresholds are breached
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline_models import DataSourceRecord, PipelineRun


# ---------------------------------------------------------------------------
# Quality scoring
# ---------------------------------------------------------------------------

@dataclass
class QualityMetrics:
    """Aggregated quality metrics for the data pipeline."""

    overall_score: float = 0.0
    completeness: float = 0.0
    accuracy: float = 0.0
    freshness_hours: float = 0.0
    duplicate_rate: float = 0.0
    source_scores: dict[str, float] = field(default_factory=dict)
    total_records: int = 0
    valid_records: int = 0
    alert_count: int = 0


@dataclass
class QualityAlert:
    """A single quality alert."""

    level: str  # "info" | "warning" | "critical"
    dimension: str  # e.g. "freshness", "duplicate_rate", "volume_anomaly"
    message: str
    source: str | None = None
    value: float = 0.0
    threshold: float = 0.0
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()


# Default thresholds
DEFAULT_THRESHOLDS = {
    "min_quality_score": 0.6,
    "max_duplicate_rate": 0.30,
    "max_freshness_hours": 48,
    "min_completeness": 0.80,
    "volume_anomaly_z": 2.0,  # z-score for volume anomaly
}


async def compute_source_quality(
    session: AsyncSession,
) -> QualityMetrics:
    """Compute quality metrics from database state (data_sources table).

    Returns a QualityMetrics snapshot.
    """
    result = await session.execute(select(DataSourceRecord))
    sources = list(result.scalars().all())

    if not sources:
        return QualityMetrics()

    source_scores: dict[str, float] = {}
    total_records = 0
    valid_records = 0
    weighted_score_sum = 0.0
    total_weight = 0.0
    duplicate_rates: list[float] = []

    for src in sources:
        source_scores[src.name] = src.avg_quality_score
        total_records += src.total_records
        valid_records += src.valid_records
        duplicate_rates.append(src.duplicate_rate)
        w = src.authority_score
        weighted_score_sum += src.avg_quality_score * w
        total_weight += w

    overall = weighted_score_sum / total_weight if total_weight > 0 else 0.0
    completeness = valid_records / total_records if total_records > 0 else 0.0
    avg_dup_rate = statistics.mean(duplicate_rates) if duplicate_rates else 0.0

    # Freshness: hours since last crawl across all sources
    freshness_hours = 0.0
    now = datetime.now(UTC)
    latest_crawl = None
    for src in sources:
        if src.last_crawl_at is not None:
            if latest_crawl is None or src.last_crawl_at > latest_crawl:
                latest_crawl = src.last_crawl_at
    if latest_crawl is not None:
        delta = now - latest_crawl.replace(tzinfo=UTC) if latest_crawl.tzinfo is None else now - latest_crawl
        freshness_hours = delta.total_seconds() / 3600.0

    return QualityMetrics(
        overall_score=round(overall, 4),
        completeness=round(completeness, 4),
        accuracy=round(overall, 4),  # proxy: weighted quality ≈ accuracy
        freshness_hours=round(freshness_hours, 2),
        duplicate_rate=round(avg_dup_rate, 4),
        source_scores=source_scores,
        total_records=total_records,
        valid_records=valid_records,
    )


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

def detect_volume_anomaly(
    recent_counts: list[int],
    current_count: int,
    z_threshold: float = 2.0,
) -> QualityAlert | None:
    """Detect if *current_count* is anomalous relative to *recent_counts*.

    Uses simple z-score method. Returns an alert or None.
    """
    if len(recent_counts) < 3:
        return None
    mean = statistics.mean(recent_counts)
    stdev = statistics.stdev(recent_counts)
    if stdev == 0:
        return None
    z = (current_count - mean) / stdev
    if abs(z) >= z_threshold:
        level = "critical" if abs(z) >= z_threshold * 1.5 else "warning"
        direction = "spike" if z > 0 else "drop"
        return QualityAlert(
            level=level,
            dimension="volume_anomaly",
            message=f"Volume {direction}: current={current_count}, mean={mean:.0f}, z={z:.2f}",
            value=float(current_count),
            threshold=z_threshold,
        )
    return None


def detect_quality_drop(
    recent_scores: list[float],
    current_score: float,
    drop_threshold: float = 0.15,
) -> QualityAlert | None:
    """Detect if quality score has dropped significantly."""
    if not recent_scores:
        return None
    mean = statistics.mean(recent_scores)
    if mean == 0:
        return None
    drop = mean - current_score
    if drop >= drop_threshold:
        level = "critical" if drop >= drop_threshold * 2 else "warning"
        return QualityAlert(
            level=level,
            dimension="quality_drop",
            message=f"Quality dropped: current={current_score:.3f}, avg={mean:.3f}, drop={drop:.3f}",
            value=current_score,
            threshold=drop_threshold,
        )
    return None


# ---------------------------------------------------------------------------
# Alert generation
# ---------------------------------------------------------------------------

async def generate_alerts(
    session: AsyncSession,
    thresholds: dict[str, float] | None = None,
) -> list[QualityAlert]:
    """Scan current state and return any active quality alerts."""
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS

    alerts: list[QualityAlert] = []

    # 1. Check each data source
    result = await session.execute(select(DataSourceRecord))
    sources = list(result.scalars().all())

    for src in sources:
        # Low quality score
        if src.avg_quality_score < thresholds["min_quality_score"]:
            alerts.append(QualityAlert(
                level="warning",
                dimension="low_quality",
                message=(
                    f"Source '{src.name}' quality score {src.avg_quality_score:.3f} "
                    f"below threshold {thresholds['min_quality_score']}"
                ),
                source=src.name,
                value=src.avg_quality_score,
                threshold=thresholds["min_quality_score"],
            ))

        # High duplicate rate
        if src.duplicate_rate > thresholds["max_duplicate_rate"]:
            alerts.append(QualityAlert(
                level="warning",
                dimension="duplicate_rate",
                message=(
                    f"Source '{src.name}' duplicate rate {src.duplicate_rate:.1%} "
                    f"exceeds threshold {thresholds['max_duplicate_rate']:.1%}"
                ),
                source=src.name,
                value=src.duplicate_rate,
                threshold=thresholds["max_duplicate_rate"],
            ))

        # Source in error state
        if src.status == "error":
            alerts.append(QualityAlert(
                level="critical",
                dimension="source_error",
                message=f"Source '{src.name}' is in error state",
                source=src.name,
            ))

        # Stale data
        if src.last_crawl_at is not None:
            now = datetime.now(UTC)
            last = src.last_crawl_at.replace(tzinfo=UTC) if src.last_crawl_at.tzinfo is None else src.last_crawl_at
            hours_since = (now - last).total_seconds() / 3600.0
            if hours_since > thresholds["max_freshness_hours"]:
                alerts.append(QualityAlert(
                    level="warning",
                    dimension="freshness",
                    message=(
                        f"Source '{src.name}' last crawl {hours_since:.0f}h ago "
                        f"(threshold {thresholds['max_freshness_hours']}h)"
                    ),
                    source=src.name,
                    value=hours_since,
                    threshold=thresholds["max_freshness_hours"],
                ))

    # 2. Check for failed pipeline runs
    failed_result = await session.execute(
        select(func.count())
        .select_from(PipelineRun)
        .where(PipelineRun.status == "failed")
    )
    recent_failures = failed_result.scalar() or 0
    if recent_failures > 3:
        alerts.append(QualityAlert(
            level="critical",
            dimension="pipeline_failures",
            message=f"{recent_failures} failed pipeline runs detected",
            value=float(recent_failures),
            threshold=3.0,
        ))

    return alerts


async def get_quality_snapshot(
    session: AsyncSession,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Return a full quality snapshot for the API layer.

    Includes metrics, alerts, and per-source breakdown.
    """
    metrics = await compute_source_quality(session)
    alerts = await generate_alerts(session, thresholds)
    metrics.alert_count = len(alerts)

    return {
        "metrics": {
            "overall_score": metrics.overall_score,
            "completeness": metrics.completeness,
            "accuracy": metrics.accuracy,
            "freshness_hours": metrics.freshness_hours,
            "duplicate_rate": metrics.duplicate_rate,
            "total_records": metrics.total_records,
            "valid_records": metrics.valid_records,
        },
        "source_scores": metrics.source_scores,
        "alerts": [
            {
                "level": a.level,
                "dimension": a.dimension,
                "message": a.message,
                "source": a.source,
                "value": a.value,
                "threshold": a.threshold,
                "timestamp": a.timestamp,
            }
            for a in alerts
        ],
        "alert_count": len(alerts),
    }
