"""Test matching scorer — Chroma degradation (M3 regression).

Phase 13 · 2026-07-27.
"""
from __future__ import annotations

import importlib

import pytest


def _reset_chroma_negative_cache():
    """Reload the scorer module to clear the _is_chroma_marked_unavailable flag."""
    import app.core.matching.scorer
    importlib.reload(app.core.matching.scorer)


def test_chroma_unavailable_degradation():
    """M3 regression: Chroma connection error must not 500 the match."""
    _reset_chroma_negative_cache()

    import chromadb as _real_chromadb
    from unittest.mock import patch

    from app.core.matching.scorer import score_skill_match

    with patch.object(_real_chromadb, "HttpClient", side_effect=Exception("Chroma unreachable")):
        target_skills = [
            {"skill": "Python", "category": "hard_skill", "proficiency": "熟悉", "importance": "required"},
            {"skill": "Docker", "category": "hard_skill", "proficiency": "熟悉", "importance": "required"},
        ]
        result = score_skill_match(target_skills=target_skills, person_skills=[
            {"name": "Python", "category": "hard_skill", "proficiency": "专家"},
            {"name": "Docker", "category": "hard_skill", "proficiency": "熟练"},
        ], threshold=0.6)
        assert "evaluated" in result, "score_skill_match must return 'evaluated' even when Chroma is down"
        assert len(result["evaluated"]) == 2, f"Expected 2 evaluated skills, got {len(result['evaluated'])}"
        matched = [e for e in result["evaluated"] if e["gap_level"] == "已掌握"]
        assert len(matched) >= 1, f"Expected at least 1 lexical match, got {matched}"
        # Each evaluated item should have a score
        for e in result["evaluated"]:
            assert isinstance(e.get("score"), (int, float)), f"Each evaluated item must have a score, got {e}"


def test_chroma_collection_missing_graceful():
    """M3 regression: Chroma get_collection 404 must not raise."""
    _reset_chroma_negative_cache()

    import chromadb as _real_chromadb
    from unittest.mock import MagicMock, patch

    from app.core.matching.scorer import score_skill_match

    mock_client = MagicMock()
    mock_client.get_collection.side_effect = Exception("Collection not found")
    with patch.object(_real_chromadb, "HttpClient", return_value=mock_client):
        target_skills = [{"skill": "Python", "category": "hard_skill", "proficiency": "熟悉", "importance": "required"}]
        result = score_skill_match(target_skills=target_skills, person_skills=[
            {"name": "Python", "category": "hard_skill", "proficiency": "专家"},
        ], threshold=0.6)
        assert "evaluated" in result
        assert len(result["evaluated"]) == 1
        assert result["evaluated"][0]["gap_level"] == "已掌握", "Python should lexically match 'Python'"