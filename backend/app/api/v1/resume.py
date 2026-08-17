"""简历解析兼容 API。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from loguru import logger

from app.api.v1.extract import ExtractionResult, _build_result, _write_extraction_to_graph
from app.api.v1.upload_validation import validate_resume_upload
from app.dependencies import get_neo4j_driver, get_redis_client
from app.exceptions import ExtractionError, StarMapError
from app.services.resume_service import run_resume_extraction

router = APIRouter(prefix="/resume", tags=["简历解析"])


@router.post("/upload", response_model=ExtractionResult)
async def upload_resume(
    file: UploadFile = File(...),  # noqa: B008
    neo4j_driver: Any = Depends(get_neo4j_driver),  # noqa: B008
    redis_client: Any = Depends(get_redis_client),  # noqa: B008
) -> dict[str, Any]:
    """阶段 4 兼容端点：上传简历并返回结构化抽取结果。"""
    logger.info("POST /resume/upload - filename={}", file.filename)

 # INJ-05 / API-06: 统一校验（扩展名 + MIME + 大小 + 魔术字节）
    content_bytes = await validate_resume_upload(file)

 # P0-AUDIT-FIX (2026-08-13): PII detection was defined but never called
 # from the upload path — raw resumes hit Neo4j/PostgreSQL with phone,
 # email, and ID-card numbers inline (GDPR / 个保法 violation). Detect
 # before extraction and emit a structured audit log entry; do NOT block
 # the upload — masking already happens inside run_resume_extraction via
 # mask_pii, this is a defensive observability hook.
    try:
        from app.services.pii_detector import detect_pii
        try:
            preview_text = content_bytes.decode("utf-8", errors="ignore")[:8192]
            pii_types = detect_pii(preview_text)
            if pii_types:
                logger.warning(
                    "Resume upload detected PII types={} filename={} bytes={}",
                    pii_types, file.filename, len(content_bytes),
                )
        except Exception as exc:  # never let observability block the request
            logger.debug("PII detection skipped ({}): {}", type(exc).__name__, exc)
    except ImportError:
        pass  # detector module not present in minimal installs

    try:
        pipeline_result = await run_resume_extraction(file.filename or "resume", content_bytes, redis_client=redis_client)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConnectionError as exc:
        raise HTTPException(status_code=502, detail=f"LLM service unavailable: {exc}") from exc
    except ExtractionError as exc:
        logger.exception("Resume extraction failed: {}", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except StarMapError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in resume extraction: {}", exc)
        raise HTTPException(status_code=500, detail="简历处理异常") from exc

    if not pipeline_result.get("success"):
        raise HTTPException(status_code=422, detail=pipeline_result.get("error", "Unknown extraction error"))

 # Write extraction to Neo4j graph
    graph_summary = await _write_extraction_to_graph(pipeline_result, neo4j_driver)
    if graph_summary:
        logger.info("Graph integration: {} triples written", graph_summary["triples_merged"])

    return _build_result(pipeline_result)
