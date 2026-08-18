"""Incremental Neo4j projection of evolution write-back edges (D-04 tail).

D-04 尾句「回写后 graph_sync 投影到 Neo4j」：演化回写成功的 upsert 行经
MERGE + SET 投影到图谱 REQUIRES 边。仅投影本次回写成功的行（增量），不做
全量重投影。无属性 MERGE（never MERGE with attributes）——graph_writer
曾因属性 MERGE 使 REQUIRES 边重复 34%（graph_writer.py:570-577 记录）。

本模块是 D-04 授权的写路径，与 D-07 只读一致性校验（consistency.py）职责
互斥：任何写 Cypher 不得出现在 consistency.py 中。

Fail-soft：整个调用 try/except 包裹，失败仅 warnings.append + logger.warning，
不阻断演化管线（D-06 延续）。
"""
from __future__ import annotations

from datetime import UTC, datetime

from loguru import logger

from app.core.extraction.graph_writer import GraphConfig

# 无属性 MERGE + SET（与 sync_pg_edges_to_graph.py:50-57 同款）——
# canonical_id 为 PG 侧 PositionRecord.id / SkillRecord.id。
# W2: 技能节点改为 MERGE 兜底创建 —— 回写新技能（_resolve_skill_id 物化的
# pending_review SkillRecord）在 Neo4j 可能尚无 :Skill 节点，原先 MATCH 不命中
# 会静默跳过投影而 projected 仍虚增计数。
_PROJECT_QUERY = (
    "MATCH (p:Position {canonical_id: $pid}) "
    "MERGE (s:Skill {canonical_id: $sid}) "
    "MERGE (p)-[r:REQUIRES]->(s) "
    "SET r.requirement_type = $rt, r.confidence = $conf, r.synced_at = $now"
)


async def project_edges_to_neo4j(
    edges: list[tuple[str, str, str, float]],
    warnings: list[str],
) -> int:
    """Project ``(pg_position_id, pg_skill_id, requirement_type, confidence)`` edges.

    Args:
        edges: (position_id, skill_id, requirement_type, confidence) — PG-side
            UUIDs (string-form) that double as Neo4j ``canonical_id``.
        warnings: fail-soft sink; failures are appended here, never raised.

    Returns:
        Number of edges successfully projected.
    """
    if not edges:
        return 0

    projected = 0
    config = GraphConfig()
    now = datetime.now(UTC).isoformat()
    try:
        async with config.get_driver() as driver:
            async with driver.session() as session:
                for pid, sid, requirement_type, confidence in edges:
                    try:
                        result = await session.run(
                            _PROJECT_QUERY,
                            pid=pid,
                            sid=sid,
                            rt=requirement_type,
                            conf=float(confidence),
                            now=now,
                        )
                        summary = await result.consume()
 # W2: 只有 MERGE 真正创建/更新了节点或边才计为投影成功。
 # MATCH 未命中 Position 节点时 MERGE 无操作，contains_updates
 # 为 False —— 不再虚增 graph_projected_edges，并告警供 排查。
                        if summary.counters.contains_updates:
                            projected += 1
                        else:
                            warnings.append(
                                f"graph_projection: edge {pid}->{sid} not projected — "
                                "Position node missing in Neo4j"
                            )
                    except Exception as exc:  # noqa: BLE001 — per-edge fail-soft
                        warnings.append(
                            f"graph_projection: edge {pid}->{sid} failed: {type(exc).__name__}: {exc}"
                        )
                        logger.warning("evolution graph_projection: edge {}->{} failed: {}", pid, sid, exc)
    except Exception as exc:  # noqa: BLE001 — driver-level fail-soft (D-06)
        warnings.append(
            f"graph_projection: Neo4j projection failed: {type(exc).__name__}: {exc}"
        )
        logger.warning("evolution graph_projection: Neo4j projection failed: {}", exc)
        return projected
    return projected
