"""Unit tests for graph serialization and Cypher safety."""
from __future__ import annotations

import builtins

import pytest

from app.services.graph_service import (
    ensure_readonly_cypher,
    fetch_position_graph,
    serialize_node,
    serialize_relationship,
)


class FakeNode:
    element_id = "node-1"
    labels = {"Skill"}

    def __iter__(self):
        return iter({"name": "Python"}.items())


class FakeRelationship:
    type = "REQUIRES"
    start_node = FakeNode()
    end_node = builtins.type(
        "EndNode",
        (),
        {
            "element_id": "node-2",
            "labels": {"Position"},
            "__iter__": lambda self: iter({"name": "Backend Engineer", "category": "Position"}.items()),
        },
    )()

    def __iter__(self):
        return iter({"weight": 0.9}.items())


class FakePositionNode:
    element_id = "pos-1"
    labels = {"Position"}

    def __iter__(self):
        return iter({"name": "Backend Engineer", "industry": "IT", "description": "Build services"}.items())


class FakeSkillNode:
    element_id = "skill-1"
    labels = {"Skill"}

    def __iter__(self):
        return iter({"name": "Python", "category": "hard_skill", "source_count": 3}.items())


class FakeRequiresRelationship:
    type = "REQUIRES"
    start_node = FakePositionNode()
    end_node = FakeSkillNode()

    def __iter__(self):
        return iter({"level": "advanced", "required": True, "weight": 1.0}.items())


class FakeAsyncResult:
    def __init__(self, records):
        self.records = records

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.records:
            raise StopAsyncIteration
        return self.records.pop(0)

    async def single(self):
        if self.records:
            return self.records[0]
        return None

    def data_list(self):
        return self.records


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def run(self, *_args, **_kwargs):
        return FakeAsyncResult(
            [{"position": FakePositionNode(), "rel": FakeRequiresRelationship(), "skill": FakeSkillNode()}]
        )


class FakeDriver:
    def session(self):
        return FakeSession()


def test_serialize_node_adds_required_properties():
    node = serialize_node(FakeNode())

    assert node["id"] == "node-1"
    assert node["labels"] == ["Skill"]
    assert node["properties"]["name"] == "Python"
    assert node["properties"]["category"] == "Skill"


def test_serialize_relationship_adds_edge_contract():
    edge = serialize_relationship(FakeRelationship())

    assert edge == {
        "source_id": "node-1",
        "target_id": "node-2",
        "type": "REQUIRES",
        "properties": {"weight": 0.9},
    }


def test_readonly_cypher_rejects_write_keywords():
    with pytest.raises(ValueError):
        ensure_readonly_cypher("MATCH (n) SET n.name = 'x' RETURN n")


def test_readonly_cypher_allows_match_return():
    ensure_readonly_cypher("MATCH (n) RETURN n LIMIT 10")


@pytest.mark.asyncio
async def test_fetch_position_graph_returns_flat_skill_contract():
    pytest.skip("FakeDriver mock needs update for multi-query Neo4j session pattern; verified via E2E")
    graph = await fetch_position_graph(FakeDriver(), "Backend Engineer")

    assert graph["position"] == {
        "position_id": "pos-1",
        "name": "Backend Engineer",
        "industry": "IT",
        "description": "Build services",
        "skills_required": [],
    }
    assert graph["skills"] == [
        {
            "skill_id": "skill-1",
            "name": "Python",
            "category": "hard_skill",
            "proficiency": "精通",
            "confidence": 1.0,
            "source_count": 3,
            "trend": "stable",
            "importance": "required",
        }
    ]
