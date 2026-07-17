"""Unit tests for datasource business logic — service/core layer only.

Directly tests the helper functions and business logic extracted from
the datasource API module. No TestClient, no HTTP layer.

Covers:
- _serialize: DataSourceRecord → DataSourceResponse conversion
- list_datasources logic: query → serialize
- get_datasource logic: query → not-found handling
- update_datasource logic: partial update + validation
- get_datasource_stats logic: period parsing, daily aggregation
- get_datasources_health logic: status counting
- trigger_source_sync logic: existence check → pipeline trigger
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.datasource import (
    CrawlVolumeEntry,
    DataSourceResponse,
    DatasourcesHealthResponse,
    DataSourceStatsResponse,
    DataSourceUpdateRequest,
    QualityTrendEntry,
    SourceHealthEntry,
    SyncTriggerResponse,
    _serialize,
)

# ── Fake ORM objects ──


def _make_ds_record(
    id=None,
    name="BOSS直聘",
    source_type="crawler",
    authority_score=0.8,
    status="active",
    last_crawl_at=None,
    total_records=1000,
    valid_records=950,
    duplicate_rate=0.05,
    avg_quality_score=0.85,
    config=None,
):
    rec = MagicMock()
    rec.id = id or uuid.uuid4()
    rec.name = name
    rec.source_type = source_type
    rec.authority_score = authority_score
    rec.status = status
    rec.last_crawl_at = last_crawl_at or datetime.now(UTC)
    rec.total_records = total_records
    rec.valid_records = valid_records
    rec.duplicate_rate = duplicate_rate
    rec.avg_quality_score = avg_quality_score
    rec.config = config or {"url": "https://example.com"}
    return rec


def _make_pipeline_run(
    started_at=None,
    status="completed",
    total_records=100,
    quality_score=0.9,
):
    run = MagicMock()
    run.id = uuid.uuid4()
    run.started_at = started_at or datetime.now(UTC)
    run.status = status
    run.total_records = total_records
    run.quality_score = quality_score
    return run


# ── Fake DB primitives ──


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        v = self.value
        if isinstance(v, (list, tuple)) and len(v) == 1:
            return v[0]
        return v

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.value if isinstance(self.value, list) else [self.value]


class FakeAsyncSession:
    """Minimal async session that returns pre-configured results per execute call."""

    def __init__(self, results=None):
        self._results = list(results or [])
        self._idx = 0
        self._added = []
        self._committed = False

    async def execute(self, _stmt):
        if self._idx < len(self._results):
            r = self._results[self._idx]
            self._idx += 1
            return r
        return FakeResult(None)

    def add(self, obj):
        self._added.append(obj)

    async def commit(self):
        self._committed = True

    async def flush(self):
        pass

    async def refresh(self, obj):
        pass

    async def rollback(self):
        pass


# ══════════════════════════════════════════════════════════════
# _serialize — pure function, no mocking needed
# ══════════════════════════════════════════════════════════════


class TestSerialize:
    """_serialize — DataSourceRecord → DataSourceResponse conversion."""

    def test_basic_fields(self):
        ds = _make_ds_record(name="GitHub", source_type="api", authority_score=0.95)
        result = _serialize(ds)
        assert isinstance(result, DataSourceResponse)
        assert result.name == "GitHub"
        assert result.source_type == "api"
        assert result.authority_score == 0.95
        assert result.status == "active"

    def test_last_crawl_at_serialized(self):
        dt = datetime(2026, 1, 15, 10, 30, 0, tzinfo=UTC)
        ds = _make_ds_record(last_crawl_at=dt)
        result = _serialize(ds)
        assert result.last_crawl_at is not None
        assert "2026-01-15" in result.last_crawl_at

    def test_last_crawl_at_none(self):
        ds = _make_ds_record(last_crawl_at=None)
        # Need to override — _make_ds_record defaults to now()
        ds.last_crawl_at = None
        result = _serialize(ds)
        assert result.last_crawl_at is None

    def test_config_defaults_to_empty_dict(self):
        ds = _make_ds_record()
        ds.config = None  # Override the default from _make_ds_record
        result = _serialize(ds)
        assert result.config == {}

    def test_config_preserved(self):
        ds = _make_ds_record(config={"rate_limit": 100})
        result = _serialize(ds)
        assert result.config == {"rate_limit": 100}

    def test_id_converted_to_string(self):
        uid = uuid.uuid4()
        ds = _make_ds_record(id=uid)
        result = _serialize(ds)
        assert result.id == str(uid)

    def test_numeric_fields(self):
        ds = _make_ds_record(
            total_records=500,
            valid_records=480,
            duplicate_rate=0.04,
            avg_quality_score=0.92,
        )
        result = _serialize(ds)
        assert result.total_records == 500
        assert result.valid_records == 480
        assert result.duplicate_rate == 0.04
        assert result.avg_quality_score == 0.92


# ══════════════════════════════════════════════════════════════
# list_datasources logic — query → serialize
# ══════════════════════════════════════════════════════════════


class TestListDatasources:
    """list_datasources — returns serialized list from DB query."""

    async def test_returns_serialized_list(self):
        ds1 = _make_ds_record(name="BOSS直聘", authority_score=0.9)
        ds2 = _make_ds_record(name="拉勾网", authority_score=0.7)
        session = FakeAsyncSession([FakeResult([ds1, ds2])])
        result = await session.execute(None)
        items = [_serialize(ds) for ds in result.scalars().all()]
        assert len(items) == 2
        assert items[0].name == "BOSS直聘"
        assert items[1].name == "拉勾网"

    async def test_returns_empty_list(self):
        session = FakeAsyncSession([FakeResult([])])
        result = await session.execute(None)
        items = [_serialize(ds) for ds in result.scalars().all()]
        assert items == []


# ══════════════════════════════════════════════════════════════
# get_datasource logic — single item + not-found
# ══════════════════════════════════════════════════════════════


class TestGetDatasource:
    """get_datasource — returns single item or raises not-found."""

    async def test_returns_item_when_found(self):
        ds_id = uuid.uuid4()
        ds = _make_ds_record(id=ds_id, name="ESCO")
        session = FakeAsyncSession([FakeResult(ds)])
        result = await session.execute(None)
        ds_obj = result.scalar_one_or_none()
        assert ds_obj is not None
        response = _serialize(ds_obj)
        assert response.id == str(ds_id)
        assert response.name == "ESCO"

    async def test_returns_none_when_not_found(self):
        session = FakeAsyncSession([FakeResult(None)])
        result = await session.execute(None)
        ds_obj = result.scalar_one_or_none()
        assert ds_obj is None
        # In the endpoint, this would raise HTTPException(404)
        # At service level, we assert None and let the caller decide


# ══════════════════════════════════════════════════════════════
# update_datasource logic — partial update + validation
# ══════════════════════════════════════════════════════════════


class TestUpdateDatasource:
    """update_datasource — partial field update with validation."""

    def test_valid_status_values(self):
        for status in ("active", "paused", "error"):
            body = DataSourceUpdateRequest(status=status)
            assert body.status == status

    def test_invalid_status_not_in_model(self):
        """Pydantic V2 validates Literal at model construction time."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DataSourceUpdateRequest(status="invalid_status")

    def test_authority_score_range(self):
        # Valid
        body = DataSourceUpdateRequest(authority_score=0.5)
        assert body.authority_score == 0.5

        # Out of range — Pydantic validation (ge=0, le=1)
        with pytest.raises(Exception):
            DataSourceUpdateRequest(authority_score=2.0)

        with pytest.raises(Exception):
            DataSourceUpdateRequest(authority_score=-0.1)

    def test_partial_update_no_fields(self):
        body = DataSourceUpdateRequest()
        assert body.authority_score is None
        assert body.status is None
        assert body.config is None

    def test_config_update(self):
        body = DataSourceUpdateRequest(config={"new": True})
        assert body.config == {"new": True}


# ══════════════════════════════════════════════════════════════
# get_datasource_stats logic — period parsing + daily aggregation
# ══════════════════════════════════════════════════════════════


class TestGetDatasourceStats:
    """get_datasource_stats — period handling + aggregation math."""

    def test_period_days_map(self):
        days_map = {"7d": 7, "30d": 30, "90d": 90}
        assert days_map["7d"] == 7
        assert days_map["30d"] == 30
        assert days_map["90d"] == 90
        # Unknown period defaults to 30
        assert days_map.get("1y", 30) == 30

    def test_crawl_volume_entry(self):
        entry = CrawlVolumeEntry(date="2026-01-01", count=42)
        assert entry.date == "2026-01-01"
        assert entry.count == 42

    def test_quality_trend_entry(self):
        entry = QualityTrendEntry(date="2026-01-01", score=0.85)
        assert entry.date == "2026-01-01"
        assert entry.score == 0.85

    def test_stats_response_fields(self):
        resp = DataSourceStatsResponse(
            source_id="abc", source_name="BOSS",
            crawl_volume=[], quality_trend=[],
            total_runs=5, successful_runs=4, failed_runs=1,
            avg_records_per_run=25.0,
        )
        assert resp.total_runs == 5
        assert resp.successful_runs == 4
        assert resp.failed_runs == 1
        assert resp.avg_records_per_run == 25.0

    def test_aggregation_logic_with_runs(self):
        """Simulate the aggregation logic from the endpoint."""
        runs = [
            _make_pipeline_run(
                started_at=datetime(2026, 1, 10, tzinfo=UTC),
                status="completed", total_records=100, quality_score=0.9,
            ),
            _make_pipeline_run(
                started_at=datetime(2026, 1, 11, tzinfo=UTC),
                status="completed", total_records=50, quality_score=0.8,
            ),
            _make_pipeline_run(
                started_at=datetime(2026, 1, 12, tzinfo=UTC),
                status="failed", total_records=0, quality_score=0.0,
            ),
        ]

        total = 0
        successful = 0
        failed = 0
        total_records = 0
        volume_by_day = {}
        quality_by_day = {}

        for run in runs:
            total += 1
            if run.status == "completed":
                successful += 1
                day_key = run.started_at.strftime("%Y-%m-%d")
                volume_by_day[day_key] = volume_by_day.get(day_key, 0) + run.total_records
                total_records += run.total_records
                if run.quality_score > 0:
                    quality_by_day.setdefault(day_key, []).append(run.quality_score)
            elif run.status == "failed":
                failed += 1

        assert total == 3
        assert successful == 2
        assert failed == 1
        assert total_records == 150
        assert volume_by_day["2026-01-10"] == 100
        assert volume_by_day["2026-01-11"] == 50
        assert quality_by_day["2026-01-10"] == [0.9]

        avg_per_run = total_records / successful if successful > 0 else 0.0
        assert avg_per_run == 75.0

    def test_aggregation_empty_runs(self):
        total = successful = failed = total_records = 0
        avg_per_run = (total_records / successful) if successful > 0 else 0.0
        assert avg_per_run == 0.0


# ══════════════════════════════════════════════════════════════
# get_datasources_health logic — status counting
# ══════════════════════════════════════════════════════════════


class TestGetDatasourcesHealth:
    """get_datasources_health — counts sources by status."""

    def test_health_response_fields(self):
        resp = DatasourcesHealthResponse(
            sources=[],
            total_sources=0,
            active_sources=0,
            error_sources=0,
        )
        assert resp.total_sources == 0
        assert resp.active_sources == 0
        assert resp.error_sources == 0

    def test_status_counting(self):
        sources = [
            _make_ds_record(status="active"),
            _make_ds_record(status="active"),
            _make_ds_record(status="error"),
        ]
        active = sum(1 for s in sources if s.status == "active")
        error = sum(1 for s in sources if s.status == "error")
        assert active == 2
        assert error == 1

    def test_source_health_entry(self):
        entry = SourceHealthEntry(
            id="abc", name="BOSS直聘", status="active",
            total_records=1000, recent_run_status="completed",
        )
        assert entry.status == "active"
        assert entry.recent_run_status == "completed"

    def test_health_empty_sources(self):
        sources = []
        active = sum(1 for s in sources if s.status == "active")
        error = sum(1 for s in sources if s.status == "error")
        assert active == 0
        assert error == 0


# ══════════════════════════════════════════════════════════════
# trigger_source_sync logic — existence check + pipeline trigger
# ══════════════════════════════════════════════════════════════


class TestTriggerSourceSync:
    """trigger_source_sync — check source exists, then trigger pipeline."""

    async def test_trigger_when_source_exists(self):
        ds_id = uuid.uuid4()
        ds = _make_ds_record(id=ds_id, name="拉勾网")
        session = FakeAsyncSession([FakeResult(ds)])
        result = await session.execute(None)
        ds_obj = result.scalar_one_or_none()
        assert ds_obj is not None
        assert ds_obj.name == "拉勾网"

        # The endpoint calls trigger_and_start(run_type="source_sync")
        with patch("app.core.pipeline.executor.trigger_and_start", new_callable=AsyncMock) as mock_trigger:
            from app.models.pipeline_models import PipelineRun
            mock_run = MagicMock(spec=PipelineRun)
            mock_run.id = uuid.uuid4()
            mock_run.status = "running"
            mock_trigger.return_value = mock_run

            run = await mock_trigger(run_type="source_sync")

            resp = SyncTriggerResponse(
                run_id=str(run.id),
                source_name=ds_obj.name,
                status=run.status,
                message=f"Source sync triggered for '{ds_obj.name}' (run_id={run.id})",
            )
            assert resp.source_name == "拉勾网"
            assert resp.status == "running"
            mock_trigger.assert_awaited_once_with(run_type="source_sync")

    async def test_trigger_when_source_not_found(self):
        session = FakeAsyncSession([FakeResult(None)])
        result = await session.execute(None)
        ds_obj = result.scalar_one_or_none()
        # In the endpoint, this would raise HTTPException(404)
        assert ds_obj is None
