"""DiffEngine — compute skill changes between two EvolutionSnapshots.

Output is a list of ``EvolutionChange`` records that the orchestrator will
persist into ``EvolutionChangelog``. Six change types, matching the column
comment on ``evolution_changelog.change_type``:

    added_required    — skill absent in old, appears in new.required_skills
    added_preferred   — skill absent in old, appears in new.preferred_skills only
    removed           — skill present in old (any bucket), absent in new
    promoted          — skill in old.preferred, in new.required (priority went up)
    demoted           — skill in old.required, in new.preferred (priority went down)
    retained          — skill in both, bucket unchanged
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.models.evolution_models import EvolutionSnapshot


class ChangeType(StrEnum):
    ADDED_REQUIRED = "added_required"
    ADDED_PREFERRED = "added_preferred"
    REMOVED = "removed"
    PROMOTED = "promoted"
    DEMOTED = "demoted"
    RETAINED = "retained"


@dataclass(frozen=True)
class EvolutionChange:
    """Single detected change between two snapshots.

    Fields map 1:1 onto EvolutionChangelog columns so the orchestrator can
    persist without reshaping.
    """

    skill_name: str
    change_type: ChangeType
    old_proficiency: str | None
    new_proficiency: str | None
    old_requirement: str | None  # "required" | "preferred" | None
    new_requirement: str | None
    mention_count_old: int = 0
    mention_count_new: int = 0


def _skill_name_set(skills: list[dict[str, Any]] | None) -> set[str]:
    if not skills:
        return set()
    return {str(s.get("name", "")).strip() for s in skills if s.get("name")}


def _skill_to_meta(skills: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    """Index skills by name → ``{"proficiency": str, "mention_count": int}``."""
    if not skills:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for s in skills:
        name = str(s.get("name", "")).strip()
        if not name:
            continue
        out[name] = {
            "proficiency": str(s.get("proficiency") or s.get("level") or ""),
            "mention_count": int(s.get("mention_count") or 0),
        }
    return out


class DiffEngine:
    """Compute 6-class diff between two EvolutionSnapshots."""

    def diff(
        self,
        old: EvolutionSnapshot | None,
        new: EvolutionSnapshot,
    ) -> list[EvolutionChange]:
        """Return the list of EvolutionChange entries.

        ``old=None`` is the cold-start case (first snapshot for a position):
        every skill in ``new`` is reported as ``added_required`` or
        ``added_preferred`` with ``old_*=None``.

        E21 fix: when the new snapshot has empty required_skills AND empty
        preferred_skills (e.g. spider failed and returned an empty payload,
        or caller passed a half-built snapshot), the previous behavior
        marked EVERY old skill as ``removed`` — flooding the review queue
        with false positives. The 143 pending "removed" entries from
        2026-08-09 18:58-19:08 (all on a single position) were caused
        exactly by this. Now: if new is empty, return [].
        """
        new_req = _skill_to_meta(new.required_skills)
        new_pref = _skill_to_meta(new.preferred_skills)

 # E21: skip if new snapshot is empty (would otherwise mark all
 # old skills as removed). This filters out spider failures that
 # produce empty snapshots.
        if not new_req and not new_pref:
            return []

        if old is None:
            return self._cold_start_changes(new_req, new_pref)

        old_req = _skill_to_meta(old.required_skills)
        old_pref = _skill_to_meta(old.preferred_skills)

        changes: list[EvolutionChange] = []
        all_names = (old_req | old_pref | new_req | new_pref).keys()

        for name in all_names:
            change = self._classify_single(
                name,
                old_req.get(name), old_pref.get(name),
                new_req.get(name), new_pref.get(name),
            )
            if change is not None:
                changes.append(change)

        return changes

 # ── internal ──

    @staticmethod
    def _cold_start_changes(
        new_req: dict[str, dict[str, Any]],
        new_pref: dict[str, dict[str, Any]],
    ) -> list[EvolutionChange]:
        out: list[EvolutionChange] = []
        for name, meta in new_req.items():
            out.append(EvolutionChange(
                skill_name=name,
                change_type=ChangeType.ADDED_REQUIRED,
                old_proficiency=None,
                new_proficiency=meta["proficiency"] or None,
                old_requirement=None,
                new_requirement="required",
                mention_count_new=meta["mention_count"],
            ))
        for name, meta in new_pref.items():
 # Skip if already added as required (de-dup)
            if name in new_req:
                continue
            out.append(EvolutionChange(
                skill_name=name,
                change_type=ChangeType.ADDED_PREFERRED,
                old_proficiency=None,
                new_proficiency=meta["proficiency"] or None,
                old_requirement=None,
                new_requirement="preferred",
                mention_count_new=meta["mention_count"],
            ))
        return out

    @staticmethod
    def _classify_single(
        name: str,
        old_req_meta: dict[str, Any] | None,
        old_pref_meta: dict[str, Any] | None,
        new_req_meta: dict[str, Any] | None,
        new_pref_meta: dict[str, Any] | None,
    ) -> EvolutionChange | None:
        in_old_req = old_req_meta is not None
        in_old_pref = old_pref_meta is not None
        in_new_req = new_req_meta is not None
        in_new_pref = new_pref_meta is not None

        old_present = in_old_req or in_old_pref
        new_present = in_new_req or in_new_pref

        if not old_present and not new_present:
            return None  # shouldn't happen, defensive

 # Removed
        if old_present and not new_present:
            old_meta = old_req_meta or old_pref_meta
            return EvolutionChange(
                skill_name=name,
                change_type=ChangeType.REMOVED,
                old_proficiency=(old_meta or {}).get("proficiency") or None,
                new_proficiency=None,
                old_requirement="required" if in_old_req else "preferred",
                new_requirement=None,
                mention_count_old=(old_meta or {}).get("mention_count", 0),
            )

 # Added (cold-start for this single skill)
        if not old_present and new_present:
            if in_new_req:
                meta = new_req_meta
                ct = ChangeType.ADDED_REQUIRED
                new_req_label = "required"
            else:
                meta = new_pref_meta
                ct = ChangeType.ADDED_PREFERRED
                new_req_label = "preferred"
            return EvolutionChange(
                skill_name=name,
                change_type=ct,
                old_proficiency=None,
                new_proficiency=(meta or {}).get("proficiency") or None,
                old_requirement=None,
                new_requirement=new_req_label,
                mention_count_new=(meta or {}).get("mention_count", 0),
            )

 # Both present — detect promotion / demotion / retention
        old_in_required = in_old_req
        new_in_required = in_new_req

        if old_in_required and not new_in_required:
 # required → preferred
            return EvolutionChange(
                skill_name=name,
                change_type=ChangeType.DEMOTED,
                old_proficiency=(old_req_meta or {}).get("proficiency") or None,
                new_proficiency=(new_pref_meta or {}).get("proficiency") or None,
                old_requirement="required",
                new_requirement="preferred",
                mention_count_old=(old_req_meta or {}).get("mention_count", 0),
                mention_count_new=(new_pref_meta or {}).get("mention_count", 0),
            )

        if not old_in_required and new_in_required:
 # preferred → required
            return EvolutionChange(
                skill_name=name,
                change_type=ChangeType.PROMOTED,
                old_proficiency=(old_pref_meta or {}).get("proficiency") or None,
                new_proficiency=(new_req_meta or {}).get("proficiency") or None,
                old_requirement="preferred",
                new_requirement="required",
                mention_count_old=(old_pref_meta or {}).get("mention_count", 0),
                mention_count_new=(new_req_meta or {}).get("mention_count", 0),
            )

 # Same bucket both sides → retained
        meta_old = old_req_meta or old_pref_meta
        meta_new = new_req_meta or new_pref_meta
        return EvolutionChange(
            skill_name=name,
            change_type=ChangeType.RETAINED,
            old_proficiency=(meta_old or {}).get("proficiency") or None,
            new_proficiency=(meta_new or {}).get("proficiency") or None,
            old_requirement="required" if in_old_req else "preferred",
            new_requirement="required" if in_new_req else "preferred",
            mention_count_old=(meta_old or {}).get("mention_count", 0),
            mention_count_new=(meta_new or {}).get("mention_count", 0),
        )
