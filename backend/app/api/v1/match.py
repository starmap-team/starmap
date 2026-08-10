"""Match API.

注意:所有 Pydantic 模型已迁移到 backend/app/schemas/match.py(Phase X 闭环审计)。
路由层只 import,不再内联 BaseModel 定义。
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy import select as sa_select
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, get_neo4j_driver
from app.exceptions import MatchingError, StarMapError
from app.models.extraction_models import PositionRecord
from app.schemas.match import (
    BatchMatchItem,  # noqa: F401  (重导出:测试/前端经 match_api.BatchMatchItem 构造)
    BatchMatchRequest,
    MatchRequestInput,
    MatchResponse,
    PersonSkillInput,
    PositionRecommendation,
    ReverseMatchRequest,
    ReverseMatchResponse,
)
from app.services.match_service import (
    MatchService,
    compute_competitiveness,
    get_match_result,
    run_match,
)

router = APIRouter(prefix="/match", tags=["match"])


async def _run_match_request(body: MatchRequestInput, driver: Any, session: AsyncSession) -> MatchResponse:
    """Execute match and persist result via the service layer.

    The service's run_match() now handles PostgreSQL persistence internally,
    so no duplicate INSERT is needed here.
    """
    result = await run_match(
        target_position=body.target_position,
        person_skills=[item.model_dump() for item in body.person_skills],
        threshold=body.options.threshold,
        driver=driver,
        db_session=session,
    )
    return MatchResponse(**result)


@router.post("/position", response_model=MatchResponse)
async def match_position(
    body: MatchRequestInput,
    driver: Annotated[Any, Depends(get_neo4j_driver)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MatchResponse:
    """Match resume skills against a target position."""
    if not body.person_skills:
        raise HTTPException(status_code=400, detail="person_skills cannot be empty.")
    return await _run_match_request(body, driver, session)


@router.post("/diagnose", response_model=MatchResponse)
async def diagnose_match(
    body: MatchRequestInput,
    driver: Annotated[Any, Depends(get_neo4j_driver)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MatchResponse:
    """Alias for /match/position — delegates to match_position.

    x-audit-note: L1 — This is a convenience alias; /match/position is the canonical endpoint.
    """
    return await match_position(body, driver, session)


@router.get("/result/{match_id}", response_model=MatchResponse)
async def get_match_result_detail(
    match_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MatchResponse:
    """Return a previously generated match result."""
    result = await get_match_result(match_id, db_session=session)
    if result is None:
        raise HTTPException(status_code=404, detail="Match result not found")
    return MatchResponse(**result)


@router.get("/history")
async def match_history(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Return recent match results."""
    try:
        result = await session.execute(
            text("""
                SELECT match_id, target_position, match_score, matched_skills, created_at
                FROM match_results
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """),
            {"limit": limit, "offset": offset},
        )
        rows = result.fetchall()
        items = []
        for row in rows:
            items.append({
                "match_id": row[0],
                "target_position": row[1],
                "match_score": float(row[2] or 0),
                "matched_skills": row[3] if isinstance(row[3], list) else [],
                "created_at": str(row[4]) if row[4] else None,
            })
        return {"items": items}
    except MatchingError as exc:
        logger.exception("Matching operation failed: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in matching: {}", exc)
        raise HTTPException(status_code=500, detail="匹配处理异常") from exc


@router.get("/competitiveness/{position}")
async def get_competitiveness(
    position: str,
    driver: Annotated[Any, Depends(get_neo4j_driver)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Return competitiveness analysis for a target position."""
    result = await compute_competitiveness(
        target_position=position,
        driver=driver,
        db_session=session,
    )
    # fix (M13): 兼容前端 store（`data.items ?? data.skills`）。原响应无 items/skills 字段
    # 导致前端 competitiveness 恒空数组。现补 items（瓶颈技能）和 skills（必备+加分）别名。
    bottleneck = result.get("bottleneck_skills") or []
    required = result.get("required_count", 0)
    bonus = result.get("bonus_count", 0)
    result["items"] = bottleneck
    result["skills"] = {
        "required_count": required,
        "bonus_count": bonus,
        "total": required + bonus,
    }
    return result


@router.post("/batch")
async def batch_match(
    body: BatchMatchRequest,
    driver: Annotated[Any, Depends(get_neo4j_driver)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Batch match: run match for multiple items at once.

    Payload compatibility: accepts both ``position`` (frontend learning store)
    and ``position_name`` (legacy contract) as the target position field.
    Each item: ``{ "skills": [...], "position": "..." }``.
    """
    items = body.entries
    results = []
    for item in items[:20]:
        # 兼容前端 {position} 与历史契约 {position_name} 两种字段命名
        position = item.position_name or item.position or ""
        skills = [s.model_dump() if isinstance(s, PersonSkillInput) else s for s in item.skills]
        try:
            result = await run_match(
                target_position=position,
                person_skills=skills,
                driver=driver,
                db_session=session,
            )
            results.append({"position_name": position, "result": result})
        except Exception as exc:
            # 批量匹配逐条隔离:任何单条失败(含 PositionNotFoundError 等 StarMapError 子类)
            # 记为 error 条目,不中断整批。契约:test_batch_partial_failure_isolation。
            results.append({"position_name": position, "error": str(exc)})
    # fix (M13): 响应中加 summary 便于前端一致性展示（plan: 当前前端按扁平 BatchMatchItem 消费，match_score 恒为 undefined）
    success_count = sum(1 for r in results if "result" in r)
    return {
        "results": results,
        "items": results,  # 别名：兼容前端按扁平 items 消费
        "summary": {
            "total": len(results),
            "success": success_count,
            "failed": len(results) - success_count,
        },
        "total": len(results),
    }


# ── FE-04: Reverse match (skills → position recommendations) ──
# ReverseMatchRequest / PositionRecommendation / ReverseMatchResponse
# 已迁至 backend/app/schemas/match.py,路由层只引用。


@router.post("/recommend", response_model=ReverseMatchResponse)
async def recommend_positions(
    body: ReverseMatchRequest,
    driver: Annotated[Any, Depends(get_neo4j_driver)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReverseMatchResponse:
    """FE-04: Reverse match — given user skills, recommend suitable positions.

    Scans available positions, computes match score for each,
    and returns the top-k positions ranked by match score.
    """
    # Get distinct position names from the database
    try:
        result = await session.execute(
            sa_select(PositionRecord.name).distinct().limit(200)
        )
        position_names = [row[0] for row in result.fetchall()]
    except MatchingError as exc:
        logger.exception("Matching operation failed: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in matching: {}", exc)
        raise HTTPException(status_code=500, detail="匹配处理异常") from exc

    if not position_names:
        # Fallback: try Neo4j
        if driver is not None:
            try:
                async with driver.session() as neo_session:
                    cypher_result = await neo_session.run(
                        "MATCH (p:Position) RETURN p.name AS name LIMIT 200"
                    )
                    position_names = []
                    async for rec in cypher_result:
                        if rec.get("name"):
                            position_names.append(rec["name"])
            except MatchingError as exc:
                logger.exception("Matching operation failed: {}", exc)
                raise HTTPException(status_code=500, detail=str(exc)) from exc
            except StarMapError:
                raise
            except Exception as exc:
                logger.exception("Unexpected error in matching: {}", exc)
                raise HTTPException(status_code=500, detail="匹配处理异常") from exc

    if not position_names:
        return ReverseMatchResponse(
            recommendations=[],
            total_positions_scanned=0,
            skills_provided=len(body.person_skills),
        )

    # Run match for each position and collect scores
    match_svc = MatchService()
    person_skills_dicts = [s.model_dump() for s in body.person_skills]

    recommendations: list[PositionRecommendation] = []
    for pos_name in position_names:
        try:
            # fix: recommend 是扫描式只读匹配，不持久化到 match_results，避免污染 /match/history
            result = await match_svc.run_match(
                target_position=pos_name,
                person_skills=person_skills_dicts,
                threshold=body.min_score,
                driver=driver,
                db_session=None,
            )
            score = result.get("match_score", 0.0)
            if score >= body.min_score:
                matched = result.get("matched_skills", [])
                gap = result.get("gap_skills", [])
                # Compute skill coverage: what fraction of position's total skills does user cover?
                total_position_skills = len(matched) + len(gap)
                coverage = len(matched) / total_position_skills if total_position_skills > 0 else 1.0
                recommendations.append(PositionRecommendation(
                    position_name=pos_name,
                    match_score=round(score, 4),
                    matched_skills=matched,
                    gap_skills=gap,
                    skill_coverage=round(coverage, 4),
                ))
        except MatchingError:
            continue
        except StarMapError:
            raise
        except Exception:
            continue  # skip positions that fail

    # Sort by match_score descending, take top_k
    recommendations.sort(key=lambda r: r.match_score, reverse=True)
    recommendations = recommendations[: body.top_k]

    return ReverseMatchResponse(
        recommendations=recommendations,
        total_positions_scanned=len(position_names),
        skills_provided=len(body.person_skills),
    )
