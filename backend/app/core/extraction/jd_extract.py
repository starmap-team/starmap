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
from app.core.extraction.prompt import get_ab_test, get_active_version, get_prompt

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
    level: str | None = Field(default="intermediate", description="Proficiency level")
    category: str | None = Field(default=None, description="Skill category: hard_skill/soft_skill/tool/certificate")
    years_of_experience: float | None = Field(default=None, description="Years of experience")


class PrerequisiteEntry(BaseModel):
    """A prerequisite skill relationship."""

    skill: str = Field(..., description="The skill that is a prerequisite")
    required_by: str = Field(..., description="The skill that requires this prerequisite")


class ToolEntry(BaseModel):
    """A tool/technology entry."""

    name: str = Field(..., description="Tool name")
    category: str | None = Field(default=None, description="Tool category: ide/framework/platform/etc")


class LearningResourceEntry(BaseModel):
    """A learning resource entry."""

    title: str = Field(..., description="Resource title")
    type: str | None = Field(default=None, description="Resource type: book/course/tutorial/docs")
    url: str | None = Field(default=None, description="Resource URL if available")
    for_skill: str | None = Field(default=None, description="Primary skill this resource teaches")


class JDExtractionResult(BaseModel):
    """Validated JD extraction output."""

    position_name: str = Field(default="", description="Job position title")
    required_skills: list[SkillEntry] = Field(default_factory=list, description="Required skills")
    preferred_skills: list[SkillEntry] = Field(default_factory=list, description="Preferred skills")
    experience_required: int | None = Field(default=None, description="Minimum years of experience")
    education_required: str | None = Field(default=None, description="Minimum education requirement")
    responsibilities: list[str] = Field(default_factory=list, description="Job responsibilities")
    industry: str | None = Field(default=None, description="Industry sector")
    description: str | None = Field(default=None, description="Brief position description")
    knowledge_areas: list[str] = Field(default_factory=list, description="Knowledge domains/areas")
    tools: list[ToolEntry] = Field(default_factory=list, description="Tools and technologies used")
    prerequisites: list[PrerequisiteEntry] = Field(default_factory=list, description="Skill prerequisite relationships")
    learning_resources: list[LearningResourceEntry] = Field(default_factory=list, description="Recommended learning resources")
    evolves_to: list[str] = Field(default_factory=list, description="Related positions this role can evolve into")


class AntiHallucinationResult(BaseModel):
    """Anti-hallucination validation result."""

    is_valid: bool = Field(default=True)
    hallucinated_skills: list[str | dict[str, Any]] = Field(default_factory=list)
    missing_skills: list[str | dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    issues: list[str] = Field(default_factory=list)


def _normalize_skill_list(skills: list[str | dict[str, Any]]) -> list[str]:
    """Normalize skill list items to strings (extract 'name' key if dict)."""
    result = []
    for s in skills:
        if isinstance(s, dict):
            result.append(str(s.get("name", str(s))))
        else:
            result.append(str(s))
    return result


@dataclass
class JDExtractionPipeline:
    """Configurable JD extraction pipeline."""

    llm_client: LLMClient = field(default_factory=LLMClient)
    anti_hallucination_enabled: bool = True
    normalize_skills_enabled: bool = True
    use_vector_normalization: bool = True
    vector_threshold: float = 0.85
    min_sources: int = 3
    source_counts: dict[str, int] | None = None

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
            "prompt_version_used": None,
            "prompt_ab_test": False,
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

        # Track which prompt version was resolved (supports A/B test)
        ab_cfg = get_ab_test("jd_extraction")
        if ab_cfg:
            # A/B test active: don't call select_version() again to avoid
            # randomness mismatch with the earlier get_prompt() call.
            # Record the test config; per-request version is random.
            result["prompt_ab_test"] = True
            result["prompt_version_used"] = (
                f"ab_test(control={ab_cfg.control_version},"
                f" canary={ab_cfg.canary_version},"
                f" traffic={ab_cfg.traffic_fraction:.0%})"
            )
            logger.info(
                "A/B test active: jd_extraction control={} canary={} traffic={:.0%}",
                ab_cfg.control_version, ab_cfg.canary_version, ab_cfg.traffic_fraction,
            )
        else:
            result["prompt_ab_test"] = False
            result["prompt_version_used"] = get_active_version("jd_extraction") or "v1"

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
            # Position/experience/education — set from parsed if available
            for key in ("position_name", "experience_required", "education_required"):
                if key in parsed:
                    setattr(validated, key, parsed.get(key, ""))
            # Required/preferred skills — parse SkillEntry objects
            for key in ("required_skills", "preferred_skills"):
                if key in parsed and parsed[key]:
                    setattr(validated, key, [
                        SkillEntry(**s) if isinstance(s, dict) else SkillEntry(name=s)
                        for s in parsed[key]
                    ])
            # Responsibilities
            if "responsibilities" in parsed:
                validated.responsibilities = parsed["responsibilities"]

        # Step 4.5: Clean up Chinese suffixes from skill names
        chinese_suffixes = [
            "系统", "安全", "开发", "管理", "平台", "框架", "技术", "语言",
            "生态", "相关", "服务", "设计", "网络", "算法", "存储", "计算",
            "容器", "工具", "应用", "架构", "工程", "引擎", "协议", "自动化",
            "编程", "部署", "监控", "测试", "运维", "研发",
            "运行时", "数据库", "环境", "桌面", "并行", "调优", "优化",
            "设计规范", "部署经验", "模型转换", "模型加速", "内核", "源码",
            # M2 low-F1 optimization: strip common Chinese suffixes that LLM appends
            "方法论", "能力", "攻防", "漏洞", "竞赛经验", "认证", "证书",
        ]
        def _clean_skill_name(name: str) -> str:
            while True:
                original = name
                for suffix in chinese_suffixes:
                    if len(name) > 3 and name.endswith(suffix):
                        cleaned = name[:-len(suffix)]
                        # Only apply strip if result is non-empty AND at least 3 chars
                        # (prevents over-stripping like "系统架构"→"系统" or "渗透测试"→"渗透")
                        if cleaned and len(cleaned) >= 3:
                            name = cleaned
                if name == original:
                    break
            return name

        for skill in validated.required_skills:
            cleaned = _clean_skill_name(skill.name)
            if cleaned != skill.name:
                logger.debug("Cleaned skill name: '{}' -> '{}'", skill.name, cleaned)
                skill.name = cleaned
        for skill in validated.preferred_skills:
            cleaned = _clean_skill_name(skill.name)
            if cleaned != skill.name:
                logger.debug("Cleaned skill name: '{}' -> '{}'", skill.name, cleaned)
                skill.name = cleaned

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
                source_counts=self.source_counts,
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
                # Normalize dict items to strings for serialization
                v_normalized = validation.model_dump()
                v_normalized["hallucinated_skills"] = _normalize_skill_list(validation.hallucinated_skills)
                v_normalized["missing_skills"] = _normalize_skill_list(validation.missing_skills)
                result["validation"] = v_normalized

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
            - source_counts (dict[str, int]): Skill name -> source count map

    Returns:
        Pipeline result dict with keys: success, data, warnings, normalization, validation, error.
    """
    pipeline = JDExtractionPipeline()
    return await pipeline.run(jd_content, options)
