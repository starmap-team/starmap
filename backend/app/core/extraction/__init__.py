"""Extraction pipeline package.

Provides JD/resume skill extraction, LLM integration,
skill normalization, and Neo4j graph persistence.
"""

from app.core.extraction.graph_writer import (
    GraphConfig,
    batch_write_extractions,
    create_requires_relationship,
    get_all_skills,
    get_position_skills,
    merge_position,
    merge_skill,
    write_extraction_to_graph,
)
from app.core.extraction.jd_extract import (
    extract_from_jd,
)
from app.core.extraction.llm_client import (
    LLMClient,
    LLMConnectionError,
    LLMResponseError,
    LLMTimeoutError,
    call_llm_with_fallback,
    call_xunfei_llm,
    parse_llm_json_response,
)
from app.core.extraction.normalize import (
    SKILL_ALIAS,
    NormalizationResult,
    batch_normalize_skills,
    build_alias_reverse_index,
    get_embedding,
    get_standard_skill_seeds,
    normalize_by_alias,
    normalize_by_vector,
    normalize_skill,
    validate_skill_by_source_count,
)
from app.core.extraction.prompt import (
    ANTI_HALLUCINATION_PROMPT,
    JD_EXTRACTION_PROMPT,
    LLM_JUDGE_PROMPT,
    RESUME_EXTRACTION_PROMPT,
    get_prompt,
)

__all__ = [
    "JD_EXTRACTION_PROMPT",
    "ANTI_HALLUCINATION_PROMPT",
    "LLM_JUDGE_PROMPT",
    "RESUME_EXTRACTION_PROMPT",
    "get_prompt",
    "LLMConnectionError",
    "LLMResponseError",
    "LLMTimeoutError",
    "call_xunfei_llm",
    "call_llm_with_fallback",
    "parse_llm_json_response",
    "LLMClient",
    "SKILL_ALIAS",
    "NormalizationResult",
    "normalize_by_alias",
    "get_embedding",
    "normalize_by_vector",
    "validate_skill_by_source_count",
    "normalize_skill",
    "batch_normalize_skills",
    "build_alias_reverse_index",
    "get_standard_skill_seeds",
    "GraphConfig",
    "write_extraction_to_graph",
    "merge_position",
    "merge_skill",
    "create_requires_relationship",
    "batch_write_extractions",
    "get_position_skills",
    "get_all_skills",
    "extract_from_jd",
]
