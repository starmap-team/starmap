"""Integration tests for the extraction API endpoint."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

SAMPLE_JD = """
岗位名称：高级后端工程师
岗位职责：
1. 负责核心 API 的设计与开发
2. 优化系统性能和可扩展性
3. 参与技术方案评审
任职要求：
- 精通 Python，熟悉 FastAPI 框架
- 熟悉 Docker、Kubernetes 等容器技术
- 了解 PostgreSQL 和 Redis
- 5 年以上后端开发经验
- 本科及以上学历
"""

MOCK_LLM_RESPONSE = {
    "role": "assistant",
    "content": json.dumps(
        {
            "position_name": "高级后端工程师",
            "required_skills": [
                {"name": "Python", "level": "expert"},
                {"name": "FastAPI", "level": "advanced"},
                {"name": "PostgreSQL", "level": "advanced"},
            ],
            "preferred_skills": [
                {"name": "Docker", "level": "intermediate"},
                {"name": "Kubernetes", "level": "intermediate"},
                {"name": "Redis", "level": "intermediate"},
            ],
            "experience_required": 5,
            "education_required": "本科",
            "responsibilities": [
                "负责核心 API 的设计与开发",
                "优化系统性能和可扩展性",
                "参与技术方案评审",
            ],
        }
    ),
    "model": "test",
}

EXPECTED_SKILL_NAMES = {"Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes", "Redis"}


@pytest.fixture(autouse=True)
def mock_llm():
    """Mock LLM calls for all integration tests."""
    with patch("app.core.extraction.llm_client.call_llm_with_fallback", new_callable=AsyncMock) as mock:
        mock.return_value = MOCK_LLM_RESPONSE
        yield mock


class TestExtractJDEndpoint:
    """Tests for POST /api/v1/extract/jd."""

    def test_extract_jd_success(self, mock_llm):
        """Test successful JD extraction returns expected structure."""
        resp = client.post("/api/v1/extract/jd", json={"jd_content": SAMPLE_JD})
        assert resp.status_code == 200

        body = resp.json()
        assert body["position_name"] == "高级后端工程师"
        assert body["experience_required"] == 5
        assert body["education_required"] == "本科"
        assert len(body["responsibilities"]) == 3

        all_skills = []
        for s in body["required_skills"]:
            all_skills.append(s["name"])
        for s in body["preferred_skills"]:
            all_skills.append(s["name"])
        assert set(all_skills) == EXPECTED_SKILL_NAMES

        assert body["confidence"] > 0
        assert isinstance(body["normalized_skills"], list)

    def test_extract_jd_empty_content_returns_422(self, mock_llm):
        """Test empty JD content returns 422 validation error."""
        resp = client.post("/api/v1/extract/jd", json={"jd_content": ""})
        assert resp.status_code == 422

    def test_extract_jd_missing_content_returns_422(self, mock_llm):
        """Test missing jd_content field returns 422."""
        resp = client.post("/api/v1/extract/jd", json={})
        assert resp.status_code == 422

    def test_extract_jd_with_options(self, mock_llm):
        """Test extraction with custom options."""
        resp = client.post(
            "/api/v1/extract/jd",
            json={"jd_content": SAMPLE_JD, "options": {"anti_hallucination_enabled": False}},
        )
        assert resp.status_code == 200
        assert resp.json()["position_name"] == "高级后端工程师"

    def test_extract_jd_response_model_matches(self, mock_llm):
        """Test response matches the ExtractionResult schema."""
        resp = client.post("/api/v1/extract/jd", json={"jd_content": SAMPLE_JD})
        body = resp.json()

        assert isinstance(body["position_name"], str)
        assert isinstance(body["required_skills"], list)
        assert isinstance(body["preferred_skills"], list)
        assert isinstance(body["responsibilities"], list)
        assert isinstance(body["normalized_skills"], list)
        assert body["experience_required"] is None or isinstance(body["experience_required"], int)
        assert body["education_required"] is None or isinstance(body["education_required"], str)
        assert isinstance(body["confidence"], (int, float))

    def test_extract_jd_llm_failure_returns_502(self, mock_llm):
        """Test LLM connection failure returns 502."""
        from app.core.extraction.jd_extract import JDExtractionPipeline

        with patch.object(JDExtractionPipeline, "run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = ConnectionError("LLM unavailable")
            resp = client.post("/api/v1/extract/jd", json={"jd_content": SAMPLE_JD})
            assert resp.status_code == 502
            assert "LLM service unavailable" in resp.json()["detail"]

    def test_extract_jd_unexpected_error_returns_500(self, mock_llm):
        """Test unexpected errors return 500."""
        from app.core.extraction.jd_extract import JDExtractionPipeline

        with patch.object(JDExtractionPipeline, "run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = RuntimeError("Unexpected failure")
            resp = client.post("/api/v1/extract/jd", json={"jd_content": SAMPLE_JD})
            assert resp.status_code == 500
