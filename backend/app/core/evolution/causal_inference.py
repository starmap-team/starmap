"""§7.6 因果推理轻量版 — 技能-岗位关联统计显著性 (DEV-01, P0)。

计划书规格: "仅条件独立性检测（PC 算法），用于验证技能-岗位关联的统计显著性。"

轻量实现: Fisher 精确检验 (2x2 列联表, 超几何分布精确 p 值)。
- 无外部依赖 (纯 stdlib math.comb)
- 对技能×岗位共现做独立性检验: H0 = 技能出现与岗位提及相互独立
- p < 0.05 → 关联统计显著 (拒绝独立)
- phi 系数: 效应量 [-1, 1]

数据来源: skill_timeseries.positions (JSON 职位列表) — 技能出现记录 vs 对照集。
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evolution_models import SkillTimeseries

ALPHA = 0.05  # 显著性水平


def fisher_exact_p(a: int, b: int, c: int, d: int) -> float:
    """双侧 Fisher 精确检验 p 值 (2x2 表 [[a, b], [c, d]])。

    固定行/列边缘, 遍历所有同边缘表, 累积概率 <= 观测表概率者。
    输入非负整数; 若边缘非法 (无满足组合) 返回 1.0。
    """
    if min(a, b, c, d) < 0:
        return 1.0
    row1, row2 = a + b, c + d
    col1, col2 = a + c, b + d
    n = row1 + row2
    if n == 0 or col1 == 0 or col2 == 0:
        return 1.0  # 无变化数据, 无法检验
 # 边缘固定的所有可能表: 第一行第一格 x 取值范围
    lo = max(0, col1 - row2)
    hi = min(row1, col1)
    if lo > hi:
        return 1.0
    p_obs = math.comb(row1, a) * math.comb(row2, c) / math.comb(n, col1)
    p_total = 0.0
    for x in range(lo, hi + 1):
        y = row1 - x
        z = col1 - x
        w = row2 - z
        if y < 0 or z < 0 or w < 0:
            continue
        p = math.comb(row1, x) * math.comb(row2, z) / math.comb(n, col1)
        if p <= p_obs + 1e-15:  # 双侧累积
            p_total += p
    return min(1.0, p_total)


def phi_coefficient(a: int, b: int, c: int, d: int) -> float:
    """phi 系数 (2x2 关联效应量) [-1, 1]; 0=无关联。"""
    denom = math.sqrt((a + b) * (c + d) * (a + c) * (b + d))
    if denom == 0:
        return 0.0
    return (a * d - b * c) / denom


def analyze_contingency(a: int, b: int, c: int, d: int) -> dict[str, Any]:
    """对 2x2 列联表做独立性检验, 返回完整统计。"""
    p_value = fisher_exact_p(a, b, c, d)
    phi = phi_coefficient(a, b, c, d)
    return {
        "a": a, "b": b, "c": c, "d": d,
        "p_value": round(p_value, 6),
        "significant": p_value < ALPHA,
        "phi": round(phi, 4),
        "method": "fisher_exact",
    }


async def skill_position_associations(
    skill: str,
    session: AsyncSession,
    *,
    alpha: float = ALPHA,
) -> dict[str, Any]:
    """技能-岗位关联显著性分析 (§7.6 轻量版)。

    从 skill_timeseries 聚合:
    - 技能出现记录: 含 positions 列表的记录
    - 对照集: 其他技能的 positions 聚合 (市场背景)

    对每个提及该技能的岗位构建 2x2 表:
      a = 含该技能且提及岗位 P 的记录数
      b = 含该技能但不含 P 的记录数
      c = 对照记录提及 P 数
      d = 对照记录不提 P 数
    """
    result = await session.execute(
        select(SkillTimeseries).where(SkillTimeseries.skill_name == skill)
    )
    skill_records = result.scalars().all()
    if not skill_records:
        return {"skill": skill, "associations": [], "total_records": 0}

 # 技能记录: positions 列表 (按记录去重计数 — 同记录重复提及只计 1 次)
    skill_pos: Counter[str] = Counter()
    for r in skill_records:
        for p in set(r.positions or []):
            if isinstance(p, str):
                skill_pos[p] += 1
    skill_total = len(skill_records)

 # 对照集: 其他技能全部记录
    other_result = await session.execute(
        select(SkillTimeseries).where(SkillTimeseries.skill_name != skill)
    )
    other_records = other_result.scalars().all()
    other_pos: Counter[str] = Counter()
    for r in other_records:
        for p in set(r.positions or []):
            if isinstance(p, str):
                other_pos[p] += 1
    other_total = len(other_records)

    associations: list[dict[str, Any]] = []
    for position, a in skill_pos.items():
        b = skill_total - a
        c = other_pos.get(position, 0)
        d = other_total - c
        stat = analyze_contingency(a, b, c, d)
        if stat["significant"] and abs(stat["phi"]) >= 0.1:  # 显著且有效应量
            stat["position"] = position
            associations.append(stat)

    associations.sort(key=lambda x: x["phi"], reverse=True)
    return {
        "skill": skill,
        "associations": associations,
        "total_records": skill_total,
        "control_records": other_total,
        "alpha": alpha,
    }
