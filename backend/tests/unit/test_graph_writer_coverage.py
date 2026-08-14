"""Coverage tests for app.core.extraction.graph_writer.

Covers pure helpers and async Neo4j functions using FakeDriver mocks.
Mock shape copied from tests/unit/test_graph_services.py.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from neo4j.exceptions import Neo4jError

from app.config import settings
from app.core.extraction.graph_writer import (
    NODE_CERTIFICATE,
    NODE_INDUSTRY,
    NODE_KNOWLEDGE_AREA,
    REL_APPLIES_TO,
    REL_BELONGS_TO,
    REL_CERTIFIES,
    REL_EVOLVES_TO,
    REL_PREREQUISITE,
    REL_RECOMMENDED_FOR,
    REL_REQUIRES,
    REL_USES,
    GraphConfig,
    GraphTriple,
    _append_unique,
    _clean_properties,
    _node_merge_properties,
    _node_ref,
    _skill_entry_confidence,
    _skill_entry_level,
    _skill_entry_source_count,
    _skill_entry_trend,
    _skill_entry_years,
    _skill_node_properties,
    _skill_source_count_increment,
    _validate_node_label,
    _validate_relationship_type,
    batch_write_extractions,
    build_triples_from_extraction,
    create_requires_relationship,
    get_all_skills,
    get_position_skills,
    merge_position,
    merge_skill,
    merge_triple,
    skill_entry_category,
    skill_entry_name,
    write_extraction_to_graph,
    write_triples_to_graph,
)
from app.exceptions import GraphProjectionError

# ── Mock helpers (from tests/unit/test_graph_services.py) ──────────────────


class FakeAsyncResult:
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
    def __init__(self, run_side_effect=None):
        self._run_side_effect = run_side_effect
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def run(self, *args, **kwargs):
        self.calls.append((args, kwargs))
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


def _universal_session():
    """Session returning appropriate records for any graph_writer query type."""
    def smart_run(*args, **kwargs):
        q = args[0] if args else ""
        if "MERGE (p:Position" in q:
            return FakeAsyncResult([{"p": {"name": kwargs.get("name", "Dev")}}])
        if "MERGE (s:Skill" in q:
            return FakeAsyncResult([{"s": {"name": kwargs.get("name", "Python")}}])
        if "MERGE (p)-[r:REQUIRES" in q:
            return FakeAsyncResult([{"r": {"weight": 1.0}}])
        return FakeAsyncResult([{"source": {"name": "X"}, "rel": {"w": 1.0}, "target": {"name": "Y"}}])
    return FakeAsyncSession(run_side_effect=smart_run)


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch):
    """Make tenacity async-retry waits instant."""
    async def _instant(*a, **kw):
        return None
    monkeypatch.setattr(asyncio, "sleep", _instant)


# ── Pure helper tests ──────────────────────────────────────────────────────


class TestPureHelpers:
    def test_validate_node_label(self):
        for lbl in ("Position", "Skill", "Tool", "KnowledgeArea", "Industry", "Certificate", "LearningResource", "Domain"):
            assert _validate_node_label(lbl) == lbl
        with pytest.raises(ValueError, match="Unsupported graph node label"):
            _validate_node_label("Foo")

    def test_validate_relationship_type(self):
        for rel in (REL_REQUIRES, REL_PREREQUISITE, REL_EVOLVES_TO, REL_USES, REL_BELONGS_TO, REL_CERTIFIES, REL_RECOMMENDED_FOR, REL_APPLIES_TO):
            assert _validate_relationship_type(rel) == rel
        with pytest.raises(ValueError, match="Unsupported graph relationship"):
            _validate_relationship_type("FOO")

    def test_clean_properties(self):
        assert _clean_properties({"a": 1, "b": None, "c": "x"}) == {"a": 1, "c": "x"}
        assert _clean_properties(None) == {}
        assert _clean_properties({}) == {}

    def test_node_ref(self):
        ref = _node_ref("Skill", "Python", {"category": "hard_skill"})
        assert ref.label == "Skill"
        assert ref.name == "Python"
        assert ref.properties["name"] == "Python"
        assert ref.properties["category"] == "hard_skill"
        assert _node_ref("Position", "  Dev  ").name == "Dev"
        ref2 = _node_ref("Tool", "Git")
        assert ref2.properties["name"] == "Git"
        # category is NOT auto-set to label anymore — only explicit category is kept
        assert "category" not in ref2.properties
        with pytest.raises(ValueError, match="cannot be empty"):
            _node_ref("Position", "  ")

    def test_skill_entry_name(self):
        assert skill_entry_name({"name": "Python"}) == "Python"
        assert skill_entry_name({"skill": "Go"}) == "Go"
        assert skill_entry_name({"title": "Rust"}) == "Rust"
        assert skill_entry_name("Java") == "Java"
        assert skill_entry_name({}) == ""

    def test_skill_entry_category(self):
        assert skill_entry_category({"category": "Tool"}) == "tool"
        assert skill_entry_category({"name": "X"}) == "skill"
        assert skill_entry_category({"name": "X"}, default="general") == "general"
        assert skill_entry_category("Python") == "skill"

    def test_skill_entry_level(self):
        assert _skill_entry_level({"level": "advanced"}) == "advanced"
        assert _skill_entry_level({"proficiency": "beginner"}) == "beginner"
        assert _skill_entry_level({}) == "intermediate"
        assert _skill_entry_level("Python") == "intermediate"

    def test_skill_entry_years(self):
        assert _skill_entry_years({"years_of_experience": 5}) == 5.0
        assert _skill_entry_years({}) is None
        assert _skill_entry_years("Python") is None

    def test_skill_entry_confidence(self):
        assert _skill_entry_confidence({"confidence": 0.9}) == 0.9
        assert _skill_entry_confidence({}) == 0.8
        assert _skill_entry_confidence("Python") == 0.8

    def test_skill_entry_source_count(self):
        assert _skill_entry_source_count({"source_count": 3}) == 3
        assert _skill_entry_source_count({}) == 1
        assert _skill_entry_source_count("Python") == 1

    def test_skill_entry_trend(self):
        assert _skill_entry_trend({"trend": "rising"}) == "rising"
        assert _skill_entry_trend({"trend": "declining"}) == "declining"
        assert _skill_entry_trend({"trend": "foo"}) == "stable"
        assert _skill_entry_trend({}) == "stable"
        assert _skill_entry_trend("Python") == "stable"

    def test_skill_node_properties(self):
        props = _skill_node_properties({"confidence": 0.9, "source_count": 3, "trend": "rising"}, "hard_skill", "advanced")
        assert props == {"category": "hard_skill", "source_category": "hard_skill", "proficiency": "精通", "confidence": 0.9, "source_count": 3, "trend": "rising"}

    def test_node_merge_properties(self):
        ref = _node_ref("Skill", "Python", {"source_count": 3, "category": "hard_skill"})
        assert "source_count" not in _node_merge_properties(ref)
        ref2 = _node_ref("Position", "Dev", {"source_count": 3})
        assert _node_merge_properties(ref2)["source_count"] == 3

    def test_skill_source_count_increment(self):
        assert _skill_source_count_increment(_node_ref("Skill", "Python", {"source_count": 5})) == 5
        assert _skill_source_count_increment(_node_ref("Skill", "Python")) == 0
        assert _skill_source_count_increment(_node_ref("Position", "Dev")) == 0

    def test_append_unique(self):
        def t(s="Dev", tgt="Python"):
            return GraphTriple(_node_ref("Position", s), REL_REQUIRES, _node_ref("Skill", tgt))
        triples = []
        _append_unique(triples, t())
        _append_unique(triples, t())  # duplicate
        _append_unique(triples, t(tgt="Go"))  # different target
        assert len(triples) == 2


# ── build_triples_from_extraction edge cases ───────────────────────────────


class TestBuildTriples:
    def test_position_from_name_and_empty(self):
        assert build_triples_from_extraction({"name": "Backend"}) == []
        assert build_triples_from_extraction({"position_name": "Dev", "required_skills": []}) == []

    def test_empty_skill_name_skipped(self):
        triples = build_triples_from_extraction({"position_name": "Dev", "required_skills": [{"name": ""}, {"name": "Python"}]})
        assert len(triples) == 1

    def test_certificate_with_certifies(self):
        triples = build_triples_from_extraction({"position_name": "Dev", "required_skills": [{"name": "AWS", "category": "certificate", "certifies": "Cloud"}]})
        cert = [t for t in triples if t.relationship == REL_CERTIFIES]
        assert len(cert) == 1
        assert cert[0].source.label == NODE_CERTIFICATE
        assert cert[0].target.name == "Cloud"

    def test_certificate_without_certifies(self):
        triples = build_triples_from_extraction({"position_name": "Dev", "required_skills": [{"name": "AWS", "category": "certificate"}]})
        assert len(triples) == 0

    def test_knowledge_areas_with_industry(self):
        triples = build_triples_from_extraction({"position_name": "Dev", "industry": "IT", "knowledge_areas": ["Algorithms"]})
        ka = [t for t in triples if t.relationship == REL_APPLIES_TO]
        assert len(ka) == 1
        assert ka[0].source.label == NODE_KNOWLEDGE_AREA
        assert ka[0].target.label == NODE_INDUSTRY

    def test_knowledge_areas_without_industry(self):
        triples = build_triples_from_extraction({"position_name": "Dev", "knowledge_areas": ["Algorithms"]})
        assert not [t for t in triples if t.relationship == REL_APPLIES_TO]

    def test_empty_tool_name_skipped(self):
        triples = build_triples_from_extraction({"position_name": "Dev", "tools": [{"name": ""}, {"name": "Git"}]})
        assert len([t for t in triples if t.relationship == REL_USES]) == 1

    def test_prereq_edge_cases(self):
        for prereqs, expected in [(["string"], 0), ([{"skill": ""}], 0), ([{"required_by": ""}], 0), ([{"prerequisite": "Python", "skill_name": "Django"}], 1)]:
            triples = build_triples_from_extraction({"position_name": "Dev", "prerequisites": prereqs})
            assert len([t for t in triples if t.relationship == REL_PREREQUISITE]) == expected

    def test_resource_edge_cases(self):
        for resources, expected in [(["string"], 0), ([{"title": ""}], 0), ([{"for_skill": ""}], 0), ([{"name": "Book", "skill": "Python"}], 1)]:
            triples = build_triples_from_extraction({"position_name": "Dev", "learning_resources": resources})
            assert len([t for t in triples if t.relationship == REL_RECOMMENDED_FOR]) == expected

    def test_evolves_to_variants(self):
        triples = build_triples_from_extraction({"position_name": "Junior", "evolves_to": [{"position": "Senior", "similarity": 0.9, "evidence_count": 3}, "Tech Lead", {"position": ""}, ""]})
        evo = [t for t in triples if t.relationship == REL_EVOLVES_TO]
        assert len(evo) == 2
        assert {t.target.name for t in evo} == {"Senior", "Tech Lead"}
        d = next(t for t in evo if t.target.name == "Senior")
        assert d.properties["similarity"] == 0.9 and d.properties["evidence_count"] == 3
        s = next(t for t in evo if t.target.name == "Tech Lead")
        assert s.properties["similarity"] == 0.5

    def test_dedup_same_skill(self):
        triples = build_triples_from_extraction({"position_name": "Dev", "required_skills": [{"name": "Python"}], "preferred_skills": [{"name": "Python"}]})
        assert len([t for t in triples if t.relationship == REL_REQUIRES]) == 1


# ── GraphConfig ──────────────────────────────────────────────────────────────


class TestGraphConfig:
    def test_defaults_and_custom(self):
        cfg = GraphConfig()
        assert cfg.uri == settings.neo4j_uri
        assert cfg.user == settings.neo4j_user
        assert cfg.max_connection_pool_size == 50
        assert cfg.connection_timeout == 30
        c2 = GraphConfig(uri="bolt://x", user="u", password="p", max_connection_pool_size=10)
        assert c2.uri == "bolt://x" and c2.max_connection_pool_size == 10

    @pytest.mark.asyncio
    async def test_get_driver(self):
        mock_drv = AsyncMock()
        mock_drv.verify_connectivity = AsyncMock()
        mock_drv.close = AsyncMock()
        with patch("neo4j.AsyncGraphDatabase") as mock_cls:
            mock_cls.driver.return_value = mock_drv
            cfg = GraphConfig(uri="bolt://t", user="u", password="p")
            async with cfg.get_driver() as drv:
                assert drv is mock_drv
        mock_cls.driver.assert_called_once()
        mock_drv.verify_connectivity.assert_awaited_once()
        mock_drv.close.assert_awaited_once()


# ── Async Neo4j functions ───────────────────────────────────────────────────


class TestMergeTripleAndWrite:
    @pytest.mark.asyncio
    async def test_merge_triple_none_record(self):
        drv = FakeDriver(FakeAsyncSession(run_side_effect=FakeAsyncResult([])))
        tr = GraphTriple(_node_ref("Position", "Dev"), REL_REQUIRES, _node_ref("Skill", "Python"))
        with pytest.raises(ValueError, match="Failed to merge triple"):
            await merge_triple(drv, tr)

    @pytest.mark.asyncio
    async def test_merge_triple_neo4j_error(self):
        def raise_err(*a, **kw):
            raise Neo4jError("boom")
        drv = FakeDriver(FakeAsyncSession(run_side_effect=raise_err))
        tr = GraphTriple(_node_ref("Position", "Dev"), REL_REQUIRES, _node_ref("Skill", "Python"))
        with pytest.raises(Neo4jError):
            await merge_triple(drv, tr)

    @pytest.mark.asyncio
    async def test_write_triples_empty(self):
        assert await write_triples_to_graph(FakeDriver(FakeAsyncSession()), []) == {"triples_merged": 0, "nodes_touched": 0, "relationships_touched": 0}

    @pytest.mark.asyncio
    async def test_write_triples_multiple(self):
        rec = {"source": {"name": "Dev"}, "rel": {"w": 1.0}, "target": {"name": "Python"}}
        drv = FakeDriver(FakeAsyncSession(run_side_effect=FakeAsyncResult([rec])))
        t1 = GraphTriple(_node_ref("Position", "Dev"), REL_REQUIRES, _node_ref("Skill", "Python"))
        t2 = GraphTriple(_node_ref("Position", "Dev"), REL_REQUIRES, _node_ref("Skill", "Go"))
        s = await write_triples_to_graph(drv, [t1, t2])
        assert s["triples_merged"] == 2 and s["nodes_touched"] == 3 and s["relationships_touched"] == 2


class TestRetryFunctions:
    """merge_position, merge_skill, create_requires - all @retry decorated."""

    @pytest.mark.asyncio
    async def test_merge_position_success(self):
        drv = FakeDriver(FakeAsyncSession(run_side_effect=FakeAsyncResult([{"p": {"name": "Dev"}}])))
        assert (await merge_position(drv, {"name": "Dev", "experience_required": "3y"}))["name"] == "Dev"

    @pytest.mark.asyncio
    async def test_merge_position_position_name_fallback(self):
        drv = FakeDriver(FakeAsyncSession(run_side_effect=FakeAsyncResult([{"p": {"name": "P"}}])))
        await merge_position(drv, {"position_name": "P"})

    @pytest.mark.asyncio
    async def test_merge_position_none_record(self):
        drv = FakeDriver(FakeAsyncSession(run_side_effect=FakeAsyncResult([])))
        with pytest.raises(ValueError, match="Failed to merge Position"):
            await merge_position(drv, {"name": "Dev"})

    @pytest.mark.asyncio
    async def test_merge_position_error(self):
        def raise_err(*a, **kw):
            raise Neo4jError("boom")
        drv = FakeDriver(FakeAsyncSession(run_side_effect=raise_err))
        with pytest.raises(Neo4jError):
            await merge_position(drv, {"name": "Dev"})

    @pytest.mark.asyncio
    async def test_merge_skill_success(self):
        drv = FakeDriver(FakeAsyncSession(run_side_effect=FakeAsyncResult([{"s": {"name": "Python"}}])))
        assert (await merge_skill(drv, "Python", {"proficiency": "advanced", "source_count": 2}))["name"] == "Python"

    # Phase 19: 投影落 trust_score（§6.2 四因子）——断言 Cypher props 含 trust_score
    @pytest.mark.asyncio
    async def test_merge_skill_writes_trust_score(self):
        fake = FakeAsyncSession(run_side_effect=FakeAsyncResult([{"s": {"name": "Python"}}]))
        drv = FakeDriver(fake)
        await merge_skill(
            drv, "Python",
            {"source_count": 5, "confidence": 0.9, "proficiency": "advanced"},
        )
        # 断言传给 Cypher 的 props 含 trust_score（Fake record["s"] 只是模拟节点，不含属性）
        sent_props = fake.calls[0][1].get("props", {})
        assert "trust_score" in sent_props
        trust = float(sent_props["trust_score"])
        assert 0.0 <= trust <= 1.0
        # source=5→sqrt(0.5)≈0.707, conf=0.9, cross=1.0, time 缺省→0 → 0.3*.707+0.3*.9+0.25 = 0.737
        assert trust > 0.5

    @pytest.mark.asyncio
    async def test_merge_skill_no_metadata_still_writes_trust(self):
        fake = FakeAsyncSession(run_side_effect=FakeAsyncResult([{"s": {"name": "Go"}}]))
        drv = FakeDriver(fake)
        await merge_skill(drv, "Go", None)
        sent_props = fake.calls[0][1].get("props", {})
        assert "trust_score" in sent_props  # 无 metadata 也落 trust_score（兜底计算）
        assert 0.0 <= float(sent_props["trust_score"]) <= 1.0

    @pytest.mark.asyncio
    async def test_merge_skill_none_record(self):
        drv = FakeDriver(FakeAsyncSession(run_side_effect=FakeAsyncResult([])))
        with pytest.raises(ValueError, match="Failed to merge Skill"):
            await merge_skill(drv, "Python")

    @pytest.mark.asyncio
    async def test_merge_skill_error(self):
        drv = FakeDriver(FakeAsyncSession(run_side_effect=lambda *a, **kw: (_ for _ in ()).throw(Neo4jError("boom"))))
        with pytest.raises(Neo4jError):
            await merge_skill(drv, "Python")

    @pytest.mark.asyncio
    async def test_create_requires_success(self):
        drv = FakeDriver(FakeAsyncSession(run_side_effect=FakeAsyncResult([{"r": {"weight": 1.0}}])))
        assert (await create_requires_relationship(drv, "Dev", "Python", level="advanced"))["weight"] == 1.0

    @pytest.mark.asyncio
    async def test_create_requires_none_record(self):
        drv = FakeDriver(FakeAsyncSession(run_side_effect=FakeAsyncResult([])))
        with pytest.raises(ValueError, match="Failed to create REQUIRES"):
            await create_requires_relationship(drv, "Dev", "Python")

    @pytest.mark.asyncio
    async def test_create_requires_error(self):
        drv = FakeDriver(FakeAsyncSession(run_side_effect=lambda *a, **kw: (_ for _ in ()).throw(Neo4jError("boom"))))
        with pytest.raises(Neo4jError):
            await create_requires_relationship(drv, "Dev", "Python")


class TestWriteExtraction:
    @pytest.mark.asyncio
    async def test_full_flow(self):
        drv = FakeDriver(_universal_session())
        extraction = {"position_name": "Dev", "required_skills": [{"name": "Python", "level": "advanced"}], "preferred_skills": [{"name": "Go"}], "industry": "IT", "tools": [{"name": "Docker"}]}
        s = await write_extraction_to_graph(extraction, drv)
        assert s["positions_merged"] == 1 and s["skills_merged"] == 2 and s["requires_created"] == 2
        # d59ffed 后 industry 改为 Position 节点属性, 不再产生 BELONGS_TO 三元组;
        # triples = requires(2) + extended/tools(1)
        assert s["triples_merged"] == 3

    @pytest.mark.asyncio
    async def test_missing_position_skips(self):
        # Phase 17-03 (Fix B3): 缺失 position_name 静默跳过(不阻塞 batch),返回 skipped 标记。
        result = await write_extraction_to_graph({}, FakeDriver(FakeAsyncSession()))
        assert result["skipped"] is True
        assert result["reason"] == "missing_position_name"

    @pytest.mark.asyncio
    async def test_merge_position_failure(self):
        # Neo4j 错误被包装为域异常 GraphProjectionError(StarMapError 子类),供上层统一处理。
        drv = FakeDriver(FakeAsyncSession(run_side_effect=lambda *a, **kw: (_ for _ in ()).throw(Neo4jError("boom"))))
        with pytest.raises(GraphProjectionError):
            await write_extraction_to_graph({"position_name": "Dev"}, drv)

    @pytest.mark.asyncio
    async def test_merge_skill_failure_continues(self):
        cnt = 0
        def smart_run(*args, **kw):
            nonlocal cnt
            cnt += 1
            q = args[0] if args else ""
            if cnt == 1:
                return FakeAsyncResult([{"p": {"name": "Dev"}}])
            if "MERGE (s:Skill" in q:
                raise Neo4jError("skill err")
            return FakeAsyncResult([{"r": {"weight": 1.0}}])
        drv = FakeDriver(FakeAsyncSession(run_side_effect=smart_run))
        s = await write_extraction_to_graph({"position_name": "Dev", "required_skills": [{"name": "Python"}]}, drv)
        assert s["skills_merged"] == 0 and s["requires_created"] == 0

    @pytest.mark.asyncio
    async def test_empty_skill_name_skipped(self):
        drv = FakeDriver(_universal_session())
        s = await write_extraction_to_graph({"position_name": "Dev", "required_skills": [{"name": ""}, {"name": "Python"}]}, drv)
        assert s["skills_merged"] == 1

    @pytest.mark.asyncio
    async def test_create_requires_failure_continues(self):
        cnt = 0
        def smart_run(*args, **kw):
            nonlocal cnt
            cnt += 1
            q = args[0] if args else ""
            if "MERGE (p:Position" in q:
                return FakeAsyncResult([{"p": {"name": "Dev"}}])
            if "MERGE (s:Skill" in q:
                return FakeAsyncResult([{"s": {"name": "Python"}}])
            raise Neo4jError("requires err")
        drv = FakeDriver(FakeAsyncSession(run_side_effect=smart_run))
        s = await write_extraction_to_graph({"position_name": "Dev", "required_skills": [{"name": "Python"}]}, drv)
        assert s["skills_merged"] == 1 and s["requires_created"] == 0


class TestBatchAndQueries:
    @pytest.mark.asyncio
    async def test_batch_write(self):
        drv = FakeDriver(_universal_session())
        results = await batch_write_extractions([{"position_name": "Dev", "required_skills": [{"name": "Python"}]}, {"position_name": "QA", "required_skills": [{"name": "Selenium"}]}], drv)
        assert len(results) == 2 and all(r["positions_merged"] == 1 for r in results)

    @pytest.mark.asyncio
    async def test_get_position_skills(self):
        records = [{"skill_name": "Python", "level": "advanced", "required": True}, {"skill_name": "Go", "level": "beginner", "required": False}]
        drv = FakeDriver(FakeAsyncSession(run_side_effect=FakeAsyncResult(records)))
        r = await get_position_skills(drv, "Dev")
        assert len(r["required"]) == 1 and r["required"][0]["name"] == "Python"
        assert len(r["preferred"]) == 1 and r["preferred"][0]["name"] == "Go"

    @pytest.mark.asyncio
    async def test_get_position_skills_default_required(self):
        drv = FakeDriver(FakeAsyncSession(run_side_effect=FakeAsyncResult([{"skill_name": "Python", "level": "advanced"}])))
        r = await get_position_skills(drv, "Dev")
        assert len(r["required"]) == 1 and len(r["preferred"]) == 0

    @pytest.mark.asyncio
    async def test_get_all_skills(self):
        records = [
            {"name": "Python", "category": "hard_skill", "proficiency": "精通", "source_count": 5, "trend": "rising", "updated_at": "2024-01-01"},
            {"name": "Go", "category": None, "proficiency": None, "source_count": None, "trend": None},
        ]
        drv = FakeDriver(FakeAsyncSession(run_side_effect=FakeAsyncResult(records)))
        r = await get_all_skills(drv)
        assert len(r) == 2 and r[0]["name"] == "Python" and r[0]["source_count"] == 5
        assert r[1]["category"] == "hard_skill" and r[1]["proficiency"] == "熟悉"
        assert r[1]["source_count"] == 0 and r[1]["trend"] == "stable" and r[1]["updated_at"] == ""
