"""PLAN-003/I18N-01: jd_extract 管线翻译钩子接线测试。

- 中文岗位名: 零成本跳过 (不调用 LLM.generate)
- 英文岗位名: 触发 translate_title_industry, name_cn/industry_zh 注入 data
- LLM 失败: 优雅降级 (data 不变, warnings 记录, 不阻断抽取)
- LLM 返回非 CJK: 防御性跳过 (不把英文当中文入库)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.extraction.jd_extract import extract_from_jd

EN_JD = {
    "position_name": "Senior Backend Engineer",
    "industry": "Internet",
    "required_skills": [{"name": "Python", "level": "advanced"}],
    "preferred_skills": [],
    "experience_required": 5,
    "education_required": "Bachelor",
    "responsibilities": ["Build APIs"],
}
CN_JD = {
    "position_name": "后端工程师",
    "industry": "互联网",
    "required_skills": [{"name": "Python", "level": "advanced"}],
    "preferred_skills": [],
}


def _patch_pipeline(**overrides):
    """patch LLMClient.extract_from_jd + validate_extraction, 返回给定数据。"""
    stack = [
        patch("app.core.extraction.llm_client.LLMClient.extract_from_jd",
              new_callable=AsyncMock, return_value=overrides.get("extract", EN_JD)),
        patch("app.core.extraction.llm_client.LLMClient.validate_extraction",
              new_callable=AsyncMock, return_value={
                  "is_valid": True, "hallucinated_skills": [],
                  "missing_skills": [], "confidence": 0.95, "issues": [],
              }),
    ]
    for p in stack:
        p.start()
    return stack


@pytest.mark.asyncio
async def test_cjk_position_skips_translation_no_generate_call():
    """中文岗位名 → 不调用 LLM.generate (零成本)。"""
    with patch("app.core.extraction.llm_client.LLMClient.generate",
               new_callable=AsyncMock) as mock_gen:
        stack = _patch_pipeline(extract=CN_JD)
        try:
            result = await extract_from_jd("测试 JD")
        finally:
            for p in stack:
                p.stop()
        assert result["success"] is True
        assert "name_cn" not in result["data"]
        mock_gen.assert_not_called()


@pytest.mark.asyncio
async def test_english_position_triggers_translation():
    """英文岗位名 → 翻译成功, name_cn/industry_zh 注入。"""
    with patch("app.core.extraction.llm_client.LLMClient.generate",
               new_callable=AsyncMock,
               return_value='{"name_cn": "高级后端工程师", "industry_zh": "互联网"}') as mock_gen:
        stack = _patch_pipeline(extract=EN_JD)
        try:
            result = await extract_from_jd("Senior Backend Engineer JD")
        finally:
            for p in stack:
                p.stop()
        assert result["success"] is True
        assert result["data"]["name_cn"] == "高级后端工程师"
        assert result["data"]["industry_zh"] == "互联网"
        assert mock_gen.await_count == 1


@pytest.mark.asyncio
async def test_translation_failure_degrades_gracefully():
    """LLM 抛异常 → data 不变, warnings 记录, 抽取仍成功 (不阻断)。"""
    with patch("app.core.extraction.llm_client.LLMClient.generate",
               new_callable=AsyncMock, side_effect=RuntimeError("llm down")):
        stack = _patch_pipeline(extract=EN_JD)
        try:
            result = await extract_from_jd("Senior Backend Engineer JD")
        finally:
            for p in stack:
                p.stop()
        assert result["success"] is True
        assert "name_cn" not in result["data"]
        assert any("Translation skipped" in w for w in result["warnings"])


@pytest.mark.asyncio
async def test_translation_non_cjk_result_not_injected():
    """LLM 返回与原文**不同**的英文 name_cn → 防御性不注入 (不存无关英文)。"""
    with patch("app.core.extraction.llm_client.LLMClient.generate",
               new_callable=AsyncMock,
               return_value='{"name_cn": "Some Unrelated English Name", "industry_zh": "互联网"}'):
        stack = _patch_pipeline(extract=EN_JD)
        try:
            result = await extract_from_jd("Senior Backend Engineer JD")
        finally:
            for p in stack:
                p.stop()
        assert result["success"] is True
        assert "name_cn" not in result["data"]


@pytest.mark.asyncio
async def test_translation_original_name_injected_as_fallback():
    """D8h 契约: LLM 返回原文（与 title 相同）→ 兜底注入 name_cn (5bea4f86)。"""
    with patch("app.core.extraction.llm_client.LLMClient.generate",
               new_callable=AsyncMock,
               return_value='{"name_cn": "Senior Backend Engineer", "industry_zh": "互联网"}'):
        stack = _patch_pipeline(extract=EN_JD)
        try:
            result = await extract_from_jd("Senior Backend Engineer JD")
        finally:
            for p in stack:
                p.stop()
        assert result["success"] is True
        assert result["data"]["name_cn"] == "Senior Backend Engineer"
