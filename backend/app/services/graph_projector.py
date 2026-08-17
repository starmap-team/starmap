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
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from neo4j.exceptions import Neo4jError
from sqlalchemy.exc import SQLAlchemyError

from app.core.extraction.industry import is_unclassified
from app.exceptions import GraphProjectionError, StarMapError

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
    skills_upserted: int = 0
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
            "skills_upserted": self.skills_upserted,
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
 # Architect review (PRD B): DB「未分类」字面量同步到 Neo4j 会污染
 # _classify_industry 聚类 —— 归一化为 None，让现有 None-drop 逻辑丢弃。
        if "industry" in props and is_unclassified(props.get("industry")):
            props["industry"] = None
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
        except StarMapError:
            raise
        except (Neo4jError, SQLAlchemyError) as exc:
            logger.exception("Graph projection DB error: %s %s", label, cid)
            raise GraphProjectionError(str(exc)) from exc
        except Exception as exc:
            logger.exception("Unexpected error in graph projection: %s %s", label, cid)
            raise GraphProjectionError(str(exc)) from exc

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
 # Phase 23 Task 3: Skill 分支单独累加 skills_upserted（修 admin
 # skills_synced 复制粘贴 bug——Position/Skill 不再共用 nodes_upserted）
                    result.skills_upserted += 1

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
        except StarMapError:
            raise
        except (Neo4jError, SQLAlchemyError) as exc:
            logger.exception("Graph projection DB error: apply_batch")
            raise GraphProjectionError(str(exc)) from exc
        except Exception as exc:
            logger.exception("Unexpected error in graph projection: apply_batch")
            raise GraphProjectionError(str(exc)) from exc

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
                except (Neo4jError, IndexError, KeyError, TypeError):
                    deleted = 1  # assume success if delete ran
            return ProjectionResult(orphans_pruned=deleted)
        except StarMapError:
            raise
        except (Neo4jError, SQLAlchemyError) as exc:
            logger.exception("Graph projection DB error: apply_delete {} {}", label, cid)
            raise GraphProjectionError(str(exc)) from exc
        except Exception as exc:
            logger.exception("Unexpected error in graph projection: apply_delete {} {}", label, cid)
            raise GraphProjectionError(str(exc)) from exc

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
 # Phase 23 核验修复 (M1b 闭环): 节点快照必须限定 approved——与边层
 # (line ~440) 及 run_build_graph_from_extractions 口径一致。否则每次
 # reconcile 都会把 pending_review 岗位回灌图谱（孤儿剪枝后又被回填）。
            pg_pos_ids = {
                str(row[0])
                for row in (
                    await pg_session.execute(
                        select(PositionRecord.id).where(
                            PositionRecord.review_status == "approved"
                        )
                    )
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

 # Phase 24 根治④: 清理 canonical_id IS NULL 的 Position 孤儿。
 # Phase 23 Task 2 切键后，无 canonical_id 的旧节点既不被上方 set-diff
 # 剪枝（只查 canonical_id IS NOT NULL）也不被投影回填，永久残留——
 # reconcile 曾报 positions_in_neo4j=189 vs PG=185 差 4 且孤儿清理无效。
 # 这里按 name 对比 PG approved 岗位名：图中有 name 但 PG 无对应
 # approved 岗位 → 孤儿，DETACH DELETE。
            try:
                pg_approved_names = {
                    str(row[0])
                    for row in (
                        await pg_session.execute(
                            select(PositionRecord.name).where(
                                PositionRecord.review_status == "approved"
                            )
                        )
                    ).all()
                }
                async with self._driver.session() as session:
                    null_cid_positions = await session.run(
                        "MATCH (p:Position) WHERE p.canonical_id IS NULL "
                        "RETURN p.name AS name, p.canonical_id AS cid"
                    )
                    async for rec in null_cid_positions:
                        name = rec["name"]
                        if name not in pg_approved_names:
 # 图内无主键孤儿：从 PG 侧找不到 → 删除（级联边）
                            await session.run(
                                "MATCH (p:Position {name: $name}) "
                                "WHERE p.canonical_id IS NULL DETACH DELETE p",
                                name=name,
                            )
                            result.orphans_pruned += 1
                            logger.info("reconcile: pruned null-cid Position orphan '{}'", name)
            except Exception as exc:  # 兜底清理 fail-soft，不阻断主对账
                logger.warning("reconcile: null-cid orphan prune skipped: {}", exc)

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

 # D5 fix (2026-08-12): 抽取图写入路径（graph_writer merge_position/merge_skill）
 # 按 name MERGE 时不设 canonical_id → 产生"同名孤儿节点"；此处先按名链接
 # （MATCH name + SET canonical_id），使 apply_batch 的 canonical MERGE 命中
 # 同一节点而非创建重复。幂等：已链接节点后续只更新属性。
                async with self._driver.session() as session:
                    for row, label in (
                        *((p, "Position") for p in positions),
                        *((s, "Skill") for s in skills),
                    ):
                        await session.run(
                            f"MATCH (n:{label} {{name: $name}}) WHERE n.canonical_id IS NULL "
                            "SET n.canonical_id = $cid",
                            name=row.name, cid=str(row.id),
                        )

                pos_dicts = [
                    {
                        "canonical_id": str(p.id),
                        "name": p.name,
                        "name_cn": p.name_cn,
 # Architect review (PRD B): 归一化为 None 避免 Neo4j
 # _classify_industry 把「未分类」聚成假行业桶。
                        "industry": None if is_unclassified(p.industry) else p.industry,
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
 # Phase 23 Task 3: Skill 分支计数单独累加（修 admin skills_synced bug）
                result.skills_upserted += backfill.skills_upserted
                result.errors.extend(backfill.errors)

 # 6. 边层补缺（Phase 23 Task 3，）：PG approved 岗位 PSR 边按
 # canonical_id 对账补缺（复用 apply_batch relations 分支）。多余边只记
 # drift（admin/daily 对账 audit diff 暴露）不自动删——抽取/演化双写路径
 # 都可能合法建边，误删风险大（phase prohibition）。
            edge_backfill = await self._reconcile_requires_edges(pg_session)
            result.edges_upserted += edge_backfill.edges_upserted
            result.errors.extend(edge_backfill.errors)

            return result
        except StarMapError:
            raise
        except (Neo4jError, SQLAlchemyError) as exc:
            logger.exception("Graph projection DB error: reconcile_all")
            raise GraphProjectionError(str(exc)) from exc
        except Exception as exc:
            logger.exception("Unexpected error in graph projection: reconcile_all")
            raise GraphProjectionError(str(exc)) from exc

    async def _reconcile_requires_edges(self, pg_session: Any) -> ProjectionResult:
        """Phase 23 Task 3: 按 canonical_id 补缺 REQUIRES 边（PG approved PSR）。

        只补缺不自动删——多余 REQUIRES 边由 admin/daily 对账的 audit diff 暴露
        （drift 告警），避免误删抽取/演化双写路径合法建边。
        """
        result = ProjectionResult()
        if self._driver is None:
            result.errors.append("neo4j_driver_unavailable")
            return result
        try:
            from sqlalchemy import select  # local import to keep module lean

            from app.models.extraction_models import PositionRecord, PositionSkillRelation

            rows = (
                await pg_session.execute(
                    select(
                        PositionSkillRelation.position_id,
                        PositionSkillRelation.skill_id,
                        PositionSkillRelation.requirement_type,
                        PositionSkillRelation.confidence,
                    )
                    .join(PositionRecord, PositionRecord.id == PositionSkillRelation.position_id)
                    .where(PositionRecord.review_status == "approved")
                )
            ).all()
            relations = [
                {
                    "position_canonical_id": str(position_id),
                    "skill_canonical_id": str(skill_id),
                    "requirement_type": requirement_type,
                    "confidence": float(confidence or 0.0),
                }
                for position_id, skill_id, requirement_type, confidence in rows
            ]
            if relations:
                edge_result = await self.apply_batch(relations=relations)
                result.edges_upserted += edge_result.edges_upserted
                result.errors.extend(edge_result.errors)
            return result
        except StarMapError:
            raise
        except (Neo4jError, SQLAlchemyError) as exc:
            logger.exception("Graph projection DB error: reconcile_requires_edges")
            raise GraphProjectionError(str(exc)) from exc
        except Exception as exc:
            logger.exception("Unexpected error in graph projection: reconcile_requires_edges")
            raise GraphProjectionError(str(exc)) from exc


__all__ = ["GraphProjector", "ProjectionResult", "PK_FIELD", "NODE_LABELS"]
