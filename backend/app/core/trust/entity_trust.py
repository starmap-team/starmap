"""EntityTrustScorer — 实体信任度四因子评分器（全系统唯一入口）。

对齐设计文档 §5.4 / §6.2 权威公式（Golden Set 校准权重）:

    T = 0.3·source_diversity + 0.3·extractor_conf + 0.25·cross_verify + 0.15·time_decay

本模块解决信任度体系统一（Phase 19）：此前系统存在三套互相脱节的口径——
① quality 直方图用 source_count/10 代理（频次当信任，把冷门误判为不可信）
② KPI 平均信任度读 Neo4j Skill.trust_score（历史 0.5 脏数据，无流程更新）
③ evolution trust_scorer（演化变更信任，独立第三套算法）

实体信任（Skill/Position 节点的可信度）统一走本模块；演化 trust_scorer 保持独立
（语义不同：变更可信度 vs 实体可信度，见 19-CONTEXT.md D-01）。
"""
from __future__ import annotations

import math
from datetime import UTC, datetime

from app.config import settings

# ── 四因子权重（设计 §6.2 Golden Set 校准，集中在此可审计调优）──
TRUST_WEIGHTS: dict[str, float] = {
    "source_diversity": 0.3,
    "extractor_conf": 0.3,
    "cross_verify": 0.25,
    "time_decay": 0.15,
}

# source_diversity 饱和点：source_count 超过此值不再增加信任
SOURCE_SATURATION = settings.trust_max_sources  # 10

# time_decay 半衰窗口（天）：30 天内检测到 → 满信任
FRESH_WINDOW_DAYS = 30


class EntityTrustScorer:
    """技能/岗位实体信任度评分器（纯函数，无状态）。"""

    def source_diversity(self, source_count: int) -> float:
        """来源多样性因子：sqrt 饱和曲线，source_count 高 → 接近 1.0。"""
        if source_count <= 0:
            return 0.0
        return min(1.0, math.sqrt(source_count / SOURCE_SATURATION))

    def extractor_conf(self, confidence: float | None) -> float:
        """抽取置信度因子：LLM 抽取 validation.confidence。

        confidence 缺失时返回 0.5 中性兜底（不报错、不归零——新抽取数据未回填置信
        度时不应被误判为完全不可信）。
        """
        if confidence is None:
            return 0.5
        return max(0.0, min(1.0, float(confidence)))

    def cross_verify(self, source_count: int) -> float:
        """多源交叉验证因子：设计 §7.2 ② —— source_count ≥ 2 标记 verified。"""
        return 1.0 if source_count >= 2 else 0.0

    def time_decay(self, last_detected_at: datetime | None) -> float:
        """时间衰减因子：近 30 天检测到 → 1.0；越久远 → 指数衰减。"""
        if last_detected_at is None:
            return 0.0
        last = last_detected_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        now = datetime.now(UTC)
        days = max(0.0, (now - last).total_seconds() / 86400.0)
        if days <= FRESH_WINDOW_DAYS:
            return 1.0
        return math.exp(-settings.trust_decay_rate * (days - FRESH_WINDOW_DAYS) / FRESH_WINDOW_DAYS)

    def score(
        self,
        source_count: int,
        confidence: float | None,
        last_detected_at: datetime | None,
    ) -> float:
        """四因子加权和，clamp [0.0, 1.0]，round 4 位。"""
        trust = (
            TRUST_WEIGHTS["source_diversity"] * self.source_diversity(source_count)
            + TRUST_WEIGHTS["extractor_conf"] * self.extractor_conf(confidence)
            + TRUST_WEIGHTS["cross_verify"] * self.cross_verify(source_count)
            + TRUST_WEIGHTS["time_decay"] * self.time_decay(last_detected_at)
        )
        return round(max(0.0, min(1.0, trust)), 4)
