"""Step 1 — JD input validation + target_position resolution (Phase 07-02 D-01).

Extracted from ``loop_orchestrator.py._step1_validate_input`` and
``_resolve_target_position``.

``target_position`` is optional per the OpenAPI contract
(``LoopRunRequest.target_position: str | None = None``). When omitted,
Step 2 will infer a ``position_name`` from the extracted JD; Steps 4/5
skip when still missing. We must NOT reject the run here — see QA B1.

Returns a tuple ``(step_result, effective_target_position)`` so the
caller can feed the resolved value into Step 3.
"""
from __future__ import annotations

import time
from typing import Any

from app.core.pipeline.loop.common import (
    STEP_NAMES,
    LoopStepResult,
    StepStatus,
)


def run_validate_step(
    jd_text: str, target_position: str | None,
) -> tuple[LoopStepResult, str | None]:
    """Step 1: Validate JD input and resolve effective target_position.

    Args:
        jd_text: Raw job description text.
        target_position: Caller-supplied target position name (may be None / empty).

    Returns:
        Tuple ``(step_result, effective_target_position)`` where
        ``effective_target_position`` is the caller value if non-empty, else
        ``None`` (will be filled by Step 2's extraction).
    """
    start = time.monotonic()
    if not jd_text or not jd_text.strip():
        return (
            LoopStepResult(
                step=1,
                name=STEP_NAMES[1],
                status=StepStatus.FAILED,
                error="JD text is empty",
                duration_seconds=time.monotonic() - start,
            ),
            None,
        )
    return (
        LoopStepResult(
            step=1,
            name=STEP_NAMES[1],
            status=StepStatus.SUCCESS,
            data={
                "jd_length": len(jd_text),
                "target_position": (target_position or "").strip(),
            },
            duration_seconds=time.monotonic() - start,
        ),
        (target_position or "").strip() or None,
    )


def resolve_target_position(
    requested: str | None,
    extraction_data: dict[str, Any],
) -> str | None:
    """Resolve the effective target_position for match diagnosis.

    Priority: caller-supplied non-empty value → LLM-extracted position_name → None.
    A ``None`` result lets downstream steps skip gracefully (see Step 4/5 in run_loop).
    """
    if requested and requested.strip():
        return requested.strip()
    inferred = (extraction_data or {}).get("position_name")
    if isinstance(inferred, str) and inferred.strip():
        return inferred.strip()
    return None


__all__ = ["run_validate_step", "resolve_target_position"]
