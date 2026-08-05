"""Coverage boost: core/extraction/translation.py — CJK 检测与翻译回退 (PLAN-013)。"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.extraction.translation import has_cjk, looks_asian, translate_title_industry


class TestHasCjk:
    def test_cjk_returns_true(self) -> None:
        assert has_cjk("后端工程师") is True

    def test_english_returns_false(self) -> None:
        assert has_cjk("Backend Engineer") is False

    def test_mixed_returns_true(self) -> None:
        assert has_cjk("Java 开发") is True

    def test_empty_and_none_return_false(self) -> None:
        assert has_cjk("") is False
        assert has_cjk(None) is False


class TestLooksAsian:
    def test_chinese_returns_true(self) -> None:
        assert looks_asian("数据分析") is True

    def test_japanese_korean_return_true(self) -> None:
        assert looks_asian("データエンジニア") is True
        assert looks_asian("개발자") is True

    def test_english_returns_false(self) -> None:
        assert looks_asian("Data Analyst") is False

    def test_empty_returns_false(self) -> None:
        assert looks_asian(None) is False


class _FakeLLM:
    """可编程假 LLM：成功返回 JSON / 抛异常 / 返回非 CJK。"""

    def __init__(self, *, result: Any = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.prompts: list[str] = []

    async def generate(self, prompt: str, **_: Any) -> str:
        self.prompts.append(prompt)
        if self._error is not None:
            raise self._error
        return self._result


class TestTranslateTitleIndustry:
    @pytest.mark.asyncio
    async def test_empty_title_returns_none_pair(self) -> None:
        llm = _FakeLLM(result='{"name_cn": "x", "industry_zh": "y"}')
        out = await translate_title_industry(llm, title="")
        assert out == {"name_cn": None, "industry_zh": None}
        assert llm.prompts == []  # 未调用 LLM

    @pytest.mark.asyncio
    async def test_cjk_title_skips_llm_returns_original(self) -> None:
        llm = _FakeLLM(result="should not be used")
        out = await translate_title_industry(llm, title="后端工程师", industry="信息技术")
        assert out == {"name_cn": "后端工程师", "industry_zh": "信息技术"}
        assert llm.prompts == []

    @pytest.mark.asyncio
    async def test_llm_success_parses_json(self) -> None:
        llm = _FakeLLM(result='{"name_cn": "数据工程师", "industry_zh": "互联网"}')
        out = await translate_title_industry(llm, title="Data Engineer", industry="Internet")
        assert out == {"name_cn": "数据工程师", "industry_zh": "互联网"}
        assert len(llm.prompts) == 1
        assert "Data Engineer" in llm.prompts[0]

    @pytest.mark.asyncio
    async def test_llm_non_cjk_result_falls_back(self) -> None:
        """防御性检查：LLM 返回英文名 → 回退 None（不把英文当中文入库）。"""
        llm = _FakeLLM(result='{"name_cn": "Data Engineer", "industry_zh": "互联网"}')
        out = await translate_title_industry(llm, title="Data Engineer")
        assert out == {"name_cn": None, "industry_zh": None}

    @pytest.mark.asyncio
    async def test_llm_exception_falls_back_gracefully(self) -> None:
        llm = _FakeLLM(error=RuntimeError("llm down"))
        out = await translate_title_industry(llm, title="Data Engineer")
        assert out == {"name_cn": None, "industry_zh": None}

    @pytest.mark.asyncio
    async def test_llm_invalid_json_falls_back(self) -> None:
        llm = _FakeLLM(result="not json at all")
        out = await translate_title_industry(llm, title="Data Engineer")
        assert out == {"name_cn": None, "industry_zh": None}
