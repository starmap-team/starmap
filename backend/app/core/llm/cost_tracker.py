"""LLM token cost tracker — in-process accumulator + structured JSON log.

Phase 4: emit per-call cost events for Loki aggregation; expose a REST summary
endpoint for the UI. No new dependencies — uses loguru (already AP-10 JSON sink)
and threading.Lock for thread-safe accumulation.

Design notes:
  - In-memory only; resets on restart. Loki is the durable record.
  - Token estimation: 1 token ≈ 4 chars (OpenAI heuristic, good enough for
    budgeting; real usage comes from provider `usage` field when available).
  - Price: ¥1 / 1M tokens (uniform for input + output, per team decision 2026-07-22).

Ponytail: single-process counter; if we add Celery multi-worker this becomes
per-worker — switch to Redis atomic counter then.
"""
from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any

from loguru import logger

# Price per 1M tokens in CNY (uniform input/output, per team decision 2026-07-22)
PRICE_CNY_PER_1M = 1.0

# Char-per-token heuristic (OpenAI convention)
_CHARS_PER_TOKEN = 4.0


class _CostTracker:
    """Thread-safe in-process LLM cost accumulator."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_model: dict[str, dict[str, float]] = {}

    def record(
        self,
        *,
        model: str,
        prompt: str,
        content: str,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Record one LLM call. Returns the cost event dict.

        Token counts fall back to char/4 estimation when the provider doesn't
        return explicit usage. Always emits a structured loguru event for Loki.
        """
        in_t = int(input_tokens) if input_tokens is not None else int(len(prompt) / _CHARS_PER_TOKEN)
        out_t = int(output_tokens) if output_tokens is not None else int(len(content) / _CHARS_PER_TOKEN)
        total = in_t + out_t
        cost_cny = round(total / 1_000_000 * PRICE_CNY_PER_1M, 6)

        # AP-10: prod env serializes to JSON; dev env prints pretty.
        logger.info("LLM cost: model={} tokens={} cost=¥{}", model, total, cost_cny)

        with self._lock:
            bucket = self._by_model.setdefault(
                model, {"input_tokens": 0.0, "output_tokens": 0.0, "cost_cny": 0.0, "calls": 0.0},
            )
            bucket["input_tokens"] += in_t
            bucket["output_tokens"] += out_t
            bucket["cost_cny"] += cost_cny
            bucket["calls"] += 1
        return {
            "type": "llm_cost",
            "model": model,
            "input_tokens": in_t,
            "output_tokens": out_t,
            "total_tokens": total,
            "cost_cny": cost_cny,
            "ts": datetime.now(UTC).isoformat(),
        }

    def summary(self) -> dict[str, Any]:
        """Snapshot for the REST endpoint."""
        with self._lock:
            models = {m: dict(v) for m, v in self._by_model.items()}
        total_cost = round(sum(v["cost_cny"] for v in models.values()), 6)
        total_tokens = int(sum(v["input_tokens"] + v["output_tokens"] for v in models.values()))
        return {
            "price_cny_per_1m_tokens": PRICE_CNY_PER_1M,
            "total_cost_cny": total_cost,
            "total_tokens": total_tokens,
            "by_model": models,
        }


# Module-level singleton — import this, not the class.
tracker = _CostTracker()
