"""source_trust_config 幂等播种 (PLAN-012 / DEV-14)。

config.authority_scores (dict[source_name -> score]) 为出厂配置源,
ensure_source_trust_config 将其幂等写入 source_trust_config 表 —
来源类型按 §7.1 Authority 表归类 (企业官方/主流平台/聚合/社交),
未知类型默认 aggregator (中立)。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.pipeline_models import SourceTrustConfig

# §7.1 来源类型归类 (已知平台映射; 其余默认 aggregator)
_PLATFORM_SOURCES = {"lagou", "zhaopin", "bosszhipin", "51job", "liepin", "boss"}
_ENTERPRISE_SOURCES = {"sap", "esco"}


def _classify_source_type(name: str) -> str:
    if name in _ENTERPRISE_SOURCES:
        return "enterprise"
    if name in _PLATFORM_SOURCES:
        return "platform"
    return "aggregator"


async def ensure_source_trust_config(session: AsyncSession) -> int:
    """幂等播种: 将 config.authority_scores 写入 source_trust_config.

    Returns: 本次写入的行数 (已存在的跳过, 不覆盖人工调整)。
    """
    existing = await session.execute(select(SourceTrustConfig.source_name))
    known = {row[0] for row in existing.all()}

    inserted = 0
    for name, score in settings.authority_scores.items():
        if name in known:
            continue
        session.add(SourceTrustConfig(
            source_name=name,
            authority_score=float(score),
            source_type=_classify_source_type(name),
        ))
        inserted += 1
    if inserted:
        await session.commit()
    return inserted
