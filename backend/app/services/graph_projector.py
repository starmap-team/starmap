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

from app.core.extraction.industry_gate import IT_INDUSTRY_WHITELIST as _IT_INDUSTRY_WHITELIST
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
    # 2026-08-21 (debug 修复): 半孤立节点被自动链接（Neo4j 有 + PG approved 有 +
    # 缺 canonical_id → SET canonical_id）数。让「立即对账并修复」按钮能向
    # operator 报告实际修复效果（修了 X 个孤儿 + 链接了 Y 个半孤立）。
    unlinked_linked: int = 0
    edges_backfilled: int = 0
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
                    edge_result = await session.run(
                        "MATCH (p:Position {canonical_id: $p_cid}) "
                        "MATCH (s:Skill {canonical_id: $s_cid}) "
                        "MERGE (p)-[r:REQUIRES]->(s) "
                        "SET r += $props, r.updated_at = datetime() "
                        "RETURN r",
                        p_cid=str(p_cid),
                        s_cid=str(s_cid),
                        props=rel_props,
                    )
                    # 端点（p/s）缺失时 MATCH 无结果 → MERGE 不创建边 → r 为 None。
                    # 此时不计 edges_upserted（避免虚增），记 error 暴露缺口。
                    if await edge_result.single() is not None:
                        result.edges_upserted += 1
                    else:
                        result.errors.append(
                            f"edge endpoints missing: {p_cid} -> {s_cid}"
                        )

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

            # 2. Snapshot PG IDs（approved-only 语义：图=已发布图谱；pending 不入图属预期，
            #    否则 reconcile 会把清理的 pending 重新回灌进图“复活”）
            pg_pos_ids = {
                str(row[0])
                for row in (
                    await pg_session.execute(
                        select(PositionRecord.id)
                        .where(PositionRecord.review_status == "approved")
                        # 2026-08-28 (debug: 非IT岗位混入图谱): 只投影 IT 领域岗位
                        .where(PositionRecord.industry.in_(_IT_INDUSTRY_WHITELIST))
                        # 2026-08-28 (批0 真相源): 空技能岗位不投影（防剪枝→回填振荡）
                        .where(
                            (PositionRecord.quality_hint.is_(None))
                            | (PositionRecord.quality_hint != "no_skills")
                        )
                    )
                ).all()
            }
            pg_skill_ids = {
                str(row[0])
                for row in (
                    await pg_session.execute(
                        select(SkillRecord.id).where(SkillRecord.review_status == "approved")
                    )
                ).all()
            }
            pg_ids = {"Position": pg_pos_ids, "Skill": pg_skill_ids}
            # 2026-08-21 (debug 修复): PG approved name→id 映射 —— 半孤立自动链接
            # （Neo4j 节点缺 canonical_id 时按 name 匹配 PG 设 cid）需要它。
            pg_name_pos = {
                str(name): str(cid)
                for cid, name in (
                    await pg_session.execute(
                        select(PositionRecord.id, PositionRecord.name)
                        .where(PositionRecord.review_status == "approved")
                    )
                ).all()
                if name
            }
            pg_name_skill = {
                str(name): str(cid)
                for cid, name in (
                    await pg_session.execute(
                        select(SkillRecord.id, SkillRecord.name)
                        .where(SkillRecord.review_status == "approved")
                    )
                ).all()
                if name
            }

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
                        "industry": p.industry,
                        "description": p.description,
                    }
                    for p in positions
                ]
                skill_dicts = [
                    {
                        "canonical_id": str(s.id),
                        "name": s.name,
                        # 2026-08-20 (修复 B): 投影带 name_cn —— 每日 reconcile 自动补齐
                        # Neo4j 缺失的中文技能名（存量 358 节点缺名根因）
                        "name_cn": s.name_cn or "",
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

            # 2026-08-21 (debug 修复): reconcile 补建 approved 岗位的全部 REQUIRES 边 ——
            # 此前 reconcile_all 从不传 relations → 只补节点不建边 → PG PSR 1549 vs
            # Neo4j 973 差异 576 条（37.2% 严重差异）无法靠 reconcile 收敛。
            # 幂等：MERGE 已存在的边不重复创建。
            edge_backfill = await self._reconcile_requires_edges(pg_session)
            result.edges_upserted += edge_backfill.edges_upserted
            result.errors.extend(edge_backfill.errors)

            # 2026-08-21 (debug 修复): 半孤立处理 —— Neo4j 有节点但缺 canonical_id：
            #   * name 匹配 PG approved → SET canonical_id 链接（unlinked_linked）
            #   * name 匹配 PG 非 approved（pending/rejected）→ 误入图的违规节点，
            #     按 approved-only 架构 DETACH DELETE 剪枝（orphans_pruned）
            # 此前只有 missing（PG 有 Neo4j 无）分支补节点，半孤立从不被处理，
            # 「立即对账并修复」对半孤立无效果。
            try:
                # pending/rejected 的 PG name 集合（用于剪枝误入图节点）
                pg_nonapproved_pos = {
                    str(name) for name, in (
                        await pg_session.execute(
                            select(PositionRecord.name).where(
                                PositionRecord.review_status != "approved"
                            )
                        )
                    ).all() if name
                }
                pg_nonapproved_skill = {
                    str(name) for name, in (
                        await pg_session.execute(
                            select(SkillRecord.name).where(
                                SkillRecord.review_status != "approved"
                            )
                        )
                    ).all() if name
                }
                async with self._driver.session() as session:
                    for label, pg_name_to_id, pg_nonapproved in (
                        ("Position", pg_name_pos, pg_nonapproved_pos),
                        ("Skill", pg_name_skill, pg_nonapproved_skill),
                    ):
                        res = await session.run(
                            f"MATCH (n:{label}) WHERE n.canonical_id IS NULL "
                            "RETURN n.name AS name"
                        )
                        async for record in res:
                            name = record.get("name") if hasattr(record, "get") else record["name"]
                            if not name:
                                continue
                            if name in pg_name_to_id:
                                await session.run(
                                    f"MATCH (n:{label} {{name: $name}}) WHERE n.canonical_id IS NULL "
                                    "SET n.canonical_id = $cid",
                                    name=name, cid=pg_name_to_id[name],
                                )
                                result.unlinked_linked += 1
                            elif name in pg_nonapproved:
                                # 误入图的未审核节点 → 剪枝（审核通过后重新投影）
                                await session.run(
                                    f"MATCH (n:{label} {{name: $name}}) WHERE n.canonical_id IS NULL "
                                    "DETACH DELETE n",
                                    name=name,
                                )
                                result.orphans_pruned += 1
                if result.unlinked_linked or result.orphans_pruned:
                    logger.info(
                        "reconcile_all: linked {} semi-orphans, pruned {} non-approved graph nodes",
                        result.unlinked_linked, result.orphans_pruned,
                    )
            except Exception as exc:  # noqa: BLE001 — 半孤立处理失败不阻断 reconcile
                logger.warning("reconcile_all: semi-orphan handling failed (non-fatal): {}", exc)

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
        （drift 告警），避免误删抽取/演化双写路径合法建边。幂等：MERGE 已存在
        的边不重复创建。
        """
        result = ProjectionResult()
        if self._driver is None:
            result.errors.append("neo4j_driver_unavailable")
            return result
        try:
            from sqlalchemy import select as sa_select

            from app.models.extraction_models import (
                PositionRecord,
                PositionSkillRelation,
                SkillRecord,
            )

            rel_rows = (
                await pg_session.execute(
                    sa_select(
                        PositionSkillRelation.position_id,
                        PositionSkillRelation.skill_id,
                        PositionSkillRelation.requirement_type,
                        PositionSkillRelation.confidence,
                    )
                    .join(
                        PositionRecord,
                        PositionRecord.id == PositionSkillRelation.position_id,
                    )
                    .join(
                        SkillRecord,
                        SkillRecord.id == PositionSkillRelation.skill_id,
                    )
                    .where(
                        PositionRecord.review_status == "approved",
                        SkillRecord.review_status == "approved",
                    )
                )
            ).all()
            relations = [
                {
                    "position_canonical_id": str(position_id),
                    "skill_canonical_id": str(skill_id),
                    # 规范化 requirement_type：仅 required/preferred 合法，
                    # 非法值（空/变体/optional）保守落 required（读路径同样按此判定）
                    "requirement_type": (
                        requirement_type
                        if requirement_type in ("required", "preferred")
                        else "required"
                    ),
                    "confidence": float(confidence or 0.0),
                }
                for position_id, skill_id, requirement_type, confidence in rel_rows
            ]
            if relations:
                # 2026-08-28 (数据源诊断超时根治): 增量对账 —— 先查 Neo4j 现有 REQUIRES 边
                # （canonical_id 对），只补缺。此前全量重放 2438 条 PSR 每次 30s+ 超时。
                existing_edges: set[tuple[str, str]] = set()
                try:
                    async with self._driver.session() as session:
                        res = await session.run(
                            "MATCH (p:Position)-[r:REQUIRES]->(s:Skill) "
                            "WHERE p.canonical_id IS NOT NULL AND s.canonical_id IS NOT NULL "
                            "RETURN p.canonical_id AS p, s.canonical_id AS s"
                        )
                        async for rec in res:
                            existing_edges.add((str(rec["p"]), str(rec["s"])))
                except Exception as exc:  # noqa: BLE001 — 查询失败则保守全量
                    logger.warning("reconcile_requires_edges: existing-edge scan failed, full replay: %s", exc)
                    existing_edges = set()
                missing = [
                    r for r in relations
                    if (r["position_canonical_id"], r["skill_canonical_id"]) not in existing_edges
                ]
                logger.info(
                    "reconcile_requires_edges: {} total, {} missing (incremental)",
                    len(relations), len(missing),
                )
                if missing:
                    edge_batch = await self.apply_batch(positions=[], skills=[], relations=missing)
                    result.edges_upserted += edge_batch.edges_upserted
                    result.errors.extend(edge_batch.errors)
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
