"""简历解析兼容 API。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from loguru import logger

from app.api.v1.extract import ExtractionResult, _build_result, _write_extraction_to_graph
from app.dependencies import get_neo4j_driver
from app.services.resume_service import run_resume_extraction

router = APIRouter(prefix="/resume", tags=["简历解析"])

MAX_RESUME_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/upload", response_model=ExtractionResult)
async def upload_resume(
    file: UploadFile = File(...),  # noqa: B008
    neo4j_driver: Any = Depends(get_neo4j_driver),  # noqa: B008
) -> dict[str, Any]:
    """阶段 4 兼容端点：上传简历并返回结构化抽取结果。"""
    logger.info("POST /resume/upload - filename={}", file.filename)

    if file.filename is None:
        raise HTTPException(status_code=400, detail="No file provided")

    try:
        content_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {exc}") from exc

    if len(content_bytes) > MAX_RESUME_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(content_bytes)} bytes). Maximum: {MAX_RESUME_SIZE} bytes (10MB)",
        )

    try:
        pipeline_result = await run_resume_extraction(file.filename, content_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConnectionError as exc:
        raise HTTPException(status_code=502, detail=f"LLM service unavailable: {exc}") from exc
    except Exception as exc:
        logger.opt(exception=True).error("Unexpected /resume/upload error: {}", exc)
        raise HTTPException(status_code=500, detail="Internal extraction error") from exc

    if not pipeline_result.get("success"):
        raise HTTPException(status_code=422, detail=pipeline_result.get("error", "Unknown extraction error"))

    # Write extraction to Neo4j graph
    graph_summary = await _write_extraction_to_graph(pipeline_result, neo4j_driver)
    if graph_summary:
        logger.info("Graph integration: {} triples written", graph_summary["triples_merged"])

    return _build_result(pipeline_result)
