"""Unit tests for app.core.extraction.industry — PRD US-003 C2.

覆盖：
- is_unclassified: None / '' / '未分类' 都判定为「未分类」；
  其他真值返回 False。
- UNCLASSIFIED_INDUSTRY_LITERAL 常量值（防止前端 chip 文案漂移）。
"""
from __future__ import annotations

from app.core.extraction.industry import (
    UNCLASSIFIED_INDUSTRY_LITERAL,
    is_unclassified,
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