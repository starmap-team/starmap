"""Pipeline 数据契约 — 求职者业务闭环步骤间的数据类型定义。

所有 Pipeline 步骤通过 PipelineContext 共享数据，通过 SSE 事件流推送进度。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ── 技能数据 ──────────────────────────────────────────────


@dataclass
class ExtractedSkill:
    """统一的技能数据格式，用于 Pipeline 步骤间传递。"""

    name: str  # 标准化后的技能名（经 normalize_skill 处理）
    raw_name: str  # 原始提取名（LLM 输出或用户输入）
    category: str  # 分类：hard_skill / soft_skill / tool
    proficiency: str  # 熟练度：了解 / 熟悉 / 掌握 / 精通
    confidence: float  # 提取置信度 [0, 1]
    source: str  # 来源：llm_extraction / graph / manual


# ── 岗位画像 ──────────────────────────────────────────────


@dataclass
class PositionProfile:
    """从 Neo4j 加载的岗位画像。"""

    name: str
    industry: str
    required_skills: list[
        dict[str, Any]
    ]  # [{"name":"Python","category":"hard_skill","proficiency":"精通","is_required":True}]
    bonus_skills: list[dict[str, Any]] = field(default_factory=list)
    market_demand: float = 0.5  # 市场需求度 [0, 1]
    # P5 fix (Phase 24 求职者分析): 岗位中文名（D8g/D8i 中文化贯穿）。
    # 分析报告此前显示英文 name（Senior Controller – Reporting & Insights），
    # 而岗位详情页用 name_cn || name（高级财务控制 — 报告与洞察）——两处不一致。
    name_cn: str = ""


@dataclass
class DataQualityStats:
    """图谱数据质量统计。"""

    total_positions: int
    positions_with_skills: int  # 有≥3个required_skills的岗位
    coverage_ratio: float  # positions_with_skills / total_positions
    total_skills: int
    skills_with_sources: int  # source_count≥3的技能
    skill_trust_ratio: float  # skills_with_sources / total_skills
    prerequisite_count: int  # PREREQUISITE关系数


# ── Pipeline 上下文 ───────────────────────────────────────


@dataclass
class PipelineContext:
    """Pipeline 步骤间共享的可变上下文。

    每个步骤读取前置步骤的输出，写入自己的输出。
    错误记录在 errors 列表中，支持部分失败的优雅降级。
    """

    resume_file: Any | None = None  # UploadFile 对象
    resume_text: str | None = None
    extracted_skills: list[ExtractedSkill] = field(default_factory=list)
    target_positions: list[str] = field(default_factory=list)
    match_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    recommended_positions: list[dict[str, Any]] = field(default_factory=list)
    data_source: str = "unknown"  # graph / postgresql / hardcoded_fallback
    errors: list[str] = field(default_factory=list)
    progress: dict[str, str] = field(default_factory=dict)  # step_name → status


# ── 步骤接口 ──────────────────────────────────────────────

# 步骤实现者只需具备 name (str), timeout (int), execute(ctx) 方法，
# PipelineEngine 通过 duck typing 编排，无需显式 Protocol 声明。
