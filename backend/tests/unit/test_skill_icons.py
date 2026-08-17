"""Skill icon taxonomy (2026-08-17) — 多层防御第 1 层图标解析。

锁定 backend/app/core/extraction/skill_icons.py 的 4 层降级行为：
1. canonical: skill_name 直接命中 yaml
2. alias: skill_name 命中 yaml alias
3. category fallback: 用技能 category (hard_skill/soft_skill/tool) 决定
4. unknown fallback: ⚡
"""
from __future__ import annotations

from app.core.extraction.skill_icons import (
    DEFAULT_ICON,
    FALLBACK_ICONS,
    get_all_canonical_skills,
    get_icon_for_skill,
    get_icon_taxonomy_stats,
    is_likely_soft_skill,
)


class TestIconResolutionLayers:
    """4 层降级：canonical → alias → category → DEFAULT_ICON."""

    def test_canonical_python(self):
        """Python 直接命中 canonical 🐍."""
        assert get_icon_for_skill("Python") == "🐍"

    def test_canonical_react(self):
        assert get_icon_for_skill("React") == "⚛️"

    def test_canonical_docker(self):
        assert get_icon_for_skill("Docker") == "🐳"

    def test_alias_k8s_resolves_to_kubernetes(self):
        """alias 'k8s' → canonical 'Kubernetes' 图标 ☸️."""
        assert get_icon_for_skill("k8s") == "☸️"

    def test_alias_kubernetes_aliases(self):
        """alias 'K8s'（不同大小写）也能匹配."""
        assert get_icon_for_skill("K8s") == "☸️"

    def test_alias_python3(self):
        """alias 'python3' → canonical 'Python' 🐍."""
        assert get_icon_for_skill("python3") == "🐍"

    def test_name_cn_with_alias_via_canonical(self):
        """中文 canonical（如 'LLM'）也能命中."""
        # LLM 是 canonical name（从 yaml 加载）
        icon = get_icon_for_skill("LLM")
        assert icon == "🧠"  # 或者 yaml 中的值

    def test_unknown_skill_uses_category_fallback(self):
        """未登记技能 + 有 category → category 默认图标."""
        icon = get_icon_for_skill("SomeRandomUnknownSkill", category="hard_skill")
        assert icon == FALLBACK_ICONS["hard_skill"]
        assert icon == "💻"

    def test_unknown_skill_soft_skill(self):
        icon = get_icon_for_skill("某未知软技能", category="soft_skill")
        assert icon == FALLBACK_ICONS["soft_skill"]

    def test_unknown_skill_tool(self):
        icon = get_icon_for_skill("某工具", category="tool")
        assert icon == FALLBACK_ICONS["tool"]

    def test_unknown_skill_no_category_falls_back_to_default(self):
        """未登记技能 + 无 category → DEFAULT_ICON ⚡."""
        icon = get_icon_for_skill("SomeRandomUnknownSkill", category=None)
        assert icon == DEFAULT_ICON

    def test_empty_skill_name_with_category(self):
        """skill_name 为空 + 有 category → category fallback."""
        assert get_icon_for_skill("", category="hard_skill") == "💻"

    def test_none_skill_name_with_category(self):
        assert get_icon_for_skill(None, category="tool") == "🔧"

    def test_none_skill_name_no_category(self):
        assert get_icon_for_skill(None, category=None) == DEFAULT_ICON

    def test_case_insensitive_canonical(self):
        """大小写不敏感：'python' / 'PYTHON' / 'Python' 都能命中 🐍."""
        assert get_icon_for_skill("python") == "🐍"
        assert get_icon_for_skill("PYTHON") == "🐍"
        assert get_icon_for_skill("Python") == "🐍"

    def test_whitespace_stripped(self):
        """首尾空白被 strip."""
        assert get_icon_for_skill("  Python  ") == "🐍"


class TestSoftSkillDetection:
    """is_likely_soft_skill() 用于前端 category 二次校准。"""

    def test_communication_keyword_chinese(self):
        assert is_likely_soft_skill("沟通能力") is True

    def test_leadership_keyword(self):
        assert is_likely_soft_skill("技术领导力") is True

    def test_english_communication(self):
        assert is_likely_soft_skill("Communication Skills") is True

    def test_hard_skill_returns_false(self):
        assert is_likely_soft_skill("Python") is False
        assert is_likely_soft_skill("Docker") is False
        assert is_likely_soft_skill("Kubernetes") is False

    def test_none_or_empty(self):
        assert is_likely_soft_skill(None) is False
        assert is_likely_soft_skill("") is False


class TestTaxonomyStats:
    """get_icon_taxonomy_stats / get_all_canonical_skills 暴露给 admin 面板。"""

    def test_stats_have_positive_counts(self):
        stats = get_icon_taxonomy_stats()
        assert stats["canonical_count"] >= 100, f"Expected >= 100 canonical skills, got {stats}"
        assert stats["alias_count"] >= 50, f"Expected >= 50 aliases, got {stats}"
        # 至少有 4 个 category default (hard_skill/soft_skill/tool/certificate)
        assert stats["category_fallback_count"] >= 4, "Should have at least 4 category defaults"

    def test_all_canonical_skills_returned(self):
        skills = get_all_canonical_skills()
        # 注意: get_all_canonical_skills 返回小写 keys（与 lookup 行为一致）
        assert "python" in skills
        assert "docker" in skills
        assert "kubernetes" in skills
        # 验证全部小写
        for s in skills:
            assert s == s.lower(), f"Skill {s!r} not lowercase"