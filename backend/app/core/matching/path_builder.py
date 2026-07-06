"""学习路径构建模块。

基于技能前置依赖关系，为缺失技能构建个性化学习路径。
"""

from __future__ import annotations

from app.core.extraction.normalize import normalize_skill


def _canonical_skill_name(name: str) -> str:
    """Canonicalize a skill name."""
    result = normalize_skill(name, use_vector=False)
    return result.normalized or name.strip()


def build_learning_path(
    skill_name: str,
    owned_skills: set[str],
    prerequisite_map: dict[str, list[str]],
) -> list[str]:
    """递归构建技能学习路径。

    基于 PREREQUISITE_MAP 中的前置依赖关系，从目标技能出发递归遍历
    其所有前置技能，生成线性的学习顺序列表。
    仅包含求职者尚未掌握的技能，已掌握的技能自动过滤。

    Args:
        skill_name: 目标技能名称
        owned_skills: 已掌握的技能集合
        prerequisite_map: 技能前置关系映射

    Returns:
        学习路径列表（按学习顺序排列）
    """
    ordered: list[str] = []
    seen: set[str] = set()

    def visit(name: str) -> None:
        canonical = _canonical_skill_name(name)
        if canonical in seen:
            return
        seen.add(canonical)
        for prerequisite in prerequisite_map.get(canonical, []):
            visit(prerequisite)
        if canonical not in owned_skills:
            ordered.append(canonical)

    visit(skill_name)
    return ordered or [_canonical_skill_name(skill_name)]
