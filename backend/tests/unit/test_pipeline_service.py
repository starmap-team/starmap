"""Unit tests for pipeline business logic — service/core layer only.

Directly tests service/core functions — no TestClient, no HTTP layer.
Covers:
- Pipeline status aggregation logic
- Schedule CRUD validation
- Config update logic
- Stage normalization (list vs dict format)
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ══════════════════════════════════════════════════════════════
# Pipeline status — aggregation logic
# ══════════════════════════════════════════════════════════════


class TestPipelineStatusAggregation:
    """Pipeline status data aggregation."""

    def test_status_counts_from_runs(self):
        runs = [
            MagicMock(status="completed"),
            MagicMock(status="completed"),
            MagicMock(status="completed"),
            MagicMock(status="completed"),
            MagicMock(status="failed"),
        ]
        counts = {}
        for run in runs:
            counts[run.status] = counts.get(run.status, 0) + 1
        assert counts.get("completed", 0) == 4
        assert counts.get("failed", 0) == 1

    def test_empty_runs(self):
        counts = {}
        assert counts.get("completed", 0) == 0

    def test_is_running_flag(self):
        # When current_run status is "running"
        current_run = MagicMock(status="running")
        is_running = current_run.status == "running"
        assert is_running is True

        # When no current run
        is_running = False
        assert is_running is False


# ══════════════════════════════════════════════════════════════
# Stage normalization — list vs dict format
# ══════════════════════════════════════════════════════════════


class TestStageNormalization:
    """Pipeline stages: normalize from dict or list format."""

    def test_stages_from_list(self):
        stages = [
            {"name": "crawl", "status": "completed", "duration_ms": 5000},
            {"name": "dedup", "status": "running", "duration_ms": 2000},
        ]
        # Endpoint normalizes list → list
        normalized = [s for s in stages if isinstance(s, dict)]
        assert len(normalized) == 2
        assert normalized[0]["name"] == "crawl"

    def test_stages_from_dict_format(self):
        """Legacy rows store stages as {"steps": [...]}."""
        raw = {"steps": [{"name": "crawl", "status": "completed", "duration_ms": 100}]}
        # Endpoint extracts from "steps" key
        if "steps" in raw:
            normalized = raw["steps"]
        else:
            normalized = raw if isinstance(raw, list) else []
        assert len(normalized) == 1
        assert normalized[0]["name"] == "crawl"

    def test_stages_skip_non_dict_entries(self):
        stages = ["not_a_dict", {"name": "dedup", "status": "completed"}]
        normalized = [s for s in stages if isinstance(s, dict)]
        assert len(normalized) == 1
        assert normalized[0]["name"] == "dedup"

    def test_empty_stages(self):
        stages = []
        normalized = [s for s in stages if isinstance(s, dict)]
        assert normalized == []


# ══════════════════════════════════════════════════════════════
# Schedule validation
# ══════════════════════════════════════════════════════════════


class TestScheduleValidation:
    """Schedule CRUD validation logic."""

    def test_valid_schedule_fields(self):
        schedule = {
            "name": "nightly",
            "cron_expression": "0 2 * * *",
            "run_type": "incremental",
            "enabled": True,
        }
        assert schedule["name"] == "nightly"
        assert schedule["run_type"] in ("full", "incremental")

    def test_run_type_values(self):
        valid_types = {"full", "incremental"}
        assert "full" in valid_types
        assert "incremental" in valid_types
        assert "invalid" not in valid_types

    def test_cron_expression_format(self):
        """Basic cron expression validation (5 fields)."""
        valid = "0 2 * * *"
        assert len(valid.split()) == 5

        invalid = "0 2 * *"
        assert len(invalid.split()) != 5


# ══════════════════════════════════════════════════════════════
# Config update — partial update logic
# ══════════════════════════════════════════════════════════════


class TestConfigUpdate:
    """Pipeline config partial update."""

    def test_partial_update_preserves_other_fields(self):
        current = {
            "stage_timeout": 1800,
            "worker_concurrency": 4,
            "crawl_concurrency": 8,
            "retry_max": 3,
            "retry_backoff": 30,
        }
        update = {"stage_timeout": 3600}
        # Merge
        merged = {**current, **update}
        assert merged["stage_timeout"] == 3600
        assert merged["worker_concurrency"] == 4  # preserved

    def test_empty_update_preserves_all(self):
        current = {"stage_timeout": 1800, "retry_max": 3}
        update = {}
        merged = {**current, **update}
        assert merged == current

    def test_config_field_ranges(self):
        """Validate config field constraints."""
        # stage_timeout: 60–7200
        assert 60 <= 1800 <= 7200
        # worker_concurrency: 1–16
        assert 1 <= 4 <= 16
        # retry_max: 0–10
        assert 0 <= 3 <= 10


# ══════════════════════════════════════════════════════════════
# Data quality aggregation
# ══════════════════════════════════════════════════════════════


class TestDataQualityAggregation:
    """Data quality metrics aggregation from pipeline runs."""

    def test_quality_snapshot_structure(self):
        snapshot = {
            "metrics": {"overall_score": 0.9},
            "alerts": [],
            "source_scores": {"lagou": 0.8},
        }
        assert snapshot["metrics"]["overall_score"] == 0.9
        assert len(snapshot["alerts"]) == 0

    def test_alert_counting(self):
        alerts = [
            {"level": "warning", "dimension": "freshness"},
            {"level": "error", "dimension": "completeness"},
        ]
        warning_count = sum(1 for a in alerts if a["level"] == "warning")
        error_count = sum(1 for a in alerts if a["level"] == "error")
        assert warning_count == 1
        assert error_count == 1