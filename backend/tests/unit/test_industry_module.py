"""Unit tests for app.core.extraction.industry — PRD US-003 C2 + Fix C.

覆盖：
- is_unclassified: None / '' / '未分类' 都判定为「未分类」；其他真值返回 False。
- is_generic_industry: 「通用」/「综合」/「其他」/English 模糊词命中。
- normalize_industry: 收口 None/空串/空白/通用词 → 「未分类」字面量。
- UNCLASSIFIED_INDUSTRY_LITERAL 常量值（防止前端 chip 文案漂移）。
"""
from __future__ import annotations

from app.core.extraction.industry import (
    UNCLASSIFIED_INDUSTRY_LITERAL,
    is_generic_industry,
    is_unclassified,
    normalize_industry,
)


class TestIsUnclassified:
    def test_none_is_unclassified(self) -> None:
        assert is_unclassified(None) is True

    def test_empty_string_is_unclassified(self) -> None:
        assert is_unclassified("") is True

    def test_unclassified_literal_is_unclassified(self) -> None:
        assert is_unclassified(UNCLASSIFIED_INDUSTRY_LITERAL) is True

    def test_real_industry_is_not_unclassified(self) -> None:
        assert is_unclassified("互联网/IT") is False
        assert is_unclassified("金融") is False


class TestConstant:
    def test_literal_value_locked(self) -> None:
        # 前端 chip 文案硬编码「未分类」（PositionList.vue:302 + ContentReviewPanel.vue:439）
        # —— 常量漂移会破坏 chip 文案 / DB 字面量 / 前端兜底三处一致性
        assert UNCLASSIFIED_INDUSTRY_LITERAL == "未分类"


class TestIsGenericIndustry:
    """Fix C: LLM 不确定时返回「通用」/「综合」等模糊行业词 → 归一化为「未分类」"""

    def test_generic_tokens_detected(self) -> None:
        for token in ("通用", "综合", "其他", "其它", "general", "Other", "N/A"):
            assert is_generic_industry(token) is True, f"{token!r} should be generic"

    def test_real_industries_not_generic(self) -> None:
        for real in ("互联网/IT", "金融", "医疗", "manufacturing"):
            assert is_generic_industry(real) is False

    def test_empty_or_none_not_generic(self) -> None:
        assert is_generic_industry("") is False
        assert is_generic_industry(None) is False


class TestNormalizeIndustry:
    """normalize_industry: 收口所有「该被归一化」的入口"""

    def test_none_returns_literal(self) -> None:
        assert normalize_industry(None) == UNCLASSIFIED_INDUSTRY_LITERAL

    def test_empty_returns_literal(self) -> None:
        assert normalize_industry("") == UNCLASSIFIED_INDUSTRY_LITERAL

    def test_whitespace_returns_literal(self) -> None:
        assert normalize_industry("   ") == UNCLASSIFIED_INDUSTRY_LITERAL

    def test_generic_tokens_normalized(self) -> None:
        assert normalize_industry("通用") == UNCLASSIFIED_INDUSTRY_LITERAL
        assert normalize_industry("其他") == UNCLASSIFIED_INDUSTRY_LITERAL

    def test_real_industry_preserved(self) -> None:
        assert normalize_industry("互联网/IT") == "互联网/IT"
        assert normalize_industry("金融科技") == "金融科技"
