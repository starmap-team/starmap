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


class TestIndustryContractInvariants:
    """契约不变量测试（PR P0-A 2026-08-17）：DB 字面量契约必须可证。

    这些不变量锁住 industry.py 的语义承诺：
    1. UNCLASSIFIED_INDUSTRY_LITERAL 必须是「未分类」字面量（前端 chip 文案依赖）。
    2. normalize_industry 的输出要么是真实行业，要么是「未分类」字面量，永不返回 None/''。
    3. is_unclassified 与 normalize_industry 互为反函数（除 None/'' 也归入未分类）。
    4. 任何 industry 字段的「真实统计」=「总行数 - 未分类行数」。
    """

    def test_literal_value_is_chinese_unclassified(self) -> None:
        """前端 chip 文案 = 后端字段值 = DB 列值 — 任何漂移都会破坏 UI。"""
        assert UNCLASSIFIED_INDUSTRY_LITERAL == "未分类"

    def test_normalize_never_returns_none(self) -> None:
        """normalize_industry 的输出永远是字符串，不能是 None（防止下游 `.strip()` 崩）。"""
        for inp in (None, "", "   ", "通用", "综合", "other", "互联网/IT", "金融科技"):
            result = normalize_industry(inp)
            assert isinstance(result, str), f"input={inp!r} → type={type(result).__name__}"
            assert len(result) > 0, f"input={inp!r} → empty string"

    def test_normalize_is_idempotent(self) -> None:
        """normalize_industry ∘ normalize_industry = normalize_industry（幂等）。"""
        for inp in (None, "", "通用", "互联网/IT", "金融科技", "其他"):
            once = normalize_industry(inp)
            twice = normalize_industry(once)
            assert once == twice, f"input={inp!r} once={once!r} twice={twice!r}"

    def test_unclassified_inverse_relation(self) -> None:
        """normalize 输出「未分类」↔ is_unclassified 返回 True；反之亦然。"""
        for inp in (None, "", "通用", "other", "互联网/IT", "金融科技"):
            normalized = normalize_industry(inp)
            assert is_unclassified(normalized) == (normalized == UNCLASSIFIED_INDUSTRY_LITERAL)

    def test_real_stats_filter_formula(self) -> None:
        """真实统计口径 = COUNT(*) - COUNT(industry = '未分类') — 文档级不变量。"""
        # 这条契约在 dashboards / evolution_report 都依赖，不能漂移。
        # 这里只验证字面量值一致；具体 SQL 在 integration 测试中验。
        assert UNCLASSIFIED_INDUSTRY_LITERAL != ""
        assert UNCLASSIFIED_INDUSTRY_LITERAL is not None

