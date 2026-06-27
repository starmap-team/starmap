"""Diff Engine — Compute skill changes between two position snapshots.

Implements set-difference logic for required/preferred skills across time
snapshots, detecting: new/deleted/retained/promoted/demoted skills.

Design reference: docs/evolution/design.md §4.1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from loguru import logger

from app.core.evolution.snapshot_manager import SnapshotData


class ChangeType(StrEnum):
    """Types of skill changes between snapshots."""

    ADDED_REQUIRED = "added_required"
    ADDED_PREFERRED = "added_preferred"
    REMOVED = "removed"
    PROMOTED = "promoted"  # preferred → required
    DEMOTED = "demoted"  # required → preferred
    RETAINED = "retained"


@dataclass
class SkillChange:
    """A single skill change detected between two snapshots."""

    skill_name: str
    change_type: ChangeType
    old_proficiency: str | None = None
    new_proficiency: str | None = None
    old_requirement: str | None = None  # "required" | "preferred" | None
    new_requirement: str | None = None  # "required" | "preferred" | None
    trust_score: float = 0.5
    confidence: float = 0.5
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class DiffResult:
    """Complete diff result between two snapshots."""

    position_name: str
    snapshot_from_id: str | None
    snapshot_to_id: str | None
    date_from: datetime | None
    date_to: datetime
    changes: list[SkillChange]
    summary: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.summary:
            self.summary = self._compute_summary()

    def _compute_summary(self) -> dict[str, int]:
        counts: dict[str, int] = {ct.value: 0 for ct in ChangeType}
        for change in self.changes:
            counts[change.change_type.value] += 1
        return counts

    @property
    def added_count(self) -> int:
        return self.summary.get(ChangeType.ADDED_REQUIRED.value, 0) + \
               self.summary.get(ChangeType.ADDED_PREFERRED.value, 0)

    @property
    def removed_count(self) -> int:
        return self.summary.get(ChangeType.REMOVED.value, 0)

    @property
    def promoted_count(self) -> int:
        return self.summary.get(ChangeType.PROMOTED.value, 0)

    @property
    def demoted_count(self) -> int:
        return self.summary.get(ChangeType.DEMOTED.value, 0)

    @property
    def retained_count(self) -> int:
        return self.summary.get(ChangeType.RETAINED.value, 0)

    @property
    def total_changes(self) -> int:
        return self.added_count + self.removed_count + self.promoted_count + self.demoted_count


class DiffEngine:
    """Compute skill set differences between two position snapshots.

    Algorithm (from design.md §4.1):
        new_required     = R2 - R1
        deleted_required = R1 - R2
        retained_required = R1 ∩ R2
        promoted         = new_required ∩ B1  (was preferred, now required)
        demoted          = new_preferred ∩ R1  (was required, now preferred)
    """

    def diff(
        self,
        older: SnapshotData | None,
        newer: SnapshotData,
    ) -> DiffResult:
        """Compute the diff between two snapshots.

        Args:
            older: The earlier snapshot (None if this is the first snapshot).
            newer: The later snapshot.

        Returns:
            DiffResult with all detected changes.
        """
        if older is None:
            return self._first_snapshot_diff(newer)

        # Build lookup dicts: name → SkillProfile
        old_req = {s.name: s for s in older.required_skills}
        old_pref = {s.name: s for s in older.preferred_skills}
        new_req = {s.name: s for s in newer.required_skills}
        new_pref = {s.name: s for s in newer.preferred_skills}

        old_all = set(old_req) | set(old_pref)
        new_all = set(new_req) | set(new_pref)

        changes: list[SkillChange] = []

        # --- Required skills analysis ---
        for name in new_req:
            new_skill = new_req[name]
            if name in old_req:
                # Retained as required
                old_skill = old_req[name]
                changes.append(SkillChange(
                    skill_name=name,
                    change_type=ChangeType.RETAINED,
                    old_proficiency=old_skill.proficiency,
                    new_proficiency=new_skill.proficiency,
                    old_requirement="required",
                    new_requirement="required",
                    confidence=0.95,
                ))
            elif name in old_pref:
                # Promoted: preferred → required
                old_skill = old_pref[name]
                changes.append(SkillChange(
                    skill_name=name,
                    change_type=ChangeType.PROMOTED,
                    old_proficiency=old_skill.proficiency,
                    new_proficiency=new_skill.proficiency,
                    old_requirement="preferred",
                    new_requirement="required",
                    confidence=0.90,
                ))
            else:
                # New required skill
                changes.append(SkillChange(
                    skill_name=name,
                    change_type=ChangeType.ADDED_REQUIRED,
                    new_proficiency=new_skill.proficiency,
                    new_requirement="required",
                    confidence=0.85,
                ))

        # --- Preferred skills analysis ---
        for name in new_pref:
            new_skill = new_pref[name]
            if name in old_pref:
                # Retained as preferred
                old_skill = old_pref[name]
                changes.append(SkillChange(
                    skill_name=name,
                    change_type=ChangeType.RETAINED,
                    old_proficiency=old_skill.proficiency,
                    new_proficiency=new_skill.proficiency,
                    old_requirement="preferred",
                    new_requirement="preferred",
                    confidence=0.95,
                ))
            elif name in old_req:
                # Demoted: required → preferred
                old_skill = old_req[name]
                changes.append(SkillChange(
                    skill_name=name,
                    change_type=ChangeType.DEMOTED,
                    old_proficiency=old_skill.proficiency,
                    new_proficiency=new_skill.proficiency,
                    old_requirement="required",
                    new_requirement="preferred",
                    confidence=0.90,
                ))
            else:
                # New preferred skill
                changes.append(SkillChange(
                    skill_name=name,
                    change_type=ChangeType.ADDED_PREFERRED,
                    new_proficiency=new_skill.proficiency,
                    new_requirement="preferred",
                    confidence=0.85,
                ))

        # --- Removed skills ---
        for name in old_all - new_all:
            old_skill = old_req.get(name) or old_pref.get(name)
            changes.append(SkillChange(
                skill_name=name,
                change_type=ChangeType.REMOVED,
                old_proficiency=old_skill.proficiency if old_skill else None,
                old_requirement="required" if name in old_req else "preferred",
                confidence=0.80,
            ))

        logger.info(
            "Diff for '{}': {} added, {} removed, {} promoted, {} demoted, {} retained",
            newer.position_name,
            sum(1 for c in changes if c.change_type in (ChangeType.ADDED_REQUIRED, ChangeType.ADDED_PREFERRED)),
            sum(1 for c in changes if c.change_type == ChangeType.REMOVED),
            sum(1 for c in changes if c.change_type == ChangeType.PROMOTED),
            sum(1 for c in changes if c.change_type == ChangeType.DEMOTED),
            sum(1 for c in changes if c.change_type == ChangeType.RETAINED),
        )

        return DiffResult(
            position_name=newer.position_name,
            snapshot_from_id=older.id,
            snapshot_to_id=newer.id,
            date_from=older.snapshot_date,
            date_to=newer.snapshot_date,
            changes=changes,
        )

    def _first_snapshot_diff(self, snapshot: SnapshotData) -> DiffResult:
        """Handle the case where there's no older snapshot — all skills are 'added'."""
        changes: list[SkillChange] = []
        for skill in snapshot.required_skills:
            changes.append(SkillChange(
                skill_name=skill.name,
                change_type=ChangeType.ADDED_REQUIRED,
                new_proficiency=skill.proficiency,
                new_requirement="required",
                confidence=0.70,
                evidence={"note": "first_snapshot"},
            ))
        for skill in snapshot.preferred_skills:
            changes.append(SkillChange(
                skill_name=skill.name,
                change_type=ChangeType.ADDED_PREFERRED,
                new_proficiency=skill.proficiency,
                new_requirement="preferred",
                confidence=0.70,
                evidence={"note": "first_snapshot"},
            ))

        logger.info(
            "First snapshot for '{}': {} skills added",
            snapshot.position_name,
            len(changes),
        )

        return DiffResult(
            position_name=snapshot.position_name,
            snapshot_from_id=None,
            snapshot_to_id=snapshot.id,
            date_from=None,
            date_to=snapshot.snapshot_date,
            changes=changes,
        )

    def diff_all(
        self,
        snapshots: list[SnapshotData],
    ) -> list[DiffResult]:
        """Compute diffs for consecutive snapshot pairs.

        Args:
            snapshots: List of snapshots sorted by date ascending.

        Returns:
            List of DiffResult for each consecutive pair.
        """
        if len(snapshots) < 2:
            if snapshots:
                return [self._first_snapshot_diff(snapshots[0])]
            return []

        results: list[DiffResult] = []
        for i in range(1, len(snapshots)):
            result = self.diff(snapshots[i - 1], snapshots[i])
            results.append(result)
        return results
