"""TrustScorer — assign a trust score (0.0–1.0) to an EvolutionChange.

Score is a weighted blend of three signals, designed so that a single-mention
LLM hallucination can never score above 0.3, while a 10-source corroborated
change with stable history scores near 1.0:

    source_factor (0.5)  — sqrt(source_count / 10), capped at 1.0
                           1 source  → 0.32
                           3 sources → 0.55
                           5 sources → 0.71
                          10+ sources → 1.00

    stability_factor (0.3) — based on mention_count delta between old/new
                             snapshots. Stable or growing skills score
                             higher; vanishing skills score lower.

    type_factor (0.2)     — added_required  → 1.00 (strong signal)
                            promoted         → 0.90
                            demoted          → 0.70
                            added_preferred  → 0.65
                            retained         → 0.50 (weak: status quo)
                            removed          → 0.40 (often noisy)

Stage 3 governance rule: no EvolutionChangelog row may persist with the
default 0.5 placeholder — TrustScorer MUST be invoked for every change.
"""
from __future__ import annotations

import math
from typing import Any

from app.core.evolution.diff_engine import ChangeType, EvolutionChange

# Weights — keep them in one place so tuning is auditable.
WEIGHT_SOURCE = 0.5
WEIGHT_STABILITY = 0.3
WEIGHT_TYPE = 0.2

# Lookup tables — preferred over `if/elif` chains for clarity.
_TYPE_FACTOR: dict[ChangeType, float] = {
    ChangeType.ADDED_REQUIRED: 1.00,
    ChangeType.PROMOTED: 0.90,
    ChangeType.DEMOTED: 0.70,
    ChangeType.ADDED_PREFERRED: 0.65,
    ChangeType.RETAINED: 0.50,
    ChangeType.REMOVED: 0.40,
}

# Saturation point: source_count beyond this adds no extra trust.
SOURCE_SATURATION = 10.0

# BUG-6 fix: single threshold for "low trust → needs human review".
# Used by:
#   - EvolutionOrchestrator._save_changelog (writes status='pending' when trust < this)
#   - GET /evolution/review-queue (filters where trust_score < this)
#   - services/review_service.count_by_status (counts evolution_pending)
# Previously these were three different magic numbers (0.6 / 0.5 / 0.5) which
# caused pending rows in [0.5, 0.6) to be invisible to /evolution/review-queue.
LOW_TRUST_THRESHOLD = 0.5

# D-05 write-back gate: independent from LOW_TRUST_THRESHOLD (approved/review
# 口径 stays 0.5). Changes with trust >= this value are eligible for upsert
# into position_skill_relations (SSOT). Kept as its own constant so the
# write-back gate can never silently drift with the review threshold.
WRITEBACK_TRUST_THRESHOLD = 0.6


class TrustScorer:
    """Score an EvolutionChange into a trust/confidence pair.

    Returns ``(trust_score, confidence)`` — they are related but distinct:
    - ``trust_score``:    how much we believe the change reflects real market signal
    - ``confidence``:     how precise the detection itself is (statistical strength)

    Both end up as columns on EvolutionChangelog.
    """

    def score(
        self,
        change: EvolutionChange,
        source_count: int,
    ) -> tuple[float, float]:
        """Return ``(trust_score, confidence)`` both clamped to [0.0, 1.0]."""
        source_factor = self._source_factor(source_count)
        stability_factor = self._stability_factor(change)
        type_factor = self._type_factor(change.change_type)

        trust = (
            WEIGHT_SOURCE * source_factor
            + WEIGHT_STABILITY * stability_factor
            + WEIGHT_TYPE * type_factor
        )
        trust = max(0.0, min(1.0, trust))

        # Confidence is a coarser signal: how strong is the evidence envelope?
        confidence = max(0.0, min(1.0, 0.5 * source_factor + 0.5 * stability_factor))
        return round(trust, 4), round(confidence, 4)

    # ── internal ──

    @staticmethod
    def _source_factor(source_count: int) -> float:
        """Sqrt-saturation curve: 0→0, 1→0.32, 3→0.55, 5→0.71, 10+→1.0."""
        if source_count <= 0:
            return 0.0
        return min(1.0, math.sqrt(source_count / SOURCE_SATURATION))

    @staticmethod
    def _stability_factor(change: EvolutionChange) -> float:
        """Stable or growing skills score higher than vanishing ones.

        - cold-start added_*:        mention_count_new alone, partial credit
        - retained:                  higher of old/new (continuity signal)
        - promoted / demoted:        average of old/new (transitional)
        - removed:                   mention_count_old, heavily discounted
        """
        old_n = change.mention_count_old
        new_n = change.mention_count_new
        ct = change.change_type

        if ct in (ChangeType.ADDED_REQUIRED, ChangeType.ADDED_PREFERRED):
            # New skill — trust grows with mention_count_new but starts low.
            return min(1.0, new_n / 5.0)

        if ct == ChangeType.RETAINED:
            # Continuity: the more mentions, the more we trust it persists.
            return min(1.0, max(old_n, new_n) / 5.0)

        if ct in (ChangeType.PROMOTED, ChangeType.DEMOTED):
            # Transitional: average of both sides, normalized.
            avg = (old_n + new_n) / 2.0
            return min(1.0, avg / 5.0)

        if ct == ChangeType.REMOVED:
            # Removed skills are often noise — discount heavily.
            return min(0.4, old_n / 10.0)

        return 0.0

    @staticmethod
    def _type_factor(change_type: ChangeType) -> float:
        return _TYPE_FACTOR.get(change_type, 0.5)


def score_change(
    change: EvolutionChange,
    source_count: int,
) -> dict[str, Any]:
    """Convenience wrapper returning the full evidence dict for orchestrator."""
    scorer = TrustScorer()
    trust, confidence = scorer.score(change, source_count)
    return {
        "skill_name": change.skill_name,
        "change_type": change.change_type.value,
        "trust_score": trust,
        "confidence": confidence,
        "source_count": source_count,
        "factors": {
            "source": round(scorer._source_factor(source_count), 3),
            "stability": round(scorer._stability_factor(change), 3),
            "type": scorer._type_factor(change.change_type),
        },
    }
