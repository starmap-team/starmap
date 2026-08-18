"""Skill icon resolution helper (2026-08-17 多模块联动 Phase 1).

背景：整个项目无 skill icon 字段/字典 —— radar 图、技能图谱、技能选择器
全是 ECharts default 符号。本模块提供 3 层降级 icon 解析:

  1. canonical: skill_name 直接命中 icon_taxonomy.yaml 的 canonical 技能
  2. alias: skill_name 命中 yaml 的 alias（如 "k8s" → "Kubernetes"）
  3. category fallback: 技能 category (hard_skill/soft_skill/tool) 决定默认图标
  4. unknown fallback: 未识别技能 → ⚡

设计选择：emoji 而非 Lucide/Heroicons —— 不依赖外部 CDN/字体，离线部署可用。

与 industry_taxonomy.yaml 同样的 YAML 加载模式（启动时一次性 load 内存）。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

DEFAULT_ICON: Final = "⚡"
FALLBACK_ICONS: Final = {
    "hard_skill": "💻",
    "soft_skill": "🤝",
    "tool": "🔧",
    "certificate": "📜",
    "unknown": "⚡",
}

_ICON_TAXONOMY_PATH_CANDIDATES = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "app"
    / "config"
    / "skill_icon_taxonomy.yaml",
    Path("/app/config/skill_icon_taxonomy.yaml"),
)


def _find_taxonomy_path() -> Path | None:
    for p in _ICON_TAXONOMY_PATH_CANDIDATES:
        if p.exists():
            return p
    return None


# 模块级缓存
_CANONICAL_ICONS: dict[str, str] = {}  # name.lower() → icon
_ALIAS_ICONS: dict[str, str] = {}  # alias.lower() → icon
_CATEGORY_FALLBACK: dict[str, str] = {}  # category → default icon
_SOFT_SKILL_KEYWORDS: set[str] = set()
_TAXONOMY_LOADED: bool = False


def _load_skill_icon_taxonomy() -> None:
    """从 YAML 加载技能图标字典（启动时一次性 load 内存）。"""
    global _CANONICAL_ICONS, _ALIAS_ICONS, _CATEGORY_FALLBACK
    global _SOFT_SKILL_KEYWORDS, _TAXONOMY_LOADED
    if _TAXONOMY_LOADED:
        return

    path = _find_taxonomy_path()
    if path is None:
        logger.warning("skill_icon_taxonomy.yaml not found — all icons fallback to DEFAULT_ICON")
        _TAXONOMY_LOADED = True
        return

    try:
        import yaml  # noqa: PLC0415
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as exc:  # noqa: BLE001 — fail-soft
        logger.warning("Failed to load skill_icon_taxonomy.yaml: {}", exc)
        _TAXONOMY_LOADED = True
        return

    for entry in data.get("canonical_skills", []):
        name = str(entry.get("name", "")).strip()
        icon = str(entry.get("icon", "")).strip() or DEFAULT_ICON
        if name:
            _CANONICAL_ICONS[name.lower()] = icon
        for alias in entry.get("aliases", []):
            alias_str = str(alias).strip()
            if alias_str:
                _ALIAS_ICONS[alias_str.lower()] = icon

    for cat, icon in (data.get("category_default_icons") or {}).items():
        _CATEGORY_FALLBACK[str(cat).lower()] = str(icon) or DEFAULT_ICON

    for kw in data.get("soft_skill_keywords", []):
        _SOFT_SKILL_KEYWORDS.add(str(kw).strip().lower())

    _TAXONOMY_LOADED = True
    logger.info(
        "Loaded skill_icon_taxonomy: {} canonical + {} aliases + {} categories + {} soft_skill_keywords",
        len(_CANONICAL_ICONS), len(_ALIAS_ICONS), len(_CATEGORY_FALLBACK), len(_SOFT_SKILL_KEYWORDS),
    )


def get_icon_for_skill(
    skill_name: str | None,
    category: str | None = None,
) -> str:
    """解析技能 icon（3 层降级：canonical → alias → category fallback → DEFAULT_ICON）。

    Args:
        skill_name: 技能名（支持 name_cn 优先，未命中再试 name）
        category: 技能 category（hard_skill/soft_skill/tool/certificate）

    Returns:
        emoji 字符串 icon（保证非空）
    """
    _load_skill_icon_taxonomy()

    if skill_name:
        key = skill_name.strip().lower()
        if key in _CANONICAL_ICONS:
            return _CANONICAL_ICONS[key]
        if key in _ALIAS_ICONS:
            return _ALIAS_ICONS[key]

    if category:
        cat_key = category.strip().lower()
        if cat_key in _CATEGORY_FALLBACK:
            return _CATEGORY_FALLBACK[cat_key]

    return DEFAULT_ICON


def is_likely_soft_skill(skill_name: str | None) -> bool:
    """判断技能名是否可能是软技能（用于前端 category 二次校准）。"""
    if not skill_name:
        return False
    _load_skill_icon_taxonomy()
    name_lower = skill_name.strip().lower()
    for kw in _SOFT_SKILL_KEYWORDS:
        if kw in name_lower:
            return True
    return False


def get_all_canonical_skills() -> list[str]:
    """返回 taxonomy 中所有 canonical 技能名（前端候选技能选择器用）。"""
    _load_skill_icon_taxonomy()
    return sorted(_CANONICAL_ICONS.keys())


def get_icon_taxonomy_stats() -> dict[str, int]:
    """返回字典统计信息（admin 面板 / 调试用）。"""
    _load_skill_icon_taxonomy()
    return {
        "canonical_count": len(_CANONICAL_ICONS),
        "alias_count": len(_ALIAS_ICONS),
        "category_fallback_count": len(_CATEGORY_FALLBACK),
        "soft_skill_keyword_count": len(_SOFT_SKILL_KEYWORDS),
    }
