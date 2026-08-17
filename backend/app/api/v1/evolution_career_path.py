"""Evolution career-path endpoint — extracted from evolution.py (Phase 7 evolution domain split).

业务说明：职业路径规划 API，基于 EVOLVES_TO 关系发现潜在职业转换路径，含多步路径和方向分类。
注册到 evolution.py 的主 router（prefix="/evolution"），最终路径 /evolution/career-path/{position}。
"""
from __future__ import annotations

from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.models.evolution_models import EvolutionPath
from app.schemas.evolution import CareerPathNode, CareerPathResponse

router = APIRouter(tags=["职业路径"])


@router.get("/career-path/{position}", response_model=CareerPathResponse)
async def get_career_path(
    position: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    depth: Annotated[int, Query(ge=1, le=4, description="路径搜索深度")] = 2,
) -> CareerPathResponse:
    """Get career path planning from a given position.

    Uses EVOLVES_TO relationships to discover potential career transitions,
    including direct transitions and multi-step paths. Classifies each
    transition as forward (promotion), lateral, or up (senior).
    """
 # Fetch direct evolution paths (depth 1)
    stmt = (
        sa.select(EvolutionPath)
        .where(
            (EvolutionPath.source_position == position)
            | (EvolutionPath.target_position == position)
        )
        .order_by(EvolutionPath.similarity.desc())
        .limit(50)
    )
    result = await session.execute(stmt)
    records = result.scalars().all()

    nodes: list[CareerPathNode] = []
    seen_positions: set[str] = set()

    for r in records:
 # Determine direction: from source → target
        if r.source_position == position:
            target = r.target_position
            direction = "forward"
        else:
            target = r.source_position
            direction = "lateral"

        if target in seen_positions:
            continue
        seen_positions.add(target)

 # Classify direction heuristically based on title keywords
        from app.services.evolution_service import SENIOR_KEYWORDS  # noqa: PLC0415
        target_lower = target.lower()
        if any(kw in target_lower for kw in SENIOR_KEYWORDS):
            direction = "up"

        nodes.append(CareerPathNode(
            position=target,
            similarity=r.similarity,
            skill_overlap=r.skill_overlap or [],
            key_gaps=r.key_gaps or [],
            evidence_count=r.evidence_count,
            direction=direction,
        ))

 # Depth 2: follow the best forward paths for multi-step discovery
    if depth >= 2:
        second_hop_nodes: list[CareerPathNode] = []
        for first_hop in nodes[:5]:  # Top 5 first-hop positions
            stmt2 = (
                sa.select(EvolutionPath)
                .where(EvolutionPath.source_position == first_hop.position)
                .order_by(EvolutionPath.similarity.desc())
                .limit(5)
            )
            result2 = await session.execute(stmt2)
            records2 = result2.scalars().all()

            for r2 in records2:
                target2 = r2.target_position
                if target2 in seen_positions or target2 == position:
                    continue
                seen_positions.add(target2)

                direction2 = "up" if any(kw in target2.lower() for kw in SENIOR_KEYWORDS) else "forward"

                second_hop_nodes.append(CareerPathNode(
                    position=target2,
                    similarity=round(r2.similarity * first_hop.similarity, 3),
                    skill_overlap=r2.skill_overlap or [],
                    key_gaps=list(set(first_hop.key_gaps) | set(r2.key_gaps or [])),
                    evidence_count=r2.evidence_count,
                    direction=direction2,
                ))

        nodes.extend(second_hop_nodes)

 # Sort by similarity descending
    nodes.sort(key=lambda n: n.similarity, reverse=True)

    return CareerPathResponse(
        origin=position,
        nodes=nodes,
        total_paths=len(nodes),
    )
