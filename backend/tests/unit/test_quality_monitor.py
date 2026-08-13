"""Tests for pipeline quality monitor."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.core.pipeline.quality_monitor import (
    QualityAlert,
    QualityMetrics,
    compute_source_quality,
    detect_quality_drop,
    detect_volume_anomaly,
    generate_alerts,
    get_quality_snapshot,
)

# ---------------------------------------------------------------------------
# Fake session
# ---------------------------------------------------------------------------

class FakeScalarsResult:
    def __init__(self, items: list):
        self._items = items

    def all(self):
        return self._items


class FakeResult:
    def __init__(self, scalars_list=None, scalar_val=None):
        self._scalars = FakeScalarsResult(scalars_list) if scalars_list is not None else None
        self._scalar_val = scalar_val

    def scalars(self):
        return self._scalars

    def scalar(self):
        return self._scalar_val


class FakeAsyncSession:
    def __init__(self, results: list | None = None):
        self._results = results or []
        self._idx = 0

    async def execute(self, stmt):
        if self._idx < len(self._results):
            r = self._results[self._idx]
            self._idx += 1
            return r
        return FakeResult(scalar_val=0)


def _make_source(
    name: str = "TestSource",
    avg_quality_score: float = 0.8,
    authority_score: float = 0.5,
    total_records: int = 100,
    valid_records: int = 90,
    duplicate_rate: float = 0.1,
    last_crawl_at: datetime | None = None,
    status: str = "active",
) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        avg_quality_score=avg_quality_score,
        authority_score=authority_score,
        total_records=total_records,
        valid_records=valid_records,
        duplicate_rate=duplicate_rate,
        last_crawl_at=last_crawl_at,
        status=status,
    )


# ---------------------------------------------------------------------------
# compute_source_quality
# ---------------------------------------------------------------------------
class TestComputeSourceQuality:
    @pytest.mark.asyncio
    async def test_empty_sources(self):
        session = FakeAsyncSession([FakeResult(scalars_list=[])])
        result = await compute_source_quality(session)
        assert isinstance(result, QualityMetrics)
        assert result.overall_score == 0.0
        assert result.total_records == 0

    @pytest.mark.asyncio
    async def test_single_source(self):
        src = _make_source(avg_quality_score=0.9, authority_score=1.0, total_records=50, valid_records=45)
        session = FakeAsyncSession([FakeResult(scalars_list=[src])])
        result = await compute_source_quality(session)
        assert result.overall_score == 0.9
        assert result.completeness == round(45 / 50, 4)
        assert result.total_records == 50
        assert result.valid_records == 45

    @pytest.mark.asyncio
    async def test_multiple_sources_weighted(self):
        src1 = _make_source(name="A", avg_quality_score=0.8, authority_score=1.0)
        src2 = _make_source(name="B", avg_quality_score=0.6, authority_score=0.5)
        session = FakeAsyncSession([FakeResult(scalars_list=[src1, src2])])
        result = await compute_source_quality(session)
        # weighted: (0.8*1.0 + 0.6*0.5) / 1.5 = 1.1/1.5 ≈ 0.7333
        assert 0.73 < result.overall_score < 0.74

    @pytest.mark.asyncio
    async def test_zero_authority_weight(self):
        src = _make_source(authority_score=0.0)
        session = FakeAsyncSession([FakeResult(scalars_list=[src])])
        result = await compute_source_quality(session)
        assert result.overall_score == 0.0

    @pytest.mark.asyncio
    async def test_freshness_with_recent_crawl(self):
        recent = datetime.now(UTC) - timedelta(hours=2)
        src = _make_source(last_crawl_at=recent)
        session = FakeAsyncSession([FakeResult(scalars_list=[src])])
        result = await compute_source_quality(session)
        assert 1.5 < result.freshness_hours < 3.0

    @pytest.mark.asyncio
    async def test_freshness_naive_datetime(self):
        """last_crawl_at without tzinfo gets UTC assigned."""
        recent_naive = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=5)
        src = _make_source(last_crawl_at=recent_naive)
        session = FakeAsyncSession([FakeResult(scalars_list=[src])])
        result = await compute_source_quality(session)
        assert 4.5 < result.freshness_hours < 6.0

    @pytest.mark.asyncio
    async def test_freshness_none_crawl(self):
        src = _make_source(last_crawl_at=None)
        session = FakeAsyncSession([FakeResult(scalars_list=[src])])
        result = await compute_source_quality(session)
        assert result.freshness_hours == 0.0

    @pytest.mark.asyncio
    async def test_duplicate_rate_averaged(self):
        src1 = _make_source(name="A", duplicate_rate=0.2)
        src2 = _make_source(name="B", duplicate_rate=0.4)
        session = FakeAsyncSession([FakeResult(scalars_list=[src1, src2])])
        result = await compute_source_quality(session)
        assert result.duplicate_rate == 0.3

    @pytest.mark.asyncio
    async def test_zero_total_records_completeness(self):
        src = _make_source(total_records=0, valid_records=0)
        session = FakeAsyncSession([FakeResult(scalars_list=[src])])
        result = await compute_source_quality(session)
        assert result.completeness == 0.0


# ---------------------------------------------------------------------------
# detect_volume_anomaly
# ---------------------------------------------------------------------------
class TestDetectVolumeAnomaly:
    def test_no_anomaly(self):
        result = detect_volume_anomaly([100, 105, 95, 110, 100], 102)
        assert result is None

    def test_spike_warning(self):
        result = detect_volume_anomaly([100, 105, 95, 110, 100], 200)
        assert result is not None
        assert result.level == "warning" or result.level == "critical"
        assert result.dimension == "volume_anomaly"

    def test_spike_critical(self):
        result = detect_volume_anomaly([100, 110, 90, 105, 95], 500)
        assert result is not None
        assert result.level == "critical"

    def test_drop_warning(self):
        result = detect_volume_anomaly([100, 110, 90, 105, 95], 10)
        assert result is not None
        assert "drop" in result.message

    def test_insufficient_data(self):
        result = detect_volume_anomaly([100], 200)
        assert result is None

    def test_zero_stdev(self):
        result = detect_volume_anomaly([100, 100, 100], 100)
        assert result is None

    def test_custom_threshold(self):
        result = detect_volume_anomaly([100, 105, 95], 120, z_threshold=1.0)
        assert result is not None

    def test_alert_has_timestamp(self):
        result = detect_volume_anomaly([100, 110, 90, 105, 95], 500)
        assert result is not None
        assert result.timestamp != ""


# ---------------------------------------------------------------------------
# detect_quality_drop
# ---------------------------------------------------------------------------
class TestDetectQualityDrop:
    def test_no_drop(self):
        result = detect_quality_drop([0.8, 0.85, 0.82], 0.80)
        assert result is None

    def test_warning_drop(self):
        result = detect_quality_drop([0.8, 0.85, 0.82], 0.6)
        assert result is not None
        assert result.level == "warning"
        assert result.dimension == "quality_drop"

    def test_critical_drop(self):
        result = detect_quality_drop([0.8, 0.85, 0.82], 0.4)
        assert result is not None
        assert result.level == "critical"

    def test_empty_scores(self):
        result = detect_quality_drop([], 0.5)
        assert result is None

    def test_zero_mean(self):
        result = detect_quality_drop([0.0, 0.0], 0.5)
        assert result is None

    def test_custom_threshold(self):
        result = detect_quality_drop([0.8], 0.7, drop_threshold=0.05)
        assert result is not None


# ---------------------------------------------------------------------------
# QualityAlert
# ---------------------------------------------------------------------------
class TestQualityAlert:
    def test_auto_timestamp(self):
        alert = QualityAlert(level="info", dimension="test", message="ok")
        assert alert.timestamp != ""

    def test_explicit_timestamp(self):
        alert = QualityAlert(level="info", dimension="test", message="ok", timestamp="2025-01-01")
        assert alert.timestamp == "2025-01-01"


# ---------------------------------------------------------------------------
# generate_alerts
# ---------------------------------------------------------------------------
class TestGenerateAlerts:
    @pytest.mark.asyncio
    async def test_no_alerts(self):
        src = _make_source(avg_quality_score=0.9, duplicate_rate=0.05, status="active")
        session = FakeAsyncSession([
            FakeResult(scalars_list=[src]),
            FakeResult(scalar_val=0),  # failed pipeline runs
        ])
        alerts = await generate_alerts(session)
        assert alerts == []

    @pytest.mark.asyncio
    async def test_low_quality_alert(self):
        src = _make_source(avg_quality_score=0.4, duplicate_rate=0.05, status="active")
        session = FakeAsyncSession([
            FakeResult(scalars_list=[src]),
            FakeResult(scalar_val=0),
        ])
        alerts = await generate_alerts(session)
        assert any(a.dimension == "low_quality" for a in alerts)

    @pytest.mark.asyncio
    async def test_high_duplicate_rate_alert(self):
        src = _make_source(avg_quality_score=0.9, duplicate_rate=0.5, status="active")
        session = FakeAsyncSession([
            FakeResult(scalars_list=[src]),
            FakeResult(scalar_val=0),
        ])
        alerts = await generate_alerts(session)
        assert any(a.dimension == "duplicate_rate" for a in alerts)

    @pytest.mark.asyncio
    async def test_error_state_alert(self):
        src = _make_source(status="error")
        session = FakeAsyncSession([
            FakeResult(scalars_list=[src]),
            FakeResult(scalar_val=0),
        ])
        alerts = await generate_alerts(session)
        assert any(a.dimension == "source_error" and a.level == "critical" for a in alerts)

    @pytest.mark.asyncio
    async def test_stale_data_alert(self):
        old_crawl = datetime.now(UTC) - timedelta(hours=72)
        src = _make_source(last_crawl_at=old_crawl)
        session = FakeAsyncSession([
            FakeResult(scalars_list=[src]),
            FakeResult(scalar_val=0),
        ])
        alerts = await generate_alerts(session)
        assert any(a.dimension == "freshness" for a in alerts)

    @pytest.mark.asyncio
    async def test_stale_data_naive_datetime(self):
        old_crawl = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=72)
        src = _make_source(last_crawl_at=old_crawl)
        session = FakeAsyncSession([
            FakeResult(scalars_list=[src]),
            FakeResult(scalar_val=0),
        ])
        alerts = await generate_alerts(session)
        assert any(a.dimension == "freshness" for a in alerts)

    @pytest.mark.asyncio
    async def test_pipeline_failures_alert(self):
        src = _make_source()
        session = FakeAsyncSession([
            FakeResult(scalars_list=[src]),
            FakeResult(scalar_val=5),  # > 3 failures
        ])
        alerts = await generate_alerts(session)
        assert any(a.dimension == "pipeline_failures" and a.level == "critical" for a in alerts)

    @pytest.mark.asyncio
    async def test_scalar_none_for_pipeline_failures(self):
        src = _make_source()
        session = FakeAsyncSession([
            FakeResult(scalars_list=[src]),
            FakeResult(scalar_val=None),
        ])
        alerts = await generate_alerts(session)
        assert not any(a.dimension == "pipeline_failures" for a in alerts)

    # ── 全盘友好性: message 中文化（2026-08-13）──
    @pytest.mark.asyncio
    async def test_low_quality_alert_message_chinese(self):
        src = _make_source(name="v2ex", avg_quality_score=0.4, duplicate_rate=0.05, status="active")
        session = FakeAsyncSession([
            FakeResult(scalars_list=[src]),
            FakeResult(scalar_val=0),
        ])
        alerts = await generate_alerts(session)
        low = next(a for a in alerts if a.dimension == "low_quality")
        assert "V2EX" in low.message  # 站点中文名映射
        assert "低于阈值" in low.message  # 中文 message（不再直出英文 below threshold）

    @pytest.mark.asyncio
    async def test_pipeline_failures_message_chinese(self):
        src = _make_source()
        session = FakeAsyncSession([
            FakeResult(scalars_list=[src]),
            FakeResult(scalar_val=5),
        ])
        alerts = await generate_alerts(session)
        fail = next(a for a in alerts if a.dimension == "pipeline_failures")
        assert "失败运行" in fail.message

    @pytest.mark.asyncio
    async def test_custom_thresholds(self):
        src = _make_source(avg_quality_score=0.7, duplicate_rate=0.2, status="active")
        session = FakeAsyncSession([
            FakeResult(scalars_list=[src]),
            FakeResult(scalar_val=0),
        ])
        # Lower the thresholds so 0.7 quality and 0.2 duplicate trigger alerts
        thresholds = {"min_quality_score": 0.8, "max_duplicate_rate": 0.1, "max_freshness_hours": 48}
        alerts = await generate_alerts(session, thresholds=thresholds)
        assert any(a.dimension == "low_quality" for a in alerts)
        assert any(a.dimension == "duplicate_rate" for a in alerts)

    @pytest.mark.asyncio
    async def test_no_last_crawl_no_freshness_alert(self):
        src = _make_source(last_crawl_at=None)
        session = FakeAsyncSession([
            FakeResult(scalars_list=[src]),
            FakeResult(scalar_val=0),
        ])
        alerts = await generate_alerts(session)
        assert not any(a.dimension == "freshness" for a in alerts)


# ---------------------------------------------------------------------------
# get_quality_snapshot
# ---------------------------------------------------------------------------
class TestGetQualitySnapshot:
    @pytest.mark.asyncio
    async def test_full_snapshot(self):
        src = _make_source(avg_quality_score=0.8, duplicate_rate=0.05, status="active")
        session = FakeAsyncSession([
            FakeResult(scalars_list=[src]),  # compute_source_quality
            FakeResult(scalars_list=[src]),  # generate_alerts (source query)
            FakeResult(scalar_val=0),        # generate_alerts (pipeline failures)
        ])
        snapshot = await get_quality_snapshot(session)
        assert "metrics" in snapshot
        assert "source_scores" in snapshot
        assert "alerts" in snapshot
        assert "alert_count" in snapshot
        assert snapshot["metrics"]["overall_score"] > 0
        assert snapshot["alert_count"] == len(snapshot["alerts"])
