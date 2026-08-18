"""SQLAlchemy models for the learning center subsystem.

Tables:
- learning_plans: User learning plans tied to target positions
- learning_progress: Per-skill progress tracking within a plan
- skill_prerequisites: Skill prerequisite DAG edges
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class LearningPlan(Base):
    """业务说明：用户学习计划主表。

    记录用户针对特定目标职位制定的学习计划，包括需要学习的技能列表、
    整体进度状态和预计完成时间。是StarMap学习路径功能的核心数据表，
    从技能匹配诊断结果生成，指导用户系统性地弥补技能缺口。
    支持多计划管理，用户可同时制定多个职位的学习计划。
    """

    __tablename__ = "learning_plans"

 # 业务说明：学习计划唯一标识
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
 # 业务说明：计划所属用户标识，关联用户系统
 # 技术说明：默认"anonymous"支持未登录用户体验，index加速用户计划查询
    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True, default="anonymous",
    )
 # 业务说明：目标职位名称，用户希望达成的职业方向
 # 技术说明：建立索引支持按职位查询学习计划分布，与PositionRecord.name关联
    position: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
        comment="Target position name",
    )
 # 业务说明：计划包含的技能列表，每个技能包含名称、重要性、缺口等级等信息
 # 技术说明：JSON格式存储技能对象数组，结构：{name, importance, gap_level, learning_path}
    skills: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=list,
        comment="List of skill dicts: {name, importance, gap_level, learning_path}",
    )
 # 业务说明：学习计划整体状态，追踪计划执行进度
 # 技术说明：默认"active"，状态流转：active -> completed -> archived
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active",
        comment="active | completed | archived",
    )
 # 业务说明：计划创建时的匹配分数，记录用户初始技能水平
 # 技术说明：默认0.0，用于对比学习前后的技能提升效果
    match_score_at_creation: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="Match score when plan was created",
    )
 # 业务说明：完成计划所需的预计总学习时长（小时）
 # 技术说明：默认0.0，基于各技能estimated_hours累加计算
    estimated_hours: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="Total estimated learning hours",
    )
 # 业务说明：计划创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )
 # 业务说明：计划最后更新时间
 # 技术说明：onupdate自动更新，反映学习进度的最新变化时间
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<LearningPlan {self.id} position={self.position} status={self.status}>"


class LearningProgress(Base):
    """业务说明：学习进度明细表。

    记录学习计划中每个技能的详细学习进度，包括掌握状态、完成百分比、
    开始和完成时间等。是用户学习看板的数据来源，支持技能级别的
    精细化进度追踪。与LearningPlan构成一对多关系：一个计划包含多个技能进度。
    """

    __tablename__ = "learning_progress"

 # 业务说明：进度记录唯一标识
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
 # 业务说明：关联的学习计划ID，指向LearningPlan
 # 技术说明：建立索引支持按计划快速查询所有技能进度，FK CASCADE (SEC-05)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learning_plans.id", ondelete="CASCADE"), nullable=False, index=True,
    )
 # 业务说明：当前进度对应的技能名称
 # 技术说明：与SkillRecord.name关联，但不做外键约束以支持自定义技能
    skill_name: Mapped[str] = mapped_column(
        String(255), nullable=False,
    )
 # 业务说明：技能学习状态，追踪学习流程
 # 技术说明：默认"not_started"，状态流转：not_started -> in_progress -> mastered
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="not_started",
        comment="not_started | in_progress | mastered",
    )
 # 业务说明：技能学习完成百分比
 # 技术说明：默认0.0，范围0.0-100.0，用于进度可视化
    progress_pct: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="0.0 - 100.0",
    )
 # 业务说明：技能重要性等级，影响学习优先级排序
 # 技术说明：默认"required"，可选值：required（必需）| bonus（加分）
    importance: Mapped[str] = mapped_column(
        String(20), nullable=False, default="required",
        comment="required | bonus",
    )
 # 业务说明：掌握该技能预计需要的学习时长（小时）
 # 技术说明：默认0.0，基于技能复杂度、用户基础等因素估算
    estimated_hours: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="Estimated hours to master this skill",
    )
 # 业务说明：用户对该技能的学习笔记和心得
 # 技术说明：Text类型支持长文本，null表示暂无笔记
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
 # 业务说明：技能学习开始时间，null表示尚未开始
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
 # 业务说明：技能学习完成时间，null表示尚未完成
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
 # 业务说明：进度记录创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )
 # 业务说明：进度记录最后更新时间
 # 技术说明：onupdate自动更新，反映学习进度的实时变化
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return (
            f"<LearningProgress plan={self.plan_id} "
            f"skill={self.skill_name} status={self.status} pct={self.progress_pct}>"
        )


class SkillPrerequisite(Base):
    """业务说明：技能前置依赖关系表。

    存储技能之间的前置依赖关系，形成有向无环图（DAG）。
    是学习路径生成的核心数据结构，确保用户按正确顺序学习技能。
    例如：学习"React"需要先掌握"JavaScript"，学习"Docker"需要先了解"Linux基础"。
    通过拓扑排序算法基于该表生成最优学习路径。
    """

    __tablename__ = "skill_prerequisites"

 # 业务说明：依赖关系唯一标识
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
 # 业务说明：目标技能，即需要前置知识的技能
 # 技术说明：建立索引支持按技能查询其所有前置依赖
    skill: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
        comment="The skill that has a prerequisite",
    )
 # 业务说明：前置技能，即必须先掌握的技能
 # 技术说明：建立索引支持按技能查询它是哪些技能的前置条件
    prerequisite: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
        comment="The prerequisite skill that must be learned first",
    )
 # 业务说明：依赖强度，表示前置技能的必要程度
 # 技术说明：默认1.0，范围0.0-1.0，1.0表示硬性要求，低于1.0表示推荐但非必需
    strength: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0,
        comment="Prerequisite strength 0.0-1.0 (1.0 = hard requirement)",
    )
 # 业务说明：依赖关系创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return (
            f"<SkillPrerequisite {self.skill} <- {self.prerequisite} "
            f"strength={self.strength}>"
        )
