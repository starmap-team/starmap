"""EvolutionOrchestrator — 8-step pipeline wiring snapshot → diff → trust → path.

This is the entry point that the Celery beat task calls every 6 hours
(see stage 3.5 wiring in app/tasks/celery_app.py). It is also callable
directly from admin tooling for ad-hoc reruns.

Steps:
    1. List positions that have ≥1 completed JDExtractionRecord
    2. For each position, for each of the last N months:
       a. SnapshotManager.create_snapshot  → EvolutionSnapshot
    3. For each position, walk its snapshot timeline:
       a. DiffEngine.diff(prev, curr)      → list[EvolutionChange]
       b. TrustScorer.score(change, source_count) → (trust, confidence)
       c. INSERT EvolutionChangelog rows
    4. PathRecommender.recommend(session)   → EvolutionPath (top-K)
    5. refresh_skill_timeseries(session)    → SkillTimeseries (existing service)
    6. Return summary report (counts + warnings)

Idempotency:
- Snapshots are window-keyed (position, month) → upserted by SnapshotManager
- Changelogs are written fresh per run — duplicate detection is by
  (position, skill, snapshot_to_id) which is naturally unique per run.
  Re-runs within the same hour are acceptable; they just produce new rows
  with refreshed trust scores.
- PathRecommender deletes + reinserts the top-K each run.

Failures:
- Any per-position exception is logged + counted, never aborts the run.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.evolution.consistency import check_pg_neo4j_consistency
from app.core.evolution.diff_engine import DiffEngine
from app.core.evolution.graph_projection import project_edges_to_neo4j
from app.core.evolution.path_recommender import PathRecommender
from app.core.evolution.snapshot_manager import (
    SnapshotManager,
    list_positions_with_records,
)
from app.core.evolution.trust_scorer import (
    LOW_TRUST_THRESHOLD,
    TrustScorer,
)
from app.core.evolution.write_back import (
    CHANGE_TO_REQUIREMENT_TYPE,
    _resolve_position_id,
    _resolve_skill_id,
    write_back_changelog_row,
)
from app.db.session import get_session_factory
from app.exceptions import StarMapError
from app.models.evolution_models import (
    EvolutionChangelog,
    EvolutionSnapshot,
)
from app.services.timeseries_service import refresh_skill_timeseries


class EvolutionPipelineError(Exception):
    """Expected error in the evolution pipeline that should be logged but not abort the run."""

    def __init__(self, message: str, step: str = "") -> None:
        super().__init__(message)
        self.step = step
        self.message = message


def _month_iter(months_back: int, ref: datetime | None = None) -> list[datetime]:
    """Return ``[ref_minus_N_months, ..., ref_minus_1_month, ref]`` month starts.

    The latest entry is the current month — callers may skip it if they only
    want completed months.
    """
    if ref is None:
        ref = datetime.now(UTC)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=UTC)
    out: list[datetime] = []
    for i in range(months_back, -1, -1):
        # Subtract i months by walking back to first-of-month, then back i months.
        anchor = datetime(ref.year, ref.month, 1, tzinfo=UTC)
        for _ in range(i):
            if anchor.month == 1:
                anchor = datetime(anchor.year - 1, 12, 1, tzinfo=UTC)
            else:
                anchor = datetime(anchor.year, anchor.month - 1, 1, tzinfo=UTC)
        out.append(anchor)
    return out


async def run_evolution_pipeline(months_back: int = 6) -> dict[str, Any]:
    """Drive the full evolution refresh. See module docstring for steps."""
    bounded_months = max(1, min(int(months_back), 24))
    months = _month_iter(bounded_months)
    logger.info(
        "evolution_orchestrator: starting months_back={} windows={}",
        bounded_months,
        [m.strftime("%Y-%m") for m in months],
    )

    session_factory = get_session_factory()
    snap_mgr = SnapshotManager()
    differ = DiffEngine()
    scorer = TrustScorer()
    path_finder = PathRecommender()

    summary: dict[str, Any] = {
        "started_at": datetime.now(UTC).isoformat(),
        "months_back": bounded_months,
        "windows": [m.strftime("%Y-%m") for m in months],
        "positions_processed": 0,
        "snapshots_created": 0,
        "changelogs_written": 0,
        "paths_written": 0,
        "timeseries": {},
        "errors": [],
        "warnings": [],
    }

    # ── Steps 1-3: per-position snapshot + diff + changelog ──
    async with session_factory() as session:
        positions = await list_positions_with_records(session)
    summary["positions_found"] = len(positions)

    if not positions:
        summary["warnings"].append("no positions with completed extraction records")
        logger.warning("evolution_orchestrator: no positions to process, aborting early")
        return summary

    projected_edges: list[tuple[str, str, str, float]] = []
    for position in positions:
        try:
            snapshots_made, changelogs_made, edges_made = await _process_single_position(
                session_factory,
                snap_mgr,
                differ,
                scorer,
                position,
                months,
                summary["warnings"],
            )
            summary["positions_processed"] += 1
            summary["snapshots_created"] += snapshots_made
            summary["changelogs_written"] += changelogs_made
            projected_edges.extend(edges_made)
        except EvolutionPipelineError as exc:
            # Expected pipeline errors: log and continue
            msg = f"position='{position}': {exc}"
            summary["errors"].append(msg)
            logger.warning("evolution_orchestrator: pipeline error for position='{}': {}", position, exc)
        except StarMapError:
            raise
        except Exception as exc:
            # Unexpected errors: log with full traceback but still continue
            msg = f"position='{position}': {type(exc).__name__}: {exc}"
            summary["errors"].append(msg)
            logger.exception("evolution_orchestrator: unexpected error for position='{}'", position)

    # ── D-04 tail: incremental Neo4j projection of this run's written-back rows ──
    # 仅投影本次回写成功的 upsert 行（增量），不触发全量重投影；fail-soft (D-06)。
    summary["graph_projected_edges"] = 0
    if projected_edges:
        try:
            summary["graph_projected_edges"] = await project_edges_to_neo4j(
                projected_edges, summary["warnings"]
            )
        except Exception as exc:  # noqa: BLE001 — D-06 fail-soft, projection never aborts
            summary["warnings"].append(
                f"graph_projection: {type(exc).__name__}: {exc}"
            )
            logger.warning("evolution_orchestrator: graph projection failed (non-fatal): {}", exc)

    # ── Step 4: path recommender (single batch) ──
    try:
        async with session_factory() as session:
            async with session.begin():
                paths = await path_finder.recommend(session)
        summary["paths_written"] = len(paths)
    except EvolutionPipelineError as exc:
        summary["errors"].append(f"path_recommender: {exc}")
        logger.warning("evolution_orchestrator: path recommender error: {}", exc)
    except StarMapError:
        raise
    except Exception as exc:
        summary["errors"].append(f"path_recommender: {type(exc).__name__}: {exc}")
        logger.exception("evolution_orchestrator: path recommender unexpected error")

    # ── Step 5: refresh skill timeseries (existing service) ──
    try:
        async with session_factory() as session:
            async with session.begin():
                summary["timeseries"] = await refresh_skill_timeseries(session)
    except EvolutionPipelineError as exc:
        summary["errors"].append(f"timeseries: {exc}")
        logger.warning("evolution_orchestrator: timeseries error: {}", exc)
    except StarMapError:
        raise
    except Exception as exc:
        summary["errors"].append(f"timeseries: {type(exc).__name__}: {exc}")
        logger.exception("evolution_orchestrator: timeseries unexpected error")

    # ── D-07: PG ↔ Neo4j 一致性校验（只读，warn-only，不改数据）──
    # 校验失败仅告警不阻断管线；consistency 模块自身只读，禁止写 Cypher。
    try:
        summary["consistency"] = await check_pg_neo4j_consistency(session_factory)
    except Exception as exc:  # noqa: BLE001 — D-07 fail-soft
        summary["warnings"].append(
            f"consistency: {type(exc).__name__}: {exc}"
        )
        logger.warning("evolution_orchestrator: consistency check failed (non-fatal): {}", exc)
        summary["consistency"] = {
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        }

    # W5: consistency.py docstring 承诺「调用方把 mismatch 降级为 warnings」——
    # 这里落地：status=="mismatch" 时追加告警，使监控 warnings 列表的运维能看到漂移（D-07 意图）。
    if summary["consistency"].get("status") == "mismatch":
        cons = summary["consistency"]
        summary["warnings"].append(
            f"consistency: PG ↔ Neo4j mismatch — "
            f"pg_only={len(cons.get('pg_only', []))}, "
            f"neo4j_only={len(cons.get('neo4j_only', []))}, "
            f"attribute_mismatches={len(cons.get('attribute_mismatches', []))}"
        )

    summary["completed_at"] = datetime.now(UTC).isoformat()
    logger.info(
        "evolution_orchestrator: done positions={} snapshots={} changelogs={} paths={} errors={}",
        summary["positions_processed"],
        summary["snapshots_created"],
        summary["changelogs_written"],
        summary["paths_written"],
        len(summary["errors"]),
    )
    return summary


async def _process_single_position(
    session_factory: async_sessionmaker[AsyncSession],
    snap_mgr: SnapshotManager,
    differ: DiffEngine,
    scorer: TrustScorer,
    position: str,
    months: list[datetime],
    warnings: list[str],
) -> tuple[int, int, list[tuple[str, str, str, float]]]:
    """Generate snapshots for each month, diff adjacent ones, write changelogs.

    Returns ``(snapshots_created, changelogs_written, projected_edges)``.
    ``warnings`` is the shared pipeline warning sink — write-back/projection
    failures append here and never abort the run (D-06).
    """
    snapshots_created = 0
    changelogs_written = 0
    projected_edges: list[tuple[str, str, str, float]] = []
    prev_snapshot: EvolutionSnapshot | None = None

    # Generate snapshots in chronological order so we can walk adjacencies.
    for month_anchor in months:
        async with session_factory() as session:
            async with session.begin():
                snap = await snap_mgr.create_snapshot(session, position, month_anchor)
                if snap is not None:
                    snapshots_created += 1
                    # Re-load previous snapshot for this position to keep the
                    # diff anchored to actual DB state (handles re-runs).
                    if prev_snapshot is None:
                        prev_snapshot = await _load_previous_snapshot(
                            session,
                            position,
                            month_anchor,
                        )
                    if prev_snapshot is not None and prev_snapshot.id != snap.id:
                        written_here, edges_here = await _diff_and_persist(
                            session,
                            differ,
                            scorer,
                            prev_snapshot,
                            snap,
                            warnings,
                        )
                        changelogs_written += written_here
                        projected_edges.extend(edges_here)
                    prev_snapshot = snap

    return snapshots_created, changelogs_written, projected_edges


async def _load_previous_snapshot(
    session: AsyncSession,
    position: str,
    before_month: datetime,
) -> EvolutionSnapshot | None:
    """Return the most recent snapshot strictly before `before_month` for position."""
    stmt = (
        sa.select(EvolutionSnapshot)
        .where(EvolutionSnapshot.position_name == position)
        .where(EvolutionSnapshot.snapshot_date < before_month)
        .order_by(EvolutionSnapshot.snapshot_date.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _diff_and_persist(
    session: AsyncSession,
    differ: DiffEngine,
    scorer: TrustScorer,
    old: EvolutionSnapshot,
    new: EvolutionSnapshot,
    warnings: list[str],
) -> tuple[int, list[tuple[str, str, str, float]]]:
    """Compute diff between two snapshots, score each change, persist to PG.

    Persists EvolutionChangelog rows, then D-04 write-back: each eligible
    high-trust row is upserted into position_skill_relations (fail-soft via
    ``write_back_changelog_row``, D-06). Successfully written-back rows are
    collected as ``projected_edges`` (pg_position_id, pg_skill_id,
    requirement_type, effective_confidence) for the incremental Neo4j
    projection — the confidence is the max actually written to the PSR row,
    not the raw changelog value (W1).

    Returns ``(changelogs_written, projected_edges)``.
    """
    changes = differ.diff(old, new)
    if not changes:
        return 0, []

    written = 0
    rows: list[EvolutionChangelog] = []
    for change in changes:
        # 去重 (QA G#3 修复): 同一 (岗位, 技能, 变更类型) 只保留一条记录，跨状态去重。
        # 此前按快照对 (from_id, to_id) 去重 — 但 create_snapshot 每月 delete+重建快照，
        # 旧快照被删触发 FK ON DELETE SET NULL 把已存行的 from/to_id 置空 → 去重键
        # 永远匹配不上 → 每轮运行重复 INSERT（Pandas|Data Analyst removed 已累积 76 条
        # pending + approved/rejected 各 1 条）。改为按业务键去重：同一条变更
        # 无论当前是 pending/approved/rejected，都不再重复入队。
        existing = (
            await session.execute(
                sa.select(EvolutionChangelog.id)
                .where(
                    EvolutionChangelog.position_name == new.position_name,
                    EvolutionChangelog.skill_name == change.skill_name,
                    EvolutionChangelog.change_type == change.change_type.value,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue  # 该变更已记录过（含已审核），跳过

        # source_count: use the newer snapshot's source_count as the strongest signal.
        source_count = int(new.source_count or 0)
        trust, confidence = scorer.score(change, source_count)
        row = EvolutionChangelog(
            position_name=new.position_name,
            skill_name=change.skill_name,
            change_type=change.change_type.value,
            old_proficiency=change.old_proficiency,
            new_proficiency=change.new_proficiency,
            old_requirement=change.old_requirement,
            new_requirement=change.new_requirement,
            snapshot_from_id=old.id,
            snapshot_to_id=new.id,
            # BUG-6 fix: use shared LOW_TRUST_THRESHOLD (was 0.6 — out of sync
            # with /evolution/review-queue filter of 0.5; pending rows in
            # [0.5, 0.6) were orphaned).
            status="approved" if trust >= LOW_TRUST_THRESHOLD else "pending",
            trust_score=trust,
            confidence=confidence,
            evidence_json={
                "mention_count_old": change.mention_count_old,
                "mention_count_new": change.mention_count_new,
                "source_count": source_count,
                # D-09 证据因子: 与 trust_scorer.score_change 输出口径一致
                "factors": {
                    "source": round(scorer._source_factor(source_count), 3),
                    "stability": round(scorer._stability_factor(change), 3),
                    "type": scorer._type_factor(change.change_type),
                },
            },
        )
        session.add(row)
        rows.append(row)
        written += 1
    await session.flush()

    # D-04/D-06: per-row write-back → position_skill_relations (fail-soft,
    # warnings thread into the pipeline summary). Collect projected edges for
    # the incremental Neo4j projection (only THIS run's written-back rows).
    # W1: 投影使用回写实际落库的有效 confidence（max(existing, new)），
    # 而不是原始 changelog confidence —— 否则 PG 保持 max 而 Neo4j 写入 raw 值会漂移。
    projected_edges: list[tuple[str, str, str, float]] = []
    for row in rows:
        try:
            effective_confidence = await write_back_changelog_row(session, row, warnings)
            if effective_confidence is not None:
                row.written_back = True
                position_id = await _resolve_position_id(session, row.position_name)
                skill_id = await _resolve_skill_id(session, row.skill_name)
                if position_id is not None:
                    projected_edges.append(
                        (
                            str(position_id),
                            str(skill_id),
                            CHANGE_TO_REQUIREMENT_TYPE[row.change_type],
                            effective_confidence,
                        )
                    )
        except Exception as exc:  # noqa: BLE001 — D-06 fail-soft, never abort
            warnings.append(f"_diff_and_persist: write-back loop failed for {row}: {type(exc).__name__}: {exc}")
            logger.warning("evolution _diff_and_persist: write-back loop failed for {}: {}", row, exc)
    return written, projected_edges
