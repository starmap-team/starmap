"""PathRecommender — discover EVOLVES_TO candidates via Jaccard similarity.

Reads PG (PositionRecord + PositionSkillRelation) as the source of truth,
computes pairwise Jaccard similarity between every position's skill set,
and upserts the top-K strongest pairs into ``evolution_paths``.

This complements the Neo4j EVOLVES_TO edges that come from LLM extraction
(``graph_writer.py``). The PG-side paths are useful when:
- Neo4j is unavailable or being rebuilt
- We need ordered similarity scores for ranking
- Auditing cross-source agreement (LLM-inferred vs statistics-inferred)

Complexity guard: full O(N²) over positions, but N is bounded by
``MAX_POSITIONS`` to prevent runaway when the position table grows.
Top-K (default 50) is enforced before UPSERT so the table stays small.
"""
from __future__ import annotations

from dataclasses import dataclass

import sqlalchemy as sa
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evolution_models import EvolutionPath
from app.models.extraction_models import PositionRecord, PositionSkillRelation, SkillRecord

# Tuning constants — exposed here so tests / admin can override when needed.
DEFAULT_MIN_SIMILARITY = 0.3
DEFAULT_MIN_EVIDENCE = 1  # at least 1 shared skill qualifies a pair
DEFAULT_TOP_K = 50
MAX_POSITIONS = 500  # safety cap to prevent O(N²) explosion


@dataclass(frozen=True)
class PositionPair:
    """Candidate evolution edge before persistence."""

    source_position: str
    target_position: str
    similarity: float
    skill_overlap: list[str]
    key_gaps: list[str]
    evidence_count: int


class PathRecommender:
    """Compute and persist position→position similarity edges."""

    def __init__(
        self,
        min_similarity: float = DEFAULT_MIN_SIMILARITY,
        min_evidence: int = DEFAULT_MIN_EVIDENCE,
        top_k: int = DEFAULT_TOP_K,
    ) -> None:
        self.min_similarity = min_similarity
        self.min_evidence = min_evidence
        self.top_k = top_k

    async def recommend(self, session: AsyncSession) -> list[EvolutionPath]:
        """Load positions, compute pairwise Jaccard, upsert top-K to PG.

        Returns the list of EvolutionPath rows that were written (post-upsert).
        Symmetric pairs (A→B and B→A) are both inserted so the API can answer
        bi-directional "what can this position evolve into / come from?".
        """
        position_skills = await self._load_position_skills(session)
        if len(position_skills) < 2:
            logger.info(
                "PathRecommender: <2 positions with skills, nothing to recommend",
            )
            return []

        if len(position_skills) > MAX_POSITIONS:
            logger.warning(
                "PathRecommender: {} positions exceed MAX_POSITIONS={}, "
                "truncating to top-{} by skill_count",
                len(position_skills), MAX_POSITIONS, MAX_POSITIONS,
            )
            # Keep the positions with most skills — they have richest overlap signal.
            position_skills = dict(
                sorted(
                    position_skills.items(),
                    key=lambda kv: (-len(kv[1]), kv[0]),
                )[:MAX_POSITIONS],
            )

        pairs = self._compute_pairs(position_skills)
        if not pairs:
            logger.info(
                "PathRecommender: no pairs passed similarity>={} evidence>={}",
                self.min_similarity, self.min_evidence,
            )
            return []

        # Top-K by similarity, then by overlap size as tiebreaker.
        pairs.sort(
            key=lambda p: (-p.similarity, -len(p.skill_overlap), p.source_position),
        )
        top_pairs = pairs[: self.top_k]

        rows = await self._upsert_pairs(session, top_pairs)
        logger.info(
            "PathRecommender: wrote {} evolution_path rows (top-{} of {} candidates)",
            len(rows), self.top_k, len(pairs),
        )
        return rows

    # ── internals ──

    @staticmethod
    async def _load_position_skills(
        session: AsyncSession,
    ) -> dict[str, set[str]]:
        """Return ``{position_name: {skill_name, ...}}``.

        Only positions that have ≥1 linked skill are returned — positions with
        zero skills are filtered out because they cannot have non-zero overlap.
        """
        stmt = (
            sa.select(PositionRecord.name, SkillRecord.name)
            .select_from(PositionRecord)
            .join(
                PositionSkillRelation,
                PositionSkillRelation.position_id == PositionRecord.id,
            )
            .join(SkillRecord, SkillRecord.id == PositionSkillRelation.skill_id)
        )
        result = await session.execute(stmt)
        position_skills: dict[str, set[str]] = {}
        for pos_name, skill_name in result.all():
            if not pos_name or not skill_name:
                continue
            position_skills.setdefault(pos_name, set()).add(str(skill_name))
        return position_skills

    def _compute_pairs(
        self,
        position_skills: dict[str, set[str]],
    ) -> list[PositionPair]:
        """O(N²) pairwise Jaccard, filtered by min_similarity and min_evidence."""
        names = list(position_skills.keys())
        pairs: list[PositionPair] = []

        for i, src in enumerate(names):
            src_skills = position_skills[src]
            for j in range(i + 1, len(names)):
                tgt = names[j]
                tgt_skills = position_skills[tgt]

                overlap = src_skills & tgt_skills
                union = src_skills | tgt_skills
                if not union:
                    continue
                similarity = len(overlap) / len(union)
                if similarity < self.min_similarity:
                    continue
                if len(overlap) < self.min_evidence:
                    continue

                # Symmetric insertion: src→tgt and tgt→src
                gaps_src_to_tgt = sorted(tgt_skills - src_skills)
                gaps_tgt_to_src = sorted(src_skills - tgt_skills)

                pairs.append(PositionPair(
                    source_position=src,
                    target_position=tgt,
                    similarity=round(similarity, 4),
                    skill_overlap=sorted(overlap),
                    key_gaps=gaps_src_to_tgt,
                    evidence_count=len(overlap),
                ))
                pairs.append(PositionPair(
                    source_position=tgt,
                    target_position=src,
                    similarity=round(similarity, 4),
                    skill_overlap=sorted(overlap),
                    key_gaps=gaps_tgt_to_src,
                    evidence_count=len(overlap),
                ))

        return pairs

    @staticmethod
    async def _upsert_pairs(
        session: AsyncSession,
        pairs: list[PositionPair],
    ) -> list[EvolutionPath]:
        """Replace existing evolution_paths with the freshly computed top pairs.

        Strategy: DELETE all existing rows, then INSERT the new batch. This is
        simpler than per-row UPSERT and the table is bounded by top-K (≤100 rows
        because we store both directions of top-K=50).
        """
        if not pairs:
            return []

        await session.execute(sa.delete(EvolutionPath))

        rows: list[EvolutionPath] = []
        for p in pairs:
            # Trust score for paths: similarity is itself the trust signal,
            # but cap below 1.0 to leave room for human approval weighting.
            trust = min(0.95, max(0.1, p.similarity))
            row = EvolutionPath(
                source_position=p.source_position,
                target_position=p.target_position,
                similarity=p.similarity,
                evidence_count=p.evidence_count,
                skill_overlap=p.skill_overlap,
                key_gaps=p.key_gaps,
                trust_score=round(trust, 4),
            )
            session.add(row)
            rows.append(row)

        await session.flush()
        return rows
