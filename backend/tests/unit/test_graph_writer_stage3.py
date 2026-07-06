"""Stage 3 graph triple ingestion tests."""
from __future__ import annotations

import pytest

from app.core.extraction.graph_writer import (
    NODE_POSITION,
    NODE_SKILL,
    NODE_TOOL,
    REL_BELONGS_TO,
    REL_EVOLVES_TO,
    REL_PREREQUISITE,
    REL_RECOMMENDED_FOR,
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
        "prerequisites": [{"skill": "Machine Learning", "required_by": "Deep Learning", "strength": 0.8}],
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
    assert python_requires.target.properties["proficiency"] == "精通"
    assert python_requires.target.properties["source_count"] == 1
    assert python_requires.target.properties["trend"] == "stable"


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
    assert params["target_props"]["proficiency"] == "精通"
    assert params["target_count_increment"] == 1
    assert params["rel_props"]["level"] == "advanced"
    assert result["relationship"] == {"weight": 1.0}


def test_build_triples_from_extraction_handles_tools_as_dicts():
    """Tools from prompts are dicts with name/category, not plain strings."""
    extraction = {
        "position_name": "DevOps Engineer",
        "tools": [
            {"name": "Docker", "category": "devops"},
            {"name": "VS Code", "category": "ide"},
        ],
    }
    triples = build_triples_from_extraction(extraction)
    tool_triples = [t for t in triples if t.relationship == REL_USES]
    assert len(tool_triples) == 2
    tool_names = {t.target.name for t in tool_triples}
    assert tool_names == {"Docker", "VS Code"}
    # Verify category is preserved on the Tool node
    docker_triple = next(t for t in tool_triples if t.target.name == "Docker")
    assert docker_triple.target.properties.get("category") == "devops"


def test_build_triples_from_extraction_handles_tools_as_strings():
    """Tools may also be plain strings for backward compatibility."""
    extraction = {
        "position_name": "Backend Engineer",
        "tools": ["Git", "Jenkins"],
    }
    triples = build_triples_from_extraction(extraction)
    tool_triples = [t for t in triples if t.relationship == REL_USES]
    assert len(tool_triples) == 2
    tool_names = {t.target.name for t in tool_triples}
    assert tool_names == {"Git", "Jenkins"}


def test_build_triples_from_extraction_handles_learning_resources_with_for_skill():
    """Learning resources from prompts use 'for_skill' field."""
    extraction = {
        "position_name": "Python Developer",
        "learning_resources": [
            {"title": "FastAPI官方文档", "type": "docs", "for_skill": "FastAPI"},
            {"title": "Python Cookbook", "type": "book", "for_skill": "Python"},
        ],
    }
    triples = build_triples_from_extraction(extraction)
    lr_triples = [t for t in triples if t.relationship == REL_RECOMMENDED_FOR]
    assert len(lr_triples) == 2
    # Check that LearningResource nodes are created
    lr_names = {t.source.name for t in lr_triples}
    assert "FastAPI官方文档" in lr_names
    assert "Python Cookbook" in lr_names
    # Check target skills
    target_names = {t.target.name for t in lr_triples}
    assert "FastAPI" in target_names
    assert "Python" in target_names


def test_build_triples_from_extraction_handles_prerequisites_with_required_by():
    """Prerequisites from prompts use 'skill' (prereq) and 'required_by' (dependent)."""
    extraction = {
        "position_name": "ML Engineer",
        "prerequisites": [
            {"skill": "Python", "required_by": "Django", "strength": 0.9},
        ],
    }
    triples = build_triples_from_extraction(extraction)
    prereq_triples = [t for t in triples if t.relationship == REL_PREREQUISITE]
    assert len(prereq_triples) == 1
    # Django -[PREREQUISITE]-> Python (Django requires Python)
    t = prereq_triples[0]
    assert t.source.name == "Django"
    assert t.target.name == "Python"
    assert t.properties["strength"] == 0.9


def test_build_triples_from_extraction_handles_evolves_to():
    """evolves_to creates Position->Position EVOLVES_TO relationships."""
    extraction = {
        "position_name": "Junior Developer",
        "evolves_to": ["Senior Developer", "Tech Lead"],
    }
    triples = build_triples_from_extraction(extraction)
    evo_triples = [t for t in triples if t.relationship == REL_EVOLVES_TO]
    assert len(evo_triples) == 2
    target_names = {t.target.name for t in evo_triples}
    assert target_names == {"Senior Developer", "Tech Lead"}
    # Source should always be the original position
    assert all(t.source.name == "Junior Developer" for t in evo_triples)
