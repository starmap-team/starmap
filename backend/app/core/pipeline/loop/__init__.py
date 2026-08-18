"""Closed-loop orchestration package — Closed-loop demonstration.

split: 5-step loop logic moved out of `loop_orchestrator.py`
into ``loop.common`` (shared types + persistence helpers) and ``loop.steps``
(one module per step). The original ``loop_orchestrator.py`` remains as a
thin compatibility / re-export shell so legacy imports keep working.

New code should import directly from ``loop.common`` or ``loop.steps.*``.
"""
from __future__ import annotations

__all__: list[str] = []
