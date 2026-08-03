"""Phase 4: LLM cost tracker unit tests.

Ponytail: covers accumulation + char/4 token estimation + per-model bucketing.
Restart-reset and concurrency are exercised via fresh tracker instances.
"""
from __future__ import annotations

import threading

from app.core.llm import cost_tracker
from app.core.llm.cost_tracker import PRICE_CNY_PER_1M, tracker


def test_price_constant_matches_team_decision() -> None:
    assert PRICE_CNY_PER_1M == 1.0, "team decision 2026-07-22: ¥1 / 1M tokens uniform"


def test_record_estimates_tokens_from_chars() -> None:
    fresh = cost_tracker._CostTracker()
    fresh.record(model="mimo-7b", prompt="a" * 400, content="b" * 200)
    s = fresh.summary()
    bucket = s["by_model"]["mimo-7b"]
    assert bucket["input_tokens"] == 100  # 400 / 4
    assert bucket["output_tokens"] == 50  # 200 / 4
    assert bucket["cost_cny"] == round(150 / 1_000_000 * 1.0, 6)


def test_explicit_token_counts_override_estimation() -> None:
    fresh = cost_tracker._CostTracker()
    fresh.record(model="deepseek", prompt="x" * 4000, content="y" * 4000,
                 input_tokens=500, output_tokens=200)
    bucket = fresh.summary()["by_model"]["deepseek"]
    assert bucket["input_tokens"] == 500
    assert bucket["output_tokens"] == 200
    assert bucket["calls"] == 1


def test_summary_aggregates_across_models() -> None:
    fresh = cost_tracker._CostTracker()
    fresh.record(model="a", prompt="x" * 1000, content="y" * 1000)
    fresh.record(model="b", prompt="x" * 2000, content="y" * 500)
    fresh.record(model="a", prompt="x" * 100, content="y" * 100)
    s = fresh.summary()
    assert s["total_tokens"] == 500 + 625 + 50  # (1000+1000)/4 + (2000+500)/4 + (100+100)/4
    assert s["by_model"]["a"]["calls"] == 2
    assert s["by_model"]["b"]["calls"] == 1


def test_thread_safety_under_concurrent_records() -> None:
    fresh = cost_tracker._CostTracker()

    def hammer() -> None:
        for _ in range(100):
            fresh.record(model="x", prompt="a" * 40, content="b" * 40)

    threads = [threading.Thread(target=hammer) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    bucket = fresh.summary()["by_model"]["x"]
    assert bucket["calls"] == 800
    assert bucket["input_tokens"] == 800 * 10  # 40/4 = 10 per call


def test_module_singleton_returns_same_instance() -> None:
    assert tracker is cost_tracker.tracker
