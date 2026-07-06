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
    """业务说明：测试JD解析主流程，验证LLM调用和结构化结果返回。"""
    # 业务说明：构造模拟LLM返回的职位信息数据
    mock_response = {
        "position_name": "后端工程师",
        "required_skills": [{"name": "Python", "level": "advanced"}],
        "preferred_skills": [{"name": "Docker", "level": "intermediate"}],
        "experience_required": 3,
        "education_required": "本科",
        "responsibilities": ["开发 API", "优化性能"],
    }

    # 技术说明：Mock LLM提取接口，模拟正常提取和验证流程
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

            # 业务说明：调用JD解析主函数，传入测试JD内容
            result = await extract_from_jd("Test JD content")

        # 技术说明：验证返回结果的结构和关键字段
        assert result["success"] is True
        data = result["data"]
        assert data["position_name"] == "后端工程师"
        assert len(data["required_skills"]) == 1
        assert data["required_skills"][0]["name"] == "Python"
        assert data["experience_required"] == 3
        assert data["education_required"] == "本科"
        assert len(data["responsibilities"]) == 2


def test_skill_normalization_alias():
    """业务说明：测试技能名称别名映射功能，确保常见别名能正确标准化。"""
    assert normalize_by_alias("Python") == "Python"
    assert normalize_by_alias("python3") == "Python"
    assert normalize_by_alias("golang") == "Go"
    assert normalize_by_alias("reactjs") == "React"
    assert normalize_by_alias("kubernetes") == "Kubernetes"
    assert normalize_by_alias("unknown_xyz") is None


def test_skill_normalization_batch():
    """业务说明：测试批量技能标准化功能，处理多个技能名称的统一映射。"""
    skills = ["Python", "golang", "reactjs", "unknown_framework_xyz"]
    results = batch_normalize_skills(skills)

    # 技术说明：验证批量处理结果，包括标准化映射和未知技能的原样保留
    assert len(results) == 4
    assert results[0].normalized == "Python"
    assert results[1].normalized == "Go"
    assert results[2].normalized == "React"
    assert results[3].normalized == "unknown_framework_xyz"
    assert results[3].method == "identity"


def test_parse_llm_json_response():
    """业务说明：测试LLM返回JSON的清洗和解析功能，处理不同格式的JSON字符串。"""
    raw = '{"name": "Python", "level": "expert"}'
    result = parse_llm_json_response(raw)
    assert result["name"] == "Python"
    assert result["level"] == "expert"

    # 技术说明：测试带语言标识的Markdown代码块格式
    raw_with_fence = "```json\n{\"name\": \"Go\"}\n```"
    result = parse_llm_json_response(raw_with_fence)
    assert result["name"] == "Go"

    # 技术说明：测试不带语言标识的Markdown代码块格式
    raw_with_fence_no_lang = "```\n{\"name\": \"Rust\"}\n```"
    result = parse_llm_json_response(raw_with_fence_no_lang)
    assert result["name"] == "Rust"

    # 技术说明：验证非法JSON输入会抛出异常
    with pytest.raises(LLMResponseError):
        parse_llm_json_response("not json at all")


def test_parse_llm_json_response_complex():
    """业务说明：测试复杂嵌套JSON的解析功能，模拟真实职位信息数据结构。"""
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
    """业务说明：测试系统健康检查接口，验证服务基本可用性。"""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"
