"""Versioned prompt template management with A/B test support.

Provides a registry of prompt templates for LLM-based skill extraction,
supporting version tracking, active version selection, and A/B testing.

Typical usage::

    from app.core.extraction.prompt import get_prompt, list_prompt_versions

    # Get active version of a prompt
    prompt = get_prompt("jd_extraction", jd_content="...")

    # List all versions
    versions = list_prompt_versions("llm_judge")

    # Use a specific version
    prompt = get_prompt("jd_extraction", version="v2", jd_content="...")
"""

import random
import re
from string import Template
from typing import Any

from loguru import logger

# ──────────────────────────────────────────────
# Prompt templates (versioned)
# ──────────────────────────────────────────────

JD_EXTRACTION_PROMPT_V1 = """你是一个专业的技能提取专家。请从以下职位描述中提取所需的技能信息。

## 职位描述
$jd_content

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
7. industry: 所属行业（如"互联网/IT"、"金融科技"、"智能制造"、"医疗健康"，无法确定则返回空字符串""）
8. description: 岗位职责概述（1-2句话概括该岗位的核心职责，从职位描述中提炼）
9. knowledge_areas: 知识领域列表（如["分布式系统", "机器学习"]，无法确定则返回空列表[]）
10. tools: 工具/技术平台列表。每项包含name和category（可选值"ide"/"framework"/"platform"/"database"/"devops"/"other"）
11. prerequisites: 技能前置依赖关系列表。每项包含skill（被依赖技能）和required_by（依赖该技能的技能）
12. learning_resources: 推荐学习资源列表。每项包含title、type（可选值"book"/"course"/"tutorial"/"docs"/"other"）和for_skill
13. evolves_to: 该岗位可能演进的目标岗位列表（无法确定则返回空列表[]）

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
- 输出必须以 { 开头，以 } 结尾（花括号包裹）
- 必须是可以直接通过 json.loads() 解析的合法 JSON，无尾逗号、无注释
- 错误的格式会导致解析失败，影响整个系统运行"""

# v4: recall-optimized — exhaustive coverage check, implicit skills, Chinese name preservation
JD_EXTRACTION_PROMPT_V4 = """你是一个专业的技能提取专家。请**完整且无遗漏**地从以下职位描述中提取所有技能信息。

## 职位描述
$jd_content

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
7. industry: 所属行业（如"互联网/IT"、"金融科技"、"智能制造"、"医疗健康"，无法确定则返回空字符串""）
8. description: 岗位职责概述（1-2句话概括该岗位的核心职责，从职位描述中提炼）
9. knowledge_areas: 知识领域列表（如["分布式系统", "机器学习", "网络安全"]，无法确定则返回空列表[]）
10. tools: 工具/技术平台列表。每项包含：
    - name: 工具名称（如"Docker"、"Jenkins"、"VS Code"）
    - category: 工具类别，可选值"ide"、"framework"、"platform"、"database"、"devops"、"analytics"、"other"
11. prerequisites: 技能前置依赖关系列表。每项包含：
    - skill: 被依赖的技能（如"Python"）
    - required_by: 依赖该技能的技能（如"Django"表示Django依赖Python）
12. learning_resources: 推荐学习资源列表（如果职位描述中提到）。每项包含：
    - title: 资源标题
    - type: 资源类型，可选值"book"、"course"、"tutorial"、"docs"、"other"
    - for_skill: 该资源主要教授的技能
13. evolves_to: 该岗位可能演进的目标岗位列表（如["技术总监", "架构师"]，无法确定则返回空列表[]）

## 分类规则
- **required_skills**: 出现在"任职要求"、"岗位职责"中，描述为"精通"、"掌握"、"熟练使用"、"熟悉"、"了解"的技能
- **preferred_skills**: 出现在"加分项"、"优先"、"plus"、"bonus"、"nice to have"分类下的技能

## 技能名称规范
1. 技能名称使用标准英文名称，首字母大写：python3→Python, reactjs→React, golang→Go, k8s→Kubernetes
2. 同时提取中文和英文技能名称，两种表达均保留
3. 带版本号的归入主技能名："C++11"→"C++", "Python3"→"Python", "ES6"→"JavaScript"
4. 不要添加中文描述后缀：
   - "Linux系统" → "Linux"，"Docker容器技术" → "Docker"
   - "CUDA并行编程" → "CUDA"，"SQL数据库" → "SQL"
5. 中文技能名可原样保留（如"数据分析"、"项目管理"、"用户调研"）
6. 无法确认的字段返回null，禁止编造

## 完整性要求（极其重要）
- **请完整提取职位描述中提到的所有技能和技术要求，不遗漏任何一项**
- 包括但不限于：编程语言、框架、工具、平台、方法论、领域知识、证书、软技能
- **隐式技能也要提取**（例如提到"构建CI/CD流水线" → 提取 CI/CD；"使用Git进行版本控制" → 提取 Git）
- 同时提取中英文两种表述的技能
- 提取后请做一次覆盖检查，确认没有遗漏

## 覆盖检查（在输出前逐项确认）
提取完成后，请逐项检查是否覆盖了职位描述中的以下类别：
- 编程语言（Python, Java, Go, Rust, C++ 等）
- Web框架（React, Vue, Django, Spring 等）
- 数据库（SQL, NoSQL, Redis, MongoDB 等）
- 云/DevOps（AWS, Docker, K8s, CI/CD, Terraform 等）
- 工具链（Git, Jenkins, Gradle, Maven 等）
- 软技能（项目管理、团队管理、沟通、产品设计 等）
- 领域知识（安全、大数据、AI/ML、嵌入式 等）
- 证书/资质（PMP, CPA, AWS认证 等）

## 输出格式（严格遵循）
- 仅返回纯 JSON，不要包含 markdown 代码块标记、不要包含任何说明文字
- 输出必须以 { 开头，以 } 结尾（花括号包裹）
- 必须是可以直接通过 json.loads() 解析的合法 JSON，无尾逗号、无注释"""


# v2: added few-shot examples for better structured output
JD_EXTRACTION_PROMPT_V2 = """你是一个专业的技能提取专家。请从以下职位描述中提取所需的技能信息。

## 职位描述
$jd_content

## 提取要求
请提取以下信息并以严格的JSON格式返回（不要包含任何其他文字或代码块标记）：

1. position_name: 职位名称
2. required_skills: 必需/必备技能列表。每项包含 name/level/category
3. preferred_skills: 加分/优先技能列表（格式同上）
4. experience_required: 所需经验年限（数字，无法确定则返回null）
5. education_required: 学历要求（如"本科及以上"）
6. responsibilities: 主要职责列表

## 示例输出
{
    "position_name": "高级Python后端工程师",
    "required_skills": [
        {"name": "Python", "level": "expert", "category": "hard_skill"},
        {"name": "FastAPI", "level": "advanced", "category": "tool"},
        {"name": "PostgreSQL", "level": "advanced", "category": "tool"}
    ],
    "preferred_skills": [
        {"name": "Kubernetes", "level": "intermediate", "category": "tool"}
    ],
    "experience_required": 5,
    "education_required": "本科及以上",
    "responsibilities": ["核心API服务设计开发", "系统架构设计"]
}

## 分类规则
- **required_skills**: "任职要求"中的"精通"、"掌握"、"熟练"、"熟悉"的技能
- **preferred_skills**: "加分项"、"优先"、"bonus"分类下的技能

## 重要规则
1. 技能名称标准化：python3→Python, k8s→Kubernetes, js→JavaScript
2. 仅提取信息技术相关技能
3. 无法确认的字段返回null，禁止编造
4. 输出纯 JSON，{ 开头 } 结尾，无markdown标记"""

# v3: Enhanced recall - exhaustive extraction, coverage check, Chinese+English support
JD_EXTRACTION_PROMPT_V3 = """你是一个专业的技能提取专家。请**完整且无遗漏**地从以下职位描述中提取所有技能信息。

## 职位描述
$jd_content

## 提取字段
1. position_name: 职位名称
2. required_skills: 必需/必备技能列表。每项包含 name / level / category
3. preferred_skills: 加分/优先技能列表（格式同上）
4. experience_required: 所需经验年限（数字，无法确定则返回null）
5. education_required: 学历要求（如"本科及以上"）
6. responsibilities: 主要职责列表

## 分类规则
- **required_skills**: "任职要求""岗位职责"中出现，配合"精通""掌握""熟练""熟悉""了解"的技能
- **preferred_skills**: "加分项""优先""plus""bonus""nice to have"分类下的技能

## 输出格式
- 纯 JSON，以 { 开头、} 结尾，无 markdown 代码块、无说明文字
- 可直接 json.loads() 解析，无尾逗号、无注释

## 技能名称规范
1. 使用标准英文名称，首字母大写：python3→Python, reactjs→React, golang→Go, k8s→Kubernetes
2. 同时提取中文名和英文名，保留中英文两种表达（例如 "Python" 和 "Python" 都会被归一化）
3. 带版本号的归入主技能名："C++11"→"C++", "Python3"→"Python", "ES6"→"JavaScript"
4. 不要添加中文描述后缀：
   - "CNN经典网络结构" → "CNN"
   - "Docker容器技术" → "Docker"
   - "CUDA并行编程" → "CUDA"
   - "Linux系统" → "Linux"
5. 无法确认的字段返回 null，禁止编造

## 完整性要求（极其重要）
- **请完整提取职位描述中提到的所有技能和技术要求，不遗漏任何一项**
- 同时也提取**非信息技术相关的技能**（如项目管理、产品设计、团队管理、沟通能力等）
- 包括但不限于：编程语言、框架、工具、平台、方法论、领域知识、证书、软技能
- 隐式技能也要提取（例如提到"构建CI/CD流水线" → 提取 CI/CD; "使用Git进行版本控制" → 提取 Git）
- 提取后请做一次覆盖检查，确认没有遗漏

## 覆盖检查（在输出前逐项确认）
提取完成后，请检查是否覆盖了以下常见类别：
- [ ] 编程语言（Python, Java, Go, Rust, C++ 等）
- [ ] Web框架（React, Vue, Django, Spring 等）
- [ ] 数据库（SQL, NoSQL, Redis, MongoDB 等）
- [ ] 云/DevOps（AWS, Docker, K8s, CI/CD, Terraform 等）
- [ ] 工具链（Git, Jenkins, Gradle, Maven 等）
- [ ] 软技能（项目管理、团队管理、沟通、产品设计 等）
- [ ] 领域知识（安全、大数据、AI/ML、嵌入式 等）
- [ ] 证书/资质（PMP, CPA, AWS认证 等）
- [ ] 中英文技能名称均已覆盖"""

ANTI_HALLUCINATION_PROMPT_V1 = """你是一个严格的技能提取验证器。请检查以下从职位描述中提取的技能是否准确。

## 提取结果
$extraction_json

## 原始职位描述
$jd_content

## 验证规则
1. 检查每个required_skills和preferred_skills是否在职位描述中有明确文本依据
2. 检查是否有明显遗漏的关键技能
3. 注意中文技能名称的匹配（如"项目管理"对应"project management"）

返回JSON格式：
{
    "is_valid": true/false,
    "hallucinated_skills": [],
    "missing_skills": [],
    "confidence": 0.0-1.0,
    "issues": []
}

输出必须以 { 开头、} 结尾，纯 JSON，不要 markdown 代码块。"""

LLM_JUDGE_PROMPT_V1 = """你是一个评估专家。请比较以下两个技能提取结果的质量。

标准答案（Golden）：
$golden_json

待评估系统输出（System）：
$system_json

评估维度：
1. precision: 精确率（提取的技能中有多少是正确的）
2. recall: 召回率（标准答案中的技能有多少被提取了）
3. completeness: 完整性（技能级别、经验等信息是否完整）
4. accuracy: 整体准确性

返回JSON格式：
{
    "precision": 0.0-1.0,
    "recall": 0.0-1.0,
    "completeness": 0.0-1.0,
    "accuracy": 0.0-1.0,
    "f1_score": 0.0-1.0,
    "details": ""
}

纯 JSON，不要 markdown 代码块，不要附加文字，输出必须以 { 开头，以 } 结尾。"""

# v2: Multi-dimensional judge prompt with detailed sub-metrics and structured reasoning
LLM_JUDGE_PROMPT_V2 = """你是一个资深评估专家，负责严格对比两份技能抽取结果。请逐维度分析。

## 标准答案（Golden）
$golden_json

## 系统输出（System）
$system_json

## 评估维度（每项 0.00-1.00）
1. 技能精确率 precision：提取的技能中正确命中 golden 的比例
2. 技能召回率 recall：golden 中的技能被正确提取的比例
3. 信息完整性 completeness：职位名、经验年限、学历等元字段是否正确
4. 职位匹配 position_match：position_name 是否语义等价
5. 经验匹配 experience_match：experience_years 是否一致（差 ±1 年算匹配）
6. 学历匹配 education_match：education_required 是否一致

## 评分标准
0.00 完全不匹配 / 0.25 差  / 0.50 一般  / 0.75 好  / 1.00 完美
F1 = 2 × precision × recall / (precision + recall)  若分母为 0 则 F1=0.00

返回 JSON 格式（严格遵守，不要 markdown 代码块）：
{
    "precision": 0.00,
    "recall": 0.00,
    "completeness": 0.00,
    "position_match": 0.00,
    "experience_match": 0.00,
    "education_match": 0.00,
    "f1_score": 0.00,
    "details": "简要分析每个维度的扣分理由"
}"""

RESUME_EXTRACTION_PROMPT_V1 = """你是一个专业的简历解析专家。请从以下简历内容中提取技能信息。

简历内容：
$resume_content

请提取以下信息并以JSON格式返回：
1. candidate_name: 候选人姓名（如能找到）
2. skills: 技能列表（每项包含 name, level, years_of_experience 字段）
3. work_experience: 工作经验列表（每项包含 company, position, duration, responsibilities）
4. education: 教育背景列表
5. certifications: 证书列表

纯 JSON，不要 markdown 代码块，不要附加文字。"""

# ──────────────────────────────────────────────
# Default active versions (maps prompt name -> version tag)
# ──────────────────────────────────────────────

_ACTIVE_VERSIONS: dict[str, str] = {
    "jd_extraction": "v1",
    "anti_hallucination": "v1",
    "llm_judge": "v1",
    "resume_extraction": "v1",
}

# ──────────────────────────────────────────────
# Versioned prompt registry
# ──────────────────────────────────────────────

_PROMPT_VERSIONS: dict[str, dict[str, str]] = {
    "jd_extraction": {
        "v1": JD_EXTRACTION_PROMPT_V1,
        "v2": JD_EXTRACTION_PROMPT_V2,
        "v3": JD_EXTRACTION_PROMPT_V3,
        "v4": JD_EXTRACTION_PROMPT_V4,
    },
    "anti_hallucination": {
        "v1": ANTI_HALLUCINATION_PROMPT_V1,
    },
    "llm_judge": {
        "v1": LLM_JUDGE_PROMPT_V1,
        "v2": LLM_JUDGE_PROMPT_V2,
    },
    "resume_extraction": {
        "v1": RESUME_EXTRACTION_PROMPT_V1,
    },
}

# ──────────────────────────────────────────────
# A/B test configuration
# ──────────────────────────────────────────────


class ABTestConfig:
    """Configuration for A/B testing between prompt versions.

    Attributes:
        prompt_name: The prompt template name to A/B test.
        canary_version: The candidate version to test.
        traffic_fraction: Fraction of requests routed to canary (0.0 - 0.5).
        control_version: The baseline version (defaults to active version).
    """

    def __init__(
        self,
        prompt_name: str,
        canary_version: str,
        traffic_fraction: float = 0.1,
        control_version: str | None = None,
    ) -> None:
        if not 0.0 < traffic_fraction <= 0.5:
            msg = f"traffic_fraction must be in (0.0, 0.5], got {traffic_fraction}"
            raise ValueError(msg)
        self.prompt_name = prompt_name
        self.canary_version = canary_version
        self.traffic_fraction = traffic_fraction
        self.control_version = control_version or _ACTIVE_VERSIONS.get(prompt_name, "v1")

    def select_version(self) -> str:
        """Randomly select control or canary version based on traffic_fraction."""
        return self.canary_version if random.random() < self.traffic_fraction else self.control_version

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_name": self.prompt_name,
            "control_version": self.control_version,
            "canary_version": self.canary_version,
            "traffic_fraction": self.traffic_fraction,
        }


_AB_TESTS: dict[str, ABTestConfig] = {}


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────


def get_prompt(name: str, **kwargs: Any) -> str:
    """Get a prompt template by name and fill in placeholders.

    If an A/B test is configured for this prompt name, the version is
    selected randomly according to the test config.  Otherwise the
    currently active version is used.

    Args:
        name: Prompt template name (e.g. ``"jd_extraction"``).
        **kwargs: Placeholder values to fill into the template.

    Returns:
        Filled prompt string.

    Raises:
        KeyError: If the prompt name is not found.
        ValueError: If required placeholders are not filled.
    """
    return _get_prompt_versioned(name, version=None, **kwargs)


def get_prompt_version(name: str, version: str, **kwargs: Any) -> str:
    """Get a specific version of a prompt template.

    Args:
        name: Prompt template name.
        version: Version tag (e.g. ``"v1"``, ``"v2"``).
        **kwargs: Placeholder values.

    Returns:
        Filled prompt string.
    """
    return _get_prompt_versioned(name, version=version, **kwargs)


def _get_prompt_versioned(name: str, version: str | None = None, **kwargs: Any) -> str:
    """Internal: resolve version, fill placeholders."""
    # Check A/B test first if no explicit version requested
    if version is None and name in _AB_TESTS:
        version = _AB_TESTS[name].select_version()
        logger.info("A/B test '{}' selected version '{}'", name, version)

    # Resolve version
    if version is None:
        version = _ACTIVE_VERSIONS.get(name, "v1")

    versions = _PROMPT_VERSIONS.get(name)
    if versions is None:
        msg = f"Unknown prompt template: {name}. Available: {list(_PROMPT_VERSIONS.keys())}"
        raise KeyError(msg)

    template = versions.get(version)
    if template is None:
        msg = f"Unknown version '{version}' for prompt '{name}'. Available: {list(versions.keys())}"
        raise KeyError(msg)

    # Fill placeholders (using $-style Template; literal braces { } are safe)
    placeholders = re.findall(r"\$(\w+)", template)
    missing = [p for p in placeholders if p not in kwargs]
    if missing:
        msg = f"Missing required placeholders {missing} for prompt '{name}' (version={version})"
        raise ValueError(msg)

    filled = Template(template).safe_substitute(**kwargs)
    logger.debug("Prompt '{}' v{} filled ({} chars)", name, version, len(filled))
    return filled


def list_prompt_names() -> list[str]:
    """List all registered prompt template names."""
    return list(_PROMPT_VERSIONS.keys())


def list_prompt_versions(name: str) -> list[str]:
    """List available versions for a given prompt template.

    Args:
        name: Prompt template name.

    Returns:
        Sorted list of version tags.
    """
    versions = _PROMPT_VERSIONS.get(name)
    if versions is None:
        msg = f"Unknown prompt template: {name}"
        raise KeyError(msg)
    return sorted(versions.keys())


def get_active_version(name: str) -> str | None:
    """Get the currently active version tag for a prompt template."""
    return _ACTIVE_VERSIONS.get(name)


def get_prompt_template_raw(name: str, version: str | None = None) -> str:
    """Get the raw prompt template string without filling placeholders.

    Args:
        name: Prompt template name.
        version: Version tag. If None, returns the active version's template.

    Returns:
        The raw template string with placeholders intact.

    Raises:
        KeyError: If the prompt name or version does not exist.
    """
    if name not in _PROMPT_VERSIONS:
        msg = f"Unknown prompt template: {name}"
        raise KeyError(msg)
    if version is None:
        version = _ACTIVE_VERSIONS.get(name, "v1")
    template = _PROMPT_VERSIONS[name].get(version)
    if template is None:
        msg = f"Unknown version '{version}' for prompt '{name}'. Available: {list(_PROMPT_VERSIONS[name].keys())}"
        raise KeyError(msg)
    return template


def set_active_version(name: str, version: str) -> None:
    """Set the active version for a prompt template.

    Args:
        name: Prompt template name.
        version: Version tag to activate.

    Raises:
        KeyError: If the prompt name or version does not exist.
    """
    if name not in _PROMPT_VERSIONS:
        msg = f"Unknown prompt template: {name}"
        raise KeyError(msg)
    if version not in _PROMPT_VERSIONS[name]:
        msg = f"Version '{version}' not found for prompt '{name}'. Available: {list(_PROMPT_VERSIONS[name].keys())}"
        raise KeyError(msg)
    _ACTIVE_VERSIONS[name] = version
    logger.info("Active version for '{}' set to '{}'", name, version)


def register_prompt_version(
    name: str,
    template: str,
    version: str | None = None,
    activate: bool = False,
) -> str:
    """Register a new prompt template or a new version of an existing one.

    Args:
        name: Prompt template name.
        template: The prompt template string.
        version: Version tag.  Auto-generated if not provided.
        activate: If True, set this version as the active version.

    Returns:
        The version tag that was registered.
    """
    if version is None:
        existing = _PROMPT_VERSIONS.get(name, {})
        next_num = len(existing) + 1
        version = f"v{next_num}"

    if name not in _PROMPT_VERSIONS:
        _PROMPT_VERSIONS[name] = {}
    _PROMPT_VERSIONS[name][version] = template

    if name not in _ACTIVE_VERSIONS:
        _ACTIVE_VERSIONS[name] = version

    if activate:
        _ACTIVE_VERSIONS[name] = version

    logger.info("Registered prompt '{}' version '{}' (active={})", name, version, activate)
    return version


def set_ab_test(
    prompt_name: str,
    canary_version: str,
    traffic_fraction: float = 0.1,
) -> ABTestConfig:
    """Configure an A/B test for a prompt template.

    Args:
        prompt_name: Prompt template name to test.
        canary_version: The candidate version to test.
        traffic_fraction: Fraction of requests to route to canary (0.0 - 0.5].

    Returns:
        The ABTestConfig instance.
    """
    config = ABTestConfig(
        prompt_name=prompt_name,
        canary_version=canary_version,
        traffic_fraction=traffic_fraction,
    )
    _AB_TESTS[prompt_name] = config
    logger.info("A/B test started for '{}': canary={}, traffic={:.0%}", prompt_name, canary_version, traffic_fraction)
    return config


def get_ab_test(prompt_name: str) -> ABTestConfig | None:
    """Get the current A/B test configuration for a prompt, if any."""
    return _AB_TESTS.get(prompt_name)


def stop_ab_test(prompt_name: str) -> None:
    """Stop an active A/B test for a prompt template."""
    _AB_TESTS.pop(prompt_name, None)
    logger.info("A/B test stopped for '{}'", prompt_name)


def list_ab_tests() -> list[dict[str, Any]]:
    """List all active A/B tests."""
    return [cfg.to_dict() for cfg in _AB_TESTS.values()]


# ──────────────────────────────────────────────
# (Legacy) flat constants for backward compatibility
# ──────────────────────────────────────────────

JD_EXTRACTION_PROMPT = JD_EXTRACTION_PROMPT_V1
ANTI_HALLUCINATION_PROMPT = ANTI_HALLUCINATION_PROMPT_V1
LLM_JUDGE_PROMPT = LLM_JUDGE_PROMPT_V1
RESUME_EXTRACTION_PROMPT = RESUME_EXTRACTION_PROMPT_V1

# Legacy alias for old code that imports _PROMPT_REGISTRY
_PROMPT_REGISTRY: dict[str, str] = {name: versions["v1"] for name, versions in _PROMPT_VERSIONS.items()}
