"""LLM token cost tracker — in-process accumulator + structured JSON log.

Phase 4: emit per-call cost events for Loki aggregation; expose a REST summary
endpoint for the UI. No new dependencies — uses loguru (already AP-10 JSON sink)
and threading.Lock for thread-safe accumulation.

Phase 27 (qwen-plus 资源包优化): 加每日成本预算守卫(`_caps`),
超过 0.8*cap 提示 WARNING,超过 1.0*cap 时本调用返回 `blocked` 标记,
由 `_call_and_track` 检测后跳过实际 provider 调用(防止意外情况下
自动化脚本/循环 bug 累积成本爆表)。

设计:
  - In-memory only; resets on restart. Loki is the durable record.
  - Token estimation: 1 token ≈ 4 chars (OpenAI heuristic, good enough for
    budgeting; real usage comes from provider `usage` field when available).
  - Price: ¥1 / 1M tokens (uniform input + output, per team decision 2026-07-22).
  - Cap 默认 ¥50/天 (settings.llm_cost_cap_cny_per_day)。 1.1 亿 tokens ≈ ¥114.4,
    设 50 防意外,正常业务不应触发。
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

# 阻断时使用的特殊 model 标记 (response_cache.py 跳过该标记以免污染)
BLOCKED_MODEL_TAG = "blocked"

# 软警告阈值(占 cap 比例)
_WARN_RATIO = 0.8


class _CostTracker:
    """Thread-safe in-process LLM cost accumulator."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_model: dict[str, dict[str, float]] = {}
        self._caps: dict[str, float] = {}

    def set_model_cap(self, model: str, cny_per_day: float) -> None:
        """Configure daily cost cap for a model. ¥0 = disabled.

        Phase 27: 由 lifespan / settings 在启动时注入。
        """
        with self._lock:
            if cny_per_day <= 0:
                self._caps.pop(model, None)
            else:
                self._caps[model] = float(cny_per_day)

    def get_model_cap(self, model: str) -> float:
        with self._lock:
            return self._caps.get(model, 0.0)

    def is_blocked(self, model: str) -> bool:
        """判断给定 model 是否已超过 cap(返回 True 时调用方应跳过 LLM 调用)。"""
        cap = self.get_model_cap(model)
        if cap <= 0:
            return False
        with self._lock:
            bucket = self._by_model.get(model, {})
            cost = bucket.get("cost_cny", 0.0)
        return cost >= cap

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

            # Phase 27: cap 检查 (软警告 + 硬阻断)
            cap = self._caps.get(model, 0.0)
            if cap > 0:
                cumulative = bucket["cost_cny"]
                if cumulative >= cap:
                    logger.warning(
                        "LLM cost cap exceeded: model={} cumulative=¥{:.4f} cap=¥{:.2f}",
                        model, cumulative, cap,
                    )
                elif cumulative >= cap * _WARN_RATIO:
                    logger.warning(
                        "LLM cost cap approaching: model={} cumulative=¥{:.4f} cap=¥{:.2f} ({:.0%})",
                        model, cumulative, cap, cumulative / cap,
                    )

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
            caps = dict(self._caps)
        total_cost = round(sum(v["cost_cny"] for v in models.values()), 6)
        total_tokens = int(sum(v["input_tokens"] + v["output_tokens"] for v in models.values()))
        return {
            "price_cny_per_1m_tokens": PRICE_CNY_PER_1M,
            "total_cost_cny": total_cost,
            "total_tokens": total_tokens,
            "by_model": models,
            "caps": caps,
        }


# Module-level singleton — import this, not the class.
tracker = _CostTracker()
