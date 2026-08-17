"""Phase 1 Industry Taxonomy (2026-08-17) — 多层防御字典层测试。

锁定 backend/app/config/industry_taxonomy.yaml 的契约：
1. canonical 行业 ≥ 20 个（GB/T 4754 简化版覆盖 95%+ IT岗位）
2. alias 近义词映射必须把 LLM 实际输出的近义词收敛到 canonical
3. generic_tokens 必须把模糊词归一化为「未分类」字面量
4. normalize_industry() 串联所有层级
"""
from __future__ import annotations

from app.core.extraction.industry import (
    UNCLASSIFIED_INDUSTRY_LITERAL,
    get_alias_map,
    get_canonical_industries,
    is_unclassified,
    normalize_industry,
)


class TestIndustryTaxonomyLoading:
    """industry_taxonomy.yaml 必须加载到内存字典（启动时一次性）。"""

    def test_yaml_loaded_at_least_20_canonical(self):
        canonical = get_canonical_industries()
        assert len(canonical) >= 20, (
            f"Expected >= 20 canonical industries, got {len(canonical)}: {canonical[:5]}"
        )

    def test_canonical_includes_core_industries(self):
        canonical = list(get_canonical_industries())
        for required in ("互联网/IT", "金融科技", "智能制造", "医疗健康", "零售/电商"):
            assert required in canonical, (
                f"Missing required industry {required!r} in canonical list"
            )

    def test_alias_map_contains_canonical_self_refs(self):
        """每个 canonical 行业都应在自己 alias map 里（大小写不敏感）"""
        alias = get_alias_map()
        for c in get_canonical_industries():
            assert c.lower() in alias, f"Canonical {c!r} missing self-ref in alias map"

    def test_alias_map_is_lowercase_normalized(self):
        alias = get_alias_map()
        # 所有 key 必须小写
        for k in alias:
            assert k == k.lower(), f"Alias key not lowercase: {k!r}"

    def test_unclassified_in_canonical(self):
        """「未分类」是 canonical 列表的最后一员（兜底桶语义）。
        它在 list 中是因为前端行业筛选 / admin 下拉需要它，但 LLM prompt
        注入时会被过滤掉（见 _get_industry_hint）。
        """
        canonical = get_canonical_industries()
        assert "未分类" in canonical


class TestAliasNormalization:
    """alias → canonical 映射必须在 normalize_industry 末段生效。"""

    def test_tech_alias_to_internet_it(self):
        """英文 "Tech" 行业别名 → 互联网/IT。"""
        assert normalize_industry("Tech") == "互联网/IT"

    def test_tech_alias_case_insensitive(self):
        """alias 匹配大小写不敏感。"""
        assert normalize_industry("TECH") == "互联网/IT"
        assert normalize_industry("tech") == "互联网/IT"

    def test_technology_internet_to_internet_it(self):
        """「信息技术/互联网」近义词 → 互联网/IT（防 PG / Neo4j 分裂）。"""
        assert normalize_industry("信息技术/互联网") == "互联网/IT"

    def test_eda_to_semiconductor(self):
        """半导体行业别名。"""
        assert normalize_industry("半导体") == "半导体"

    def test_saas_to_internet_it(self):
        """SaaS 行业归到 IT。"""
        assert normalize_industry("SaaS") == "互联网/IT"

    def test_unchanged_when_not_in_dict(self):
        """不在字典中的 industry 原样返回（让 admin 可手动覆盖）。"""
        assert normalize_industry("外星科技") == "外星科技"


class TestGenericTokens:
    """模糊词必须归一化为「未分类」字面量。"""

    def test_unchanged_unclassified_literal(self):
        """「未分类」字面量保持不变。"""
        assert normalize_industry("未分类") == "未分类"

    def test_old_generic_tokens_mapped(self):
        for tok in ["通用", "综合", "其他", "其它", "general", "misc", "other", "n/a"]:
            assert normalize_industry(tok) == UNCLASSIFIED_INDUSTRY_LITERAL, (
                f"Generic token {tok!r} should map to 未分类"
            )

    def test_additional_generic_tokens_mapped(self):
        """YAML 字典扩展的模糊词。"""
        for tok in ["一般", "通用行业", "综合行业", "Misc", "Other"]:
            assert normalize_industry(tok) == UNCLASSIFIED_INDUSTRY_LITERAL, (
                f"Additional generic {tok!r} should map to 未分类"
            )

    def test_generic_token_case_insensitive(self):
        assert normalize_industry("GENERAL") == UNCLASSIFIED_INDUSTRY_LITERAL
        assert normalize_industry("Miscellaneous") == UNCLASSIFIED_INDUSTRY_LITERAL


class TestNormalizeIndustryIntegration:
    """normalize_industry 串联所有层级：None/''/模糊词/alias/canonical。"""

    def test_none_returns_literal(self):
        assert normalize_industry(None) == UNCLASSIFIED_INDUSTRY_LITERAL

    def test_empty_string_returns_literal(self):
        assert normalize_industry("") == UNCLASSIFIED_INDUSTRY_LITERAL

    def test_whitespace_returns_literal(self):
        assert normalize_industry("   ") == UNCLASSIFIED_INDUSTRY_LITERAL

    def test_real_canonical_preserved(self):
        """真实 canonical 行业原样保留。"""
        for industry in ("互联网/IT", "金融科技", "智能制造", "医疗健康", "销售/营销"):
            assert normalize_industry(industry) == industry

    def test_real_with_whitespace_normalized(self):
        assert normalize_industry("  互联网/IT  ") == "互联网/IT"


class TestIsUnclassifiedBackwardCompat:
    """is_unclassified 是 D-04 诚实空态判定核心，必须保持向后兼容。"""

    def test_none_is_unclassified(self):
        assert is_unclassified(None) is True

    def test_empty_is_unclassified(self):
        assert is_unclassified("") is True

    def test_literal_is_unclassified(self):
        assert is_unclassified("未分类") is True

    def test_real_industry_not_unclassified(self):
        assert is_unclassified("互联网/IT") is False
        assert is_unclassified("金融科技") is False


class TestPromptIndustryHint:
    """prompt.py 的 _get_industry_hint 必须排除「未分类」兜底桶。"""

    def test_industry_hint_excludes_unclassified(self):
        from app.core.extraction.prompt import _get_industry_hint

        hint = _get_industry_hint()
        # 「未分类」不应出现在 hint 里（LLM 不该直接选这个）
        assert "未分类" not in hint

    def test_industry_hint_includes_core(self):
        from app.core.extraction.prompt import _get_industry_hint

        hint = _get_industry_hint()
        for required in ("互联网/IT", "金融科技", "智能制造"):
            assert required in hint, f"Required industry {required!r} missing from hint"

    def test_industry_hint_cached(self):
        """第二次调用返回相同对象（模块级 cache）。"""
        from app.core.extraction.prompt import _get_industry_hint

        h1 = _get_industry_hint()
        h2 = _get_industry_hint()
        assert h1 == h2
