"""Graph Projector — PG → Neo4j 同步投影服务。

架构角色 (Architecture Round 1–3 决策):
  - PostgreSQL = 唯一真相源 (SSOT)
  - Neo4j = 只读投影（节点类型与关系类型的派生缓存）
  - 本服务负责把 PG 的状态推到 Neo4j，同时反向检测并清理孤儿

设计原则:
  1. **canonical_id 贯通**：所有节点使用 PG 的 UUID (`PositionRecord.id`,
     `SkillRecord.id`) 作为 Neo4j MERGE 键，不再用 name 兜底。
  2. **同步写后投影 (sync write)**：调用方负责在 PG 写事务 commit 后再调用
     `apply_change` / `apply_batch`。失败也不阻塞 PG 写。
  3. **可重放 reconcile**：`reconcile_all()` 读取 PG 全部实体，与 Neo4j diff，
     把孤儿 (Neo4j 上存在但 PG 已删除) 剪枝，把缺失 (PG 有 Neo4j 没) 补齐。
  4. **失败回滚友好**：本服务只 read/write Neo4j，对 PG 状态零依赖；如果 Neo4j
     不可达，PG 仍然权威，调用方可以选择把投影任务丢进 outbox。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable
from uuid import UUID

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants — must stay aligned with PG model fields.
# ---------------------------------------------------------------------------

# Neo4j node label ↔ PG table name (used by reconcile)
NODE_LABELS: dict[str, str] = {
    "Position": "positions",
    "Skill": "skills",
    "Domain": "domains",
    "Industry": "industries",
}

# PG → Neo4j MERGE key
PK_FIELD = "canonical_id"


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class ProjectionResult:
    """Outcome of a single projection operation."""

    nodes_upserted: int = 0
    edges_upserted: int = 0
    orphans_pruned: int = 0
    errors: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes_upserted": self.nodes_upserted,
            "edges_upserted": self.edges_upserted,
            "orphans_pruned": self.orphans_pruned,
            "errors": self.errors,
            "ok": self.ok,
        }


# ---------------------------------------------------------------------------
# Projector service
# ---------------------------------------------------------------------------

class GraphProjector:
    """Pushes PG state into Neo4j as a derived read projection.

    Usage::

        projector = GraphProjector(driver)
        await projector.apply_change(
            label="Position",
            canonical_id=position.id,
            properties={"name": position.name, "industry": position.industry},
        )
    """

    def __init__(self, driver: Any) -> None:
        self._driver = driver

    # ------------------------------------------------------------------
    # Single-entity projection
    # ------------------------------------------------------------------

    async def apply_change(
        self,
        *,
        label: str,
        canonical_id: UUID | str,
        properties: dict[str, Any] | None = None,
    ) -> ProjectionResult:
        """Upsert one node by canonical_id. Properties are merged on top of existing."""
        if label not in NODE_LABELS:
            return ProjectionResult(errors=[f"unsupported label: {label}"])
        cid = str(canonical_id)
        props = dict(properties or {})
        props[PK_FIELD] = cid
        # Drop None values to avoid Neo4j complaints
        props = {k: v for k, v in props.items() if v is not None}
        try:
            async with self._driver.session() as session:
                await session.run(
                    f"MERGE (n:{label} {{{PK_FIELD}: $cid}}) "
                    "SET n += $props, n.updated_at = datetime()",
                    cid=cid,
                    props=props,
                )
            return ProjectionResult(nodes_upserted=1)
        except Exception as exc:  # noqa: BLE001 (projection best-effort)
            logger.warning("apply_change failed for %s %s: %s", label, cid, exc)
            return ProjectionResult(errors=[f"apply_change {label}/{cid}: {exc}"])

    # ------------------------------------------------------------------
    # Batch projection (called after pipeline graph_sync stage)
    # ------------------------------------------------------------------

    async def apply_batch(
        self,
        *,
        positions: Iterable[dict[str, Any]] | None = None,
        skills: Iterable[dict[str, Any]] | None = None,
        relations: Iterable[dict[str, Any]] | None = None,
    ) -> ProjectionResult:
        """Upsert many nodes + their REQUIRES relations in one driver session."""
        result = ProjectionResult()
        if self._driver is None:
            result.errors.append("neo4j_driver_unavailable")
            return result

        try:
            async with self._driver.session() as session:
                # Position nodes
                for pos in positions or ():
                    cid = pos.get("canonical_id") or pos.get("id")
                    if not cid:
                        result.errors.append("position missing canonical_id")
                        continue
                    props = {k: v for k, v in pos.items() if v is not None}
                    props[PK_FIELD] = str(cid)
                    await session.run(
                        "MERGE (n:Position {canonical_id: $cid}) "
                        "SET n += $props, n.updated_at = datetime()",
                        cid=str(cid),
                        props=props,
                    )
                    result.nodes_upserted += 1

                # Skill nodes
                for sk in skills or ():
                    cid = sk.get("canonical_id") or sk.get("id")
                    if not cid:
                        result.errors.append("skill missing canonical_id")
                        continue
                    props = {k: v for k, v in sk.items() if v is not None}
                    props[PK_FIELD] = str(cid)
                    await session.run(
                        "MERGE (n:Skill {canonical_id: $cid}) "
                        "SET n += $props, n.updated_at = datetime()",
                        cid=str(cid),
                        props=props,
                    )
                    result.nodes_upserted += 1

                # REQUIRES relations (position_cid -> skill_cid)
                for rel in relations or ():
                    p_cid = rel.get("position_canonical_id")
                    s_cid = rel.get("skill_canonical_id")
                    if not p_cid or not s_cid:
                        result.errors.append("relation missing canonical_ids")
                        continue
                    rel_props = {
                        k: v
                        for k, v in rel.items()
                        if v is not None
                        and k not in {"position_canonical_id", "skill_canonical_id"}
                    }
                    await session.run(
                        "MATCH (p:Position {canonical_id: $p_cid}) "
                        "MATCH (s:Skill {canonical_id: $s_cid}) "
                        "MERGE (p)-[r:REQUIRES]->(s) "
                        "SET r += $props, r.updated_at = datetime()",
                        p_cid=str(p_cid),
                        s_cid=str(s_cid),
                        props=rel_props,
                    )
                    result.edges_upserted += 1

            return result
        except Exception as exc:  # noqa: BLE001
            logger.warning("apply_batch failed: %s", exc)
            result.errors.append(f"apply_batch: {exc}")
            return result

    # ------------------------------------------------------------------
    # Single-entity delete projection
    # ------------------------------------------------------------------

    async def apply_delete(
        self,
        *,
        label: str,
        canonical_id: UUID | str,
    ) -> ProjectionResult:
        """Detach-delete one node from Neo4j (cascades to its relations)."""
        if label not in NODE_LABELS:
            return ProjectionResult(errors=[f"unsupported label: {label}"])
        cid = str(canonical_id)
        try:
            async with self._driver.session() as session:
                result = await session.run(
                    f"MATCH (n:{label} {{{PK_FIELD}: $cid}}) "
                    "DETACH DELETE n RETURN count(n) AS deleted",
                    cid=cid,
                )
                # Modern neo4j driver returns an EagerResult; .single() works.
                try:
                    record = await result.single()
                    deleted = int(record["deleted"]) if record else 0
                except Exception:
                    deleted = 1  # assume success if delete ran
            return ProjectionResult(orphans_pruned=deleted)
        except Exception as exc:  # noqa: BLE001
            logger.warning("apply_delete failed for %s %s: %s", label, cid, exc)
            return ProjectionResult(errors=[f"apply_delete {label}/{cid}: {exc}"])

    # ------------------------------------------------------------------
    # Full reconciliation — diff PG vs Neo4j and prune orphans
    # ------------------------------------------------------------------

    async def reconcile_all(self, pg_session: Any) -> ProjectionResult:
        """Reconcile the entire PG → Neo4j graph.

        Strategy:
          1. List every Neo4j node by label.
          2. List every PG PositionRecord.id + SkillRecord.id.
          3. Compute set diff: orphans = neo4j_ids − pg_ids.
          4. DETACH DELETE orphan nodes.
          5. (Optional) upsert PG nodes that are missing in Neo4j.

        Returns aggregate counts.
        """
        result = ProjectionResult()
        if self._driver is None:
            result.errors.append("neo4j_driver_unavailable")
            return result

        try:
            from sqlalchemy import select  # local import to keep module lean
            from app.models.extraction_models import PositionRecord, SkillRecord

            # 1. Snapshot Neo4j IDs by label
            neo4j_ids: dict[str, set[str]] = {}
            async with self._driver.session() as session:
                for label in ("Position", "Skill"):
                    res = await session.run(
                        f"MATCH (n:{label}) WHERE n.canonical_id IS NOT NULL "
                        "RETURN n.canonical_id AS cid"
                    )
                    ids: set[str] = set()
                    async for record in res:
                        cid = record.get("cid") if hasattr(record, "get") else record["cid"]
                        if cid:
                            ids.add(str(cid))
                    neo4j_ids[label] = ids

            # 2. Snapshot PG IDs
            pg_pos_ids = {
                str(row[0])
                for row in (
                    await pg_session.execute(select(PositionRecord.id))
                ).all()
            }
            pg_skill_ids = {
                str(row[0])
                for row in (
                    await pg_session.execute(select(SkillRecord.id))
                ).all()
            }
            pg_ids = {"Position": pg_pos_ids, "Skill": pg_skill_ids}

            # 3+4. Prune orphans
            async with self._driver.session() as session:
                for label, neo_ids in neo4j_ids.items():
                    orphans = neo_ids - pg_ids[label]
                    if not orphans:
                        continue
                    logger.info(
                        "reconcile: %s orphans=%d (e.g. %s)",
                        label, len(orphans), next(iter(orphans), ""),
                    )
                    for cid in orphans:
                        await session.run(
                            f"MATCH (n:{label} {{canonical_id: $cid}}) "
                            "DETACH DELETE n",
                            cid=cid,
                        )
                        result.orphans_pruned += 1

            # 5. Backfill PG → Neo4j for missing nodes (best-effort)
            missing_pos = pg_pos_ids - neo4j_ids["Position"]
            missing_skill = pg_skill_ids - neo4j_ids["Skill"]

            if missing_pos or missing_skill:
                positions = (
                    await pg_session.execute(
                        select(PositionRecord).where(PositionRecord.id.in_([UUID(c) for c in missing_pos]))
                    )
                ).scalars().all() if missing_pos else []
                skills = (
                    await pg_session.execute(
                        select(SkillRecord).where(SkillRecord.id.in_([UUID(c) for c in missing_skill]))
                    )
                ).scalars().all() if missing_skill else []

                pos_dicts = [
                    {
                        "canonical_id": str(p.id),
                        "name": p.name,
                        "name_cn": p.name_cn,
                        "industry": p.industry,
                        "description": p.description,
                    }
                    for p in positions
                ]
                skill_dicts = [
                    {
                        "canonical_id": str(s.id),
                        "name": s.name,
                        "category": s.category,
                        "source_count": s.source_count,
                    }
                    for s in skills
                ]
                backfill = await self.apply_batch(
                    positions=pos_dicts,
                    skills=skill_dicts,
                )
                result.nodes_upserted += backfill.nodes_upserted
                result.errors.extend(backfill.errors)

            return result
        except Exception as exc:  # noqa: BLE001
            logger.warning("reconcile_all failed: %s", exc)
            result.errors.append(f"reconcile_all: {exc}")
            return result


__all__ = ["GraphProjector", "ProjectionResult", "PK_FIELD", "NODE_LABELS"]