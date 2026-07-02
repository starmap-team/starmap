"""Source authority scoring engine.

Computes a composite authority score (0.0 – 1.0) for each data source based on:
- Historical quality (avg quality score from past pipeline runs)
- Data volume   (total / valid records ratio)
- Consistency   (duplicate rate, freshness regularity)

The resulting scores are written back to the data_sources table.
"""
from __future__ import annotations

import statistics
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline_models import DataSourceRecord, PipelineRun


# ---------------------------------------------------------------------------
# Per-source scoring
# ---------------------------------------------------------------------------

def compute_authority(
    source_name: str,
    historical_quality: float,
    data_volume: float,
    consistency: float,
) -> float:
    """Return a composite authority score in [0.0, 1.0].

    Parameters
    ----------
    source_name : str
        Human-readable source label (used in logs only).
    historical_quality : float
        Average quality score from past runs (0.0 – 1.0).
    data_volume : float
        valid_records / total_records ratio (0.0 – 1.0).
    consistency : float
        1.0 - duplicate_rate (higher is better, 0.0 – 1.0).

    Weights: quality 50%, volume 25%, consistency 25%.
    """
    if historical_quality < 0 or data_volume < 0 or consistency < 0:
        logger.warning("Negative metric for source '{}', clamping to 0", source_name)
    historical_quality = max(0.0, min(1.0, historical_quality))
    data_volume = max(0.0, min(1.0, data_volume))
    consistency = max(0.0, min(1.0, consistency))

    score = (
        historical_quality * 0.50
        + data_volume * 0.25
        + consistency * 0.25
    )
    return round(min(1.0, max(0.0, score)), 4)


# ---------------------------------------------------------------------------
# Batch update
# ---------------------------------------------------------------------------

async def update_authority_scores(session: AsyncSession) -> dict[str, float]:
    """Recompute and persist authority scores for **all** data sources.

    Returns ``{source_name: new_authority_score}``.
    """
    result = await session.execute(select(DataSourceRecord))
    sources = list(result.scalars().all())

    updated: dict[str, float] = {}
    for src in sources:
        quality = src.avg_quality_score
        volume = (src.valid_records / src.total_records) if src.total_records > 0 else 0.0
        consistency = max(0.0, 1.0 - src.duplicate_rate)

        new_score = compute_authority(
            source_name=src.name,
            historical_quality=quality,
            data_volume=volume,
            consistency=consistency,
        )

        await session.execute(
            update(DataSourceRecord)
            .where(DataSourceRecord.id == src.id)
            .values(authority_score=new_score)
        )
        updated[src.name] = new_score

    await session.flush()
    logger.info("Updated authority scores for {} sources", len(updated))
    return updated
