"""Test zombie-skip logic (_pick_best_run) — pure Python, no DB needed.

Phase 13 · 2026-07-27.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.api.v1.pipeline.routes import _pick_best_run


def _make_mock_run(status: str, total_records: int = 0) -> MagicMock:
    run = MagicMock()
    run.status = status
    run.total_records = total_records
    return run


def test_empty_list_returns_none():
    assert _pick_best_run([]) is None


def test_running_is_top_priority():
    r1 = _make_mock_run("running")
    r2 = _make_mock_run("completed", total_records=46)
    r3 = _make_mock_run("cancelled", total_records=0)
    assert _pick_best_run([r2, r3, r1]) is r1  # running wins regardless of order


def test_completed_with_records_beats_failed():
    completed = _make_mock_run("completed", total_records=46)
    failed = _make_mock_run("failed")
    assert _pick_best_run([failed, completed]) is completed


def test_failed_beats_cancelled_with_records():
    failed = _make_mock_run("failed")
    cancelled_with = _make_mock_run("cancelled", total_records=10)
    cancelled_zero = _make_mock_run("cancelled", total_records=0)
    assert _pick_best_run([cancelled_with, cancelled_zero, failed]) is failed


def test_cancelled_with_records_beats_zombie():
    zombie = _make_mock_run("cancelled", total_records=0)
    partial = _make_mock_run("cancelled", total_records=5)
    assert _pick_best_run([zombie, partial]) is partial


def test_more_records_preferred_within_same_priority():
    few = _make_mock_run("completed", total_records=10)
    many = _make_mock_run("completed", total_records=100)
    assert _pick_best_run([few, many]) is many


def test_zombie_is_last_resort():
    zombie = _make_mock_run("cancelled", total_records=0)
    assert _pick_best_run([zombie]) is zombie  # still returns something, not None