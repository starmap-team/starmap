"""Prompt template management for LLM-based skill extraction."""

import re
from typing import Any

from loguru import logger

JD_EXTRACTION_PROMPT = """你是一个专业的技能提取专家。请从以下职位描述中提取所需的技能信息。

## 职位描述
{jd_content}

## 提取要求
请提取以下信息并以严格的JSON格式返回（不要包含任何其他文字或代码块标记）：

1. position_name: 职位名称（如"高级Python后端工程师"）
2. required_skills: 必需/必备技能列表。每项包含：
    - name: 技能标准化名称（仅英文，首字母大写，不要加中文描述或后缀）
   - level: 熟练度，可选值"expert"、"advanced"、"intermediate"、"beginner"
   - category: 类别，可选值"hard_skill"、"soft_skill"、"tool"、"certificate"
3. preferred_skills: 加分/优先技能列表（格式同上，每项含name/level/category）
4. experience_required: 所需经验年限（数字，无法确定则返回null）
5. education_required: 学历要求（如"本科及以上"、"硕士及以上"，无法确定则返回null）
6. responsibilities: 主要职责列表（如["开发API", "性能优化"]）

## 分类规则
- **required_skills**: 出现在"任职要求"、"岗位职责"中，描述为"精通"、"掌握"、"熟练使用"、"熟悉"的技能
- **preferred_skills**: 出现在"加分项"、"优先"、"plus"、"bonus"、"nice to have"分类下的技能

## 重要规则
1. 技能名称使用标准名称：python3→Python, reactjs→React, golang→Go, k8s→Kubernetes
2. 同时提取中文和英文技能名称
3. 无法确认的字段返回null，禁止编造
4. 仅提取信息技术相关技能，过滤无关描述
5. 区分大小写，技能名称首字母大写
6. 技能名称使用干净的标准英文名称，不要添加中文说明或后缀：例如输出 "Linux" 而不是 "Linux系统" 或 "Linux系统安全"；输出 "Go" 而不是 "Go语言"；输出 "Docker" 而不是 "Docker容器" 或 "Docker安全"
7. ❌ 禁止输出格式示例（不要加中文后缀或描述）：
   - "Linux系统" ❌ → "Linux" ✅
   - "Docker容器技术" ❌ → "Docker" ✅
   - "CUDA并行编程" ❌ → "CUDA" ✅
   - "SQL数据库" ❌ → "SQL" ✅
   - "Tokio运行时" ❌ → "Tokio" ✅
   - "CNN经典网络结构" ❌ → "CNN" ✅
   - "数据分析" ✅（中文技能名可保留）

8. 技能名称如果含版本号（如 "C++11"、"Python3"）归入主技能名："C++11" → "C++"，"Python3" → "Python"

## 输出格式（严格遵循）
- 仅返回纯 JSON，不要包含 markdown 代码块标记、不要包含任何说明文字
- 输出必须以 {{ 开头，以 }} 结尾（花括号包裹）
- 必须是可以直接通过 json.loads() 解析的合法 JSON，无尾逗号、无注释
- 错误的格式会导致解析失败，影响整个系统运行"""

ANTI_HALLUCINATION_PROMPT = """你是一个严格的技能提取验证器。请检查以下从职位描述中提取的技能是否准确。

## 提取结果
{extraction_json}

## 原始职位描述
{jd_content}

## 验证规则
1. 检查每个required_skills和preferred_skills是否在职位描述中有明确文本依据
2. 检查是否有明显遗漏的关键技能
3. 注意中文技能名称的匹配（如"项目管理"对应"project management"）

返回JSON格式：
{{
    "is_valid": true/false,
    "hallucinated_skills": [],
    "missing_skills": [],
    "confidence": 0.0-1.0,
    "issues": []
}}

输出必须以 {{ 开头、}} 结尾，纯 JSON，不要 markdown 代码块。"""

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

纯 JSON，不要 markdown 代码块，不要附加文字。"""

RESUME_EXTRACTION_PROMPT = """你是一个专业的简历解析专家。请从以下简历内容中提取技能信息。

简历内容：
{resume_content}

请提取以下信息并以JSON格式返回：
1. candidate_name: 候选人姓名（如能找到）
2. skills: 技能列表（每项包含 name, level, years_of_experience 字段）
3. work_experience: 工作经验列表（每项包含 company, position, duration, responsibilities）
4. education: 教育背景列表
5. certifications: 证书列表

纯 JSON，不要 markdown 代码块，不要附加文字。"""

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
