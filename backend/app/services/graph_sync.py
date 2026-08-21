"""Neo4j 图谱同步 — 将 Pipeline 提取结果写入图谱。

从 graph_service.py 拆分（m7），职责单一：
  1. Inline 模式（遗留）：逐条 MERGE skills/edges/positions
  2. DB-Query 模式（推荐）：通过 graph_writer 批量写入完整本体
"""
from __future__ import annotations

from typing import Any

from loguru import logger
from neo4j.exceptions import Neo4jError
from sqlalchemy.exc import SQLAlchemyError

from app.exceptions import GraphProjectionError


async def recompute_skill_trust(session: Any, driver: Any) -> dict[str, Any]:
    """全量重算 Skill 节点 trust_score（Phase 19 D-02/D-04）。

    用 §6.2 四因子公式(EntityTrustScorer)对全部 SkillRecord 重算信任度并写回 Neo4j，
    覆盖历史 0.5 脏数据（投影不写 trust_score 时代的默认值）。幂等：重复调用结果一致。

    Returns: {"skills": n, "updated": m}
    """
    from sqlalchemy import select

    from app.core.trust.entity_trust import EntityTrustScorer
    from app.models.extraction_models import PositionSkillRelation, SkillRecord

    if driver is None:
        return {"skills": 0, "updated": 0}

    # 1. 全部技能 + 审核状态（approved 技能重算时保底 0.8，避免每日重算覆盖审核高值）
    skill_rows = (
        await session.execute(
            select(
                SkillRecord.id,
                SkillRecord.name,
                SkillRecord.source_count,
                SkillRecord.last_detected_at,
                SkillRecord.review_status,
            )
        )
    ).all()

    # 2026-08-21 (debug 修复): confidence 从 PSR 按技能聚合 —— 原实现用
    # JDExtractionRecord.job_title 建 dict 却用 SkillRecord.name（技能名）查，
    # 0/1229 命中 → 所有技能 confidence 走 0.5 兜底。PSR 有真实 confidence。
    from sqlalchemy import func

    conf_stmt = (
        select(
            PositionSkillRelation.skill_id,
            func.avg(PositionSkillRelation.confidence),
        )
        .where(PositionSkillRelation.confidence.isnot(None))
        .group_by(PositionSkillRelation.skill_id)
    )
    conf_rows = (await session.execute(conf_stmt)).all()
    conf_by_skill: dict[str, float] = {str(sid): float(avg) for sid, avg in conf_rows}

    scorer = EntityTrustScorer()
    updated = 0
    async with driver.session() as neo4j_session:
        for row in skill_rows:
            confidence = conf_by_skill.get(str(row.id))
            trust = scorer.score(
                source_count=int(row.source_count or 0),
                confidence=confidence,
                last_detected_at=row.last_detected_at,
            )
            # 审核补偿：approved 技能保底 0.8 —— 审核通过 = 人工确认可信，
            # 不因单源/置信缺失被四因子拉低（原实现次日重算把审核 1.0 拉回 0.39）
            if row.review_status == "approved":
                trust = max(trust, 0.8)
            await neo4j_session.run(
                "MATCH (s:Skill {canonical_id: $cid}) "
                "SET s.trust_score = $trust, s.trust_updated_at = datetime()",
                cid=str(row.id),
                trust=trust,
            )
            updated += 1
    logger.info("recompute_skill_trust: {} skills, {} updated", len(skill_rows), updated)
    return {"skills": len(skill_rows), "updated": updated}


async def sync_from_pipeline(
    run_id: str,
    new_skills: list[dict[str, Any]] | None = None,
    new_edges: list[dict[str, Any]] | None = None,
    new_positions: list[dict[str, Any]] | None = None,
    extraction_data: dict[str, Any] | None = None,
    target_position: str = "",
) -> dict[str, Any]:
    # 业务说明：将 Pipeline（如 JD 解析流水线）提取出的职位、技能及关系数据同步写入 Neo4j 图谱，
    # 采用 MERGE 语义保证幂等性，支持两种写入模式：
    #   1. Inline 模式（遗留）：直接传入 new_skills / new_edges / new_positions 进行逐条 MERGE；
    #   2. DB-Query 模式（推荐）：传入 extraction_data，函数会查询 PostgreSQL 中的 JDExtractionRecord，
    #      并通过 graph_writer.batch_write_extractions 使用完整的本体（7 节点类型、8 关系类型）批量写入。
    """将 pipeline 提取结果写入 Neo4j 图谱（MERGE 幂等）。

    Supports two modes:
      1. **Inline mode** (legacy): pass new_skills / new_edges / new_positions directly.
      2. **DB-query mode** (preferred): pass extraction_data from Step 2, and optionally
         query JDExtractionRecord from PostgreSQL for richer ontology triples via
         graph_writer.batch_write_extractions.

    When extraction_data is provided, the function queries completed JDExtractionRecords
    created within the pipeline run timeframe and writes them using the full ontology
    (7 node types, 8 relationship types) with retry logic.
    """
    from app.services.resources import resources as app_resources

    driver = app_resources.neo4j_driver
    if driver is None:
        return {"synced": False, "error": "neo4j_driver_unavailable", "count": 0}

    # ── DB-query mode: use graph_writer.batch_write_extractions ──
    if extraction_data is not None:
        return await _sync_via_graph_writer(run_id, driver, app_resources, extraction_data, target_position=target_position)

    # ── Inline mode (legacy): direct MERGE of skills / edges / positions ──
    total_nodes = 0
    total_edges = 0
    errors: list[str] = []

    try:
        async with driver.session() as session:
            for pos in (new_positions or []):
                try:
                    await session.run(
                        "MERGE (p:Position {name: $name}) SET p.industry = $industry, p.updated_at = datetime()",
                        name=pos.get("name", ""), industry=pos.get("industry", ""),
                    )
                    total_nodes += 1
                except (Neo4jError, SQLAlchemyError) as exc:
                    errors.append(f"position '{pos.get('name')}': {exc}")
                except Exception as exc:
                    logger.exception("Unexpected error in sync position: {}", exc)
                    errors.append(f"position '{pos.get('name')}': {GraphProjectionError(str(exc))}")

            for skill in (new_skills or []):
                try:
                    await session.run(
                        "MERGE (s:Skill {name: $name}) SET s.category = $category, s.source_count = coalesce(s.source_count, 0) + 1",
                        name=skill.get("name", ""), category=skill.get("category", "hard_skill"),
                    )
                    total_nodes += 1
                except (Neo4jError, SQLAlchemyError) as exc:
                    errors.append(f"skill '{skill.get('name')}': {exc}")
                except Exception as exc:
                    logger.exception("Unexpected error in sync skill: {}", exc)
                    errors.append(f"skill '{skill.get('name')}': {GraphProjectionError(str(exc))}")

            for edge in (new_edges or []):
                try:
                    await session.run(
                        "MATCH (p:Position {name: $pos_name}) MATCH (s:Skill {name: $skill_name}) "
                        "MERGE (p)-[r:REQUIRES]->(s) SET r.level = $level, r.required = $required",
                        pos_name=edge.get("position_name", ""), skill_name=edge.get("skill_name", ""),
                        level=edge.get("level", "熟悉"), required=edge.get("required", True),
                    )
                    total_edges += 1
                except (Neo4jError, SQLAlchemyError) as exc:
                    errors.append(f"edge: {exc}")
                except Exception as exc:
                    logger.exception("Unexpected error in sync edge: {}", exc)
                    errors.append(f"edge: {GraphProjectionError(str(exc))}")

        logger.info("sync_from_pipeline (inline): {} nodes, {} edges (run_id={})", total_nodes, total_edges, run_id)
        return {"synced": len(errors) == 0, "count": total_nodes + total_edges, "nodes": total_nodes, "edges": total_edges, "errors": errors}
    except (Neo4jError, SQLAlchemyError) as exc:
        logger.error("sync_from_pipeline (inline) DB error: {}", exc)
        return {"synced": False, "error": str(exc), "count": total_nodes + total_edges}
    except Exception as exc:
        logger.exception("Unexpected error in sync_from_pipeline (inline): {}", exc)
        return {"synced": False, "error": str(exc), "count": total_nodes + total_edges}


async def _sync_via_graph_writer(
    run_id: str,
    driver: Any,
    app_resources: Any,
    extraction_data: dict[str, Any],
    target_position: str = "",
) -> dict[str, Any]:
    # 业务说明：DB-Query 模式的核心实现，通过 graph_writer 批量将提取结果写入 Neo4j。
    # 技术说明：
    #   1. 先从当前 pipeline 的 extraction_data 构建提取字典；
    #   2. 再查询近 5 分钟内的 JDExtractionRecord 补充更多数据；
    #   3. 最后调用 batch_write_extractions 使用完整本体（7 节点 + 8 关系）批量写入，
    #      内置 MERGE + 重试机制，避免重复写入。
    """Query JDExtractionRecord from PostgreSQL and write to Neo4j via graph_writer.

    Strategy:
      1. Build an extraction dict from the Step 2 extraction_data for immediate write.
      2. Query JDExtractionRecords created during the pipeline run timeframe
         (last 5 minutes) for additional records that may have been persisted
         by the batch pipeline executor.
      3. Write all collected extractions via graph_writer.batch_write_extractions
         which uses the full 7-node / 8-relationship ontology with MERGE + retry.
    """
    from datetime import UTC, datetime, timedelta

    from app.core.extraction.graph_writer import batch_write_extractions
    from app.models.extraction_models import JDExtractionRecord

    extractions: list[dict[str, Any]] = []
    nodes_written = 0
    edges_written = 0

    try:
        # ── 1. Build extraction from the current pipeline run's Step 2 data ──
        position_name = extraction_data.get("position_name", "")
        skills = extraction_data.get("skills", [])

        if position_name:
            required_skills = []
            preferred_skills = []
            for s in skills:
                entry = {
                    "name": s.get("name", ""),
                    "category": s.get("category", "hard_skill"),
                    "level": s.get("proficiency", "熟悉"),
                }
                if s.get("importance") == "required":
                    required_skills.append(entry)
                else:
                    preferred_skills.append(entry)

            current_extraction: dict[str, Any] = {
                "position_name": position_name,
                "industry": extraction_data.get("industry", ""),
                "description": extraction_data.get("description", ""),
                "experience_required": extraction_data.get("experience_required"),
                "education_required": extraction_data.get("education_required"),
                "knowledge_areas": extraction_data.get("knowledge_areas", []),
                "required_skills": required_skills,
                "preferred_skills": preferred_skills,
                "tools": extraction_data.get("tools", []),
                "prerequisites": extraction_data.get("prerequisites", []),
                "learning_resources": extraction_data.get("learning_resources", []),
                "evolves_to": extraction_data.get("evolves_to", []),
            }
            extractions.append(current_extraction)

        # If target_position differs from position_name, also create a Position node
        # with the target_position name so Step 4 match diagnosis can find it.
        if target_position and target_position != position_name and skills:
            required_skills_alt = []
            preferred_skills_alt = []
            for s in skills:
                entry = {
                    "name": s.get("name", ""),
                    "category": s.get("category", "hard_skill"),
                    "level": s.get("proficiency", "熟悉"),
                }
                if s.get("importance") == "required":
                    required_skills_alt.append(entry)
                else:
                    preferred_skills_alt.append(entry)
            target_extraction: dict[str, Any] = {
                "position_name": target_position,
                "industry": extraction_data.get("industry", ""),
                "description": extraction_data.get("description", ""),
                "experience_required": extraction_data.get("experience_required"),
                "education_required": extraction_data.get("education_required"),
                "knowledge_areas": extraction_data.get("knowledge_areas", []),
                "required_skills": required_skills_alt,
                "preferred_skills": preferred_skills_alt,
                "tools": extraction_data.get("tools", []),
                "prerequisites": extraction_data.get("prerequisites", []),
                "learning_resources": extraction_data.get("learning_resources", []),
                "evolves_to": extraction_data.get("evolves_to", []),
            }
            extractions.append(target_extraction)

        # ── 2. Query JDExtractionRecords from PostgreSQL ──
        pg_sessionmaker = app_resources.pg_sessionmaker
        if pg_sessionmaker is not None:
            try:
                import sqlalchemy as sa

                # Look for records created within the pipeline run timeframe
                since = datetime.now(UTC) - timedelta(minutes=5)
                async with pg_sessionmaker() as session:
                    rows = (
                        await session.execute(
                            sa.select(JDExtractionRecord)
                            .where(
                                JDExtractionRecord.status == "completed",
                                JDExtractionRecord.created_at >= since,
                            )
                            .order_by(JDExtractionRecord.created_at.desc())
                            .limit(200)
                        )
                    ).scalars().all()

                for record in rows:
                    payload = record.to_extraction_payload()
                    # Avoid duplicating the current run's extraction
                    if position_name and payload.get("position_name") == position_name:
                        # Check if skills overlap significantly — skip if same extraction
                        existing_names = {s.get("name") for s in current_extraction.get("required_skills", []) if s.get("name")}
                        existing_names |= {s.get("name") for s in current_extraction.get("preferred_skills", []) if s.get("name")}
                        payload_names = set()
                        for entries in (payload.get("required_skills", []), payload.get("preferred_skills", [])):
                            for entry in entries or []:
                                name = entry.get("name") if isinstance(entry, dict) else str(entry)
                                if name:
                                    payload_names.add(name)
                        if existing_names and payload_names and existing_names == payload_names:
                            continue
                    extractions.append(payload)

                logger.info(
                    "sync_from_pipeline: found {} DB records for run_id={}",
                    len(rows), run_id,
                )
            except (SQLAlchemyError, Neo4jError) as exc:
                logger.warning(
                    "sync_from_pipeline: DB query failed (non-fatal, using inline data): {}", exc,
                )
            except Exception as exc:
                logger.exception(
                    "sync_from_pipeline: Unexpected DB query failure: {}", exc,
                )
        else:
            logger.debug("sync_from_pipeline: pg_sessionmaker not available, using inline data only")

        # ── 3. Write all extractions to Neo4j via graph_writer ──
        if not extractions:
            return {"synced": True, "nodes_written": 0, "edges_written": 0, "extractions_processed": 0}

        summaries = await batch_write_extractions(extractions, driver)

        # Aggregate counts from all summaries
        for summary in summaries:
            nodes_written += int(summary.get("nodes_touched", 0))
            edges_written += int(summary.get("relationships_touched", 0))

        logger.info(
            "sync_from_pipeline (graph_writer): {} extractions, {} nodes, {} edges (run_id={})",
            len(extractions), nodes_written, edges_written, run_id,
        )
        return {
            "synced": True,
            "nodes_written": nodes_written,
            "edges_written": edges_written,
            "extractions_processed": len(extractions),
        }
    except (Neo4jError, SQLAlchemyError) as exc:
        logger.error("sync_from_pipeline (graph_writer) DB error: {}", exc)
        return {"synced": False, "error": str(exc), "nodes_written": nodes_written, "edges_written": edges_written}
    except Exception as exc:
        logger.exception("Unexpected error in sync_from_pipeline (graph_writer): {}", exc)
        return {"synced": False, "error": str(exc), "nodes_written": nodes_written, "edges_written": edges_written}
