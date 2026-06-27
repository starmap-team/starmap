"""Emergence Finder — Z-score based emerging skill detection.

Implements the emergence detection algorithm from design.md §4.5:
    z = (f(t) - μ) / σ
    if z > 2.0 AND f(t) > 3 AND independent sources >= 3: mark as emerging
    elif z > 1.5: mark as rising
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from loguru import logger


class EmergenceLevel(StrEnum):
    """Classification of skill emergence."""

    EMERGING = "emerging"  # z > 2.0, strong signal
    RISING = "rising"  # z > 1.5, moderate signal
    STABLE = "stable"  # normal fluctuation
    DECLINING = "declining"  # z < -1.5


@dataclass
class EmergenceSignal:
    """A single emergence detection result."""

    skill_name: str
    level: EmergenceLevel
    z_score: float
    current_frequency: int
    mean_frequency: float
    std_frequency: float
    source_count: int
    positions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EmergenceReport:
    """Complete emergence detection report."""

    emerging: list[EmergenceSignal]
    rising: list[EmergenceSignal]
    stable: list[EmergenceSignal]
    declining: list[EmergenceSignal]
    total_skills_analyzed: int
    window_description: str = ""

    @property
    def all_signals(self) -> list[EmergenceSignal]:
        return self.emerging + self.rising + self.stable + self.declining


class EmergenceFinder:
    """Detect emerging skills using Z-score analysis.

    Thresholds (from design.md §4.5):
        z > 2.0 AND f(t) > 3 AND sources >= 3 → emerging
        z > 1.5 → rising
        z < -1.5 → declining
        otherwise → stable
    """

    # Thresholds
    EMERGING_Z = 2.0
    RISING_Z = 1.5
    DECLINING_Z = -1.5
    MIN_FREQUENCY = 3
    MIN_SOURCES = 3

    def detect(
        self,
        skill_name: str,
        frequencies: list[int],
        current_frequency: int,
        source_count: int = 1,
        positions: list[str] | None = None,
    ) -> EmergenceSignal:
        """Detect emergence for a single skill.

        Args:
            skill_name: Name of the skill.
            frequencies: Historical frequency values (excluding current).
            current_frequency: Current window frequency.
            source_count: Number of independent sources.
            positions: Positions mentioning this skill.

        Returns:
            EmergenceSignal with classification.
        """
        # Compute statistics from historical data
        if len(frequencies) < 2:
            # Insufficient history — can't compute meaningful z-score
            return EmergenceSignal(
                skill_name=skill_name,
                level=EmergenceLevel.STABLE,
                z_score=0.0,
                current_frequency=current_frequency,
                mean_frequency=float(current_frequency),
                std_frequency=0.0,
                source_count=source_count,
                positions=positions or [],
                metadata={"note": "insufficient_history", "history_len": len(frequencies)},
            )

        mean = sum(frequencies) / len(frequencies)
        variance = sum((f - mean) ** 2 for f in frequencies) / len(frequencies)
        std = math.sqrt(variance)

        # Compute z-score (handle zero std)
        if std < 1e-6:
            # No variance — if current > mean, it's a jump; otherwise stable
            z = 10.0 if current_frequency > mean else 0.0
        else:
            z = (current_frequency - mean) / std

        # Classify
        level = self._classify(z, current_frequency, source_count)

        logger.debug(
            "Emergence '{}': z={:.2f} freq={} mean={:.1f} std={:.2f} level={}",
            skill_name, z, current_frequency, mean, std, level.value,
        )

        return EmergenceSignal(
            skill_name=skill_name,
            level=level,
            z_score=round(z, 3),
            current_frequency=current_frequency,
            mean_frequency=round(mean, 2),
            std_frequency=round(std, 2),
            source_count=source_count,
            positions=positions or [],
        )

    def _classify(
        self,
        z: float,
        frequency: int,
        source_count: int,
    ) -> EmergenceLevel:
        """Classify based on z-score and supporting criteria."""
        if z > self.EMERGING_Z and frequency >= self.MIN_FREQUENCY and source_count >= self.MIN_SOURCES:
            return EmergenceLevel.EMERGING
        if z > self.RISING_Z:
            return EmergenceLevel.RISING
        if z < self.DECLINING_Z:
            return EmergenceLevel.DECLINING
        return EmergenceLevel.STABLE

    def scan(
        self,
        skill_data: dict[str, dict[str, Any]],
    ) -> EmergenceReport:
        """Scan all skills for emergence signals.

        Args:
            skill_data: Dict of skill_name → {
                "frequencies": list[int],  # historical frequencies
                "current": int,            # current window frequency
                "sources": int,            # source count
                "positions": list[str],    # positions mentioning this skill
            }

        Returns:
            EmergenceReport with all signals classified.
        """
        emerging: list[EmergenceSignal] = []
        rising: list[EmergenceSignal] = []
        stable: list[EmergenceSignal] = []
        declining: list[EmergenceSignal] = []

        for skill_name, data in skill_data.items():
            signal = self.detect(
                skill_name=skill_name,
                frequencies=data.get("frequencies", []),
                current_frequency=data.get("current", 0),
                source_count=data.get("sources", 1),
                positions=data.get("positions", []),
            )

            if signal.level == EmergenceLevel.EMERGING:
                emerging.append(signal)
            elif signal.level == EmergenceLevel.RISING:
                rising.append(signal)
            elif signal.level == EmergenceLevel.DECLINING:
                declining.append(signal)
            else:
                stable.append(signal)

        # Sort by z-score descending
        emerging.sort(key=lambda s: s.z_score, reverse=True)
        rising.sort(key=lambda s: s.z_score, reverse=True)
        declining.sort(key=lambda s: s.z_score)

        logger.info(
            "Emergence scan: {} emerging, {} rising, {} stable, {} declining (total: {})",
            len(emerging), len(rising), len(stable), len(declining),
            len(skill_data),
        )

        return EmergenceReport(
            emerging=emerging,
            rising=rising,
            stable=stable,
            declining=declining,
            total_skills_analyzed=len(skill_data),
        )
