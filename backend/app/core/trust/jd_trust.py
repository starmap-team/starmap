"""§7.1 多源交叉验证的数据信任度模型 (PLAN-012).

TrustScore(D) = w1*Authority(D) + w2*Timeliness(D) + w3*Independence(D) + w4*Consistency(D)

- Authority: 来源类型表 (企业官方 0.9 / 主流平台 0.7 / 聚合 0.5 / 社交 0.3)
- Timeliness: T(D) = exp(-2 * days / 180)  (发布时间越近越高, >6 月趋近 0)
- Independence: I(D) = 1 - max(同源 SimHash 相似度)  (高相似 = 疑似抄袭)
- Consistency: C(D) = 交叉验证技能数 / 总技能数  (技能需在 >=2 独立来源出现)
- 默认权重: w1=0.3, w2=0.2, w3=0.2, w4=0.3

校准 (权重网格搜索): w ∈ {0.1..0.4}, 取模型预测 vs 人工标签 Pearson 相关
最高的组合 — 实现已就绪, 待人工标注数据 (Golden Set 子集 ~50 条) 后运行。
"""
from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

# 默认权重 (校准前的出厂配置, 校准后由 config/外部覆盖)
DEFAULT_WEIGHTS: dict[str, float] = {
    "authority": 0.3,
    "timeliness": 0.2,
    "independence": 0.2,
    "consistency": 0.3,
}

# Authority 来源类型表
AUTHORITY_BY_SOURCE_TYPE: dict[str, float] = {
    "enterprise": 0.9,   # 企业官方招聘网站
    "platform": 0.7,     # 主流招聘平台 (BOSS/拉勾/猎聘)
    "aggregator": 0.5,   # 猎头/聚合网站
    "social": 0.3,       # 社交媒体/论坛
}

# 校准网格: 每维权重取值空间 (w1+w2+w3+w4 = 1)
_GRID_VALUES = (0.1, 0.2, 0.3, 0.4)


def authority_score(source_type: str) -> float:
    """来源权威性评分 [0, 1]; 未知类型取聚合档 0.5 (中立)."""
    return AUTHORITY_BY_SOURCE_TYPE.get(source_type, 0.5)


def timeliness_score(publish_date: str | None, now: datetime | None = None) -> float:
    """T(D) = exp(-2 * days/180). 无/非法日期 → 0.0 (证据缺失不信任)."""
    if not publish_date:
        return 0.0
    now = now or datetime.now(UTC)
    try:
        dt = datetime.fromisoformat(publish_date.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    days = max(0, (now - dt).days)
    return round(math.exp(-2.0 * days / 180.0), 4)


def independence_score(sim_scores: list[float] | None) -> float:
    """I(D) = 1 - max(同源相似度). 无同源样本 → 1.0 (无抄袭证据即独立)."""
    sims = sim_scores or []
    if not sims:
        return 1.0
    return round(1.0 - max(0.0, min(1.0, max(sims))), 4)


def consistency_score(cross_validated: int, total: int) -> float:
    """C(D) = 交叉验证技能数 / 总技能数. total<=0 → 0.0 (无技能可验证)."""
    if total <= 0:
        return 0.0
    return round(min(cross_validated, total) / total, 4)


def trust_score(jd: dict[str, Any], weights: dict[str, float] | None = None) -> dict[str, Any]:
    """§7.1 综合信任度计算.

    jd 输入字段: source_type / publish_date / sim_scores / cross_validated_skills / total_skills
    返回: {"trust_score": float, "factors": {authority, timeliness, independence, consistency}}
    """
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    factors = {
        "authority": authority_score(jd.get("source_type") or ""),
        "timeliness": timeliness_score(jd.get("publish_date")),
        "independence": independence_score(jd.get("sim_scores")),
        "consistency": consistency_score(
            int(jd.get("cross_validated_skills") or 0),
            int(jd.get("total_skills") or 0),
        ),
    }
    score = (
        w["authority"] * factors["authority"]
        + w["timeliness"] * factors["timeliness"]
        + w["independence"] * factors["independence"]
        + w["consistency"] * factors["consistency"]
    )
    return {
        "trust_score": round(max(0.0, min(1.0, score)), 4),
        "factors": factors,
    }


def _pearson(x: list[float], y: list[float]) -> float:
    """Pearson 相关系数 (标准库实现, 不引入 numpy 依赖)."""
    if len(x) != len(y) or len(x) < 2:
        return 0.0
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    num = sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True))
    dx = math.sqrt(sum((a - mx) ** 2 for a in x))
    dy = math.sqrt(sum((b - my) ** 2 for b in y))
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)


def grid_search_weights(
    samples: list[dict[str, Any]],
    human_labels: list[float],
) -> dict[str, Any]:
    """§7.1 网格校准: 权重空间 {0.1..0.4}^4 (sum=1), 选 Pearson 相关最高的组合.

    Args:
        samples: JD 特征 dict 列表 (source_type/publish_date/sim_scores/...)
        human_labels: 人工标注的真实可信度 (0-100, 归一化到 0-1)

    Returns:
        {"weights": {...}, "pearson": float, "combos_evaluated": int}
    """
    labels = [max(0.0, min(1.0, label / 100.0)) for label in human_labels]
 # 样本不足 (<2) 无法计算相关性 → 返回出厂默认权重
    if len(samples) < 2 or len(labels) < 2 or len(samples) != len(labels):
        return {"weights": dict(DEFAULT_WEIGHTS), "pearson": 0.0, "combos_evaluated": 0}
    best_weights: dict[str, float] = dict(DEFAULT_WEIGHTS)
    best_pearson = -1.0
    combos = 0

    for w1 in _GRID_VALUES:
        for w2 in _GRID_VALUES:
            for w3 in _GRID_VALUES:
                w4 = round(1.0 - w1 - w2 - w3, 1)
                if w4 not in _GRID_VALUES:
                    continue
                combos += 1
                weights = {"authority": w1, "timeliness": w2, "independence": w3, "consistency": w4}
                preds = [trust_score(s, weights)["trust_score"] for s in samples]
                p = _pearson(preds, labels)
                if p > best_pearson:
                    best_pearson, best_weights = p, weights

    return {"weights": best_weights, "pearson": round(best_pearson, 4), "combos_evaluated": combos}
