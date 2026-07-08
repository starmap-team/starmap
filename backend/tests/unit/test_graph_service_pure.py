"""Coverage boost tests for graph_service pure helper functions."""

from __future__ import annotations

from app.services.graph_service import (
    _position_item,
    _relationship_endpoint,
    _relationship_type,
    _skill_item,
)


class TestRelationshipType:
    def test_with_type_attr(self):
        class Rel:
            type = "REQUIRES"

        assert _relationship_type(Rel()) == "REQUIRES"

    def test_fallback_to_class_name(self):
        class CustomRel:
            pass

        assert _relationship_type(CustomRel()) == "CustomRel"


class TestRelationshipEndpoint:
    def test_from_node(self):
        class Node:
            element_id = "n-1"
            id = None

        class Rel:
            start_node = Node()
            start_node_node_id = None

        assert _relationship_endpoint(Rel(), "start_node") == "n-1"

    def test_from_node_id_attr(self):
        class Rel:
            start_node = None
            start_node_node_id = "fallback-1"

        assert _relationship_endpoint(Rel(), "start_node") == "fallback-1"

    def test_missing_returns_empty(self):
        class Rel:
            start_node = None

        assert _relationship_endpoint(Rel(), "start_node") == ""


class TestPositionItem:
    def test_basic(self):
        node = {
            "id": "pos-1",
            "properties": {
                "name": "Backend",
                "industry": "IT",
                "description": "Build APIs",
            },
        }
        result = _position_item(node)
        assert result["position_id"] == "pos-1"
        assert result["name"] == "Backend"
        assert result["industry"] == "IT"
        assert result["skills_required"] == []

    def test_empty_properties(self):
        node = {"id": "pos-1", "properties": None}
        result = _position_item(node)
        assert result["position_id"] == "pos-1"
        assert result["name"] == "pos-1"
        assert result["industry"] == ""


class TestSkillItem:
    def test_basic_no_rel(self):
        node = {
            "id": "s-1",
            "properties": {"name": "Python", "category": "hard_skill", "source_count": 5},
        }
        result = _skill_item(node)
        assert result["skill_id"] == "s-1"
        assert result["name"] == "Python"
        assert result["importance"] == "bonus"

    def test_with_required_rel(self):
        node = {"id": "s-1", "properties": {"name": "Python"}}
        rel = {
            "properties": {
                "level": "advanced",
                "required": True,
                "confidence": 0.9,
            }
        }
        result = _skill_item(node, rel)
        assert result["proficiency"] == "精通"
        assert result["importance"] == "required"
        assert result["confidence"] == 0.9

