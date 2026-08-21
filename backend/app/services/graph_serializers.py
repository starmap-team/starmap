"""Neo4j node/edge count helpers + serializers — extracted from graph_service.py (m7).

业务说明：
    节点/关系计数、序列化、去重等纯函数逻辑；与 Neo4j 交互的查询逻辑仍保留在 graph_service.py。
    graph_service.py 重新导出本模块的公共符号以保持向后兼容。
"""
from __future__ import annotations

from typing import Any

from loguru import logger
from neo4j.exceptions import Neo4jError

from app.exceptions import StarMapError

# ── Count helpers ─────────────────────────────────────────────────────────

async def count_positions_neo4j(driver: Any) -> int:
 # 业务说明：统计 Neo4j 图谱中职位（Position）节点的总数量，用于仪表盘或健康检查。
 # 技术说明：当 driver 未初始化或查询异常时返回 0，保证服务降级不中断。
    """Count Position nodes in Neo4j."""
    if driver is None:
        return 0
    try:
        async with driver.session() as session:
            result = await session.run("MATCH (p:Position) RETURN count(p) AS cnt")
            record = await result.single()
            return int(record["cnt"]) if record else 0
    except (Neo4jError, StarMapError):
        return 0
    except Exception:
        logger.exception("Unexpected error in count_positions_neo4j")
        return 0


async def count_skills_neo4j(driver: Any) -> int:
 # 业务说明：统计 Neo4j 图谱中技能（Skill）节点的总数量，作为技能库规模的权威来源。
    """Count Skill nodes in Neo4j (source of truth)."""
    if driver is None:
        return 0
    try:
        async with driver.session() as session:
            result = await session.run("MATCH (s:Skill) RETURN count(s) AS cnt")
            record = await result.single()
            return int(record["cnt"]) if record else 0
    except (Neo4jError, StarMapError):
        return 0
    except Exception:
        logger.exception("Unexpected error in count_skills_neo4j")
        return 0


async def count_edges_neo4j(driver: Any) -> int:
 # 业务说明：统计 Neo4j 中所有关系类型的总数量 (REQUIRES + USES + BELONGS_TO + ...),
 # 而不仅是 REQUIRES。这是图谱连接密度的真实指标。
    """Count ALL relationships in Neo4j (regardless of type)."""
    if driver is None:
        return 0
    try:
        async with driver.session() as session:
 # E20b fix: previously matched only :REQUIRES which excluded
 # USES/BELONGS_TO/PREREQUISITE/APPLIES_TO/etc. Cross-page
 # audit (data_truth vs dashboard) revealed a 755-edge gap
 # (REQUIRES=1139 vs total=1894). Now match all relationship types.
            result = await session.run("MATCH ()-[r]->() RETURN count(r) AS cnt")
            record = await result.single()
            return int(record["cnt"]) if record else 0
    except (Neo4jError, StarMapError):
        return 0
    except Exception:
        logger.exception("Unexpected error in count_edges_neo4j")
        return 0


# ── Serialization helpers ─────────────────────────────────────────────────

def _safe_properties(value: Any) -> dict[str, Any]:
 # 技术说明：Neo4j 节点/关系的属性字典化辅助函数，兼容 Neo4j ≥5.x 的 temporal 类型（如 DateTime），
 # 通过 iso_format() 将时间对象转为字符串，避免 JSON 序列化异常。
 # dict() works for Neo4j ≥5.x; iso_format guard for temporal types
    try:
        return {k: (v.iso_format() if hasattr(v, 'iso_format') else v) for k, v in dict(value).items()}
    except (ValueError, TypeError, AttributeError):
        return {}


def _node_id(node: Any) -> str:
 # 技术说明：从 Neo4j 节点中提取唯一标识符的降级策略：
 # 优先 element_id（Neo4j ≥5.x），其次 id（旧版），最后从属性中回退 name。
    element_id = getattr(node, "element_id", None)
    if element_id is not None:
        return str(element_id)
    node_id = getattr(node, "id", None)
    if node_id is not None:
        return str(node_id)
    props = _safe_properties(node)
    return str(props.get("id") or props.get("name") or "")


def _relationship_type(rel: Any) -> str:
 # 技术说明：从 Neo4j 关系对象中提取关系类型名称，兼容不同驱动版本。
    rel_type = getattr(rel, "type", None)
    if rel_type is not None:
        return str(rel_type)
    return rel.__class__.__name__


def _relationship_endpoint(rel: Any, attr: str) -> str:
 # 技术说明：获取关系的起点或终点节点 ID，支持 start_node / end_node 两种属性名。
    node = getattr(rel, attr, None)
    if node is not None:
        return _node_id(node)
    value = getattr(rel, f"{attr}_node_id", None)
    return "" if value is None else str(value)


def serialize_node(node: Any) -> dict[str, Any]:
 # 业务说明：将 Neo4j 节点对象转换为前端图可视化组件（如 D3 / ECharts）所需的统一节点数据结构。
 # 技术说明：提取 labels、category、name 等字段，确保前端渲染时节点样式和分组正确。
    """Convert a Neo4j Node-like object to the frontend graph node contract."""
    props = _safe_properties(node)
    labels = list(getattr(node, "labels", []) or [])
    category = props.get("category") or (labels[0] if labels else "unknown")
    name = props.get("name") or props.get("title") or _node_id(node)
    props.setdefault("name", name)
    props.setdefault("category", category)
    return {
        "id": _node_id(node),
        "labels": labels,
        "properties": props,
    }


def serialize_relationship(rel: Any) -> dict[str, Any]:
 # 业务说明：将 Neo4j 关系对象转换为前端图可视化组件所需的统一边（edge/relationship）数据结构。
 # 技术说明：包含 source_id、target_id、type 及属性（如 weight），用于前端连线渲染和交互。
    """Convert a Neo4j Relationship-like object to the frontend graph edge contract."""
    props = _safe_properties(rel)
    props.setdefault("weight", 1.0)
    return {
        "source_id": _relationship_endpoint(rel, "start_node"),
        "target_id": _relationship_endpoint(rel, "end_node"),
        "type": _relationship_type(rel),
        "properties": props,
    }


def dedupe_graph(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
 # 业务说明：对图谱节点和边进行去重，保留首次出现的元素，避免前端渲染时出现重叠或重复数据。
 # 技术说明：节点以 id 为键去重，边以 (source_id, target_id, type) 三元组为键去重。
    """Remove duplicate graph elements while preserving first-seen order."""
    node_map: dict[str, dict[str, Any]] = {}
    for node in nodes:
        node_id = str(node.get("id", ""))
        if node_id:
            node_map.setdefault(node_id, node)

    edge_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    for edge in edges:
        key = (str(edge.get("source_id", "")), str(edge.get("target_id", "")), str(edge.get("type", "")))
        if all(key):
            edge_map.setdefault(key, edge)

    return {"nodes": list(node_map.values()), "edges": list(edge_map.values())}


# ── Position/Skill item formatters (extracted from graph_service.py — m7) ──

def position_item(node: dict[str, Any]) -> dict[str, Any]:
 # 业务说明：将图谱中的 Position 节点转换为 API 响应中职位列表的标准数据结构。
 # 技术说明：从 node.properties 中提取职位 ID、名称、行业、描述及所需技能列表。
    """Format a position node dict into the API position-item contract."""
    props = dict(node.get("properties") or {})
    return {
        "position_id": str(props.get("position_id") or node.get("id") or props.get("name") or ""),
        "name": props.get("name") or node.get("id") or "",
        "name_cn": props.get("name_cn") or props.get("name") or "",
        "industry": props.get("industry") or "",
        "description": props.get("description") or "",
        "skills_required": props.get("skills_required") or [],
    }


def skill_item(node: dict[str, Any], rel: dict[str, Any] | None = None) -> dict[str, Any]:
 # 业务说明：将图谱中的 Skill 节点（及可选的关联关系）转换为 API 响应中技能列表的标准数据结构。
 # 技术说明：结合节点属性与关系属性（如 level、required）生成 proficiency、importance 等字段。
    """Format a skill node dict (+ optional relationship) into the API skill-item contract."""
 # Lazy import to avoid circular dependency with graph_service re-exports.
    from app.core.extraction.normalize import normalize_proficiency

    props = dict(node.get("properties") or {})
    rel_props = dict((rel or {}).get("properties") or {})
    level = rel_props.get("level")
    # 关系属性命名有两种来源（历史演进）：
    # - 旧写路径（graph_writer.create_requires_relationship）写 `required: bool`
    # - 现写路径（graph_projection / graph_projector）写 `requirement_type: "required|preferred"`
    # 二者语义一致，读側统一兼容；缺省按 bonus 处理（保持原默认）。
    raw_required = rel_props.get("requirement_type") if "requirement_type" in rel_props else rel_props.get("required")
    if raw_required is None:
        required = False
    elif isinstance(raw_required, bool):
        required = raw_required
    else:
        required = str(raw_required).lower() == "required"
    category = props.get("category") or props.get("source_category") or "hard_skill"
    if category == "Skill":
        category = props.get("source_category") or "hard_skill"
    return {
        "skill_id": str(props.get("skill_id") or node.get("id") or props.get("name") or ""),
        "name": props.get("name") or node.get("id") or "",
        # 2026-08-20 (修复 B): 透传 name_cn —— Neo4j 节点有中文名时前端直接可用
        "name_cn": props.get("name_cn") or "",
        "category": category,
        "proficiency": props.get("proficiency") or normalize_proficiency(level),
        "confidence": float(props.get("confidence") or rel_props.get("confidence") or 1.0),
        "source_count": int(props.get("source_count") or 0),
        "trend": props.get("trend") or "stable",
        "importance": "required" if required is not False else "bonus",
    }
