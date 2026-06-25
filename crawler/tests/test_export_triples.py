"""Tests for crawler/scripts/export_triples.py."""
from __future__ import annotations

from crawler.scripts.export_triples import (
    extract_triples,
    triples_to_cypher,
)


class TestExtractTriples:
    def test_basic_extraction(self) -> None:
        records = [
            {
                "id": "abc-123",
                "job_title": "Python后端",
                "extracted_skills": {
                    "required_skills": [{"name": "Python", "level": "advanced"}],
                    "preferred_skills": [{"name": "Docker"}],
                },
                "confidence": 0.9,
                "status": "completed",
            },
        ]
        triples = extract_triples(records)
        assert len(triples) == 2
        # REQUIRES
        req = [t for t in triples if t["relationship"] == "REQUIRES"]
        assert len(req) == 2
        # Check required=True for required_skills
        python_triple = next(t for t in req if t["target"]["name"] == "Python")
        assert python_triple["properties"]["required"] is True
        assert python_triple["properties"]["level"] == "advanced"
        # Check required=False for preferred_skills
        docker_triple = next(t for t in req if t["target"]["name"] == "Docker")
        assert docker_triple["properties"]["required"] is False

    def test_tools_become_uses(self) -> None:
        records = [
            {
                "id": "abc-456",
                "job_title": "DevOps",
                "extracted_skills": {
                    "required_skills": [],
                    "preferred_skills": [],
                    "tools": [{"name": "Kubernetes"}],
                },
                "confidence": 0.85,
                "status": "completed",
            },
        ]
        triples = extract_triples(records)
        assert len(triples) == 1
        assert triples[0]["relationship"] == "USES"
        assert triples[0]["target"]["label"] == "Tool"
        assert triples[0]["target"]["name"] == "Kubernetes"

    def test_empty_skills(self) -> None:
        records = [
            {
                "id": "abc-789",
                "job_title": "Manager",
                "extracted_skills": {},
                "confidence": 0.5,
                "status": "completed",
            },
        ]
        triples = extract_triples(records)
        assert len(triples) == 0

    def test_dedup_across_records(self) -> None:
        records = [
            {
                "id": "1",
                "job_title": "Python后端",
                "extracted_skills": {"required_skills": [{"name": "Python"}]},
                "confidence": 0.9,
                "status": "completed",
            },
            {
                "id": "2",
                "job_title": "Python后端",
                "extracted_skills": {"required_skills": [{"name": "Python"}]},
                "confidence": 0.8,
                "status": "completed",
            },
        ]
        triples = extract_triples(records)
        # Same position + same skill = dedup
        assert len(triples) == 1

    def test_empty_job_title_skipped(self) -> None:
        records = [
            {
                "id": "1",
                "job_title": "",
                "extracted_skills": {"required_skills": [{"name": "Python"}]},
                "confidence": 0.9,
                "status": "completed",
            },
        ]
        triples = extract_triples(records)
        assert len(triples) == 0

    def test_empty_skill_name_skipped(self) -> None:
        records = [
            {
                "id": "1",
                "job_title": "Backend",
                "extracted_skills": {"required_skills": [{"unknown": "key"}]},
                "confidence": 0.9,
                "status": "completed",
            },
        ]
        triples = extract_triples(records)
        assert len(triples) == 0


class TestTriplesToCypher:
    def test_basic_cypher(self) -> None:
        triples = [
            {
                "source": {"label": "Position", "name": "Backend"},
                "relationship": "REQUIRES",
                "target": {"label": "Skill", "name": "Python"},
                "properties": {"required": True, "confidence": 0.9},
            },
        ]
        stmts = triples_to_cypher(triples)
        assert len(stmts) == 1
        assert "MERGE (s:Position" in stmts[0]
        assert "MERGE (t:Skill" in stmts[0]
        assert "REQUIRES" in stmts[0]
        assert "required: true" in stmts[0]

    def test_empty_triples(self) -> None:
        stmts = triples_to_cypher([])
        assert stmts == []
