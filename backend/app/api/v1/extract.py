"""信息抽取 API：从 JD/简历中提取技能并归一化。"""

from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from loguru import logger
from pydantic import BaseModel, Field

from app.core.extraction.jd_extract import extract_from_jd
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
        "position_name": data.get("position_name", ""),
        "required_skills": [
            _map_skill_item(s)
            for s in data.get("required_skills", [])
        ],
        "preferred_skills": [
            _map_skill_item(s)
            for s in data.get("preferred_skills", [])
        ],
        "experience_required": data.get("experience_required"),
        "education_required": data.get("education_required"),
        "responsibilities": data.get("responsibilities", []),
        "confidence": validation.get("confidence", 0.85),
        "hallucination_score": None if validation.get("is_valid", True) else validation.get("confidence"),
        "normalized_skills": pipeline_result.get("normalization", []),
    }


@router.post("/jd", response_model=ExtractionResult)
async def extract_jd(request: ExtractionRequest) -> dict[str, Any]:
    """从职位描述中提取技能信息。

    - 调用 LLM 进行结构化抽取
    - 对技能名称做别名归一化
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
    except Exception as e:
        logger.opt(exception=True).error("Unexpected extraction error: {}", e)
        raise HTTPException(status_code=500, detail="Internal extraction error") from e

    if not pipeline_result.get("success"):
        error_msg = pipeline_result.get("error", "Unknown extraction error")
        logger.error("Pipeline returned error: {}", error_msg)
        raise HTTPException(status_code=422, detail=error_msg)

    return _build_result(pipeline_result)


@router.post("/resume", response_model=ExtractionResult)
async def extract_resume(file: UploadFile = File(...)) -> dict[str, Any]:  # noqa: B008
    """从简历文件（PDF/Word）中提取技能信息。

    - 解析文件内容
    - 调用 LLM 进行结构化抽取
    - 返回结构化结果
    """
    logger.info("POST /extract/resume - filename={}", file.filename)

    if file.filename is None:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in {"pdf", "docx", "doc"}:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{ext}. Supported: .pdf, .docx, .doc",
        )

    try:
        content_bytes = await file.read()
    except Exception as e:
        logger.error("Failed to read uploaded file: {}", e)
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}") from e

    try:
        pipeline_result = await run_resume_extraction(file.filename, content_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ConnectionError as e:
        raise HTTPException(status_code=502, detail=f"LLM service unavailable: {e}") from e
    except Exception as e:
        logger.opt(exception=True).error("Unexpected resume extraction error: {}", e)
        raise HTTPException(status_code=500, detail="Internal extraction error") from e

    if not pipeline_result.get("success"):
        error_msg = pipeline_result.get("error", "Unknown extraction error")
        raise HTTPException(status_code=422, detail=error_msg)

    return _build_result(pipeline_result)
