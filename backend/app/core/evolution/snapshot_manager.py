"""SnapshotManager — 聚合 JDExtractionRecord 生成 EvolutionSnapshot。

职责边界（与 timeseries_service 的差异）：
- timeseries_service: 技能维度按月聚合频率（SkillTimeseries）
- snapshot_manager:  岗位维度按月聚合完整技能画像（EvolutionSnapshot）

幂等性：同 (position_name, month) 调用 N 次只保留最新一条 — 通过
DELETE + INSERT 实现，避免依赖不存在的 UNIQUE 约束。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evolution_models import EvolutionSnapshot
from app.models.extraction_models import JDExtractionRecord

# Stage 3.1 governance: a skill must be mentioned in at least N independent
# JD extractions within the snapshot window to be considered a real signal.
# Single-mention skills are likely LLM noise or one-off JD quirks.
MIN_MENTIONS_PER_SKILL = 2


class SnapshotManager:
    """Create / retrieve / list EvolutionSnapshot rows.

    Usage:
        mgr = SnapshotManager()
        snap = await mgr.create_snapshot(session, "Python Backend Engineer", datetime(...))
    """

    async def create_snapshot(
        self,
        session: AsyncSession,
        position_name: str,
        snapshot_date: datetime,
    ) -> EvolutionSnapshot | None:
        """Aggregate JDs for `position_name` in the calendar month of `snapshot_date`.

        Returns ``None`` when there are no completed extraction records in the
        window — the caller may decide to skip or treat as "no data".
        """
        window_start, window_end = self._month_window(snapshot_date)

        records = await self._load_records(
            session,
            position_name,
            window_start,
            window_end,
        )
        if not records:
            logger.info(
                "SnapshotManager: no records for position='{}' in [{}, {})",
                position_name,
                window_start.date(),
                window_end.date(),
            )
            return None

        required_counts: dict[str, int] = defaultdict(int)
        preferred_counts: dict[str, int] = defaultdict(int)
        category_index: dict[str, str] = {}

        for rec in records:
            payload = rec.to_extraction_payload()
            for skill in self._normalize_skill_entries(payload.get("required_skills", [])):
                required_counts[skill["name"]] += 1
                category_index.setdefault(skill["name"], skill["category"])
            for skill in self._normalize_skill_entries(payload.get("preferred_skills", [])):
                preferred_counts[skill["name"]] += 1
                category_index.setdefault(skill["name"], skill["category"])

        required_skills = self._top_skills(required_counts, category_index, MIN_MENTIONS_PER_SKILL)
        preferred_skills = self._top_skills(preferred_counts, category_index, MIN_MENTIONS_PER_SKILL)

        if not required_skills and not preferred_skills:
            logger.info(
                "SnapshotManager: records exist but none passed MIN_MENTIONS={} filter for position='{}'",
                MIN_MENTIONS_PER_SKILL,
                position_name,
            )
            return None

        # Idempotency: same (position, month) → replace existing snapshot.
        await session.execute(
            sa.delete(EvolutionSnapshot).where(
                EvolutionSnapshot.position_name == position_name,
                EvolutionSnapshot.snapshot_date >= window_start,
                EvolutionSnapshot.snapshot_date < window_end,
            )
        )

        snapshot = EvolutionSnapshot(
            position_name=position_name,
            snapshot_date=window_start,  # canonical: month start as snapshot_date
            required_skills=required_skills,
            preferred_skills=preferred_skills,
            source_count=len(records),
            metadata_json={
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "min_mentions_filter": MIN_MENTIONS_PER_SKILL,
                "distinct_required": len(required_counts),
                "distinct_preferred": len(preferred_counts),
            },
        )
        session.add(snapshot)
        await session.flush()
        logger.info(
            "SnapshotManager: created snapshot position='{}' date={} required={} preferred={} source_count={}",
            position_name,
            window_start.date(),
            len(required_skills),
            len(preferred_skills),
            len(records),
        )
        return snapshot

    async def list_snapshots(
        self,
        session: AsyncSession,
        position_name: str | None = None,
        limit: int = 50,
    ) -> list[EvolutionSnapshot]:
        stmt = sa.select(EvolutionSnapshot).order_by(
            EvolutionSnapshot.snapshot_date.desc(),
        )
        if position_name:
            stmt = stmt.where(EvolutionSnapshot.position_name == position_name)
        stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    # ── helpers ──

    @staticmethod
    def _month_window(snapshot_date: datetime) -> tuple[datetime, datetime]:
        """Return (first_day_of_month 00:00 UTC, first_day_of_next_month 00:00 UTC)."""
        if snapshot_date.tzinfo is None:
            snapshot_date = snapshot_date.replace(tzinfo=UTC)
        start = datetime(snapshot_date.year, snapshot_date.month, 1, tzinfo=UTC)
        if snapshot_date.month == 12:
            end = datetime(snapshot_date.year + 1, 1, 1, tzinfo=UTC)
        else:
            end = datetime(snapshot_date.year, snapshot_date.month + 1, 1, tzinfo=UTC)
        return start, end

    @staticmethod
    async def _load_records(
        session: AsyncSession,
        position_name: str,
        window_start: datetime,
        window_end: datetime,
    ) -> list[JDExtractionRecord]:
        stmt = (
            sa.select(JDExtractionRecord)
            .where(JDExtractionRecord.job_title == position_name)
            .where(JDExtractionRecord.status == "completed")
            .where(JDExtractionRecord.created_at >= window_start)
            .where(JDExtractionRecord.created_at < window_end)
            .order_by(JDExtractionRecord.created_at.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _normalize_skill_entries(
        entries: list[Any] | None,
    ) -> list[dict[str, str]]:
        """Coerce raw skill entries to ``{"name", "category"}`` dicts.

        Handles the two JSON shapes found in production data:
        - ``[{"name": "Python", "category": "hard_skill"}, ...]``
        - ``["Python", "Go"]``  (bare strings, rare)
        """
        out: list[dict[str, str]] = []
        if not entries:
            return out
        for entry in entries:
            if isinstance(entry, dict):
                name = str(entry.get("name") or "").strip()
                if not name:
                    continue
                category = str(entry.get("category") or "general").strip()
                out.append({"name": name, "category": category})
            elif isinstance(entry, str):
                name = entry.strip()
                if name:
                    out.append({"name": name, "category": "general"})
        return out

    @staticmethod
    def _top_skills(
        counts: dict[str, int],
        category_index: dict[str, str],
        min_mentions: int,
    ) -> list[dict[str, Any]]:
        """Return skills sorted by mention count desc, filtered by min_mentions."""
        ranked = sorted(
            ((name, count) for name, count in counts.items() if count >= min_mentions),
            key=lambda x: (-x[1], x[0]),
        )
        return [
            {
                "name": name,
                "category": category_index.get(name, "general"),
                "mention_count": count,
            }
            for name, count in ranked
        ]


async def list_positions_with_records(
    session: AsyncSession,
    since: datetime | None = None,
    min_monthly_jds: int = 30,  # Sprint 2: condition — only positions with enough data
) -> list[str]:
    """Distinct job_titles that have at least one completed extraction.

    Sprint 2: Added min_monthly_jds filter — only positions with sufficient
    JD data get snapshots, preventing pseudo-temporal analysis on sparse data.

    Used by orchestrator to decide which positions need snapshotting.
    """
    # First: get positions with any completed extraction
    # P0-AUDIT-FIX (2026-08-13): the previous implementation declared
    # `min_monthly_jds=30` but never used it — sparse-data positions produced
    # noisy changelogs and contaminated PSR/Neo4j writes. Apply the threshold
    # via HAVING on a per-position count subquery.
    if min_monthly_jds > 0:
        from sqlalchemy import func
        # Subquery: distinct job_titles whose completed-record count >= threshold
        stmt = (
            sa.select(JDExtractionRecord.job_title)
            .where(JDExtractionRecord.status == "completed")
            .group_by(JDExtractionRecord.job_title)
            .having(func.count(JDExtractionRecord.id) >= min_monthly_jds)
        )
    else:
        stmt = sa.select(JDExtractionRecord.job_title).where(
            JDExtractionRecord.status == "completed"
        ).distinct()
    if since is not None:
        stmt = stmt.where(JDExtractionRecord.created_at >= since)
    result = await session.execute(stmt)
    return [str(name) for name in result.scalars().all() if name]
