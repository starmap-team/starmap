"""Prompt template management for LLM-based skill extraction."""

import re
from typing import Any

from loguru import logger

JD_EXTRACTION_PROMPT = """你是一个专业的技能提取专家。请从以下职位描述中提取所需的技能信息。

职位描述：
{jd_content}

请提取以下信息并以JSON格式返回：
1. position_name: 职位名称
2. required_skills: 必需技能列表（每项包含 name 和 level 字段，level 为 "expert"、"advanced"、"intermediate" 或 "beginner"）
3. preferred_skills: 优先技能列表（格式同上）
4. experience_required: 所需经验年限（数字）
5. education_required: 学历要求
6. responsibilities: 主要职责列表

仅返回JSON格式，不要包含其他文字。"""

ANTI_HALLUCINATION_PROMPT = """你是一个严格的技能提取验证器。请检查以下从职位描述中提取的技能是否准确。

提取结果：
{extraction_json}

原始职位描述：
{jd_content}

请验证每个技能是否在职位描述中有明确依据。返回JSON格式：
{{
    "is_valid": true/false,
    "hallucinated_skills": [],
    "missing_skills": [],
    "confidence": 0.0-1.0,
    "issues": []
}}

仅返回JSON格式，不要包含其他文字。"""

LLM_JUDGE_PROMPT = """你是一个评估专家。请比较以下两个技能提取结果的质量。

标准答案（Golden）：
{golden_json}

待评估系统输出（System）：
{system_json}

评估维度：
1. precision: 精确率（提取的技能中有多少是正确的）
2. recall: 召回率（标准答案中的技能有多少被提取了）
3. completeness: 完整性（技能级别、经验等信息是否完整）
4. accuracy: 整体准确性

返回JSON格式：
{{
    "precision": 0.0-1.0,
    "recall": 0.0-1.0,
    "completeness": 0.0-1.0,
    "accuracy": 0.0-1.0,
    "f1_score": 0.0-1.0,
    "details": ""
}}

仅返回JSON格式，不要包含其他文字。"""

RESUME_EXTRACTION_PROMPT = """你是一个专业的简历解析专家。请从以下简历内容中提取技能信息。

简历内容：
{resume_content}

请提取以下信息并以JSON格式返回：
1. candidate_name: 候选人姓名（如能找到）
2. skills: 技能列表（每项包含 name, level, years_of_experience 字段）
3. work_experience: 工作经验列表（每项包含 company, position, duration, responsibilities）
4. education: 教育背景列表
5. certifications: 证书列表

仅返回JSON格式，不要包含其他文字。"""

_PROMPT_REGISTRY: dict[str, str] = {
    "jd_extraction": JD_EXTRACTION_PROMPT,
    "anti_hallucination": ANTI_HALLUCINATION_PROMPT,
    "llm_judge": LLM_JUDGE_PROMPT,
    "resume_extraction": RESUME_EXTRACTION_PROMPT,
}


def get_prompt(name: str, **kwargs: Any) -> str:
    """Get a prompt template by name and fill in placeholders.

    Args:
        name: Prompt template name.
        **kwargs: Placeholder values to fill into the template.

    Returns:
        Filled prompt string.

    Raises:
        KeyError: If the prompt name is not found.
        ValueError: If required placeholders are not filled.
    """
    template = _PROMPT_REGISTRY.get(name)
    if template is None:
        msg = f"Unknown prompt template: {name}. Available: {list(_PROMPT_REGISTRY.keys())}"
        raise KeyError(msg)

    placeholders = re.findall(r"\{(\w+)\}", template)
    missing = [p for p in placeholders if p not in kwargs]
    if missing:
        msg = f"Missing required placeholders {missing} for prompt '{name}'"
        raise ValueError(msg)

    filled = template.format(**kwargs)
    logger.debug("Prompt '{}' filled ({} chars)", name, len(filled))
    return filled
