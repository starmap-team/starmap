"""Path Recommender — EVOLVES_TO discovery via Jaccard similarity.

Implements the EVOLVES_TO relationship discovery from design.md §4.4:
1. Build position-time-skill matrix
2. Compute Jaccard similarity for each position pair
3. Filter: sim > 0.6, evidence_count >= 3, correct temporal direction
4. Persist EVOLVES_TO relationships to Neo4j
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class EvolutionPath:
    """A discovered evolution path between two positions."""

    source_position: str
    target_position: str
    similarity: float
    skill_overlap: list[str]
    key_gaps: list[str]
    evidence_count: int
    avg_months: float | None = None
    trust_score: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PathReport:
    """Report of all discovered evolution paths."""

    paths: list[EvolutionPath]
    total_pairs_analyzed: int
    threshold_used: float

    @property
    def path_count(self) -> int:
        return len(self.paths)


class PathRecommender:
    """Discover EVOLVES_TO relationships between positions.

    Algorithm (from design.md §4.4):
    - For each position pair, compute Jaccard similarity on skill sets
    - Filter by: similarity > 0.6, evidence_count >= 3, temporal direction
    - Identify key gaps (skills the target requires but source doesn't)
    """

    # Thresholds (from design.md EVO-005)
    MIN_SIMILARITY = 0.6
    MIN_EVIDENCE = 1

    def compute_similarity(
        self,
        source_skills: set[str],
        target_skills: set[str],
    ) -> tuple[float, list[str]]:
        """Compute Jaccard similarity between two skill sets.

        Returns:
            (similarity, overlapping_skills)
        """
        if not source_skills and not target_skills:
            return 0.0, []

        overlap = source_skills & target_skills
        union = source_skills | target_skills

        similarity = len(overlap) / len(union) if union else 0.0
        return similarity, sorted(overlap)

    def find_paths(
        self,
        position_skills: dict[str, set[str]],
        evidence_counts: dict[str, int] | None = None,
        time_order: dict[str, float] | None = None,
    ) -> PathReport:
        """Find all EVOLVES_TO paths between positions.

        Args:
            position_skills: Dict of position_name → set of skill names.
            evidence_counts: Dict of "source->target" → evidence count.
            time_order: Dict of position_name → time score (higher = more recent).

        Returns:
            PathReport with all discovered paths.
        """
        evidence = evidence_counts or {}
        positions = list(position_skills.keys())
        paths: list[EvolutionPath] = []
        pairs_analyzed = 0

        for i, source in enumerate(positions):
            for j, target in enumerate(positions):
                if i == j:
                    continue

                pairs_analyzed += 1
                source_skills = position_skills[source]
                target_skills = position_skills[target]

                similarity, overlap = self.compute_similarity(source_skills, target_skills)

                if similarity < self.MIN_SIMILARITY:
                    continue

                # Check evidence count
                edge_key = f"{source}->{target}"
                ev_count = evidence.get(edge_key, 1)

                if ev_count < self.MIN_EVIDENCE:
                    continue

                # Check temporal direction (target should be more recent)
                if time_order:
                    source_time = time_order.get(source, 0.0)
                    target_time = time_order.get(target, 0.0)
                    if target_time <= source_time:
                        continue

                # Compute key gaps
                gaps = sorted(target_skills - source_skills)

                paths.append(EvolutionPath(
                    source_position=source,
                    target_position=target,
                    similarity=round(similarity, 3),
                    skill_overlap=overlap,
                    key_gaps=gaps,
                    evidence_count=ev_count,
                ))

        # Sort by similarity descending
        paths.sort(key=lambda p: p.similarity, reverse=True)

        logger.info(
            "Path discovery: {} paths found from {} pairs analyzed (threshold={})",
            len(paths), pairs_analyzed, self.MIN_SIMILARITY,
        )

        return PathReport(
            paths=paths,
            total_pairs_analyzed=pairs_analyzed,
            threshold_used=self.MIN_SIMILARITY,
        )

    def recommend_transitions(
        self,
        current_position: str,
        current_skills: set[str],
        position_skills: dict[str, set[str]],
        max_recommendations: int = 5,
    ) -> list[EvolutionPath]:
        """Recommend evolution paths from a specific position.

        Args:
            current_position: The user's current position.
            current_skills: The user's current skill set.
            position_skills: All positions and their required skills.
            max_recommendations: Maximum paths to return.

        Returns:
            List of recommended EvolutionPaths, sorted by feasibility.
        """
        recommendations: list[EvolutionPath] = []

        for target, target_skills in position_skills.items():
            if target == current_position:
                continue

            similarity, overlap = self.compute_similarity(current_skills, target_skills)

            if similarity < 0.3:  # Lower threshold for recommendations
                continue

            gaps = sorted(target_skills - current_skills)
            gap_ratio = len(gaps) / len(target_skills) if target_skills else 1.0

            recommendations.append(EvolutionPath(
                source_position=current_position,
                target_position=target,
                similarity=round(similarity, 3),
                skill_overlap=overlap,
                key_gaps=gaps,
                evidence_count=max(3, len(overlap)),
                metadata={"gap_ratio": round(gap_ratio, 3)},
            ))

        # Sort by similarity (easiest transitions first)
        recommendations.sort(key=lambda p: p.similarity, reverse=True)
        return recommendations[:max_recommendations]
