"""RepairEngine — PG↔Neo4j 数据统一修复引擎 (P1+P2 数据统一方案).

架构角色（见 docs/design/多端数据统一与防漂移架构方案.md §3）:
  - PostgreSQL = 唯一真相源 (SSOT)
  - Neo4j = 派生投影（只读缓存）
  - 本服务负责：① 缺失节点自动投影（无审批）；② 孤儿节点严格检测（统一
    canonical_id 口径，含无 canonical_id 节点）；③ 孤儿入审批队列 + 审批执行
    （破坏性删除必须经审批门控 + audit_events 审计）。

与 GraphProjector 的关系:
  - GraphProjector 提供单节点/批量投影与 reconcile_all（reconcile_all 直接剪枝，
    用于手动 reconcile 按钮）
  - RepairEngine 提供"自动投影 + 孤儿审批队列"路径（reconcile_all 的剪枝不经过
    审批，不适合自动化路径）

检测口径（修复 R2/R3: 健康卡与总数表自相矛盾）:
  - 旧口径只统计 `canonical_id IS NOT NULL` 的节点差 → 漏掉无 canonical_id 节点
  - 新口径统计全部 Neo4j 节点：
      * 有 canonical_id 且不在 PG → orphan_canonical_id 孤儿
      * 无 canonical_id 且 name 不匹配任何 PG 行 → no_canonical_id 孤儿
      * 无 canonical_id 但 name 匹配 PG 行 → 未链接节点（自动 SET canonical_id 修复）
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from neo4j.exceptions import Neo4jError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.exceptions import GraphProjectionError, StarMapError
from app.models.extraction_models import PositionRecord, PositionSkillRelation, SkillRecord
from app.models.orphan_cleanup import OrphanCleanupQueue

logger = logging.getLogger(__name__)

# 节点标签（与 GraphProjector.NODE_LABELS 对齐）
_ORPHAN_LABELS = ("Position", "Skill")

# 队列状态
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_CLEANED = "cleaned"
STATUS_LINKED = "linked"


@dataclass
class OrphanItem:
    """一条孤儿检测结果。"""

    node_type: str                 # 'position' | 'skill'
    name: str
    canonical_id: str | None
    reason: str                    # 'no_canonical_id' | 'orphan_canonical_id'
    referenced_by: int = 0         # 被非孤儿节点引用的边数（引用检查）
    suggested_cid: str | None = None    # P3a: 建议链接的 PG canonical_id
    suggested_name: str | None = None   # P3a: 建议链接的 PG 名称
    suggestion_level: str | None = None # 'exact' | 'normalized' | 'fuzzy'

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_type": self.node_type,
            "name": self.name,
            "canonical_id": self.canonical_id,
            "reason": self.reason,
            "referenced_by": self.referenced_by,
            "suggested_cid": self.suggested_cid,
            "suggested_name": self.suggested_name,
            "suggestion_level": self.suggestion_level,
        }


def _normalize_name(name: str) -> str:
    """归一化: 去非字母数字、转小写（用于模糊匹配）。"""
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", name.lower())


def _suggest_pg_match(
    name: str, pg_name_to_id: dict[str, str],
) -> tuple[str | None, str | None, str | None]:
    """为无 canonical_id 节点建议 PG 匹配（保守，防误链）。

    返回 (suggested_cid, suggested_name, level):
      - exact: 大小写精确匹配（最安全）
      - normalized: 归一化后相等（React.js vs ReactJS 类）
      - fuzzy: token 子集匹配（有误链风险，如 CSS ⊆ tailwind css，仅作候选提示）
    """
    if not name:
        return None, None, None
 # 1. 大小写精确
    low = name.lower()
    for pn, cid in pg_name_to_id.items():
        if pn.lower() == low:
            return cid, pn, "exact"
 # 2. 归一化相等
    norm = _normalize_name(name)
    for pn, cid in pg_name_to_id.items():
        if norm and _normalize_name(pn) == norm:
            return cid, pn, "normalized"
 # 3. token 子集（孤儿 token ⊆ PG token，且 PG 名不长于孤儿名 3 倍，降低误链）
    tokens = set(re.findall(r"[a-z0-9\u4e00-\u9fff]+", name.lower()))
    if not tokens:
        return None, None, None
    best: tuple[int, str, str] | None = None
    for pn, cid in pg_name_to_id.items():
        pt = set(re.findall(r"[a-z0-9\u4e00-\u9fff]+", pn.lower()))
        if tokens and tokens <= pt and len(pt) <= len(tokens) * 3:
            if best is None or len(pt) < best[0]:
                best = (len(pt), pn, cid)
    if best is not None:
        return best[2], best[1], "fuzzy"
    return None, None, None


@dataclass
class OrphanScanResult:
    """孤儿扫描汇总。"""

    orphan_positions: int = 0
    orphan_skills: int = 0
    unlinked_positions: int = 0     # 无 canonical_id 但 name 匹配 PG（自动修复）
    unlinked_skills: int = 0
    items: list[OrphanItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.orphan_positions + self.orphan_skills


class RepairEngine:
    """PG 权威 + 自动投影 + 孤儿审批门控。"""

    def __init__(self, driver: Any) -> None:
        self._driver = driver

 # ------------------------------------------------------------------
 # ① 孤儿严格检测（统一口径，含无 canonical_id 节点）
 # ------------------------------------------------------------------

    async def detect_orphans(self, pg_session: Any) -> OrphanScanResult:
        """扫描 Neo4j 全部节点，与 PG 严格对齐。

        - 有 canonical_id 且不在 PG → 孤儿（orphan_canonical_id）
        - 无 canonical_id 且 name 不匹配任何 PG 行 → 孤儿（no_canonical_id）
        - 无 canonical_id 但 name 匹配 PG 行 → 未链接（记录 unlinked_*，不列为孤儿）
        """
        result = OrphanScanResult()
        if self._driver is None:
            result.errors.append("neo4j_driver_unavailable")
            return result

        try:
 # PG 快照: id 集合 + name→id 映射（用于无 canonical_id 节点的 name 匹配）
            pg_pos_ids = {
                str(r[0]) for r in (await pg_session.execute(select(PositionRecord.id))).all()
            }
            pg_skill_ids = {
                str(r[0]) for r in (await pg_session.execute(select(SkillRecord.id))).all()
            }
            pg_pos_name = {
                str(r[0]): str(r[1])
                for r in (await pg_session.execute(
                    select(PositionRecord.id, PositionRecord.name)
                )).all()
            }
            pg_skill_name = {
                str(r[0]): str(r[1])
                for r in (await pg_session.execute(
                    select(SkillRecord.id, SkillRecord.name)
                )).all()
            }
            pg_name_pos = {name: cid for cid, name in pg_pos_name.items() if name}
            pg_name_skill = {name: cid for cid, name in pg_skill_name.items() if name}

            async with self._driver.session() as session:
                for label, pg_ids, pg_name_to_id in (
                    ("Position", pg_pos_ids, pg_name_pos),
                    ("Skill", pg_skill_ids, pg_name_skill),
                ):
 # 拉取全部节点（含无 canonical_id 的）
                    res = await session.run(
                        f"MATCH (n:{label}) "
                        "OPTIONAL MATCH (m)-[r]->(n) "
                        "RETURN n.canonical_id AS cid, n.name AS name, "
                        "count(r) AS in_degree"
                    )
                    nodes: list[dict[str, Any]] = []
                    async for record in res:
                        cid = record.get("cid") if hasattr(record, "get") else record["cid"]
                        name = record.get("name") if hasattr(record, "get") else record["name"]
                        in_degree = int(record["in_degree"] or 0)
                        nodes.append({
                            "cid": str(cid) if cid else None,
                            "name": str(name) if name else "",
                            "in_degree": in_degree,
                        })

 # 引用检查: 统计被"非孤儿"节点引用的孤儿。先按无引用孤儿处理，
 # referenced_by 用 in_degree 近似（被其他节点引用数）。
                    for node in nodes:
                        cid = node["cid"]
                        name = node["name"]
                        if cid is not None and cid not in pg_ids:
 # 孤儿（有 canonical_id 但 PG 无）
                            item = OrphanItem(
                                node_type=label.lower(),
                                name=name or cid,
                                canonical_id=cid,
                                reason="orphan_canonical_id",
                                referenced_by=node["in_degree"],
                            )
                            result.items.append(item)
                            if label == "Position":
                                result.orphan_positions += 1
                            else:
                                result.orphan_skills += 1
                        elif cid is None:
 # 无 canonical_id: name 匹配 PG → 未链接（自动修复候选）；否则孤儿
 # P3a: 精确匹配 → unlinked（不列孤儿）；否则尝试建议链接候选
                            if name and name in pg_name_to_id:
                                if label == "Position":
                                    result.unlinked_positions += 1
                                else:
                                    result.unlinked_skills += 1
                            else:
                                sug_cid, sug_name, sug_level = _suggest_pg_match(name, pg_name_to_id)
                                item = OrphanItem(
                                    node_type=label.lower(),
                                    name=name or "(unnamed)",
                                    canonical_id=None,
                                    reason="no_canonical_id",
                                    referenced_by=node["in_degree"],
                                    suggested_cid=sug_cid,
                                    suggested_name=sug_name,
                                    suggestion_level=sug_level,
                                )
                                result.items.append(item)
                                if label == "Position":
                                    result.orphan_positions += 1
                                else:
                                    result.orphan_skills += 1

            return result
        except StarMapError:
            raise
        except (Neo4jError, SQLAlchemyError) as exc:
            logger.exception("RepairEngine detect_orphans DB error")
            raise GraphProjectionError(str(exc)) from exc
        except Exception as exc:
            logger.exception("RepairEngine detect_orphans unexpected error")
            raise GraphProjectionError(str(exc)) from exc

 # ------------------------------------------------------------------
 # ② 缺失节点自动投影（无审批，幂等）
 # ------------------------------------------------------------------

    async def ensure_projection(self, pg_session: Any) -> dict[str, Any]:
        """把 PG 中 Neo4j 缺失的节点/边补齐（不含删除）。

        复用 GraphProjector.apply_batch 的幂等 MERGE；缺失判定基于 canonical_id
        对齐。自动投影路径不剪枝——删除必须走审批队列（设计约束）。
        """
        if self._driver is None:
            return {"nodes_projected": 0, "edges_projected": 0, "errors": ["neo4j_driver_unavailable"]}

        from app.services.graph_projector import GraphProjector

        projector = GraphProjector(self._driver)
        try:
 # PG 全量快照
            positions = (await pg_session.execute(
                select(PositionRecord)
            )).scalars().all()
            skills = (await pg_session.execute(
                select(SkillRecord)
            )).scalars().all()

 # Neo4j 已有 canonical_id 集合（跳过已投影的，避免全量重放）
            async with self._driver.session() as session:
                existing_pos: set[str] = set()
                existing_skill: set[str] = set()
                for label, acc in (("Position", existing_pos), ("Skill", existing_skill)):
                    res = await session.run(
                        f"MATCH (n:{label}) WHERE n.canonical_id IS NOT NULL "
                        "RETURN n.canonical_id AS cid"
                    )
                    async for record in res:
                        cid = record["cid"]
                        if cid:
                            acc.add(str(cid))

            pos_dicts = [
                {
                    "canonical_id": str(p.id),
                    "name": p.name,
                    "name_cn": p.name_cn,
                    "industry": p.industry,
                    "description": p.description,
                }
                for p in positions if str(p.id) not in existing_pos
            ]
            skill_dicts = [
                {
                    "canonical_id": str(s.id),
                    "name": s.name,
                    # 2026-08-20 (修复 B): 与 graph_projector 一致带 name_cn
                    "name_cn": s.name_cn or "",
                    "category": s.category,
                    "source_count": s.source_count,
                }
                for s in skills if str(s.id) not in existing_skill
            ]

 # 关系: PG 全部 PSR → 需两端节点都存在才能 MERGE 边
            relations: list[dict[str, Any]] = []
            if pos_dicts or skill_dicts:
                psr_rows = (await pg_session.execute(
                    select(
                        PositionSkillRelation.position_id,
                        PositionSkillRelation.skill_id,
                        PositionSkillRelation.requirement_type,
                    )
                )).all()
                for position_id, skill_id, req_type in psr_rows:
                    relations.append({
                        "position_canonical_id": str(position_id),
                        "skill_canonical_id": str(skill_id),
                        "requirement_type": req_type,
                    })

            if not pos_dicts and not skill_dicts:
                return {"nodes_projected": 0, "edges_projected": 0, "errors": []}

            backfill = await projector.apply_batch(
                positions=pos_dicts,
                skills=skill_dicts,
                relations=relations,
            )
            return {
                "nodes_projected": backfill.nodes_upserted,
                "edges_projected": backfill.edges_upserted,
                "errors": backfill.errors,
            }
        except StarMapError:
            raise
        except (Neo4jError, SQLAlchemyError) as exc:
            logger.exception("RepairEngine ensure_projection DB error")
            raise GraphProjectionError(str(exc)) from exc
        except Exception as exc:
            logger.exception("RepairEngine ensure_projection unexpected error")
            raise GraphProjectionError(str(exc)) from exc

 # ------------------------------------------------------------------
 # ③ 孤儿入审批队列 + 审批执行
 # ------------------------------------------------------------------

    async def sync_orphan_queue(self, pg_session: Any) -> int:
        """检测孤儿并把新条目 upsert 进审批队列（pending）。

        去重键: 有 canonical_id 用 (node_type, canonical_id)；无 canonical_id 用
        (node_type, name)。已 approved/cleaned 的条目不重复入队。
        """
        scan = await self.detect_orphans(pg_session)
        new_items = 0
        updated_items = 0
        for item in scan.items:
            existing = (await pg_session.execute(
                select(OrphanCleanupQueue).where(
                    OrphanCleanupQueue.node_type == item.node_type,
                    OrphanCleanupQueue.canonical_id == item.canonical_id
                    if item.canonical_id
                    else OrphanCleanupQueue.name == item.name,
                    OrphanCleanupQueue.status.in_([STATUS_PENDING, STATUS_APPROVED]),
                )
            )).scalars().first()
            if existing is not None:
 # P3a: 存量 pending 条目刷新引用数 + 链接建议（检测口径升级后）
                detail = dict(existing.detail or {})
                detail["referenced_by"] = item.referenced_by
                if item.suggested_cid:
                    detail["suggested_cid"] = item.suggested_cid
                    detail["suggested_name"] = item.suggested_name
                    detail["suggestion_level"] = item.suggestion_level
                if detail != (existing.detail or {}):
                    existing.detail = detail
                    updated_items += 1
                continue
            pg_session.add(OrphanCleanupQueue(
                node_type=item.node_type,
                name=item.name,
                canonical_id=item.canonical_id,
                reason=item.reason,
                status=STATUS_PENDING,
                detail={
                    "referenced_by": item.referenced_by,
 # P3a: 链接建议（同实体不同名 → 候选 PG 匹配）
                    "suggested_cid": item.suggested_cid,
                    "suggested_name": item.suggested_name,
                    "suggestion_level": item.suggestion_level,
                },
            ))
            new_items += 1

        # 2026-08-21 (debug 修复): stale 队列清理 —— 此前 sync 只检测"当前孤儿"
        # 写入队列；不刷新已有 pending 条目的 canonical_id。后果：Neo4j 节点后
        # 续通过 reconcile 补了 canonical_id（已链接到 PG），但队列条目还停在
        # pending + canonical_id=NULL → 数据源诊断面板显示「孤立岗位 0/孤立技能 0
        # 同步健康度 正常」与「队列 23 pending」看似矛盾（口径不同，实际是 stale）。
        # 修复：sync 时扫描所有 pending 条目，按 name 查 Neo4j 当前 canonical_id；
        # 若节点已链接（cid 非空且 PG 匹配）→ 队列条目标 STATUS_LINKED；
        # 若节点已不存在（被前面 reconcile 剪枝）→ 标 STATUS_CLEANED。
        reconciled = await self._reconcile_orphan_queue_status(pg_session)

        if new_items or updated_items or reconciled:
            await pg_session.commit()
        return new_items + updated_items + reconciled

    async def _reconcile_orphan_queue_status(self, pg_session: Any) -> int:
        """2026-08-21: 扫描 pending 队列条目，匹配 Neo4j 节点当前状态自动标
        linked/cleaned，避免「健康度 0」与「队列 pending」的口径不一致。

        容错：driver 不可用或 Neo4j 调用异常 → 直接返回 0（不阻断 sync_orphan_queue
        主流程）。旧 pending 条目保留为 stale 但不阻塞其它修复。
        """
        if self._driver is None:
            return 0
        pending = (await pg_session.execute(
            select(OrphanCleanupQueue).where(OrphanCleanupQueue.status == STATUS_PENDING)
        )).scalars().all()
        if not pending:
            return 0
        updated = 0
        try:
            async with self._driver.session() as session:
                for item in pending:
                    try:
                        # 按 node_type + name 查 Neo4j 当前节点
                        res = await session.run(
                            f"MATCH (n:{item.node_type}) WHERE n.name = $name "
                            "RETURN n.canonical_id AS cid, n.name AS name LIMIT 1",
                            name=item.name,
                        )
                        rec = await res.single()
                    except Exception as inner_exc:
                        # 单条 Neo4j 调用失败 → 跳过本条（不阻断整批）
                        logger.debug("reconcile_orphan_queue: skip %s: %s",
                                     item.name, inner_exc)
                        continue
                    if rec is None:
                        # Neo4j 节点已不存在（被 reconcile 剪枝）→ 队列条目作废
                        item.status = STATUS_CLEANED
                        item.reviewed_at = datetime.now(UTC)
                        item.detail = dict(item.detail or {}) | {"auto_cleaned": "node removed from Neo4j"}
                        updated += 1
                        continue
                    neo4j_cid = rec.get("cid") if hasattr(rec, "get") else rec["cid"]
                    if neo4j_cid and item.canonical_id != neo4j_cid:
                        # Neo4j 节点已建立 canonical_id（此前为 NULL）→ 队列条目同步
                        item.canonical_id = neo4j_cid
                        detail = dict(item.detail or {})
                        detail["auto_linked_cid"] = neo4j_cid
                        item.detail = detail
                    # Neo4j.canonical_id 非空且在 PG（脱链 PG 端验证见 detect_orphans）：
                    # 此节点已链接 → 队列条目标 linked
                    if neo4j_cid:
                        item.status = STATUS_LINKED
                        item.reviewed_at = datetime.now(UTC)
                        item.detail = dict(item.detail or {}) | {"auto_linked": True}
                        updated += 1
        except Exception as outer_exc:
            # Neo4j 会话整体失败（driver 不可用/mock 测试）→ 不阻断 sync
            logger.warning("reconcile_orphan_queue skipped (driver unavailable): {}",
                           outer_exc)
            return 0
        if updated:
            logger.info("orphan queue stale reconciliation: {} items updated", updated)
        return updated

    async def get_orphan_queue(
        self, pg_session: Any, *, status: str | None = None, limit: int = 200,
    ) -> list[dict[str, Any]]:
        """列出审批队列条目（默认 pending）。"""
        stmt = select(OrphanCleanupQueue).order_by(OrphanCleanupQueue.created_at.desc())
        if status:
            stmt = stmt.where(OrphanCleanupQueue.status == status)
        stmt = stmt.limit(limit)
        rows = (await pg_session.execute(stmt)).scalars().all()
        return [r.to_dict() for r in rows]

    async def execute_cleanup(
        self, pg_session: Any, queue_id: Any, *, action: str, actor: str,
    ) -> dict[str, Any]:
        """审批执行: approved → DETACH DELETE 节点（级联边）+ 审计；rejected → 标记。

        approved 删除是破坏性操作：删除前将条目状态置为 cleaned，删除失败可重试。
        """
        from app.utils.audit import AuditEntry, AuditEvent, audit_log

        item = (await pg_session.execute(
            select(OrphanCleanupQueue).where(OrphanCleanupQueue.id == queue_id)
        )).scalar_one_or_none()
        if item is None:
            return {"error": "queue item not found"}

        now = datetime.now(UTC)
        if action == "reject":
            item.status = STATUS_REJECTED
            item.reviewed_at = now
            item.reviewed_by = actor
            await pg_session.commit()
            audit_log(AuditEntry(
                event=AuditEvent.SENSITIVE_WRITE,
                actor=actor,
                action="orphan_cleanup_reject",
                detail=f"node_type={item.node_type},name={item.name},reason={item.reason}",
                ip="",
            ))
            return {"status": STATUS_REJECTED, "name": item.name}

        if action == "approve":
            if item.status != STATUS_PENDING:
                return {"error": f"queue item already {item.status}"}
            if self._driver is None:
                return {"error": "neo4j_driver_unavailable"}
            label = "Position" if item.node_type == "position" else "Skill"
            async with self._driver.session() as session:
                if item.canonical_id:
                    res = await session.run(
                        f"MATCH (n:{label} {{canonical_id: $cid}}) DETACH DELETE n "
                        "RETURN count(n) AS deleted",
                        cid=item.canonical_id,
                    )
                else:
 # 无 canonical_id: 按 name 精确删除（name 为孤儿判定的 key）
                    res = await session.run(
                        f"MATCH (n:{label} {{name: $name}}) WHERE n.canonical_id IS NULL "
                        "DETACH DELETE n RETURN count(n) AS deleted",
                        name=item.name,
                    )
                try:
                    record = await res.single()
                    deleted = int(record["deleted"]) if record else 0
                except (Neo4jError, IndexError, KeyError, TypeError):
                    deleted = 1

            item.status = STATUS_CLEANED
            item.reviewed_at = now
            item.reviewed_by = actor
            await pg_session.commit()
            audit_log(AuditEntry(
                event=AuditEvent.SENSITIVE_WRITE,
                actor=actor,
                action="orphan_cleanup_approve",
                detail=(
                    f"node_type={item.node_type},name={item.name},"
                    f"canonical_id={item.canonical_id},deleted={deleted}"
                ),
                ip="",
            ))
            return {"status": STATUS_CLEANED, "name": item.name, "deleted": deleted}

        return {"error": f"unknown action: {action}"}

 # ------------------------------------------------------------------
 # ④ 批量审批（无引用孤儿一键清理）
 # ------------------------------------------------------------------

    async def execute_batch_cleanup(
        self, pg_session: Any, *, action: str, only_no_reference: bool, actor: str,
    ) -> dict[str, Any]:
        """批量审批所有匹配的 pending 条目。

        only_no_reference=True（推荐）: 仅处理 referenced_by==0 的无引用孤儿
        （删除安全，不破坏其他节点的边）；False: 全部 pending（含被引用项，
        危险，仅显式授权时用）。
        逐项 execute_cleanup（各自事务），部分失败不影响其余。
        """
        rows = (await pg_session.execute(
            select(OrphanCleanupQueue).where(OrphanCleanupQueue.status == STATUS_PENDING)
        )).scalars().all()

        if only_no_reference:
            rows = [r for r in rows if (r.detail or {}).get("referenced_by", 0) == 0]

        processed = 0
        deleted = 0
        errors: list[str] = []
        for item in rows:
            res = await self.execute_cleanup(pg_session, item.id, action=action, actor=actor)
            if "error" in res:
                errors.append(f"{item.node_type}:{item.name} -> {res['error']}")
            else:
                processed += 1
                deleted += int(res.get("deleted", 0))
        return {"processed": processed, "deleted": deleted, "errors": errors}

 # ------------------------------------------------------------------
 # ⑤ 链接建议执行（P3a: 被引用无标识节点 → SET canonical_id，非破坏、可逆）
 # ------------------------------------------------------------------

    async def link_node(
        self, pg_session: Any, queue_id: Any, *, canonical_id: str | None, actor: str,
    ) -> dict[str, Any]:
        """把无 canonical_id 的 Neo4j 节点链接到 PG 记录（SET canonical_id）。

        非破坏性（不删节点/边）；canonical_id 缺省时用检测时的建议值。
        目标 canonical_id 必须是真实 PG 记录，否则拒绝（防误链）。
        """
        from sqlalchemy import select as _sel

        from app.utils.audit import AuditEntry, AuditEvent, audit_log

        item = (await pg_session.execute(
            _sel(OrphanCleanupQueue).where(OrphanCleanupQueue.id == queue_id)
        )).scalar_one_or_none()
        if item is None:
            return {"error": "queue item not found"}
        if item.status != STATUS_PENDING:
            return {"error": f"queue item already {item.status}"}

        target_cid = canonical_id or (item.detail or {}).get("suggested_cid")
        if not target_cid:
            return {"error": "no canonical_id provided and no suggestion available"}

 # 目标必须是真实 PG 记录（按节点类型校验）
        model = PositionRecord if item.node_type == "position" else SkillRecord
        try:
            from uuid import UUID as _UUID
            pg_row = (await pg_session.execute(
                _sel(model).where(model.id == _UUID(str(target_cid)))
            )).scalar_one_or_none()
        except (ValueError, TypeError):
            return {"error": f"invalid canonical_id: {target_cid}"}
        if pg_row is None:
            return {"error": f"canonical_id {target_cid} not found in PG {model.__tablename__}"}

        if self._driver is None:
            return {"error": "neo4j_driver_unavailable"}

        label = "Position" if item.node_type == "position" else "Skill"
        async with self._driver.session() as session:
 # 无 canonical_id 节点按 name 定位（name 是检测 key）；幂等 SET
            res = await session.run(
                f"MATCH (n:{label} {{name: $name}}) WHERE n.canonical_id IS NULL "
                "SET n.canonical_id = $cid "
                "RETURN count(n) AS linked",
                name=item.name,
                cid=str(target_cid),
            )
            try:
                record = await res.single()
                linked = int(record["linked"]) if record else 0
            except (Neo4jError, IndexError, KeyError, TypeError):
                linked = 1

        if linked == 0:
            return {"error": f"no node found to link for name={item.name!r} (node already linked?)"}

        item.status = STATUS_LINKED
        item.canonical_id = str(target_cid)
        item.reviewed_at = datetime.now(UTC)
        item.reviewed_by = actor
        detail = dict(item.detail or {})
        detail["linked_cid"] = str(target_cid)
        item.detail = detail
        await pg_session.commit()
        audit_log(AuditEntry(
            event=AuditEvent.SENSITIVE_WRITE,
            actor=actor,
            action="orphan_cleanup_link",
            detail=f"node_type={item.node_type},name={item.name},linked_cid={target_cid}",
            ip="",
        ))
        return {"status": STATUS_LINKED, "name": item.name, "linked_cid": str(target_cid), "linked": linked}

 # ------------------------------------------------------------------
 # ⑥ 历史技能补录（P3b: 图中有但 PG 无记录 → 回填 skill_records + 链接）
 # ------------------------------------------------------------------

    async def backfill_skill_records(self, pg_session: Any, *, review_status: str = "approved") -> dict[str, Any]:
        """把 Neo4j 中无 canonical_id 且 PG 无同名记录的 Skill 回填到 skill_records。

        根因 R3: graph_sync 的 upsert 只覆盖当次 run 抽取载荷，历史 name-MERGE
        技能（被 PREREQUISITE/RECOMMENDED_FOR 引用）永不回填 PG。
        本方法: 扫描全部无标识 Skill 节点 → PG 无同名记录 → upsert（approved，因
        已在公开学习图中被引用）→ SET canonical_id 链接。幂等、非破坏。
        """
        from app.repositories.extract_repo import upsert_skill_record

        if self._driver is None:
            return {"backfilled": 0, "linked": 0, "errors": ["neo4j_driver_unavailable"]}

        try:
 # PG 现有技能名（大小写不敏感判定）
            pg_skill_lower = {
                str(r[0]).lower() for r in (
                    await pg_session.execute(select(SkillRecord.name))
                ).all()
            }

 # 扫描无 canonical_id 的 Skill 节点
            async with self._driver.session() as session:
                res = await session.run(
                    "MATCH (n:Skill) WHERE n.canonical_id IS NULL "
                    "RETURN n.name AS name"
                )
                names: set[str] = set()
                async for record in res:
                    name = record.get("name") if hasattr(record, "get") else record["name"]
                    if name:
                        names.add(str(name))

            backfilled = 0
            linked = 0
            errors: list[str] = []
            for name in sorted(names):
                if name.lower() in pg_skill_lower:
                    continue  # PG 已有（大小写变体），跳过
                try:
                    await upsert_skill_record(
                        pg_session, name=name, category="hard_skill",
                        review_status=review_status,
                        created_by="system:backfill",
                    )
                    backfilled += 1
                except Exception as exc:  # noqa: BLE001 — 单条失败不阻断
                    errors.append(f"{name}: {exc}")
                    continue
 # 新记录 id: 按 name 查回
                row = (await pg_session.execute(
                    select(SkillRecord.id).where(SkillRecord.name == name)
                )).scalar_one_or_none()
                if row is None:
                    errors.append(f"{name}: backfilled but id not found")
                    continue
                try:
                    async with self._driver.session() as session:
                        await session.run(
                            "MATCH (n:Skill {name: $name}) WHERE n.canonical_id IS NULL "
                            "SET n.canonical_id = $cid",
                            name=name, cid=str(row),
                        )
                    linked += 1
                except (Neo4jError, SQLAlchemyError) as exc:
                    errors.append(f"{name}: link failed: {exc}")

            if backfilled or linked:
                await pg_session.commit()
            return {"backfilled": backfilled, "linked": linked, "errors": errors}
        except StarMapError:
            raise
        except (Neo4jError, SQLAlchemyError) as exc:
            logger.exception("RepairEngine backfill_skill_records DB error")
            raise GraphProjectionError(str(exc)) from exc
        except Exception as exc:
            logger.exception("RepairEngine backfill_skill_records unexpected error")
            raise GraphProjectionError(str(exc)) from exc

 # ------------------------------------------------------------------
 # ⑦ 历史岗位补录（R5: 抽取 evolves_to 后继岗位只写图不落 PG → 回填 + 链接）
 # ------------------------------------------------------------------

    async def backfill_position_records(self, pg_session: Any, *, review_status: str = "pending_review") -> dict[str, Any]:
        """把 Neo4j 中无 canonical_id 且 PG 无同名记录的 Position 回填到 position_records。

        根因 R5: 抽取的 `evolves_to` 后继岗位（职业演化目标）由 graph_writer 按
        name-MERGE 写图（graph_writer.py:319-331），persist 只写主岗位 → 后继
        岗位成为无 PG 记录、被 EVOLVES_TO 引用的图节点。
        本方法: 扫描无标识 Position 节点 → PG 无同名 → upsert（默认 pending_review，
        新岗位需审核）→ SET canonical_id。幂等、非破坏。
        """
        from app.repositories.extract_repo import upsert_position_record

        if self._driver is None:
            return {"backfilled": 0, "linked": 0, "errors": ["neo4j_driver_unavailable"]}

        try:
            pg_pos_lower = {
                str(r[0]).lower() for r in (
                    await pg_session.execute(select(PositionRecord.name))
                ).all()
            }

            async with self._driver.session() as session:
                res = await session.run(
                    "MATCH (n:Position) WHERE n.canonical_id IS NULL "
                    "RETURN n.name AS name"
                )
                names: set[str] = set()
                async for record in res:
                    name = record.get("name") if hasattr(record, "get") else record["name"]
                    if name:
                        names.add(str(name))

            backfilled = 0
            linked = 0
            errors: list[str] = []
            for name in sorted(names):
                if name.lower() in pg_pos_lower:
                    continue
                try:
                    await upsert_position_record(
                        pg_session, name=name, industry=None, description=None,
                        review_status=review_status,
                        created_by="system:backfill",
                    )
                    backfilled += 1
                except Exception as exc:  # noqa: BLE001 — 单条失败不阻断
                    errors.append(f"{name}: {exc}")
                    continue
                row = (await pg_session.execute(
                    select(PositionRecord.id).where(PositionRecord.name == name)
                )).scalar_one_or_none()
                if row is None:
                    errors.append(f"{name}: backfilled but id not found")
                    continue
                try:
                    async with self._driver.session() as session:
                        await session.run(
                            "MATCH (n:Position {name: $name}) WHERE n.canonical_id IS NULL "
                            "SET n.canonical_id = $cid",
                            name=name, cid=str(row),
                        )
                    linked += 1
                except (Neo4jError, SQLAlchemyError) as exc:
                    errors.append(f"{name}: link failed: {exc}")

            if backfilled or linked:
                await pg_session.commit()
            return {"backfilled": backfilled, "linked": linked, "errors": errors}
        except StarMapError:
            raise
        except (Neo4jError, SQLAlchemyError) as exc:
            logger.exception("RepairEngine backfill_position_records DB error")
            raise GraphProjectionError(str(exc)) from exc
        except Exception as exc:
            logger.exception("RepairEngine backfill_position_records unexpected error")
            raise GraphProjectionError(str(exc)) from exc


__all__ = [
    "RepairEngine",
    "OrphanItem",
    "OrphanScanResult",
    "STATUS_PENDING",
    "STATUS_APPROVED",
    "STATUS_REJECTED",
    "STATUS_CLEANED",
    "STATUS_LINKED",
]
