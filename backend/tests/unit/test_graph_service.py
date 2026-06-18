"""Unit tests for graph serialization and Cypher safety."""
from __future__ import annotations

import builtins

import pytest

from app.services.graph_service import ensure_readonly_cypher, serialize_node, serialize_relationship


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
