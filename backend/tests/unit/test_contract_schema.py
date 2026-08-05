"""契约形状回归测试（graph 域 Schema 集中管理 + 契约对齐）。

防止三类回归：
1. 路由文件重新内联 Pydantic 模型（违反 AGENTS.md Schema 集中管理约定）
2. PositionSkillDetailResponse 契约与真实 API 漂移（paths vs edges）
3. 导出的 JSON Schema 出现悬空 $ref（前端运行时校验静默跳过）
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.api.v1 import dashboard as dashboard_router
from app.api.v1 import graph as graph_router
from app.api.v1 import position as position_router

REPO_ROOT = Path(__file__).resolve().parents[3]
GRAPH_SCHEMA = REPO_ROOT / "starmap-contracts" / "schemas" / "graph.schema.json"
POSITION_SCHEMA = REPO_ROOT / "starmap-contracts" / "schemas" / "position.schema.json"


def _load_graph_schema() -> dict[str, Any]:
    return json.loads(GRAPH_SCHEMA.read_text(encoding="utf-8"))


def _inline_models(module: Any) -> list[str]:
    return [
        name
        for name, obj in inspect.getmembers(module, inspect.isclass)
        if issubclass(obj, BaseModel) and obj.__module__ == module.__name__
    ]


class TestRouteModelCentralization:
    """路由文件不得内联定义 Pydantic 模型（AGENTS.md Schema 集中管理）。"""

    def test_graph_route_has_no_inline_models(self) -> None:
        assert _inline_models(graph_router) == []

    def test_position_route_has_no_inline_models(self) -> None:
        assert _inline_models(position_router) == []

    def test_dashboard_route_has_no_inline_models(self) -> None:
        assert _inline_models(dashboard_router) == []


class TestPositionSkillDetailShape:
    """/graph/position/{id}/skills 契约与真实 API 对齐（{position, skills, edges}）。"""

    def test_has_edges_not_paths(self) -> None:
        doc = _load_graph_schema()
        props = doc["definitions"]["PositionSkillDetailResponse"]["properties"]
        assert "edges" in props, "契约缺 edges（真实 API 返回边列表）"
        assert "paths" not in props, "契约含过时 paths 字段（与真实 API 漂移）"

    def test_position_nullable(self) -> None:
        doc = _load_graph_schema()
        psdr = doc["definitions"]["PositionSkillDetailResponse"]
        assert "position" not in psdr.get("required", []), "position 可空（未找到岗位时 404 前的缺省）"


class TestPositionNodeShape:
    """/positions 列表契约与真实 API 对齐（industry 可为空串）。"""

    def test_industry_nullable(self) -> None:
        doc = json.loads(POSITION_SCHEMA.read_text(encoding="utf-8"))
        pn = doc["definitions"]["PositionNode"]
        assert "industry" not in pn.get("required", []), "industry 可空（DB 存在 NULL/空 industry 岗位）"
        assert pn["properties"]["industry"].get("default") == ""


class TestExportedSchemaRefs:
    """导出的 JSON Schema 不得有悬空 $ref。"""

    def test_no_dangling_refs(self) -> None:
        doc = _load_graph_schema()
        root_defs = doc.get("$defs", {})
        dangling: list[str] = []

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                ref = node.get("$ref")
                if isinstance(ref, str) and ref.startswith("#/$defs/"):
                    if ref.split("/")[-1] not in root_defs:
                        dangling.append(ref)
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(doc)
        assert dangling == [], f"悬空 $ref: {dangling}"

    def test_graph_flat_models_exported(self) -> None:
        doc = _load_graph_schema()
        assert "GraphPositionNode" in doc["$defs"]
        assert "GraphSkillNode" in doc["$defs"]
        assert "KAPositionsResponse" in doc["definitions"]

class TestDomainOverviewResponseHasGeneratedAt:
    """PLAN-006④: overview 响应必须含 generated_at 时间戳（前端 honest freshness 信号）。"""

    def test_generated_at_field_present(self) -> None:
        doc = _load_graph_schema()
        dor = doc["definitions"]["DomainOverviewResponse"]
        assert "generated_at" in dor["properties"], "DomainOverviewResponse 缺 generated_at 字段（PLAN-006④ 诚实时效）"
        assert dor["properties"]["generated_at"]["type"] == "number"
