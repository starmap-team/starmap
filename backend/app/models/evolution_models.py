"""PostgreSQL SQLAlchemy models for the evolution subsystem.

Tables:
- evolution_snapshot: Point-in-time skill profiles per position
- evolution_changelog: Skill changes detected by DiffEngine
- evolution_path: EVOLVES_TO relationships with evidence
- skill_timeseries: Skill frequency tracking over time windows
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class EvolutionSnapshot(Base):
    """业务说明：职位技能快照表。

    记录特定时间点某个职位的完整技能画像，包括必需技能和优先技能的全集。
    是DiffEngine差异分析的基础数据源，通过对比两个时间点的快照
    计算技能变化（新增、删除、升级、降级），驱动技能演化追踪。
    支持按职位和时间维度回溯技能需求的历史变迁。
    """

    __tablename__ = "evolution_snapshots"

    # 业务说明：快照唯一标识
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    # 业务说明：快照对应的职位名称
    # 技术说明：建立索引支持按职位快速查询历史快照序列
    position_name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )
    # 业务说明：快照时间点，标记技能画像的采集时间
    # 技术说明：建立索引支持按时间范围查询，通常按月/季度聚合
    snapshot_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
    )
    # 业务说明：该职位在快照时间点的必需技能列表
    # 技术说明：JSON格式存储技能对象数组，每个元素包含name、category、proficiency
    required_skills: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=list,
        comment="List of {name, category, proficiency} dicts",
    )
    # 业务说明：该职位在快照时间点的优先/加分技能列表
    # 技术说明：JSON格式存储，结构与required_skills一致，用于区分技能重要性等级
    preferred_skills: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=list,
        comment="List of {name, category, proficiency} dicts",
    )
    # 业务说明：构成该快照的JD来源数量，反映数据可信度
    # 技术说明：默认0，source_count越大，快照统计越可靠
    source_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Number of JDs contributing to this snapshot",
    )
    # 业务说明：快照的额外元数据，如查询窗口、过滤条件等
    # 技术说明：JSON格式存储灵活扩展，记录快照生成时的上下文信息
    metadata_json: Mapped[dict] = mapped_column(
        JSON, nullable=True, default=dict,
        comment="Extra metadata (query window, filters applied, etc.)",
    )
    # 业务说明：快照记录创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return (
            f"<EvolutionSnapshot {self.position_name} "
            f"date={self.snapshot_date.date()} skills={len(self.required_skills or [])}>"
        )


class EvolutionChangelog(Base):
    """业务说明：技能演化变更日志表。

    记录DiffEngine检测到的技能变化事件，每条记录代表一个具体的技能变更
    （新增必需、新增优先、删除、升级、降级、保留）。
    是技能趋势分析、职位演化报告、技能预警的核心数据来源。
    通过关联两个快照ID，可追溯变更的上下文和证据。
    """

    __tablename__ = "evolution_changelog"

    # 业务说明：变更记录唯一标识
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    # 业务说明：发生技能变更的职位名称
    # 技术说明：建立索引支持按职位查询变更历史
    position_name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )
    # 业务说明：发生变更的技能名称
    # 技术说明：建立索引支持按技能查询哪些职位发生了相关变更
    skill_name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )
    # 业务说明：变更类型，标识技能状态的具体变化
    # 技术说明：枚举值：added_required（新增必需）| added_preferred（新增优先）|
    #          removed（删除）| promoted（升级）| demoted（降级）| retained（保留）
    change_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="added_required | added_preferred | removed | promoted | demoted | retained",
    )
    # 业务说明：变更前的技能熟练度要求，null表示新增技能
    old_proficiency: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 业务说明：变更后的技能熟练度要求，null表示删除技能
    new_proficiency: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 业务说明：变更前的技能要求类型，null表示新增技能
    # 技术说明：枚举值：required（必需）| preferred（优先）| null（新增时）
    old_requirement: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="required | preferred | null (if new)",
    )
    # 业务说明：变更后的技能要求类型，null表示删除技能
    # 技术说明：枚举值：required（必需）| preferred（优先）| null（删除时）
    new_requirement: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="required | preferred | null (if removed)",
    )
    # 业务说明：变更前快照ID，指向演化前的技能画像
    # 技术说明：nullable=True兼容首次快照，index加速关联查询，FK SET NULL (SEC-05)
    snapshot_from_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evolution_snapshots.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    # 业务说明：变更后快照ID，指向演化后的技能画像
    # 技术说明：nullable=True兼容最新快照，index加速关联查询，FK SET NULL (SEC-05)
    snapshot_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evolution_snapshots.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    # 业务说明：TrustScorer计算的可信度分数，评估变更的可靠性
    # 技术说明：默认0.5，范围0.0-1.0，值越高变更越可信，低分变更需人工复核
    trust_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5,
        comment="Trust score from TrustScorer (0.0-1.0)",
    )
    # 业务说明：DiffEngine检测到的变更置信度
    # 技术说明：默认0.5，范围0.0-1.0，基于统计显著性计算
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5,
        comment="Detection confidence (0.0-1.0)",
    )
    # 业务说明：支持该变更的证据详情，包括来源JD、时间戳等
    # 技术说明：JSON格式存储，为变更提供可追溯的数据依据
    evidence_json: Mapped[dict] = mapped_column(
        JSON, nullable=True, default=dict,
        comment="Evidence details (source JDs, timestamps, etc.)",
    )
    # 业务说明：变更检测时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return (
            f"<EvolutionChangelog {self.position_name} "
            f"{self.skill_name} {self.change_type}>"
        )


class EvolutionPath(Base):
    """业务说明：职位演化路径表。

    存储发现的职位间演化关系（如"后端工程师"→"全栈工程师"），
    包含Jaccard相似度和支持证据。是职业路径规划的核心数据，
    帮助用户理解不同职位间的技能关联和转型可行性。
    基于技能集合的相似性计算和自然语言处理技术自动发现。
    """

    __tablename__ = "evolution_paths"

    # 业务说明：演化路径唯一标识
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    # 业务说明：源职位名称，即转型的起点职位
    # 技术说明：建立索引支持按源职位查询可达的目标职位
    source_position: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )
    # 业务说明：目标职位名称，即转型的终点职位
    # 技术说明：建立索引支持按目标职位查询可能的来源职位
    target_position: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )
    # 业务说明：两个职位技能集合的Jaccard相似度
    # 技术说明：计算公式：交集大小 / 并集大小，值越高职位越相似
    similarity: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="Jaccard similarity between position skill sets",
    )
    # 业务说明：支持该演化路径的证据数量
    # 技术说明：默认0，基于JD数据、职业轨迹等多种证据源统计
    evidence_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Number of supporting evidence items",
    )
    # 业务说明：两个职位共有的重叠技能列表
    # 技术说明：JSON数组格式，展示职位间的技能交集，帮助用户了解已有基础
    skill_overlap: Mapped[dict] = mapped_column(
        JSON, nullable=True, default=list,
        comment="List of overlapping skill names",
    )
    # 业务说明：目标职位要求但源职位不具备的关键技能缺口
    # 技术说明：JSON数组格式，识别转型的核心学习需求
    key_gaps: Mapped[dict] = mapped_column(
        JSON, nullable=True, default=list,
        comment="List of skills the target requires but source doesn't",
    )
    # 业务说明：预计完成职位转型所需的月数
    # 技术说明：null表示暂无法估计，基于技能缺口和学习曲线模型计算
    avg_months: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Estimated months for transition",
    )
    # 业务说明：演化路径的可信度分数
    # 技术说明：默认0.5，综合证据数量、来源质量、时间跨度等因素计算
    trust_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5,
    )
    # 业务说明：该演化路径首次被发现的时间
    first_detected: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )
    # 业务说明：该演化路径最近一次更新的时间
    # 技术说明：onupdate自动更新，反映路径数据的最新验证时间
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return (
            f"<EvolutionPath {self.source_position} → {self.target_position} "
            f"sim={self.similarity:.2f}>"
        )


class SkillTimeseries(Base):
    """业务说明：技能时间序列统计表。

    按时间窗口统计各技能的出现频率，支持技能趋势分析和Z-score新兴技能检测。
    通过对比不同时间窗口的技能频率变化，识别正在兴起或衰退的技能。
    是技能市场趋势报告、技术雷达图、新兴技能预警的数据基础。
    """

    __tablename__ = "skill_timeseries"

    # 业务说明：时间序列记录唯一标识
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    # 业务说明：统计的技能名称
    # 技术说明：建立索引支持按技能查询历史趋势
    skill_name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )
    # 业务说明：统计窗口的起始时间
    # 技术说明：建立索引支持按时间范围聚合查询，通常按月或季度窗口
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
    )
    # 业务说明：统计窗口的结束时间
    window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    # 业务说明：该技能在该时间窗口内出现的JD数量
    # 技术说明：默认0，反映技能的市场需求量，是趋势分析的核心指标
    frequency: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Number of JDs mentioning this skill in this window",
    )
    # 业务说明：该时间窗口内统计的独立数据来源数量
    # 技术说明：默认0，source_count越高，frequency数据越可靠
    source_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Number of independent sources",
    )
    # 业务说明：提及该技能的相关职位列表
    # 技术说明：JSON数组格式，了解技能在哪些职位类型中流行
    positions: Mapped[dict] = mapped_column(
        JSON, nullable=True, default=list,
        comment="List of positions mentioning this skill",
    )
    # 业务说明：技能分类，用于分类级别的趋势分析
    # 技术说明：默认"general"，与SkillRecord.category保持一致
    category: Mapped[str] = mapped_column(
        String(100), nullable=False, default="general",
    )
    # 业务说明：记录创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return (
            f"<SkillTimeseries {self.skill_name} "
            f"window={self.window_start.date()}-{self.window_end.date()} "
            f"freq={self.frequency}>"
        )
