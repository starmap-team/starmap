"""Hallucination Guard — Three-layer defense against skill hallucination.

Implements the three-layer defense from design.md §4.3:
- Layer 1: Ontology whitelist (exact match + semantic match >= 0.85)
- Layer 2: Multi-source verification (>= 3 independent sources, span >= 4 weeks)
- Layer 3: Confidence grading (>= 0.8 → verified, >= 0.5 → pending, < 0.5 → high_risk)
- Extra: LLM-as-judge (SUPPORTED/UNSUPPORTED/AMBIGUOUS)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from loguru import logger


class VerificationStatus(StrEnum):
    """Status of hallucination verification."""

    VERIFIED = "verified"  # Passed all layers
    PENDING = "pending"  # Needs more evidence
    HIGH_RISK = "high_risk"  # Likely hallucination
    REJECTED = "rejected"  # Confirmed hallucination


class LLMJudgment(StrEnum):
    """LLM-as-judge verdict."""

    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass
class LayerResult:
    """Result from a single defense layer."""

    layer: int
    passed: bool
    score: float  # 0.0-1.0
    details: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GuardResult:
    """Complete hallucination guard result."""

    skill_name: str
    status: VerificationStatus
    overall_score: float
    layer_results: list[LayerResult]
    llm_judgment: LLMJudgment | None = None
    recommendations: list[str] = field(default_factory=list)


class HallucinationGuard:
    """Three-layer defense against skill hallucination.

    Layer 1: Ontology whitelist — check if skill exists in the known ontology.
    Layer 2: Multi-source verification — check source count and time span.
    Layer 3: Confidence grading — aggregate confidence from all evidence.
    Extra: LLM-as-judge — optional LLM verification for ambiguous cases.
    """

    # Thresholds (from design.md §4.3)
    SEMANTIC_MATCH_THRESHOLD = 0.85
    MIN_SOURCES = 3
    MIN_SPAN_WEEKS = 4
    VERIFIED_THRESHOLD = 0.8
    PENDING_THRESHOLD = 0.5

    def check(
        self,
        skill_name: str,
        ontology_matches: list[str] | None = None,
        semantic_score: float = 0.0,
        source_count: int = 0,
        first_detected: Any = None,
        last_detected: Any = None,
        llm_judgment: LLMJudgment | None = None,
    ) -> GuardResult:
        """Run all three defense layers on a skill.

        Args:
            skill_name: Name of the skill to verify.
            ontology_matches: List of exact matches from ontology.
            semantic_score: Best semantic similarity score (0.0-1.0).
            source_count: Number of independent sources.
            first_detected: When the skill was first detected.
            last_detected: When the skill was last detected.
            llm_judgment: Optional LLM-as-judge verdict.

        Returns:
            GuardResult with verification status.
        """
        layers: list[LayerResult] = []

        # Layer 1: Ontology whitelist
        layer1 = self._check_ontology(skill_name, ontology_matches, semantic_score)
        layers.append(layer1)

        # Layer 2: Multi-source verification
        layer2 = self._check_sources(source_count, first_detected, last_detected)
        layers.append(layer2)

        # Layer 3: Confidence grading
        layer3 = self._check_confidence(layer1.score, layer2.score, llm_judgment)
        layers.append(layer3)

        # Compute overall score (weighted average)
        overall = 0.4 * layer1.score + 0.35 * layer2.score + 0.25 * layer3.score
        overall = max(0.0, min(1.0, overall))

        # Determine status
        if overall >= self.VERIFIED_THRESHOLD:
            status = VerificationStatus.VERIFIED
        elif overall >= self.PENDING_THRESHOLD:
            status = VerificationStatus.PENDING
        else:
            status = VerificationStatus.HIGH_RISK

        # Override: if LLM says UNSUPPORTED, force HIGH_RISK
        if llm_judgment == LLMJudgment.UNSUPPORTED:
            status = VerificationStatus.HIGH_RISK
            overall = min(overall, 0.4)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            status, layer1, layer2, layer3, llm_judgment,
        )

        logger.debug(
            "HallucinationGuard '{}': status={} score={:.3f} layers=[{:.2f}, {:.2f}, {:.2f}]",
            skill_name, status.value, overall,
            layer1.score, layer2.score, layer3.score,
        )

        return GuardResult(
            skill_name=skill_name,
            status=status,
            overall_score=overall,
            layer_results=layers,
            llm_judgment=llm_judgment,
            recommendations=recommendations,
        )

    def _check_ontology(
        self,
        skill_name: str,
        ontology_matches: list[str] | None,
        semantic_score: float,
    ) -> LayerResult:
        """Layer 1: Check if skill exists in the ontology."""
        matches = ontology_matches or []

        if skill_name in matches:
            return LayerResult(
                layer=1, passed=True, score=1.0,
                details="Exact match in ontology",
            )

        if semantic_score >= self.SEMANTIC_MATCH_THRESHOLD:
            return LayerResult(
                layer=1, passed=True, score=semantic_score,
                details=f"Semantic match (score={semantic_score:.3f})",
            )

        if matches:
            return LayerResult(
                layer=1, passed=False, score=0.3,
                details=f"Partial matches found: {matches[:3]}",
                metadata={"partial_matches": matches},
            )

        return LayerResult(
            layer=1, passed=False, score=0.0,
            details="No ontology match found",
        )

    def _check_sources(
        self,
        source_count: int,
        first_detected: Any,
        last_detected: Any,
    ) -> LayerResult:
        """Layer 2: Multi-source verification."""
        if source_count < self.MIN_SOURCES:
            return LayerResult(
                layer=2, passed=False,
                score=min(1.0, source_count / self.MIN_SOURCES),
                details=f"Insufficient sources ({source_count} < {self.MIN_SOURCES})",
            )

        # Check time span
        span_weeks = self._compute_span_weeks(first_detected, last_detected)
        if span_weeks < self.MIN_SPAN_WEEKS:
            return LayerResult(
                layer=2, passed=False,
                score=0.5 + 0.5 * (span_weeks / self.MIN_SPAN_WEEKS),
                details=f"Time span too short ({span_weeks:.1f} weeks < {self.MIN_SPAN_WEEKS})",
            )

        return LayerResult(
            layer=2, passed=True, score=1.0,
            details=f"Verified: {source_count} sources over {span_weeks:.1f} weeks",
        )

    def _check_confidence(
        self,
        layer1_score: float,
        layer2_score: float,
        llm_judgment: LLMJudgment | None,
    ) -> LayerResult:
        """Layer 3: Confidence grading."""
        base_score = 0.6 * layer1_score + 0.4 * layer2_score

        if llm_judgment == LLMJudgment.SUPPORTED:
            score = min(1.0, base_score + 0.2)
            return LayerResult(
                layer=3, passed=True, score=score,
                details="LLM confirms: SUPPORTED",
            )
        if llm_judgment == LLMJudgment.UNSUPPORTED:
            score = max(0.0, base_score - 0.3)
            return LayerResult(
                layer=3, passed=False, score=score,
                details="LLM rejects: UNSUPPORTED",
            )
        if llm_judgment == LLMJudgment.AMBIGUOUS:
            return LayerResult(
                layer=3, passed=False, score=base_score,
                details="LLM verdict: AMBIGUOUS",
            )

        return LayerResult(
            layer=3, passed=base_score >= self.PENDING_THRESHOLD,
            score=base_score,
            details="No LLM judgment available",
        )

    def _generate_recommendations(
        self,
        status: VerificationStatus,
        layer1: LayerResult,
        layer2: LayerResult,
        layer3: LayerResult,
        llm_judgment: LLMJudgment | None,
    ) -> list[str]:
        """Generate actionable recommendations based on results."""
        recs: list[str] = []

        if not layer1.passed:
            recs.append("Add skill to ontology or verify spelling")

        if not layer2.passed:
            if "sources" in layer2.details:
                recs.append("Collect more JD sources mentioning this skill")
            if "span" in layer2.details:
                recs.append("Wait for more time-series data to accumulate")

        if llm_judgment == LLMJudgment.AMBIGUOUS:
            recs.append("Request manual review for ambiguous skill")

        if status == VerificationStatus.HIGH_RISK:
            recs.append("Flag for manual review before including in reports")

        return recs

    @staticmethod
    def _compute_span_weeks(first: Any, last: Any) -> float:
        """Compute time span in weeks between two datetimes."""
        if first is None or last is None:
            return 0.0
        try:
            if hasattr(first, "timestamp") and hasattr(last, "timestamp"):
                delta = (last - first).total_seconds()
                return delta / (7 * 24 * 3600)
        except (TypeError, AttributeError):
            pass
        return 0.0
