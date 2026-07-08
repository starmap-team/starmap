"""Unit tests for graph_serializers, graph_overview, graph_sync.

Covers pure functions directly and Neo4j-dependent functions via mocks.
Focuses on edge cases: empty input, None values, exception handling.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.graph_overview import (
    _classify_level,
    _classify_tech_stack,
    fetch_overview_by_level,
    fetch_overview_by_tech_stack,
)
from app.services.graph_serializers import (
    _node_id,
    _relationship_endpoint,
    _relationship_type,
    _safe_properties,
    count_edges_neo4j,
    count_positions_neo4j,
    count_skills_neo4j,
    dedupe_graph,
    position_item,
    serialize_node,
    serialize_relationship,
    skill_item,
)
from app.services.graph_sync import sync_from_pipeline

# ── Helpers for mocking Neo4j async sessions ─────────────────────────────


class FakeAsyncResult:
    """Mimics a Neo4j async result with async iteration and .single()."""

    def __init__(self, records):
        self._records = list(records)

    def __aiter__(self):
        self._idx = 0
        return self

    async def __anext__(self):
        if self._idx >= len(self._records):
            raise StopAsyncIteration
        rec = self._records[self._idx]
        self._idx += 1
        return rec

    async def single(self):
        return self._records[0] if self._records else None


class FakeAsyncSession:
    """Async context manager session that returns self on __aenter__."""

    def __init__(self, run_side_effect=None):
        self._run_side_effect = run_side_effect

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def run(self, *args, **kwargs):
        if self._run_side_effect is not None:
            if callable(self._run_side_effect):
                return self._run_side_effect(*args, **kwargs)
            return self._run_side_effect
        return FakeAsyncResult([])


class FakeDriver:
    def __init__(self, session):
        self._session = session

    def session(self):
        return self._session


# ── graph_serializers: _safe_properties ──────────────────────────────────


class TestSafeProperties:
    def test_plain_dict(self):
        assert _safe_properties({"a": 1, "b": "x"}) == {"a": 1, "b": "x"}

    def test_none_returns_empty(self):
        assert _safe_properties(None) == {}

    def test_temporal_iso_format(self):
        class T:
            def iso_format(self):
                return "2024-06-01"

        result = _safe_properties({"ts": T()})
        assert result["ts"] == "2024-06-01"

    def test_mixed_temporal_and_plain(self):
        class T:
            def iso_format(self):
                return "2024-01-01"

        result = _safe_properties({"ts": T(), "count": 5})
        assert result == {"ts": "2024-01-01", "count": 5}

    def test_exception_returns_empty(self):
        class Bad:
            def __iter__(self):
                raise ValueError("boom")

        assert _safe_properties(Bad()) == {}


# ── graph_serializers: _node_id ──────────────────────────────────────────


class TestNodeId:
    def test_element_id_preferred(self):
        class N:
            element_id = "elem-1"
            id = 99

        assert _node_id(N()) == "elem-1"

    def test_fallback_to_id(self):
        class N:
            element_id = None
            id = 42

        assert _node_id(N()) == "42"

    def test_fallback_to_properties_name(self):
        assert _node_id({"name": "Python"}) == "Python"

    def test_fallback_to_properties_id(self):
        assert _node_id({"id": "x-1"}) == "x-1"

    def test_id_over_name_in_properties(self):
        assert _node_id({"id": "x-1", "name": "Python"}) == "x-1"

    def test_empty_when_no_identifiers(self):
        assert _node_id({}) == ""


# ── graph_serializers: _relationship_type ────────────────────────────────


class TestRelationshipType:
    def test_with_type_attr(self):
        class R:
            type = "REQUIRES"

        assert _relationship_type(R()) == "REQUIRES"

    def test_fallback_class_name(self):
        class MyRel:
            pass

        assert _relationship_type(MyRel()) == "MyRel"


# ── graph_serializers: _relationship_endpoint ────────────────────────────


class TestRelationshipEndpoint:
    def test_from_node(self):
        class N:
            element_id = "n-1"

        class R:
            start_node = N()

        assert _relationship_endpoint(R(), "start_node") == "n-1"

    def test_from_node_id_attr(self):
        class R:
            start_node = None
            start_node_node_id = "fallback"

        assert _relationship_endpoint(R(), "start_node") == "fallback"

    def test_missing_returns_empty(self):
        class R:
            start_node = None

        assert _relationship_endpoint(R(), "start_node") == ""


# ── graph_serializers: serialize_node ────────────────────────────────────


class TestSerializeNode:
    def test_basic_skill_node(self):
        class N:
            element_id = "s-1"
            labels = ["Skill"]

            def __iter__(self):
                return iter({"name": "Python", "category": "hard_skill"}.items())

        result = serialize_node(N())
        assert result["id"] == "s-1"
        assert result["labels"] == ["Skill"]
        assert result["properties"]["name"] == "Python"
        assert result["properties"]["category"] == "hard_skill"

    def test_node_without_labels(self):
        class N:
            element_id = "n-1"
            labels = None

            def __iter__(self):
                return iter({"name": "X"}.items())

        result = serialize_node(N())
        assert result["labels"] == []
        assert result["properties"]["category"] == "unknown"

    def test_category_from_labels_when_missing_in_props(self):
        class N:
            element_id = "n-1"
            labels = ["Position"]

            def __iter__(self):
                return iter({"name": "Dev"}.items())

        result = serialize_node(N())
        assert result["properties"]["category"] == "Position"

    def test_name_fallback_to_title(self):
        class N:
            element_id = "n-1"
            labels = []

            def __iter__(self):
                return iter({"title": "Engineer"}.items())

        result = serialize_node(N())
        assert result["properties"]["name"] == "Engineer"

    def test_name_fallback_to_node_id(self):
        class N:
            element_id = "n-1"
            labels = []

            def __iter__(self):
                return iter({}.items())

        result = serialize_node(N())
        assert result["properties"]["name"] == "n-1"


# ── graph_serializers: serialize_relationship ────────────────────────────


class TestSerializeRelationship:
    def test_basic(self):
        class StartN:
            element_id = "n-1"

        class EndN:
            element_id = "n-2"

        class R:
            type = "REQUIRES"
            start_node = StartN()
            end_node = EndN()

            def __iter__(self):
                return iter({"weight": 0.8}.items())

        result = serialize_relationship(R())
        assert result["source_id"] == "n-1"
        assert result["target_id"] == "n-2"
        assert result["type"] == "REQUIRES"
        assert result["properties"]["weight"] == 0.8

    def test_default_weight(self):
        class R:
            type = "KNOWS"
            start_node = None
            end_node = None

            def __iter__(self):
                return iter({}.items())

        result = serialize_relationship(R())
        assert result["properties"]["weight"] == 1.0


# ── graph_serializers: dedupe_graph ──────────────────────────────────────


class TestDedupeGraph:
    def test_dedupes_nodes_by_id(self):
        nodes = [{"id": "a", "name": "A"}, {"id": "a", "name": "A2"}, {"id": "b", "name": "B"}]
        result = dedupe_graph(nodes, [])
        assert len(result["nodes"]) == 2
        assert result["nodes"][0]["name"] == "A"  # first-seen wins

    def test_dedupes_edges_by_triple(self):
        edges = [
            {"source_id": "a", "target_id": "b", "type": "R"},
            {"source_id": "a", "target_id": "b", "type": "R"},
        ]
        result = dedupe_graph([], edges)
        assert len(result["edges"]) == 1

    def test_skips_empty_id_nodes(self):
        nodes = [{"id": "", "name": "X"}, {"id": "a", "name": "A"}]
        result = dedupe_graph(nodes, [])
        assert len(result["nodes"]) == 1

    def test_skips_edges_with_empty_parts(self):
        edges = [{"source_id": "", "target_id": "b", "type": "R"}]
        result = dedupe_graph([], edges)
        assert len(result["edges"]) == 0

    def test_empty_input(self):
        result = dedupe_graph([], [])
        assert result == {"nodes": [], "edges": []}

    def test_different_edge_types_not_deduped(self):
        edges = [
            {"source_id": "a", "target_id": "b", "type": "R1"},
            {"source_id": "a", "target_id": "b", "type": "R2"},
        ]
        result = dedupe_graph([], edges)
        assert len(result["edges"]) == 2


# ── graph_serializers: position_item ─────────────────────────────────────


class TestPositionItem:
    def test_basic(self):
        node = {"id": "pos-1", "properties": {"name": "Dev", "industry": "IT", "description": "Code"}}
        result = position_item(node)
        assert result["position_id"] == "pos-1"
        assert result["name"] == "Dev"
        assert result["industry"] == "IT"
        assert result["skills_required"] == []

    def test_none_properties(self):
        node = {"id": "pos-1", "properties": None}
        result = position_item(node)
        assert result["name"] == "pos-1"
        assert result["industry"] == ""

    def test_position_id_from_properties(self):
        node = {"id": "pos-1", "properties": {"position_id": "P-100", "name": "Dev"}}
        result = position_item(node)
        assert result["position_id"] == "P-100"

    def test_position_id_fallback_to_name(self):
        node = {"id": None, "properties": {"name": "Dev"}}
        result = position_item(node)
        assert result["position_id"] == "Dev"

    def test_skills_required_preserved(self):
        node = {"id": "pos-1", "properties": {"name": "Dev", "skills_required": ["Python", "Go"]}}
        result = position_item(node)
        assert result["skills_required"] == ["Python", "Go"]


# ── graph_serializers: skill_item ────────────────────────────────────────


class TestSkillItem:
    def test_basic_no_rel(self):
        node = {"id": "s-1", "properties": {"name": "Python", "category": "hard_skill", "source_count": 5}}
        result = skill_item(node)
        assert result["skill_id"] == "s-1"
        assert result["name"] == "Python"
        assert result["category"] == "hard_skill"
        assert result["importance"] == "bonus"
        assert result["confidence"] == 1.0
        assert result["trend"] == "stable"

    def test_with_required_rel(self):
        node = {"id": "s-1", "properties": {"name": "Python"}}
        rel = {"properties": {"level": "advanced", "required": True, "confidence": 0.9}}
        result = skill_item(node, rel)
        assert result["importance"] == "required"
        assert result["confidence"] == 0.9

    def test_skill_category_fallback_to_source_category(self):
        node = {"id": "s-1", "properties": {"name": "Python", "category": "Skill", "source_category": "soft_skill"}}
        result = skill_item(node)
        assert result["category"] == "soft_skill"

    def test_skill_category_default_hard_skill(self):
        node = {"id": "s-1", "properties": {"name": "Python"}}
        result = skill_item(node)
        assert result["category"] == "hard_skill"

    def test_none_rel(self):
        node = {"id": "s-1", "properties": {"name": "Python"}}
        result = skill_item(node, None)
        assert result["importance"] == "bonus"

    def test_rel_with_none_properties(self):
        node = {"id": "s-1", "properties": {"name": "Python"}}
        result = skill_item(node, {"properties": None})
        assert result["importance"] == "bonus"

    def test_skill_id_from_properties(self):
        node = {"id": "s-1", "properties": {"skill_id": "SK-100", "name": "Python"}}
        result = skill_item(node)
        assert result["skill_id"] == "SK-100"

    def test_source_count_from_props(self):
        node = {"id": "s-1", "properties": {"name": "Python", "source_count": 10}}
        result = skill_item(node)
        assert result["source_count"] == 10

    def test_trend_from_props(self):
        node = {"id": "s-1", "properties": {"name": "Python", "trend": "rising"}}
        result = skill_item(node)
        assert result["trend"] == "rising"


# ── graph_serializers: count_*_neo4j ─────────────────────────────────────


class TestCountNeo4j:
    @pytest.mark.asyncio
    async def test_count_positions_none_driver(self):
        assert await count_positions_neo4j(None) == 0

    @pytest.mark.asyncio
    async def test_count_skills_none_driver(self):
        assert await count_skills_neo4j(None) == 0

    @pytest.mark.asyncio
    async def test_count_edges_none_driver(self):
        assert await count_edges_neo4j(None) == 0

    @pytest.mark.asyncio
    async def test_count_positions_query_error(self):
        session = FakeAsyncSession(run_side_effect=Exception("connection lost"))
        driver = FakeDriver(session)
        assert await count_positions_neo4j(driver) == 0

    @pytest.mark.asyncio
    async def test_count_positions_success(self):
        result = FakeAsyncResult([{"cnt": 42}])
        session = FakeAsyncSession(run_side_effect=result)
        driver = FakeDriver(session)
        assert await count_positions_neo4j(driver) == 42

    @pytest.mark.asyncio
    async def test_count_positions_no_record(self):
        result = FakeAsyncResult([])
        session = FakeAsyncSession(run_side_effect=result)
        driver = FakeDriver(session)
        assert await count_positions_neo4j(driver) == 0


# ── graph_overview: _classify_tech_stack ─────────────────────────────────


class TestClassifyTechStack:
    def test_ai_keywords(self):
        assert _classify_tech_stack("", "AI Engineer") == "人工智能"
        assert _classify_tech_stack("", "机器学习工程师") == "人工智能"
        assert _classify_tech_stack("", "深度学习研究员 NLP") == "人工智能"

    def test_big_data_keywords(self):
        assert _classify_tech_stack("", "大数据开发") == "大数据"
        assert _classify_tech_stack("", "Spark工程师") == "大数据"

    def test_iot_keywords(self):
        assert _classify_tech_stack("", "物联网平台") == "物联网"
        assert _classify_tech_stack("", "IoT架构师") == "物联网"

    def test_cloud_devops_keywords(self):
        assert _classify_tech_stack("", "DevOps工程师") == "云计算/DevOps"
        assert _classify_tech_stack("", "Kubernetes运维") == "云计算/DevOps"

    def test_security_keywords(self):
        assert _classify_tech_stack("", "网络安全工程师") == "网络安全"
        assert _classify_tech_stack("", "渗透测试") == "网络安全"

    def test_smart_system_keywords(self):
        assert _classify_tech_stack("", "智能制造") == "智能系统"
        assert _classify_tech_stack("", "自动化工程师") == "智能系统"

    def test_fallback_other(self):
        assert _classify_tech_stack("", "产品经理") == "其他"
        assert _classify_tech_stack("金融", "分析师") == "其他"

    def test_industry_and_name_combined(self):
        assert _classify_tech_stack("人工智能", "研究员") == "人工智能"

    def test_case_insensitive(self):
        assert _classify_tech_stack("", "ai engineer") == "人工智能"
        assert _classify_tech_stack("", "DOCKER专家") == "云计算/DevOps"


# ── graph_overview: _classify_level ──────────────────────────────────────


class TestClassifyLevel:
    def test_junior_from_props(self):
        assert _classify_level("Dev", {"level": "初级"}) == "初级"
        assert _classify_level("Dev", {"level": "junior"}) == "初级"
        assert _classify_level("Dev", {"level": "entry"}) == "初级"

    def test_senior_from_props(self):
        assert _classify_level("Dev", {"level": "高级"}) == "高级"
        assert _classify_level("Dev", {"level": "senior"}) == "高级"
        assert _classify_level("Dev", {"level": "expert"}) == "高级"
        assert _classify_level("Dev", {"level": "资深"}) == "高级"

    def test_mid_from_props(self):
        assert _classify_level("Dev", {"level": "中级"}) == "中级"
        assert _classify_level("Dev", {"level": "mid"}) == "中级"
        assert _classify_level("Dev", {"level": "intermediate"}) == "中级"

    def test_infer_senior_from_name(self):
        assert _classify_level("高级工程师", {}) == "高级"
        assert _classify_level("资深开发", {}) == "高级"
        assert _classify_level("架构师", {}) == "高级"
        assert _classify_level("首席技术官", {}) == "高级"

    def test_infer_junior_from_name(self):
        assert _classify_level("初级开发", {}) == "初级"
        assert _classify_level("实习生", {}) == "初级"
        assert _classify_level("助理工程师", {}) == "初级"

    def test_default_mid(self):
        assert _classify_level("开发工程师", {}) == "中级"

    def test_empty_level_prop(self):
        assert _classify_level("Dev", {"level": ""}) == "中级"

    def test_unknown_level_prop(self):
        assert _classify_level("Dev", {"level": "unknown"}) == "中级"


# ── graph_overview: fetch_overview_by_tech_stack ─────────────────────────


class TestFetchOverviewByTechStack:
    @pytest.mark.asyncio
    async def test_driver_exception_returns_empty(self):
        session = FakeAsyncSession(run_side_effect=Exception("neo4j down"))
        driver = FakeDriver(session)
        result = await fetch_overview_by_tech_stack(driver)
        assert result["domains"] == []
        assert result["connections"] == []
        assert result["total_positions"] == 0

    @pytest.mark.asyncio
    async def test_empty_graph(self):
        pos_result = FakeAsyncResult([])
        skill_result = FakeAsyncResult([])
        conn_result = FakeAsyncResult([])
        call_count = 0

        class MultiQuerySession(FakeAsyncSession):
            async def run(self, *args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return pos_result
                if call_count == 2:
                    return skill_result
                return conn_result

        driver = FakeDriver(MultiQuerySession())
        result = await fetch_overview_by_tech_stack(driver)
        assert result["total_positions"] == 0
        assert result["total_skills"] == 0
        assert result["domains"] == []

    @pytest.mark.asyncio
    async def test_with_positions_and_skills(self):
        class PosNode:
            element_id = "p-1"
            labels = ["Position"]

            def __iter__(self):
                return iter({"name": "AI Engineer", "industry": "人工智能"}.items())

        pos_result = FakeAsyncResult([{"p": PosNode()}])
        skill_result = FakeAsyncResult(
            [{"pos_name": "AI Engineer", "pos_industry": "人工智能", "skills": ["Python", "TensorFlow"]}]
        )
        conn_result = FakeAsyncResult([])
        call_count = 0

        class MultiQuerySession(FakeAsyncSession):
            async def run(self, *args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return pos_result
                if call_count == 2:
                    return skill_result
                return conn_result

        driver = FakeDriver(MultiQuerySession())
        result = await fetch_overview_by_tech_stack(driver)
        assert result["total_positions"] == 1
        assert result["total_skills"] == 2
        assert len(result["domains"]) == 1
        assert result["domains"][0]["name"] == "人工智能"

    @pytest.mark.asyncio
    async def test_null_node_skipped(self):
        pos_result = FakeAsyncResult([{"p": None}])
        skill_result = FakeAsyncResult([])
        conn_result = FakeAsyncResult([])
        call_count = 0

        class MultiQuerySession(FakeAsyncSession):
            async def run(self, *args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return pos_result
                if call_count == 2:
                    return skill_result
                return conn_result

        driver = FakeDriver(MultiQuerySession())
        result = await fetch_overview_by_tech_stack(driver)
        assert result["total_positions"] == 0


# ── graph_overview: fetch_overview_by_level ──────────────────────────────


class TestFetchOverviewByLevel:
    @pytest.mark.asyncio
    async def test_driver_exception_returns_empty(self):
        session = FakeAsyncSession(run_side_effect=Exception("neo4j down"))
        driver = FakeDriver(session)
        result = await fetch_overview_by_level(driver)
        assert result["domains"] == []
        assert result["total_positions"] == 0

    @pytest.mark.asyncio
    async def test_with_positions(self):
        class SeniorNode:
            element_id = "p-1"
            labels = ["Position"]

            def __iter__(self):
                return iter({"name": "高级工程师", "level": "高级"}.items())

        pos_result = FakeAsyncResult([{"p": SeniorNode()}])
        skill_result = FakeAsyncResult(
            [{"pos_name": "高级工程师", "pos_level": "高级", "skills": ["Python"]}]
        )
        call_count = 0

        class MultiQuerySession(FakeAsyncSession):
            async def run(self, *args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return pos_result
                return skill_result

        driver = FakeDriver(MultiQuerySession())
        result = await fetch_overview_by_level(driver)
        assert result["total_positions"] == 1
        assert result["total_skills"] == 1
        # Evolution connections always present
        assert len(result["connections"]) == 2
        assert result["connections"][0]["type"] == "EVOLVES_TO"

    @pytest.mark.asyncio
    async def test_evolution_connections_always_present(self):
        pos_result = FakeAsyncResult([])
        skill_result = FakeAsyncResult([])
        call_count = 0

        class MultiQuerySession(FakeAsyncSession):
            async def run(self, *args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return pos_result
                return skill_result

        driver = FakeDriver(MultiQuerySession())
        result = await fetch_overview_by_level(driver)
        # Even with no data, evolution connections are hardcoded
        assert len(result["connections"]) == 2


# ── graph_sync: sync_from_pipeline ───────────────────────────────────────


class TestSyncFromPipeline:
    @pytest.mark.asyncio
    async def test_no_driver_returns_error(self):
        with patch("app.services.resources.resources") as mock_res:
            mock_res.neo4j_driver = None
            result = await sync_from_pipeline("run-1")
            assert result["synced"] is False
            assert result["error"] == "neo4j_driver_unavailable"

    @pytest.mark.asyncio
    async def test_inline_mode_empty_lists(self):
        session = FakeAsyncSession()
        driver = FakeDriver(session)

        with patch("app.services.resources.resources") as mock_res:
            mock_res.neo4j_driver = driver
            result = await sync_from_pipeline("run-1", new_skills=[], new_edges=[], new_positions=[])
            assert result["synced"] is True
            assert result["count"] == 0
            assert result["nodes"] == 0
            assert result["edges"] == 0

    @pytest.mark.asyncio
    async def test_inline_mode_with_positions(self):
        session = FakeAsyncSession()
        driver = FakeDriver(session)

        with patch("app.services.resources.resources") as mock_res:
            mock_res.neo4j_driver = driver
            result = await sync_from_pipeline(
                "run-1",
                new_positions=[{"name": "Dev", "industry": "IT"}],
            )
            assert result["synced"] is True
            assert result["nodes"] == 1
            assert result["edges"] == 0

    @pytest.mark.asyncio
    async def test_inline_mode_with_skills(self):
        session = FakeAsyncSession()
        driver = FakeDriver(session)

        with patch("app.services.resources.resources") as mock_res:
            mock_res.neo4j_driver = driver
            result = await sync_from_pipeline(
                "run-1",
                new_skills=[{"name": "Python", "category": "hard_skill"}],
            )
            assert result["synced"] is True
            assert result["nodes"] == 1

    @pytest.mark.asyncio
    async def test_inline_mode_with_edges(self):
        session = FakeAsyncSession()
        driver = FakeDriver(session)

        with patch("app.services.resources.resources") as mock_res:
            mock_res.neo4j_driver = driver
            result = await sync_from_pipeline(
                "run-1",
                new_edges=[{"position_name": "Dev", "skill_name": "Python", "level": "熟悉", "required": True}],
            )
            assert result["synced"] is True
            assert result["edges"] == 1

    @pytest.mark.asyncio
    async def test_inline_mode_position_error_continues(self):
        call_count = 0

        class ErrorThenOkSession(FakeAsyncSession):
            async def run(self, *args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise Exception("write failed")
                return FakeAsyncResult([])

        driver = FakeDriver(ErrorThenOkSession())

        with patch("app.services.resources.resources") as mock_res:
            mock_res.neo4j_driver = driver
            result = await sync_from_pipeline(
                "run-1",
                new_positions=[{"name": "Bad"}],
                new_skills=[{"name": "Python", "category": "hard_skill"}],
            )
            assert result["synced"] is False  # errors present
            assert len(result["errors"]) == 1
            assert result["nodes"] == 1  # skill still counted

    @pytest.mark.asyncio
    async def test_inline_mode_session_error(self):
        # Session itself raises on __aenter__ — the outer try/except catches it
        class BrokenSession:
            async def __aenter__(self):
                raise Exception("session error")

            async def __aexit__(self, *args):
                return False

        driver = FakeDriver(BrokenSession())

        with patch("app.services.resources.resources") as mock_res:
            mock_res.neo4j_driver = driver
            result = await sync_from_pipeline("run-1", new_positions=[{"name": "Dev"}])
            assert result["synced"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_db_query_mode_no_extraction_data(self):
        session = FakeAsyncSession()
        driver = FakeDriver(session)

        with patch("app.services.resources.resources") as mock_res:
            mock_res.neo4j_driver = driver
            # extraction_data is not None but empty position_name
            result = await sync_from_pipeline("run-1", extraction_data={})
            # Should go through _sync_via_graph_writer path
            # With no position_name, no extractions built, but pg_sessionmaker may be None
            assert "synced" in result

    @pytest.mark.asyncio
    async def test_db_query_mode_with_extraction_data(self):
        session = FakeAsyncSession()
        driver = FakeDriver(session)
        mock_batch = AsyncMock(return_value=[{"nodes_touched": 5, "relationships_touched": 3}])

        with (
            patch("app.services.resources.resources") as mock_res,
            patch("app.core.extraction.graph_writer.batch_write_extractions", mock_batch),
        ):
            mock_res.neo4j_driver = driver
            mock_res.pg_sessionmaker = None
            extraction_data = {
                "position_name": "AI Engineer",
                "industry": "人工智能",
                "skills": [
                    {"name": "Python", "category": "hard_skill", "proficiency": "精通", "importance": "required"},
                    {"name": "SQL", "category": "hard_skill", "proficiency": "熟悉", "importance": "bonus"},
                ],
            }
            result = await sync_from_pipeline("run-1", extraction_data=extraction_data)
            assert result["synced"] is True
            assert result["nodes_written"] == 5
            assert result["edges_written"] == 3
            assert result["extractions_processed"] == 1

    @pytest.mark.asyncio
    async def test_db_query_mode_with_target_position(self):
        session = FakeAsyncSession()
        driver = FakeDriver(session)
        mock_batch = AsyncMock(return_value=[{"nodes_touched": 10, "relationships_touched": 6}])

        with (
            patch("app.services.resources.resources") as mock_res,
            patch("app.core.extraction.graph_writer.batch_write_extractions", mock_batch),
        ):
            mock_res.neo4j_driver = driver
            mock_res.pg_sessionmaker = None
            extraction_data = {
                "position_name": "AI Engineer",
                "industry": "人工智能",
                "skills": [{"name": "Python", "category": "hard_skill", "proficiency": "精通", "importance": "required"}],
            }
            result = await sync_from_pipeline(
                "run-1",
                extraction_data=extraction_data,
                target_position="ML Engineer",
            )
            # Should create 2 extractions: one for AI Engineer, one for ML Engineer
            assert result["synced"] is True
            assert result["extractions_processed"] == 2

    @pytest.mark.asyncio
    async def test_db_query_mode_graph_writer_failure(self):
        session = FakeAsyncSession()
        driver = FakeDriver(session)
        mock_batch = AsyncMock(side_effect=Exception("write failed"))

        with (
            patch("app.services.resources.resources") as mock_res,
            patch("app.core.extraction.graph_writer.batch_write_extractions", mock_batch),
        ):
            mock_res.neo4j_driver = driver
            mock_res.pg_sessionmaker = None
            extraction_data = {
                "position_name": "Dev",
                "skills": [{"name": "Python", "category": "hard_skill", "importance": "required"}],
            }
            result = await sync_from_pipeline("run-1", extraction_data=extraction_data)
            assert result["synced"] is False
            assert "error" in result
