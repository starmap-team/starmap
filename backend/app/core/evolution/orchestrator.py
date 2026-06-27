"""Evolution Orchestrator — 8-step pipeline coordinating all evolution components.

Pipeline (from design.md §7):
1. Load snapshots (SnapshotManager)
2. Compute diff (DiffEngine)
3. Score trust (TrustScorer)
4. Check hallucination (HallucinationGuard)
5. Detect emergence (EmergenceFinder)
6. Discover paths (PathRecommender)
7. Save changelog (PostgreSQL)
8. Update graph (Neo4j EVOLVES_TO)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.evolution.diff_engine import DiffEngine, DiffResult
from app.core.evolution.emergence_finder import EmergenceFinder, EmergenceReport
from app.core.evolution.hallucination_guard import GuardResult, HallucinationGuard
from app.core.evolution.path_recommender import PathRecommender, PathReport
from app.core.evolution.snapshot_manager import SnapshotManager
from app.core.evolution.trust_integration import TrustScorer
from app.models.evolution_models import EvolutionChangelog, EvolutionPath, SkillTimeseries


@dataclass
class EvolutionResult:
    """Complete result of an evolution analysis run."""

    position_name: str
    diff_result: DiffResult | None = None
    trust_results: dict[str, float] = field(default_factory=dict)
    guard_results: dict[str, GuardResult] = field(default_factory=dict)
    emergence_report: EmergenceReport | None = None
    path_report: PathReport | None = None
    changelog_entries: int = 0
    graph_updates: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


class EvolutionOrchestrator:
    """Coordinate the full evolution analysis pipeline.

    Usage:
        orchestrator = EvolutionOrchestrator(session)
        result = await orchestrator.analyze("Backend Engineer")
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._snapshot_mgr = SnapshotManager(session)
        self._diff_engine = DiffEngine()
        self._trust_scorer = TrustScorer()
        self._halluc_guard = HallucinationGuard()
        self._emergence_finder = EmergenceFinder()
        self._path_recommender = PathRecommender()

    async def analyze(
        self,
        position_name: str,
        ontology_skills: set[str] | None = None,
    ) -> EvolutionResult:
        """Run the full 8-step evolution analysis pipeline.

        Args:
            position_name: Position to analyze.
            ontology_skills: Known skills from ontology (for hallucination check).

        Returns:
            EvolutionResult with all analysis outputs.
        """
        import time

        start = time.monotonic()
        result = EvolutionResult(position_name=position_name)
        errors: list[str] = []

        # Step 1: Load snapshots
        logger.info("Step 1: Loading snapshots for '{}'", position_name)
        older, newer = await self._snapshot_mgr.get_snapshot_pair(position_name)

        # Step 2: Compute diff (handle both-snapshots-missing gracefully)
        logger.info("Step 2: Computing diff")
        if newer is None:
            logger.info("No snapshots found for '{}', returning empty result", position_name)
            result.duration_seconds = time.monotonic() - start
            return result
        diff_result = self._diff_engine.diff(older, newer)
        result.diff_result = diff_result

        # Step 3: Score trust for changed skills
        logger.info("Step 3: Scoring trust for {} changes", len(diff_result.changes))
        trust_scores: dict[str, float] = {}
        for change in diff_result.changes:
            if change.change_type.value != "retained":
                trust = self._trust_scorer.compute_from_source_count(
                    source_count=newer.source_count if newer else 1,
                )
                trust_scores[change.skill_name] = trust.score
                change.trust_score = trust.score
        result.trust_results = trust_scores

        # Step 4: Check hallucination for new skills
        logger.info("Step 4: Checking hallucination for new skills")
        guard_results: dict[str, GuardResult] = {}
        for change in diff_result.changes:
            if change.change_type.value in ("added_required", "added_preferred"):
                guard = self._halluc_guard.check(
                    skill_name=change.skill_name,
                    ontology_matches=list(ontology_skills) if ontology_skills else None,
                    source_count=newer.source_count if newer else 1,
                )
                guard_results[change.skill_name] = guard
                if guard.status.value == "high_risk":
                    errors.append(f"High-risk skill detected: {change.skill_name}")
        result.guard_results = guard_results

        # Step 5: Detect emergence (from timeseries data)
        logger.info("Step 5: Detecting emergence signals")
        emergence_report: EmergenceReport | None = None
        emergence_data = await self._load_timeseries(position_name)
        if emergence_data:
            emergence_report = self._emergence_finder.scan(emergence_data)
            result.emergence_report = emergence_report
        else:
            result.emergence_report = None

        # Step 6: Discover evolution paths
        logger.info("Step 6: Discovering evolution paths")
        path_data = await self._load_path_data()
        if path_data:
            path_report = self._path_recommender.find_paths(path_data)
            result.path_report = path_report
        else:
            result.path_report = None

        # Step 7: Save changelog
        logger.info("Step 7: Saving changelog")
        changelog_count = await self._save_changelog(diff_result)
        result.changelog_entries = changelog_count

        # Step 8: Update graph (EVOLVES_TO)
        logger.info("Step 8: Updating graph")
        graph_count = await self._save_paths_to_db(result.path_report)
        result.graph_updates = graph_count

        result.errors = errors
        result.duration_seconds = time.monotonic() - start

        logger.info(
            "Evolution analysis complete for '{}': {} changes, {} trust scores, "
            "{} guard checks, {} emergence signals, {} paths, {:.1f}s",
            position_name,
            len(diff_result.changes),
            len(trust_scores),
            len(guard_results),
            len(emergence_report.emerging) if emergence_report else 0,
            graph_count,
            result.duration_seconds,
        )

        return result

    async def _load_timeseries(
        self, position_name: str,
    ) -> dict[str, dict[str, Any]] | None:
        """Load skill timeseries data for emergence detection."""
        from sqlalchemy import select

        stmt = (
            select(SkillTimeseries)
            .where(SkillTimeseries.positions.contains([position_name]))
            .order_by(SkillTimeseries.window_start.asc())
        )
        db_result = await self._session.execute(stmt)
        records = list(db_result.scalars().all())

        if not records:
            return None

        # Group by skill name
        skill_data: dict[str, dict[str, Any]] = {}
        for record in records:
            name = record.skill_name
            if name not in skill_data:
                skill_data[name] = {
                    "frequencies": [],
                    "current": 0,
                    "sources": record.source_count,
                    "positions": record.positions or [],
                }
            skill_data[name]["frequencies"].append(record.frequency)

        # Set current = last frequency
        for _name, data in skill_data.items():
            freqs = data["frequencies"]
            if freqs:
                data["current"] = freqs[-1]
                data["frequencies"] = freqs[:-1]

        return skill_data

    async def _load_path_data(self) -> dict[str, set[str]] | None:
        """Load position-skill mappings for path discovery."""
        from sqlalchemy import func, select

        from app.models.extraction_models import (
            PositionRecord,
            PositionSkillRelation,
            SkillRecord,
        )

        stmt = (
            select(
                PositionRecord.name,
                func.array_agg(SkillRecord.name),
            )
            .join(PositionSkillRelation, PositionSkillRelation.position_id == PositionRecord.id)
            .join(SkillRecord, SkillRecord.id == PositionSkillRelation.skill_id)
            .group_by(PositionRecord.name)
        )
        db_result = await self._session.execute(stmt)
        rows = db_result.all()

        if not rows:
            return None

        return {row[0]: set(row[1]) for row in rows}

    async def _save_changelog(self, diff_result: DiffResult) -> int:
        """Save diff changes to the evolution_changelog table."""
        count = 0
        for change in diff_result.changes:
            if change.change_type.value == "retained":
                continue

            record = EvolutionChangelog(
                position_name=diff_result.position_name,
                skill_name=change.skill_name,
                change_type=change.change_type.value,
                old_proficiency=change.old_proficiency,
                new_proficiency=change.new_proficiency,
                old_requirement=change.old_requirement,
                new_requirement=change.new_requirement,
                snapshot_from_id=diff_result.snapshot_from_id,
                snapshot_to_id=diff_result.snapshot_to_id,
                trust_score=change.trust_score,
                confidence=change.confidence,
                evidence_json=change.evidence,
            )
            self._session.add(record)
            count += 1

        if count > 0:
            await self._session.flush()

        return count

    async def _save_paths_to_db(self, path_report: PathReport | None) -> int:
        """Save discovered evolution paths to PostgreSQL."""
        if not path_report:
            return 0

        count = 0
        for path in path_report.paths:
            record = EvolutionPath(
                source_position=path.source_position,
                target_position=path.target_position,
                similarity=path.similarity,
                evidence_count=path.evidence_count,
                skill_overlap=path.skill_overlap,
                key_gaps=path.key_gaps,
                trust_score=path.trust_score,
            )
            self._session.add(record)
            count += 1

        if count > 0:
            await self._session.flush()

        return count
