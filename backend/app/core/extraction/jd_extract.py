"""Main JD extraction orchestrator.

Pipeline: prompt filling -> LLM call -> JSON parsing -> pydantic validation
          -> skill normalization -> anti-hallucination check.
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from app.core.extraction.llm_client import (
    LLMClient,
    LLMConnectionError,
    LLMResponseError,
    LLMTimeoutError,
    parse_llm_json_response,
)
from app.core.extraction.normalize import (
    batch_normalize_skills,
)
from app.core.extraction.prompt import get_prompt

# Chinese PII patterns
_PII_PATTERNS: list[re.Pattern] = [
    re.compile(r"1[3-9]\d{9}"),           # Mobile phone
    re.compile(r"\d{18}[\dXx]"),           # ID card number
    re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),  # Email
]


class SkillCategory(StrEnum):
    """Skill category enum matching ontology values."""

    hard_skill = "hard_skill"
    soft_skill = "soft_skill"
    tool = "tool"
    certificate = "certificate"


def mask_pii(text: str, replacement: str = "[REDACTED]") -> str:
    """Mask Chinese PII (phone, ID, email) in text."""
    for pattern in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class SkillEntry(BaseModel):
    """A single skill entry in extraction results."""

    name: str = Field(..., description="Skill name")
    level: str = Field(default="intermediate", description="Proficiency level")
    category: str | None = Field(default=None, description="Skill category: hard_skill/soft_skill/tool/certificate")
    years_of_experience: float | None = Field(default=None, description="Years of experience")


class JDExtractionResult(BaseModel):
    """Validated JD extraction output."""

    position_name: str = Field(default="", description="Job position title")
    required_skills: list[SkillEntry] = Field(default_factory=list, description="Required skills")
    preferred_skills: list[SkillEntry] = Field(default_factory=list, description="Preferred skills")
    experience_required: int | None = Field(default=None, description="Minimum years of experience")
    education_required: str | None = Field(default=None, description="Minimum education requirement")
    responsibilities: list[str] = Field(default_factory=list, description="Job responsibilities")


class AntiHallucinationResult(BaseModel):
    """Anti-hallucination validation result."""

    is_valid: bool = Field(default=True)
    hallucinated_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    issues: list[str] = Field(default_factory=list)


@dataclass
class JDExtractionPipeline:
    """Configurable JD extraction pipeline."""

    llm_client: LLMClient = field(default_factory=LLMClient)
    anti_hallucination_enabled: bool = True
    normalize_skills_enabled: bool = True
    use_vector_normalization: bool = False
    vector_threshold: float = 0.85
    min_sources: int = 3

    async def run(self, jd_content: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute the full extraction pipeline.

        Args:
            jd_content: Raw job description text.
            options: Override pipeline options.

        Returns:
            Dict with 'success', 'data', 'warnings', 'normalization', 'validation', 'error'.
        """
        if options:
            for k, v in options.items():
                if hasattr(self, k):
                    setattr(self, k, v)

        result: dict[str, Any] = {
            "success": False,
            "data": None,
            "warnings": [],
            "normalization": [],
            "validation": None,
            "error": None,
        }

        if not jd_content or not jd_content.strip():
            result["error"] = "Empty JD content"
            return result

        # PII masking before sending to LLM
        jd_content_safe = mask_pii(jd_content)

        # Step 1: Fill prompt
        logger.info("JD extraction pipeline starting ({} chars)", len(jd_content_safe))
        try:
            _ = get_prompt("jd_extraction", jd_content=jd_content_safe)
        except (KeyError, ValueError) as e:
            result["error"] = f"Prompt error: {e}"
            return result

        # Step 2: Call LLM
        try:
            raw = await self.llm_client.extract_from_jd(jd_content_safe)
        except LLMConnectionError as e:
            logger.error("LLM connection failed: {}", e)
            result["error"] = f"LLM connection error: {e}"
            return result
        except LLMResponseError as e:
            logger.error("LLM response error: {}", e)
            result["error"] = f"LLM response error: {e}"
            return result
        except LLMTimeoutError as e:
            logger.error("LLM timeout: {}", e)
            result["error"] = f"LLM timeout: {e}"
            return result

        # Step 3: Parse JSON
        try:
            parsed = parse_llm_json_response(raw["content"]) if isinstance(raw, dict) and "content" in raw else raw
        except LLMResponseError as e:
            result["error"] = f"JSON parse error: {e}"
            return result

        # Step 4: Pydantic validation
        try:
            validated = JDExtractionResult(**parsed)
        except (TypeError, ValueError) as e:
            logger.warning("Pydantic validation failed, using raw data: {}", e)
            result["warnings"].append(f"Pydantic validation issue: {e}")
            validated = JDExtractionResult()
            for key in ("position_name", "required_skills", "preferred_skills", "experience_required", "education_required", "responsibilities"):
                if key in parsed:
                    if key in ("required_skills", "preferred_skills"):
                        setattr(validated, key, [SkillEntry(**s) if isinstance(s, dict) else SkillEntry(name=s) for s in parsed[key]])
                elif key in ("experience_required",):
                    setattr(validated, key, parsed.get(key))
                elif key == "responsibilities":
                    setattr(validated, key, parsed.get(key, []))
                else:
                    setattr(validated, key, parsed.get(key, ""))

        # Step 5: Normalize skills
        if self.normalize_skills_enabled:
            all_skill_names = []
            for skill in validated.required_skills:
                all_skill_names.append(skill.name)
            for skill in validated.preferred_skills:
                all_skill_names.append(skill.name)

            normalized_results = batch_normalize_skills(
                all_skill_names,
                use_vector=self.use_vector_normalization,
                vector_threshold=self.vector_threshold,
                min_sources=self.min_sources,
            )

            result["normalization"] = [nr.__dict__ for nr in normalized_results]

            nr_iter = iter(normalized_results)
            for skill in validated.required_skills:
                nr = next(nr_iter)
                if nr.normalized:
                    skill.name = nr.normalized
            for skill in validated.preferred_skills:
                nr = next(nr_iter)
                if nr.normalized:
                    skill.name = nr.normalized

        # Step 6: Anti-hallucination check
        validation = None
        if self.anti_hallucination_enabled:
            try:
                v = await self.llm_client.validate_extraction(
                    validated.model_dump(),
                    jd_content_safe,
                )
                # MiMo reasoning model may return dicts with {name, reasoning}
                # instead of plain strings — normalize ALL list[str] fields
                def _normalize_str_list(items):
                    if not items:
                        return []
                    result = []
                    for item in items:
                        if isinstance(item, dict):
                            # Extract most meaningful string value from dict
                            result.append(item.get("name") or item.get("skill")
                                          or item.get("issue") or str(item))
                        elif isinstance(item, str):
                            result.append(item)
                        else:
                            result.append(str(item))
                    return result

                v["hallucinated_skills"] = _normalize_str_list(v.get("hallucinated_skills", []))
                v["missing_skills"] = _normalize_str_list(v.get("missing_skills", []))
                v["issues"] = _normalize_str_list(v.get("issues", []))
                validation = AntiHallucinationResult(**v)
                result["validation"] = validation.model_dump()

                if not validation.is_valid:
                    msg = f"Anti-hallucination: {len(validation.hallucinated_skills)} hallucinated, {len(validation.missing_skills)} missing"
                    result["warnings"].append(msg)
                    logger.warning(msg)

            except (LLMConnectionError, LLMResponseError, LLMTimeoutError) as e:
                logger.warning("Anti-hallucination check failed: {}", e)
                result["warnings"].append(f"Validation error: {e}")

        result["success"] = True
        result["data"] = validated.model_dump()
        logger.info("JD extraction pipeline complete: {} required, {} preferred skills",
                     len(validated.required_skills), len(validated.preferred_skills))
        return result


async def extract_from_jd(
    jd_content: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convenience function to run the full JD extraction pipeline.

    Args:
        jd_content: Raw job description text.
        options: Optional pipeline configuration overrides:
            - anti_hallucination_enabled (bool)
            - normalize_skills_enabled (bool)
            - use_vector_normalization (bool)
            - vector_threshold (float)
            - min_sources (int)

    Returns:
        Pipeline result dict with keys: success, data, warnings, normalization, validation, error.
    """
    pipeline = JDExtractionPipeline()
    return await pipeline.run(jd_content, options)
