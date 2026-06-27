"""Trust Scorer — Weighted trust model with exponential decay.

Implements the trust scoring model from design.md §4.2:
    TrustChange(C) = w1*SourceCount + w2*TemporalContinuity + w3*CrossValidation + w4*ManualReview
    w1=0.35, w2=0.25, w3=0.25, w4=0.15
    TrustDecay(T) = Trust(T0) * exp(-0.15 * Δt)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from loguru import logger


class TrustLevel(StrEnum):
    """Trust level classification."""

    VERIFIED = "verified"  # >= 0.8
    PENDING = "pending"  # >= 0.5
    HIGH_RISK = "high_risk"  # < 0.5


@dataclass
class TrustFactors:
    """Input factors for trust computation."""

    source_count: int = 0
    """Number of independent sources confirming this skill."""

    temporal_continuity: float = 0.0
    """How consistently this skill appears over time (0.0-1.0)."""

    cross_validation: float = 0.0
    """Cross-validation score from multiple detection methods (0.0-1.0)."""

    manual_review: float = 0.0
    """Manual review score if available (0.0-1.0)."""


@dataclass
class TrustResult:
    """Output of trust computation."""

    score: float
    """Computed trust score (0.0-1.0)."""

    level: TrustLevel
    """Classification of the trust score."""

    factors: TrustFactors
    """Input factors used."""

    decay_applied: float = 1.0
    """Decay multiplier applied (1.0 = no decay)."""

    metadata: dict[str, Any] = field(default_factory=dict)


class TrustScorer:
    """Weighted trust scoring with exponential decay.

    Weights (from design.md §4.2):
        w1=0.35 (source_count)
        w2=0.25 (temporal_continuity)
        w3=0.25 (cross_validation)
        w4=0.15 (manual_review)

    Decay formula:
        TrustDecay(T) = Trust(T0) * exp(-0.15 * Δt)
        where Δt is in months
    """

    # Weights
    W_SOURCE = 0.35
    W_TEMPORAL = 0.25
    W_CROSS = 0.25
    W_MANUAL = 0.15

    # Decay rate (per month)
    DECAY_RATE = 0.15

    # Source count normalization (cap at 10 sources)
    MAX_SOURCES = 10

    def compute(
        self,
        factors: TrustFactors,
        last_updated: datetime | None = None,
    ) -> TrustResult:
        """Compute trust score from input factors.

        Args:
            factors: Input trust factors.
            last_updated: When this skill was last confirmed (for decay).

        Returns:
            TrustResult with computed score and level.
        """
        # Normalize source count to 0.0-1.0
        source_norm = min(1.0, factors.source_count / self.MAX_SOURCES)

        # Compute weighted score
        raw_score = (
            self.W_SOURCE * source_norm
            + self.W_TEMPORAL * factors.temporal_continuity
            + self.W_CROSS * factors.cross_validation
            + self.W_MANUAL * factors.manual_review
        )

        # Apply decay if last_updated is provided
        decay_multiplier = 1.0
        if last_updated is not None:
            now = datetime.now(UTC)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=UTC)
            delta_months = (now - last_updated).total_seconds() / (30 * 24 * 3600)
            decay_multiplier = math.exp(-self.DECAY_RATE * delta_months)
            raw_score *= decay_multiplier

        # Clamp to [0, 1]
        score = max(0.0, min(1.0, raw_score))

        # Classify
        level = self._classify(score)

        logger.debug(
            "Trust score: {:.3f} (level={}) sources={} temporal={:.2f} cross={:.2f} decay={:.3f}",
            score, level.value, factors.source_count,
            factors.temporal_continuity, factors.cross_validation, decay_multiplier,
        )

        return TrustResult(
            score=score,
            level=level,
            factors=factors,
            decay_applied=decay_multiplier,
        )

    def compute_from_source_count(
        self,
        source_count: int,
        last_updated: datetime | None = None,
    ) -> TrustResult:
        """Simplified trust computation from source count only.

        Uses heuristics for other factors based on source count.
        """
        # Heuristic: more sources → higher temporal continuity and cross-validation
        temporal = min(1.0, source_count / 8.0)
        cross = min(1.0, source_count / 6.0)

        factors = TrustFactors(
            source_count=source_count,
            temporal_continuity=temporal,
            cross_validation=cross,
            manual_review=0.0,
        )
        return self.compute(factors, last_updated)

    def update_trust(
        self,
        current_score: float,
        new_evidence: TrustFactors,
        last_updated: datetime | None = None,
    ) -> TrustResult:
        """Update an existing trust score with new evidence.

        Uses exponential moving average to blend old and new scores.
        """
        new_result = self.compute(new_evidence, last_updated)

        # Blend: 70% old + 30% new (conservative update)
        blended = 0.7 * current_score + 0.3 * new_result.score
        blended = max(0.0, min(1.0, blended))

        level = self._classify(blended)

        return TrustResult(
            score=blended,
            level=level,
            factors=new_evidence,
            decay_applied=new_result.decay_applied,
            metadata={"previous_score": current_score, "blend_ratio": "70/30"},
        )

    @staticmethod
    def _classify(score: float) -> TrustLevel:
        """Classify trust score into a level."""
        if score >= 0.8:
            return TrustLevel.VERIFIED
        if score >= 0.5:
            return TrustLevel.PENDING
        return TrustLevel.HIGH_RISK
