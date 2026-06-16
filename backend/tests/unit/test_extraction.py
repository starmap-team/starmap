"""Unit tests for extraction pipeline (LLM, normalization, JSON parsing)."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.core.extraction.jd_extract import extract_from_jd
from app.core.extraction.llm_client import LLMResponseError, parse_llm_json_response
from app.core.extraction.normalize import (
    batch_normalize_skills,
    normalize_by_alias,
)


@pytest.mark.asyncio
async def test_extract_from_jd_basic():
    """Test that extract_from_jd calls LLM and returns structured result."""
    mock_response = {
        "position_name": "后端工程师",
        "required_skills": [{"name": "Python", "level": "advanced"}],
        "preferred_skills": [{"name": "Docker", "level": "intermediate"}],
        "experience_required": 3,
        "education_required": "本科",
        "responsibilities": ["开发 API", "优化性能"],
    }

    with patch("app.core.extraction.llm_client.LLMClient.extract_from_jd", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = mock_response
        with patch("app.core.extraction.llm_client.LLMClient.validate_extraction", new_callable=AsyncMock) as mock_val:
            mock_val.return_value = {
                "is_valid": True,
                "hallucinated_skills": [],
                "missing_skills": [],
                "confidence": 0.95,
                "issues": [],
            }

            result = await extract_from_jd("Test JD content")

        assert result["success"] is True
        data = result["data"]
        assert data["position_name"] == "后端工程师"
        assert len(data["required_skills"]) == 1
        assert data["required_skills"][0]["name"] == "Python"
        assert data["experience_required"] == 3
        assert data["education_required"] == "本科"
        assert len(data["responsibilities"]) == 2


def test_skill_normalization_alias():
    """Test alias-based skill normalization."""
    assert normalize_by_alias("Python") == "Python"
    assert normalize_by_alias("python3") == "Python"
    assert normalize_by_alias("golang") == "Go"
    assert normalize_by_alias("reactjs") == "React"
    assert normalize_by_alias("kubernetes") == "Kubernetes"
    assert normalize_by_alias("unknown_xyz") is None


def test_skill_normalization_batch():
    """Test batch normalization of multiple skills."""
    skills = ["Python", "golang", "reactjs", "unknown_framework_xyz"]
    results = batch_normalize_skills(skills)

    assert len(results) == 4
    assert results[0].normalized == "Python"
    assert results[1].normalized == "Go"
    assert results[2].normalized == "React"
    assert results[3].normalized == "unknown_framework_xyz"
    assert results[3].method == "identity"


def test_parse_llm_json_response():
    """Test JSON cleaning from LLM responses."""
    raw = '{"name": "Python", "level": "expert"}'
    result = parse_llm_json_response(raw)
    assert result["name"] == "Python"
    assert result["level"] == "expert"

    raw_with_fence = "```json\n{\"name\": \"Go\"}\n```"
    result = parse_llm_json_response(raw_with_fence)
    assert result["name"] == "Go"

    raw_with_fence_no_lang = "```\n{\"name\": \"Rust\"}\n```"
    result = parse_llm_json_response(raw_with_fence_no_lang)
    assert result["name"] == "Rust"

    with pytest.raises(LLMResponseError):
        parse_llm_json_response("not json at all")


def test_parse_llm_json_response_complex():
    """Test parsing of complex nested JSON from LLM responses."""
    complex_json = json.dumps(
        {
            "position_name": "Senior Python Developer",
            "required_skills": [{"name": "Python", "level": "expert"}, {"name": "Django", "level": "advanced"}],
            "preferred_skills": [{"name": "Docker", "level": "intermediate"}],
            "experience_required": 5,
            "education_required": "Bachelor's degree",
            "responsibilities": ["Write Python code", "Code review", "Mentor juniors"],
        }
    )

    result = parse_llm_json_response(complex_json)
    assert result["position_name"] == "Senior Python Developer"
    assert len(result["required_skills"]) == 2
    assert result["experience_required"] == 5


def test_health(client):
    """Update existing health test to use client fixture."""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"
