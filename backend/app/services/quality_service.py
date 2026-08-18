"""Quality service layer — thin re-export of shared quality KPIs.

Layer-boundary rule: api/v1 → services → core. quality.py must not import
app.core.metrics directly, so this module re-exports the shared metric
functions (D1+D2 fix). Consumers outside services keep their exact signatures.
"""
from __future__ import annotations

from typing import Any

from app.core.metrics import ( # noqa: F401 — §metrics re-export (路由经 service 访问 core)
 avg_skill_trust,
 weekly_new_nodes,
)
from app.core.pipeline.quality_monitor import ( # noqa: F401 — 质量预警/快照 re-export
 generate_alerts,
 get_quality_snapshot,
)

__all__ = [
 "avg_skill_trust",
 "weekly_new_nodes",
 "generate_alerts",
 "get_quality_snapshot",
 "compute_trust_distribution",
]

async def compute_trust_distribution(session: Any) -> list[dict[str, Any]]:
 """ 四因子综合信任度分布（与 KPI avg(n.trust_score) 同口径）。

 从 PG 用 EntityTrustScorer 计算每个技能的真实信任度分桶，不依赖 Neo4j 时序。
 层边界修复（2026-08-14）：原 quality.py 直连 app.core.trust.entity_trust 的
 违规导入迁至此 service 层，路由经 service 访问 core。
 """
 import sqlalchemy as sa

 from app.core.trust.entity_trust import EntityTrustScorer # noqa: PLC0415
 from app.models.extraction_models import SkillRecord

 _trust_scorer = EntityTrustScorer
 _trust_scores: list[float] = []
 _skill_trust_rows = (
 await session.execute(
 sa.select(SkillRecord.source_count, SkillRecord.last_detected_at)
 )
 ).all
 for _row in _skill_trust_rows:
 _trust_scores.append(_trust_scorer.score(
 source_count=int(_row.source_count or 0),
 confidence=None, # PG 侧置信度在抽取记录表，逐技能关联成本高；source+time 已够分桶
 last_detected_at=_row.last_detected_at,
 ))
 trust_ranges = [
 ("0-20%", 0, 0.2), ("20-40%", 0.2, 0.4), ("40-60%", 0.4, 0.6),
 ("60-80%", 0.6, 0.8), ("80-100%", 0.8, 1.01),
 ]
 return [
 {"range": label, "count": int(sum(1 for t in _trust_scores if lo <= t < hi))}
 for label, lo, hi in trust_ranges
 ]
