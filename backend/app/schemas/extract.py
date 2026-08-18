"""抽取域 Schema：JD 文本抽取请求/响应。

LLM 驱动的 JD 文本 → 结构化技能数据的输入输出模型。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SkillItem(BaseModel):
    """单条技能抽取结果（LLM 输出）。"""

    skill: str = Field(
        min_length=1,
        max_length=200,
        description="技能名称",
        examples=["Python", "Docker"],
    )
    category: str = Field(
        min_length=1,
        max_length=50,
        description="技能分类标签",
        examples=["hard_skill", "tool"],
    )
    proficiency: str = Field(
        min_length=1,
        max_length=20,
        description="要求熟练度",
        examples=["精通", "熟悉", "了解"],
    )


class NormalizedSkill(BaseModel):
    """归一化后的技能。"""

    original: str = Field(
        min_length=1,
        max_length=200,
        description="抽取的原始技能名称",
    )
    normalized: str = Field(
        min_length=1,
        max_length=200,
        description="归一化后的标准技能名称",
    )
    method: str = Field(
        min_length=1,
        max_length=50,
        description="归一化方法（alias / embedding / llm）",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="归一化置信度 [0, 1]",
    )


class ExtractionRequest(BaseModel):
    """JD 文本抽取请求。"""

    jd_content: str = Field(
        min_length=1,
        max_length=100_000,
        description="职位描述原始文本（支持中英文）",
    )
    options: dict[str, Any] | None = Field(
        default=None,
        description="抽取选项（model, temperature, max_tokens 等）",
    )


class ExtractionResult(BaseModel):
    """JD 文本抽取结果。

    这是 LLM 抽取管线的最终输出，同时作为归一化和图谱写入的输入。
    """

    position_name: str = Field(
        default="",
        max_length=200,
        description="抽取出的岗位名称",
    )
    required_skills: list[SkillItem] = Field(
        default_factory=list,
        description="必须掌握的技能",
    )
    preferred_skills: list[SkillItem] = Field(
        default_factory=list,
        description="加分技能",
    )
    experience_required: int | None = Field(
        default=None,
        ge=0,
        le=50,
        description="要求的工作经验年数",
    )
    education_required: str | None = Field(
        default=None,
        max_length=50,
        description="学历要求",
        examples=["本科", "硕士", "不限"],
    )
    responsibilities: list[str] = Field(
        default_factory=list,
        description="岗位职责列表",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="整体抽取置信度 [0, 1]",
    )
    hallucination_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="幻觉风险评分 [0, 1]（越低越好）",
    )
    normalized_skills: list[NormalizedSkill] = Field(
        default_factory=list,
        description="归一化后的技能列表",
    )
 # 真实 API 透传字段（原 extract 路由内联版, 批次13 迁入时对齐）：
    tools: list[dict[str, Any]] = Field(
        default_factory=list,
        description="JD 提及的工具与框架",
    )
    learning_resources: list[dict[str, Any]] = Field(
        default_factory=list,
        description="JD 提及的学习资源",
    )
    evolves_to: list[str] = Field(
        default_factory=list,
        description="该岗位演进方向",
    )
    hallucinated_skills: list[str] = Field(
        default_factory=list,
        description="反幻觉检查判定的幻觉技能",
    )
    missing_skills: list[str] = Field(
        default_factory=list,
        description="缺失的核心技能",
    )
    issues: list[str] = Field(
        default_factory=list,
        description="反幻觉检查问题清单",
    )
    model_used: str | None = Field(
        default=None,
        max_length=200,
        description="实际用于本次抽取的 LLM 模型标识（含本地降级回退时的模型名）",
        examples=["qwen2.5:7b", "qwen2.5-7b-fallback"],
    )
