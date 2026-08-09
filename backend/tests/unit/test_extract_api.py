"""Deep tests for Extract API — pure functions and endpoint tests.

Covers:
- _map_proficiency: proficiency string mapping
- _map_skill_item: skill item dict/string mapping
- _build_result: pipeline result transformation
- _write_extraction_to_graph: Neo4j write bridge
- _write_extraction_to_pg: PostgreSQL write
- extract_jd endpoint: POST /extract/jd
- extract_resume endpoint: POST /extract/resume
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.v1.extract import (
    _build_result,
    _map_proficiency,
    _map_skill_item,
    _write_extraction_to_graph,
    _write_extraction_to_pg,
)

# ═══════════════════════════════════════════════════════════════
# TestMapProficiency — pure function, no external deps
# ═══════════════════════════════════════════════════════════════


class TestMapProficiency:
    """Tests for _map_proficiency — pure function mapping."""

    def test_beginner_maps_to_liaojie(self):
        assert _map_proficiency("beginner") == "了解"

    def test_basic_maps_to_liaojie(self):
        assert _map_proficiency("basic") == "了解"

    def test_intermediate_maps_to_shuxi(self):
        assert _map_proficiency("intermediate") == "熟悉"

    def test_advanced_maps_to_jingtong(self):
        assert _map_proficiency("advanced") == "精通"

    def test_expert_maps_to_jingtong(self):
        assert _map_proficiency("expert") == "精通"

    def test_chinese_liaojie_passes_through(self):
        assert _map_proficiency("了解") == "了解"

    def test_chinese_shuxi_passes_through(self):
        assert _map_proficiency("熟悉") == "熟悉"

    def test_chinese_jingtong_passes_through(self):
        assert _map_proficiency("精通") == "精通"

    def test_unknown_defaults_to_shuxi(self):
        assert _map_proficiency("unknown_level") == "熟悉"

    def test_none_defaults_to_shuxi(self):
        assert _map_proficiency(None) == "熟悉"

    def test_empty_string_defaults_to_shuxi(self):
        assert _map_proficiency("") == "熟悉"

    def test_case_insensitive(self):
        assert _map_proficiency("Beginner") == "了解"
        assert _map_proficiency("INTERMEDIATE") == "熟悉"
        assert _map_proficiency("Expert") == "精通"

    def test_whitespace_stripped(self):
        assert _map_proficiency("  beginner  ") == "了解"


# ═══════════════════════════════════════════════════════════════
# TestMapSkillItem — pure function, no external deps
# ═══════════════════════════════════════════════════════════════


class TestMapSkillItem:
    """Tests for _map_skill_item — skill item dict/string mapping."""

    def test_string_input(self):
        result = _map_skill_item("Python")
        assert result["skill"] == "Python"
        assert result["category"] == "hard_skill"
        assert result["proficiency"] == "熟悉"

    def test_dict_input_with_proficiency(self):
        result = _map_skill_item({"name": "Python", "proficiency": "advanced"})
        assert result["skill"] == "Python"
        assert result["proficiency"] == "精通"

    def test_dict_input_with_level(self):
        result = _map_skill_item({"name": "Docker", "level": "beginner"})
        assert result["skill"] == "Docker"
        assert result["proficiency"] == "了解"

    def test_dict_input_with_skill_key(self):
        result = _map_skill_item({"skill": "K8s", "proficiency": "expert"})
        assert result["skill"] == "K8s"

    def test_dict_missing_name_uses_empty(self):
        result = _map_skill_item({"proficiency": "advanced"})
        assert result["skill"] == ""

    def test_dict_missing_proficiency_defaults(self):
        result = _map_skill_item({"name": "Go"})
        assert result["proficiency"] == "熟悉"

    def test_dict_missing_category_defaults(self):
        result = _map_skill_item({"name": "Go"})
        assert result["category"] == "hard_skill"

    def test_dict_with_category(self):
        result = _map_skill_item({"name": "Leadership", "category": "soft_skill", "proficiency": "intermediate"})
        assert result["category"] == "soft_skill"
        assert result["proficiency"] == "熟悉"

    def test_pydantic_model_input(self):
        """Objects with model_dump method are handled."""
        mock_model = MagicMock()
        mock_model.model_dump.return_value = {"name": "Rust", "proficiency": "expert", "category": "hard_skill"}
        result = _map_skill_item(mock_model)
        assert result["skill"] == "Rust"
        assert result["proficiency"] == "精通"


# ═══════════════════════════════════════════════════════════════
# TestBuildResult — pure function, no external deps
# ═══════════════════════════════════════════════════════════════


class TestBuildResult:
    """Tests for _build_result — pipeline result transformation."""

    def test_full_pipeline_result(self):
        pipeline_result = {
            "success": True,
            "data": {
                "position_name": "Backend Dev",
                "required_skills": [{"name": "Python", "proficiency": "advanced"}],
                "preferred_skills": [{"name": "Docker", "proficiency": "intermediate"}],
                "experience_required": 3,
                "education_required": "本科",
                "responsibilities": ["开发REST API"],
            },
            "validation": {
                "is_valid": True,
                "confidence": 0.92,
            },
            "normalization": [{"original": "py", "normalized": "Python"}],
        }
        result = _build_result(pipeline_result)

        assert result["position_name"] == "Backend Dev"
        assert len(result["required_skills"]) == 1
        assert result["required_skills"][0]["skill"] == "Python"
        assert result["required_skills"][0]["proficiency"] == "精通"
        assert len(result["preferred_skills"]) == 1
        assert result["experience_required"] == 3
        assert result["education_required"] == "本科"
        assert result["responsibilities"] == ["开发REST API"]
        assert result["confidence"] == 0.92
        assert result["hallucination_score"] is None
        assert len(result["normalized_skills"]) == 1

    def test_empty_skills(self):
        pipeline_result = {
            "data": {
                "position_name": "Empty Job",
            },
            "validation": {},
        }
        result = _build_result(pipeline_result)

        assert result["position_name"] == "Empty Job"
        assert result["required_skills"] == []
        assert result["preferred_skills"] == []

    def test_missing_optional_fields(self):
        pipeline_result = {}
        result = _build_result(pipeline_result)

        assert result["position_name"] == ""
        assert result["required_skills"] == []
        assert result["preferred_skills"] == []
        assert result["experience_required"] is None
        assert result["education_required"] is None
        assert result["responsibilities"] == []
        assert result["confidence"] == 0.85  # default
        assert result["hallucination_score"] is None

    def test_hallucination_detected(self):
        """When validation.is_valid is False, hallucination_score is set."""
        pipeline_result = {
            "data": {"position_name": "Test"},
            "validation": {"is_valid": False, "confidence": 0.3},
        }
        result = _build_result(pipeline_result)

        assert result["hallucination_score"] == 0.3

    def test_no_data_key(self):
        """Missing data key uses empty dict."""
        pipeline_result = {"validation": {"confidence": 0.9}}
        result = _build_result(pipeline_result)

        assert result["position_name"] == ""
        assert result["confidence"] == 0.9

    def test_passes_through_enrichment_and_hallucination_fields(self):
        """契约锁定: 反幻觉 + 富化字段透传给前端 (ExtractJD.vue 新增展示区依赖)。

        后端已透传, 前端此前丢弃; 此测试防止 _build_result 回归丢掉这些字段。
        """
        pipeline_result = {
            "data": {
                "position_name": "Backend Dev",
                "tools": [{"name": "Docker", "category": "devops"}],
                "learning_resources": [{"title": "Python 官方文档", "type": "docs"}],
                "evolves_to": ["技术架构师"],
            },
            "validation": {
                "is_valid": False,
                "confidence": 0.35,
                "hallucinated_skills": ["量子编程"],
                "missing_skills": ["RESTful API"],
                "issues": ["技能超出本体白名单"],
            },
            "model_used": "qwen2.5-7b-fallback",
        }
        result = _build_result(pipeline_result)

        # 幻觉防控信号
        assert result["hallucination_score"] == 0.35
        assert result["hallucinated_skills"] == ["量子编程"]
        assert result["missing_skills"] == ["RESTful API"]
        assert result["issues"] == ["技能超出本体白名单"]
        # 富化字段
        assert result["tools"][0]["name"] == "Docker"
        assert result["learning_resources"][0]["title"] == "Python 官方文档"
        assert result["evolves_to"] == ["技术架构师"]
        # 模型透明化（含降级）
        assert result["model_used"] == "qwen2.5-7b-fallback"

    def test_enrichment_fields_default_to_empty(self):
        """无富化/反幻觉数据时默认空列表, 不抛错。"""
        result = _build_result({"data": {"position_name": "X"}, "validation": {}})
        assert result["tools"] == []
        assert result["learning_resources"] == []
        assert result["evolves_to"] == []
        assert result["hallucinated_skills"] == []
        assert result["missing_skills"] == []
        assert result["issues"] == []


# ═══════════════════════════════════════════════════════════════
# TestWriteExtractionToGraph — async function with mocked Neo4j
# ═══════════════════════════════════════════════════════════════


class TestWriteExtractionToGraph:
    """Tests for _write_extraction_to_graph — Neo4j write bridge."""

    @pytest.mark.asyncio
    async def test_no_data_returns_none(self):
        result = await _write_extraction_to_graph({}, MagicMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_no_position_name_returns_none(self):
        result = await _write_extraction_to_graph({"data": {}}, MagicMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_success_returns_summary(self):
        mock_driver = MagicMock()
        with patch("app.api.v1.extract.write_extraction_to_graph", new_callable=AsyncMock) as mock_write:
            mock_write.return_value = {"triples_merged": 5, "nodes_touched": 3}
            result = await _write_extraction_to_graph(
                {"data": {"position_name": "Backend Dev", "required_skills": []}},
                mock_driver,
            )

        assert result["triples_merged"] == 5
        assert result["nodes_touched"] == 3

    @pytest.mark.asyncio
    async def test_failure_returns_none(self):
        mock_driver = MagicMock()
        with patch("app.api.v1.extract.write_extraction_to_graph", new_callable=AsyncMock) as mock_write:
            mock_write.side_effect = Exception("Neo4j down")
            result = await _write_extraction_to_graph(
                {"data": {"position_name": "Backend Dev"}},
                mock_driver,
            )

        assert result is None


# ═══════════════════════════════════════════════════════════════
# TestWriteExtractionToPg — async function with mocked session
# ═══════════════════════════════════════════════════════════════


class TestWriteExtractionToPg:
    """Tests for _write_extraction_to_pg — PostgreSQL write."""

    @pytest.mark.asyncio
    async def test_no_data_returns_none(self):
        mock_session = AsyncMock()
        result = await _write_extraction_to_pg({}, mock_session)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_position_name_returns_none(self):
        mock_session = AsyncMock()
        result = await _write_extraction_to_pg({"data": {}}, mock_session)
        assert result is None

    @pytest.mark.asyncio
    async def test_success_returns_true(self):
        mock_session = AsyncMock()
        pipeline_result = {
            "data": {
                "position_name": "Backend Dev",
                "industry": "Tech",
                "description": "Build APIs",
                "required_skills": [{"skill": "Python"}, {"name": "Docker"}],
                "preferred_skills": [{"skill": "K8s"}],
            }
        }
        result = await _write_extraction_to_pg(pipeline_result, mock_session)

        assert result is True
        mock_session.execute.assert_called()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_failure_returns_none(self):
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("DB error")
        pipeline_result = {
            "data": {
                "position_name": "Backend Dev",
                "required_skills": [],
            }
        }
        result = await _write_extraction_to_pg(pipeline_result, mock_session)

        assert result is None
        mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_skills_extracted_from_dicts(self):
        """Skills are extracted from both required and preferred, deduped."""
        mock_session = AsyncMock()
        pipeline_result = {
            "data": {
                "position_name": "Full Stack",
                "required_skills": [{"skill": "Python"}, {"name": "React"}],
                "preferred_skills": [{"skill": "Python"}, {"name": "TypeScript"}],
            }
        }
        result = await _write_extraction_to_pg(pipeline_result, mock_session)

        assert result is True
        # Should have 3 unique skills (Python deduped)
        execute_calls = mock_session.execute.call_args_list
        # 1 position upsert + 3 skill upserts
        assert len(execute_calls) == 4

    @pytest.mark.asyncio
    async def test_string_skills_handled(self):
        """Skills as plain strings are handled."""
        mock_session = AsyncMock()
        pipeline_result = {
            "data": {
                "position_name": "DevOps",
                "required_skills": ["Python", "Docker"],
                "preferred_skills": ["K8s"],
            }
        }
        result = await _write_extraction_to_pg(pipeline_result, mock_session)

        assert result is True


# ═══════════════════════════════════════════════════════════════
# TestExtractJDEndpoint — TestClient with mocked dependencies
# ═══════════════════════════════════════════════════════════════


class TestExtractJDEndpoint:
    """Tests for POST /extract/jd endpoint via TestClient."""

    def _get_client(self):
        from app.dependencies import get_current_user, get_db_session
        from app.main import app
        mock_session = AsyncMock()
        mock_user = {"sub": "test_user", "role": "admin", "username": "test_admin"}
        app.dependency_overrides[get_db_session] = lambda: mock_session
        app.dependency_overrides[get_current_user] = lambda: mock_user
        client = TestClient(app)
        return client, mock_session

    def _cleanup(self):
        from app.dependencies import get_current_user, get_db_session
        from app.main import app
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_current_user, None)

    def test_extract_jd_success(self):
        client, mock_session = self._get_client()
        try:
            pipeline_result = {
                "success": True,
                "data": {
                    "position_name": "Backend Dev",
                    "required_skills": [{"name": "Python", "proficiency": "advanced"}],
                    "preferred_skills": [],
                    "experience_required": 3,
                    "education_required": "本科",
                    "responsibilities": [],
                },
                "validation": {"is_valid": True, "confidence": 0.9},
                "normalization": [],
            }
            with patch("app.api.v1.extract.extract_from_jd", new_callable=AsyncMock) as mock_extract, \
                 patch("app.api.v1.extract._write_extraction_to_graph", new_callable=AsyncMock) as mock_graph, \
                 patch("app.api.v1.extract._write_extraction_to_pg", new_callable=AsyncMock) as mock_pg:
                mock_extract.return_value = pipeline_result
                mock_graph.return_value = None
                mock_pg.return_value = True

                response = client.post(
                    "/api/v1/extract/jd",
                    json={"jd_content": "We need a Python developer with 3 years experience"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["position_name"] == "Backend Dev"
        finally:
            self._cleanup()

    def test_extract_jd_llm_failure_502(self):
        client, mock_session = self._get_client()
        try:
            with patch("app.api.v1.extract.extract_from_jd", new_callable=AsyncMock) as mock_extract:
                mock_extract.side_effect = ConnectionError("LLM down")

                response = client.post(
                    "/api/v1/extract/jd",
                    json={"jd_content": "Some JD text"},
                )

            assert response.status_code == 502
        finally:
            self._cleanup()

    def test_extract_jd_value_error_422(self):
        client, mock_session = self._get_client()
        try:
            with patch("app.api.v1.extract.extract_from_jd", new_callable=AsyncMock) as mock_extract:
                mock_extract.side_effect = ValueError("Invalid input")

                response = client.post(
                    "/api/v1/extract/jd",
                    json={"jd_content": "Some JD text"},
                )

            assert response.status_code == 422
        finally:
            self._cleanup()

    def test_extract_jd_pipeline_not_success_422(self):
        client, mock_session = self._get_client()
        try:
            with patch("app.api.v1.extract.extract_from_jd", new_callable=AsyncMock) as mock_extract:
                mock_extract.return_value = {"success": False, "error": "Extraction failed"}

                response = client.post(
                    "/api/v1/extract/jd",
                    json={"jd_content": "Some JD text"},
                )

            assert response.status_code == 422
        finally:
            self._cleanup()

    def test_extract_jd_unexpected_error_500(self):
        client, mock_session = self._get_client()
        try:
            with patch("app.api.v1.extract.extract_from_jd", new_callable=AsyncMock) as mock_extract:
                mock_extract.side_effect = RuntimeError("Unexpected")

                response = client.post(
                    "/api/v1/extract/jd",
                    json={"jd_content": "Some JD text"},
                )

            assert response.status_code == 500
        finally:
            self._cleanup()

    def test_extract_jd_empty_content_422(self):
        client, mock_session = self._get_client()
        try:
            response = client.post(
                "/api/v1/extract/jd",
                json={"jd_content": ""},
            )
            assert response.status_code == 422
        finally:
            self._cleanup()


# ═══════════════════════════════════════════════════════════════
# TestExtractResumeEndpoint — TestClient with mocked dependencies
# ═══════════════════════════════════════════════════════════════


class TestExtractResumeEndpoint:
    """Tests for POST /extract/resume endpoint via TestClient."""

    def _get_client(self):
        from app.dependencies import get_current_user, get_db_session
        from app.main import app
        mock_session = AsyncMock()
        mock_user = {"sub": "test_user", "role": "admin", "username": "test_admin"}
        app.dependency_overrides[get_db_session] = lambda: mock_session
        app.dependency_overrides[get_current_user] = lambda: mock_user
        client = TestClient(app)
        return client, mock_session

    def _cleanup(self):
        from app.dependencies import get_current_user, get_db_session
        from app.main import app
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_current_user, None)

    def test_extract_resume_no_file_422(self):
        client, mock_session = self._get_client()
        try:
            # No file uploaded
            response = client.post("/api/v1/extract/resume")
            assert response.status_code == 422
        finally:
            self._cleanup()

    def test_extract_resume_unsupported_file_type_400(self):
        client, mock_session = self._get_client()
        try:
            response = client.post(
                "/api/v1/extract/resume",
                files={"file": ("test.txt", b"content", "text/plain")},
            )
            assert response.status_code == 400
            assert "Unsupported file type" in response.json()["detail"]
        finally:
            self._cleanup()

    def test_extract_resume_llm_failure_502(self):
        client, mock_session = self._get_client()
        try:
            with patch("app.api.v1.extract.run_resume_extraction", new_callable=AsyncMock) as mock_resume:
                mock_resume.side_effect = ConnectionError("LLM down")

                response = client.post(
                    "/api/v1/extract/resume",
                    files={"file": ("resume.pdf", b"%PDF-1.4 fake", "application/pdf")},
                )

            assert response.status_code == 502
        finally:
            self._cleanup()

    def test_extract_resume_value_error_400(self):
        client, mock_session = self._get_client()
        try:
            with patch("app.api.v1.extract.run_resume_extraction", new_callable=AsyncMock) as mock_resume:
                mock_resume.side_effect = ValueError("Invalid resume")

                response = client.post(
                    "/api/v1/extract/resume",
                    files={"file": ("resume.pdf", b"%PDF-1.4 fake", "application/pdf")},
                )

            assert response.status_code == 400
        finally:
            self._cleanup()

    def test_extract_resume_success(self):
        client, mock_session = self._get_client()
        try:
            pipeline_result = {
                "success": True,
                "data": {
                    "position_name": "Frontend Dev",
                    "required_skills": [{"name": "React", "proficiency": "advanced"}],
                    "preferred_skills": [],
                },
                "validation": {"is_valid": True, "confidence": 0.88},
                "normalization": [],
            }
            with patch("app.api.v1.extract.run_resume_extraction", new_callable=AsyncMock) as mock_resume, \
                 patch("app.api.v1.extract._write_extraction_to_graph", new_callable=AsyncMock) as mock_graph, \
                 patch("app.api.v1.extract._write_extraction_to_pg", new_callable=AsyncMock) as mock_pg:
                mock_resume.return_value = pipeline_result
                mock_graph.return_value = None
                mock_pg.return_value = True

                response = client.post(
                    "/api/v1/extract/resume",
                    files={"file": ("resume.pdf", b"%PDF-1.4 fake", "application/pdf")},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["position_name"] == "Frontend Dev"
        finally:
            self._cleanup()

    def test_extract_resume_no_filename_400(self):
        client, mock_session = self._get_client()
        try:
            # Upload a file without a proper filename
            # The endpoint checks file.filename is None
            response = client.post(
                "/api/v1/extract/resume",
                files={"file": (None, b"content", "application/pdf")},
            )
            # FastAPI may set filename to the field name or None
            # Either 400 (no filename) or 422 (validation) is acceptable
            assert response.status_code in (400, 422)
        finally:
            self._cleanup()
