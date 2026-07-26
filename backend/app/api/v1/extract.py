"""信息抽取 API：从 JD/简历中提取技能并归一化。

完成抽取后自动将结果写入 Neo4j 图数据库，打通 extract -> graph 数据链路。
同时写入 PostgreSQL PositionRecord/SkillRecord，打通 extract -> positions 数据链路 (LOOP-05)。
"""

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.upload_validation import validate_resume_upload
from app.core.extraction.graph_writer import write_extraction_to_graph
from app.core.extraction.jd_extract import extract_from_jd
from app.core.llm.cost_tracker import tracker
from app.dependencies import get_db_session, get_neo4j_driver
from app.exceptions import ExtractionError, ExtractionLLMError, StarMapError
from app.services.resume_service import run_resume_extraction

router = APIRouter(prefix="/extract", tags=["信息抽取"])


class ExtractionRequest(BaseModel):
    """JD 内容 + 可选的抽取选项。"""

    jd_content: str = Field(..., min_length=1, max_length=50000, description="职位描述文本")
    options: dict[str, Any] | None = Field(None, description="抽取选项（model, temperature 等）")


class ExtractionResult(BaseModel):
    """抽取结果。"""

    position_name: str
    required_skills: list[dict[str, Any]] = []
    preferred_skills: list[dict[str, Any]] = []
    experience_required: int | None = None
    education_required: str | None = None
    responsibilities: list[str] = []
    confidence: float = 0.0
    hallucination_score: float | None = None
    normalized_skills: list[dict[str, Any]] = []
    # fix: 透传原 JDExtractionResult 丢弃的 4 个字段 + 3 个反幻觉字段
    tools: list[dict[str, Any]] = []
    learning_resources: list[dict[str, Any]] = []
    evolves_to: list[str] = []
    hallucinated_skills: list[str] = []
    missing_skills: list[str] = []
    issues: list[str] = []


def _map_proficiency(value: str | None) -> str:
    mapping = {
        "beginner": "了解",
        "basic": "了解",
        "intermediate": "熟悉",
        "advanced": "精通",
        "expert": "精通",
        "了解": "了解",
        "熟悉": "熟悉",
        "精通": "精通",
    }
    normalized = (value or "").strip().lower()
    return mapping.get(normalized, "熟悉")


def _map_skill_item(item: Any) -> dict[str, Any]:
    if isinstance(item, str):
        payload = {"skill": item}
    elif hasattr(item, "model_dump"):
        payload = item.model_dump()
    else:
        payload = dict(item)
    return {
        "skill": payload.get("skill") or payload.get("name") or "",
        "category": payload.get("category") or "hard_skill",
        "proficiency": _map_proficiency(payload.get("proficiency") or payload.get("level")),
    }


def _build_result(pipeline_result: dict[str, Any]) -> dict[str, Any]:
    """Transform pipeline result dict into ExtractionResult-compatible dict."""
    data = pipeline_result.get("data") or {}
    validation = pipeline_result.get("validation") or {}

    return {
        "position_name": data.get("position_name") or "",
        "required_skills": [_map_skill_item(s) for s in data.get("required_skills", [])],
        "preferred_skills": [_map_skill_item(s) for s in data.get("preferred_skills", [])],
        "experience_required": data.get("experience_required"),
        "education_required": data.get("education_required"),
        "responsibilities": data.get("responsibilities", []),
        "confidence": validation.get("confidence", 0.85),
        "hallucination_score": None if validation.get("is_valid", True) else validation.get("confidence"),
        "normalized_skills": pipeline_result.get("normalization", []),
        # fix: 透传 4 个原被丢弃字段 + 反幻觉结果
        "tools": data.get("tools", []),
        "learning_resources": data.get("learning_resources", []),
        "evolves_to": data.get("evolves_to", []),
        "hallucinated_skills": validation.get("hallucinated_skills", []),
        "missing_skills": validation.get("missing_skills", []),
        "issues": validation.get("issues", []),
    }


async def _write_extraction_to_graph(
    pipeline_result: dict[str, Any],
    neo4j_driver: Any,
) -> dict[str, int] | None:
    """Write extraction result to Neo4j graph. Returns summary or None on failure.

    This is the bridge that connects the extraction pipeline to the graph store,
    solving the data pipeline break where extractions were never persisted to Neo4j.
    """
    data = pipeline_result.get("data")
    if not data or not data.get("position_name"):
        logger.debug("Skipping graph write: no extraction data or position_name")
        return None

    try:
        summary = await write_extraction_to_graph(data, neo4j_driver)
        logger.info(
            "Graph write complete: {} triples merged, {} nodes touched for '{}'",
            summary["triples_merged"],
            summary["nodes_touched"],
            data.get("position_name"),
        )
        return summary
    except (ExtractionError, ExtractionLLMError) as exc:
        logger.exception("Extraction failed: {}", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error during extraction: {}", exc)
        raise HTTPException(status_code=500, detail="抽取处理异常") from exc


async def _write_extraction_to_pg(
    pipeline_result: dict[str, Any],
    session: AsyncSession,
) -> bool | None:
    """Write extraction result to PostgreSQL PositionRecord + SkillRecord (LOOP-05).

    Delegates to the extract repository — no raw SQL in the API layer.
    Returns True on success, None on failure (non-blocking).
    """
    from app.repositories.extract_repo import write_extraction_to_pg

    data = pipeline_result.get("data")
    if not data or not data.get("position_name"):
        logger.debug("Skipping PG write: no extraction data or position_name")
        return None

    return await write_extraction_to_pg(session, pipeline_data=data)


@router.get("/cost-summary", response_model=dict)
async def get_llm_cost_summary() -> dict[str, Any]:
    """累计 LLM 调用成本快照（进程内存，单进程聚合，重启清零）。"""
    return tracker.summary()


@router.post("/jd", response_model=ExtractionResult)
async def extract_jd(
    request: ExtractionRequest,
    neo4j_driver: Any = Depends(get_neo4j_driver),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """从职位描述中提取技能信息。

    - 调用 LLM 进行结构化抽取
    - 对技能名称做别名归一化
    - 自动写入 Neo4j 图数据库（打通 extract -> graph 数据链路）
    - 自动写入 PostgreSQL PositionRecord/SkillRecord（打通 extract -> positions 数据链路）
    - 返回结构化结果及置信度
    """
    logger.info("POST /extract/jd - jd_content={} chars", len(request.jd_content))

    try:
        pipeline_result = await extract_from_jd(request.jd_content, options=request.options)
    except ValueError as e:
        logger.error("Extraction failed: {}", e)
        raise HTTPException(status_code=422, detail=str(e)) from e
    except ConnectionError as e:
        logger.error("LLM connection failed: {}", e)
        raise HTTPException(status_code=502, detail=f"LLM service unavailable: {e}") from e
    except (ExtractionError, ExtractionLLMError) as exc:
        logger.exception("Extraction failed: {}", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error during extraction: {}", exc)
        raise HTTPException(status_code=500, detail="抽取处理异常") from exc

    if not pipeline_result.get("success"):
        error_msg = pipeline_result.get("error", "Unknown extraction error")
        logger.error("Pipeline returned error: {}", error_msg)
        raise HTTPException(status_code=422, detail=error_msg)

    # Write extraction to Neo4j graph (non-blocking: failure won't break the response)
    graph_summary = await _write_extraction_to_graph(pipeline_result, neo4j_driver)
    if graph_summary:
        logger.info("Graph integration: {} triples written", graph_summary["triples_merged"])

    # Write extraction to PostgreSQL (non-blocking: failure won't break the response) (LOOP-05)
    pg_result = await _write_extraction_to_pg(pipeline_result, session)
    if pg_result:
        logger.info("PG integration: PositionRecord created")

    return _build_result(pipeline_result)


@router.post("/resume", response_model=ExtractionResult)
async def extract_resume(
    file: UploadFile = File(...),  # noqa: B008
    neo4j_driver: Any = Depends(get_neo4j_driver),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """从简历文件（PDF/Word）中提取技能信息。

    - 解析文件内容
    - 调用 LLM 进行结构化抽取
    - 自动写入 Neo4j 图数据库
    - 自动写入 PostgreSQL PositionRecord/SkillRecord (LOOP-05)
    - 返回结构化结果
    """
    logger.info("POST /extract/resume - filename={}", file.filename)

    # INJ-05 / API-06: 统一校验（扩展名 + MIME + 大小 + 魔术字节）
    content_bytes = await validate_resume_upload(file)

    try:
        pipeline_result = await run_resume_extraction(file.filename or "resume", content_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ConnectionError as e:
        raise HTTPException(status_code=502, detail=f"LLM service unavailable: {e}") from e
    except (ExtractionError, ExtractionLLMError) as exc:
        logger.exception("Extraction failed: {}", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error during extraction: {}", exc)
        raise HTTPException(status_code=500, detail="抽取处理异常") from exc

    if not pipeline_result.get("success"):
        error_msg = pipeline_result.get("error", "Unknown extraction error")
        raise HTTPException(status_code=422, detail=error_msg)

    # Write extraction to Neo4j graph
    graph_summary = await _write_extraction_to_graph(pipeline_result, neo4j_driver)
    if graph_summary:
        logger.info("Graph integration: {} triples written", graph_summary["triples_merged"])

    # Write extraction to PostgreSQL (LOOP-05)
    pg_result = await _write_extraction_to_pg(pipeline_result, session)
    if pg_result:
        logger.info("PG integration: PositionRecord created")

    return _build_result(pipeline_result)
