"""Stage 3 graph triple ingestion tests."""
from __future__ import annotations

import pytest

from app.core.extraction.graph_writer import (
    NODE_POSITION,
    NODE_SKILL,
    NODE_TOOL,
    REL_BELONGS_TO,
    REL_PREREQUISITE,
    REL_REQUIRES,
    REL_USES,
    build_triples_from_extraction,
    merge_triple,
)


def test_build_triples_from_extraction_maps_core_ontology_edges():
    extraction = {
        "position_name": "AI 后端工程师",
        "industry": "新一代信息技术",
        "required_skills": [
            {"name": "Python", "level": "advanced", "category": "hard_skill"},
            {"name": "Docker", "level": "intermediate", "category": "tool"},
        ],
        "preferred_skills": [{"name": "Neo4j", "level": "intermediate"}],
        "prerequisites": [{"skill": "Deep Learning", "prerequisite": "Machine Learning", "strength": 0.8}],
    }

    triples = build_triples_from_extraction(extraction)
    keys = {(t.source.label, t.source.name, t.relationship, t.target.label, t.target.name) for t in triples}

    assert (NODE_POSITION, "AI 后端工程师", REL_REQUIRES, NODE_SKILL, "Python") in keys
    assert (NODE_POSITION, "AI 后端工程师", REL_USES, NODE_TOOL, "Docker") in keys
    assert (NODE_POSITION, "AI 后端工程师", REL_REQUIRES, NODE_SKILL, "Neo4j") in keys
    assert (NODE_POSITION, "AI 后端工程师", REL_BELONGS_TO, "Industry", "新一代信息技术") in keys
    assert (NODE_SKILL, "Deep Learning", REL_PREREQUISITE, NODE_SKILL, "Machine Learning") in keys

    python_requires = next(t for t in triples if t.relationship == REL_REQUIRES and t.target.name == "Python")
    assert python_requires.properties["required"] is True
    assert python_requires.properties["level"] == "advanced"


def test_build_triples_from_extraction_rejects_missing_position_name():
    with pytest.raises(ValueError):
        build_triples_from_extraction({"required_skills": ["Python"]})


class FakeNeo4jResult:
    async def single(self):
        return {"source": {"name": "Backend"}, "rel": {"weight": 1.0}, "target": {"name": "Python"}}


class FakeNeo4jSession:
    def __init__(self):
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def run(self, query, **params):
        self.calls.append((query, params))
        return FakeNeo4jResult()


class FakeNeo4jDriver:
    def __init__(self):
        self.session_obj = FakeNeo4jSession()

    def session(self):
        return self.session_obj


@pytest.mark.asyncio
async def test_merge_triple_uses_validated_labels_and_parameterized_properties():
    triple = build_triples_from_extraction(
        {"position_name": "Backend", "required_skills": [{"name": "Python", "level": "advanced"}]}
    )[0]
    driver = FakeNeo4jDriver()

    result = await merge_triple(driver, triple)

    query, params = driver.session_obj.calls[0]
    assert "MERGE (source:Position {name: $source_name})" in query
    assert "MERGE (source)-[rel:REQUIRES]->(target)" in query
    assert params["source_name"] == "Backend"
    assert params["target_name"] == "Python"
    assert params["rel_props"]["level"] == "advanced"
    assert result["relationship"] == {"weight": 1.0}
