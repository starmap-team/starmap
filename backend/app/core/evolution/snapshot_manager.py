"""Snapshot Manager — Create, store, and retrieve position skill snapshots.

Snapshots capture the full skill profile (required + preferred) of a position
at a specific point in time, enabling DiffEngine to compute changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evolution_models import EvolutionSnapshot


@dataclass
class SkillProfile:
    """A single skill in a position's profile."""

    name: str
    category: str = "hard_skill"
    proficiency: str = "熟悉"

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "category": self.category,
            "proficiency": self.proficiency,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | str) -> SkillProfile:
        if isinstance(data, str):
            return cls(name=data)
        return cls(
            name=str(data.get("name") or data.get("skill") or "").strip(),
            category=str(data.get("category") or "hard_skill"),
            proficiency=str(data.get("proficiency") or data.get("level") or "熟悉"),
        )


@dataclass
class SnapshotData:
    """Structured snapshot data returned by SnapshotManager."""

    id: str
    position_name: str
    snapshot_date: datetime
    required_skills: list[SkillProfile]
    preferred_skills: list[SkillProfile]
    source_count: int
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def all_skill_names(self) -> set[str]:
        return {s.name for s in self.required_skills} | {s.name for s in self.preferred_skills}

    @property
    def required_names(self) -> set[str]:
        return {s.name for s in self.required_skills}

    @property
    def preferred_names(self) -> set[str]:
        return {s.name for s in self.preferred_skills}


class SnapshotManager:
    """Manage evolution snapshots in PostgreSQL.

    Responsibilities:
    - Create snapshots from extraction results
    - Retrieve snapshots by position and date range
    - Get the latest snapshot for a position
    - Get two snapshots for diff comparison
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_snapshot(
        self,
        position_name: str,
        required_skills: list[dict[str, Any] | str],
        preferred_skills: list[dict[str, Any] | str],
        source_count: int = 1,
        snapshot_date: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SnapshotData:
        """Create a new snapshot for a position.

        Args:
            position_name: Name of the position.
            required_skills: List of required skill dicts or strings.
            preferred_skills: List of preferred skill dicts or strings.
            source_count: Number of JDs contributing to this snapshot.
            snapshot_date: Override snapshot timestamp (default: now).
            metadata: Extra metadata to store.

        Returns:
            The created SnapshotData.
        """
        date = snapshot_date or datetime.now(UTC)
        req_profiles = [SkillProfile.from_dict(s) for s in required_skills]
        pref_profiles = [SkillProfile.from_dict(s) for s in preferred_skills]

        record = EvolutionSnapshot(
            position_name=position_name,
            snapshot_date=date,
            required_skills=[p.to_dict() for p in req_profiles],
            preferred_skills=[p.to_dict() for p in pref_profiles],
            source_count=source_count,
            metadata_json=metadata or {},
        )
        self._session.add(record)
        await self._session.flush()

        logger.info(
            "Created snapshot for '{}' at {} with {} required + {} preferred skills",
            position_name,
            date.date(),
            len(req_profiles),
            len(pref_profiles),
        )

        return SnapshotData(
            id=str(record.id),
            position_name=position_name,
            snapshot_date=date,
            required_skills=req_profiles,
            preferred_skills=pref_profiles,
            source_count=source_count,
            metadata=metadata or {},
        )

    async def get_latest_snapshot(self, position_name: str) -> SnapshotData | None:
        """Get the most recent snapshot for a position."""
        stmt = (
            select(EvolutionSnapshot)
            .where(EvolutionSnapshot.position_name == position_name)
            .order_by(EvolutionSnapshot.snapshot_date.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return self._record_to_data(record)

    async def get_snapshot_pair(
        self, position_name: str
    ) -> tuple[SnapshotData | None, SnapshotData | None]:
        """Get the two most recent snapshots for diff comparison.

        Returns:
            (older_snapshot, newer_snapshot) or (None, None) if insufficient data.
        """
        stmt = (
            select(EvolutionSnapshot)
            .where(EvolutionSnapshot.position_name == position_name)
            .order_by(EvolutionSnapshot.snapshot_date.desc())
            .limit(2)
        )
        result = await self._session.execute(stmt)
        records = list(result.scalars().all())

        if len(records) < 2:
            if records:
                return None, self._record_to_data(records[0])
            return None, None

        return self._record_to_data(records[1]), self._record_to_data(records[0])

    async def get_snapshots_by_range(
        self,
        position_name: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[SnapshotData]:
        """Get all snapshots for a position within a date range."""
        stmt = (
            select(EvolutionSnapshot)
            .where(
                EvolutionSnapshot.position_name == position_name,
                EvolutionSnapshot.snapshot_date >= start_date,
                EvolutionSnapshot.snapshot_date <= end_date,
            )
            .order_by(EvolutionSnapshot.snapshot_date.asc())
        )
        result = await self._session.execute(stmt)
        return [self._record_to_data(r) for r in result.scalars().all()]

    async def get_all_positions(self) -> list[str]:
        """Get all position names that have snapshots."""
        stmt = (
            select(EvolutionSnapshot.position_name)
            .distinct()
            .order_by(EvolutionSnapshot.position_name)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def snapshot_from_extraction(
        self,
        extraction: dict[str, Any],
        source_count: int = 1,
        snapshot_date: datetime | None = None,
    ) -> SnapshotData:
        """Create a snapshot directly from an extraction result dict.

        Convenience method that extracts skills from the standard
        extraction format used by jd_extract pipeline.
        """
        position_name = str(
            extraction.get("position_name") or extraction.get("name") or ""
        ).strip()
        if not position_name:
            raise ValueError("Extraction result is missing position_name")

        return await self.create_snapshot(
            position_name=position_name,
            required_skills=extraction.get("required_skills", []),
            preferred_skills=extraction.get("preferred_skills", []),
            source_count=source_count,
            snapshot_date=snapshot_date,
            metadata={"source": "extraction_pipeline"},
        )

    def _record_to_data(self, record: EvolutionSnapshot) -> SnapshotData:
        """Convert an ORM record to a SnapshotData dataclass."""
        return SnapshotData(
            id=str(record.id),
            position_name=record.position_name,
            snapshot_date=record.snapshot_date,
            required_skills=[
                SkillProfile.from_dict(s) for s in (record.required_skills or [])
            ],
            preferred_skills=[
                SkillProfile.from_dict(s) for s in (record.preferred_skills or [])
            ],
            source_count=record.source_count or 0,
            metadata=record.metadata_json or {},
        )
