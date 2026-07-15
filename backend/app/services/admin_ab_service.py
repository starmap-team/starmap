"""Admin A/B test result service — aggregation logic extracted from admin_prompts.py.

The API layer (admin_prompts.py) handles HTTP request/response and storage
routing (Redis vs in-memory). This service owns the pure aggregation math
so it can be unit-tested without any HTTP or storage dependency.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any


def aggregate_ab_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate a list of A/B test result entries into a versioned summary.

    Each entry in *results* must have at least ``version`` (str) and
    ``success`` (bool).  Optional keys: ``f1`` (float), ``latency_ms`` (float).

    Returns::

        {
            "total": <int>,
            "versions": {
                "<version>": {
                    "count": int,
                    "success_rate": float,
                    "avg_f1": float | None,
                    "avg_latency_ms": float | None,
                },
                ...
            }
        }
    """
    if not results:
        return {"total": 0, "versions": {}}

    by_version: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "count": 0, "success_count": 0, "f1_sum": 0.0, "f1_count": 0,
        "latency_sum": 0.0, "latency_count": 0,
    })
    for r in results:
        v = r["version"]
        by_version[v]["count"] += 1
        if r["success"]:
            by_version[v]["success_count"] += 1
        if r.get("f1") is not None:
            by_version[v]["f1_sum"] += r["f1"]
            by_version[v]["f1_count"] += 1
        if r.get("latency_ms") is not None:
            by_version[v]["latency_sum"] += r["latency_ms"]
            by_version[v]["latency_count"] += 1

    summary: dict[str, dict[str, Any]] = {}
    for v, stats in by_version.items():
        summary[v] = {
            "count": stats["count"],
            "success_rate": round(stats["success_count"] / stats["count"], 4),
            "avg_f1": round(stats["f1_sum"] / stats["f1_count"], 4) if stats["f1_count"] else None,
            "avg_latency_ms": round(stats["latency_sum"] / stats["latency_count"], 1) if stats["latency_count"] else None,
        }

    return {"total": len(results), "versions": summary}
