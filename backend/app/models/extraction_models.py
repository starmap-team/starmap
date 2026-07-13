"""PostgreSQL SQLAlchemy models for extraction pipeline."""

import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class JDExtractionRecord(Base):
    """业务说明：JD（职位描述）提取记录表。

    记录每次从职位描述中提取技能、经验、学历等信息的完整结果。
    是StarMap系统的核心数据入口，所有技能图谱数据均源于此表的提取结果。
    用于追踪提取质量、回溯数据来源、支持模型迭代优化。
    """

    __tablename__ = "jd_extraction_records"

    # 业务说明：记录唯一标识，系统自动生成
    # 技术说明：使用UUID作为主键，避免分布式环境下的ID冲突
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # 业务说明：原始JD文本内容，用于回溯和重新提取
    jd_content: Mapped[str] = mapped_column(Text, nullable=False)
    # 业务说明：从JD中提取的职位名称，用于关联职位记录
    job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    # 业务说明：提取出的技能列表，以JSON格式存储结构化数据
    # 技术说明：JSON类型支持灵活的技能结构扩展，无需修改表结构
    extracted_skills: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # 业务说明：从JD中提取的所需工作年限，null表示未提取到或JD中未提及
    experience_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 业务说明：从JD中提取的学历要求，如"本科"、"硕士"等
    education: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 业务说明：提取结果的置信度分数，用于质量评估和筛选
    # 技术说明：默认0.0，低于阈值的结果需人工复核
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 业务说明：幻觉检测分数，评估提取结果是否存在编造内容
    # 技术说明：分数越高幻觉风险越大，null表示未进行幻觉检测
    hallucination_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 业务说明：记录创建时间，用于数据时效性分析和按时间窗口聚合
    # 技术说明：使用UTC时间避免时区问题，支持全球化部署
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    # 业务说明：提取处理状态，用于追踪异步提取流程
    # 技术说明：状态机流转：pending -> processing -> completed/failed
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )

    def __repr__(self) -> str:
        return f"<JDExtractionRecord {self.id} job_title={self.job_title} status={self.status}>"

    def to_extraction_payload(self) -> dict[str, Any]:
        """Convert this record to the dict format expected by graph_writer and pipeline sync.

        Handles the `extracted_skills` JSON field which may be a list of skill dicts
        or a dict with required/preferred keys, normalizing into a consistent shape.
        """
        from typing import Any as _Any  # noqa: F811 — local alias for readability

        raw = self.extracted_skills
        if isinstance(raw, list):
            skills_list = [s.get("name", s) if isinstance(s, dict) else s for s in raw]
            payload: dict[str, _Any] = {"required_skills": skills_list}
        elif isinstance(raw, dict):
            payload = dict(raw)
        else:
            payload = {}
        payload.setdefault("position_name", self.job_title)
        payload.setdefault("experience_required", self.experience_years)
        payload.setdefault("education_required", self.education)
        return payload


class RawJDRecord(Base):
    """业务说明：原始JD爬取数据表。

    存储从各招聘平台爬取的原始职位数据，是JD提取的上游数据源。
    保留原始文本用于数据溯源、去重和质量审计。
    与JDExtractionRecord构成一对多关系：一条原始JD可触发多次提取。
    """

    __tablename__ = "raw_jd_records"

    # 业务说明：原始记录唯一标识
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    # 业务说明：JD来源URL，用于溯源和数据更新
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 业务说明：数据来源平台标识，如"BOSS直聘"、"拉勾网"等
    # 技术说明：默认"manual"表示手动录入，用于区分自动化爬取和人工数据
    source_platform: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    # 业务说明：原始职位描述文本，未经任何清洗处理
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    # 业务说明：原始职位标题，可能包含平台特有的格式标记
    title_raw: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 业务说明：发布职位的公司名称
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 业务说明：数据爬取时间，用于数据新鲜度评估
    crawl_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )
    # 业务说明：内容去重哈希值，基于文本内容计算的唯一指纹
    # 技术说明：建立索引加速重复检测，64位字符串存储SHA-256哈希
    hash_dedup: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    # 业务说明：数据处理状态，追踪从原始数据到提取完成的流程
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    def __repr__(self) -> str:
        return f"<RawJDRecord {self.id} title={self.title_raw}>"


class SkillAliasRecord(Base):
    """业务说明：技能别名映射表。

    技能标准化流程的第一步：将各种别名、简称、中英文混用等
    非标准技能名称映射为系统认可的标准技能名称。
    例如："Vue.js"、"VueJS"、"vue" -> "Vue.js"
    是构建统一技能图谱的基础数据层。
    """

    __tablename__ = "skill_alias_records"

    # 业务说明：映射记录唯一标识
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    # 业务说明：原始别名，用户输入或从JD中提取的非标准技能名称
    # 技术说明：建立索引支持快速别名查找和去重检测
    alias: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # 业务说明：映射后的标准技能名称，用于统一技能表示
    standard_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # 业务说明：映射规则创建时间，用于管理别名规则的时效性
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<SkillAliasRecord {self.alias}->{self.standard_name}>"


class ExtractionEvaluationRecord(Base):
    """业务说明：提取质量评估记录表。

    对JD提取结果进行质量审计，通过与黄金标准（人工标注）对比
    计算精确率、召回率、F1分数等指标。
    是持续优化提取模型、监控线上提取质量的关键数据表。
    """

    __tablename__ = "extraction_evaluation_records"

    # 业务说明：评估记录唯一标识
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    # 业务说明：关联的提取记录ID，建立评估与提取结果的关联
    # 技术说明：nullable=True允许独立评估，index加速关联查询，FK SET NULL (SEC-05)
    extraction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jd_extraction_records.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    # 业务说明：黄金标准样本ID，指向人工标注的参考数据
    golden_id: Mapped[str] = mapped_column(String(100), nullable=False)
    # 业务说明：精确率，提取结果中正确技能的比例
    # 技术说明：默认0.0，计算公式：正确提取数 / 总提取数
    precision: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 业务说明：召回率，黄金标准中被成功提取的技能比例
    # 技术说明：默认0.0，计算公式：正确提取数 / 黄金标准总数
    recall: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 业务说明：F1分数，精确率和召回率的调和平均数
    # 技术说明：默认0.0，综合评估提取质量的核心指标
    f1_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 业务说明：职位名称是否匹配，评估职位提取准确性
    job_title_match: Mapped[bool] = mapped_column(sa.Boolean, nullable=True)
    # 业务说明：工作年限提取误差，null表示未评估或JD中未提及
    # 技术说明：以年为单位，正值表示高估，负值表示低估
    experience_error: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 业务说明：学历要求是否匹配，评估学历提取准确性
    education_match: Mapped[bool | None] = mapped_column(sa.Boolean, nullable=True)
    # 业务说明：评估执行时间，用于追踪评估流程时效
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<ExtractionEvaluationRecord {self.id} F1={self.f1_score:.3f}>"


class PositionSkillRelation(Base):
    """业务说明：职位-技能关联关系表。

    记录每个职位所需的具体技能及其要求类型（必需/加分）和置信度。
    是构建职位技能图谱的核心关联表，支持多对多关系建模。
    用于技能匹配诊断、学习路径生成、技能趋势分析等业务场景。
    """

    __tablename__ = "position_skill_relations"

    # 业务说明：关联关系唯一标识
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    # 业务说明：关联的职位ID，指向职位主数据表
    # 技术说明：建立索引支持按职位快速查询所需技能，FK CASCADE (SEC-05)
    position_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("position_records.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    # 业务说明：关联的技能ID，指向技能主数据表
    # 技术说明：建立索引支持按技能快速查询相关职位，FK CASCADE (SEC-05)
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skill_records.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    # 业务说明：技能要求类型，区分必需技能和加分技能
    # 技术说明：默认"required"，可选值：required | preferred | optional
    requirement_type: Mapped[str] = mapped_column(String(20), nullable=False, default="required")
    # 业务说明：关联置信度，表示该技能-职位关联的可信程度
    # 技术说明：默认1.0，基于多份JD统计计算得出，值越高关联越可靠
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    # 业务说明：关联记录创建时间，用于数据新鲜度管理
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<PositionSkillRelation pos={self.position_id} skill={self.skill_id}>"


class SystemConfig(Base):
    """业务说明：系统配置表。

    存储系统运行所需的各类配置项，包括提取提示词版本、
    模型参数、阈值设置等。支持动态配置更新，无需重启服务。
    是系统运维和A/B测试的基础设施。
    """

    __tablename__ = "system_config"

    # 业务说明：配置记录唯一标识
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    # 业务说明：配置项键名，全局唯一标识一个配置项
    # 技术说明：unique=True确保键名唯一，index加速配置查询
    config_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    # 业务说明：配置项值，以文本形式存储，根据类型解析
    config_value: Mapped[str] = mapped_column(Text, nullable=False)
    # 业务说明：配置值类型，指导前端如何解析和展示配置值
    # 技术说明：默认"string"，可选值：string | int | float | bool | json
    config_type: Mapped[str] = mapped_column(String(20), nullable=False, default="string")
    # 业务说明：配置项描述，帮助运维人员理解配置用途
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 业务说明：配置最后更新时间，用于配置变更追踪
    # 技术说明：onupdate自动更新，确保修改时间始终最新
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<SystemConfig {self.config_key}={self.config_value[:50]}>"


class SkillRecord(Base):
    """业务说明：技能主数据表。

    存储系统中所有已识别的标准技能，是技能图谱的节点数据。
    包含技能名称、分类、来源统计等信息，用于技能标准化和趋势分析。
    与PositionSkillRelation关联构建职位-技能关系网络。
    """

    __tablename__ = "skill_records"

    # 业务说明：技能唯一标识
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # 业务说明：技能标准名称，全局唯一
    # 技术说明：unique=True防止重复技能，index加速技能查找
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    # 业务说明：技能分类，如"编程语言"、"框架"、"工具"等
    # 技术说明：默认"general"，用于技能分组展示和分类统计
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="general")
    # 业务说明：该技能被检测到的来源数量，反映技能普及度
    # 技术说明：默认0，随新JD提取自动递增，用于技能热度排序
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 业务说明：技能首次被检测到的时间，用于新技能发现追踪
    first_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    # 业务说明：技能最近一次被检测到的时间，用于技能活跃度评估
    # 技术说明：onupdate自动更新，反映技能的最新出现时间
    last_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<SkillRecord {self.name} category={self.category}>"


class PositionRecord(Base):
    """业务说明：职位主数据表。

    存储系统中所有已识别的标准职位名称，是职位图谱的节点数据。
    包含职位名称、所属行业、描述等信息。
    与SkillRecord通过PositionSkillRelation关联，构建完整的职位技能图谱。
    """

    __tablename__ = "position_records"

    # 业务说明：职位唯一标识
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # 业务说明：职位标准名称，全局唯一
    # 技术说明：unique=True确保职位名称唯一性，index加速职位查询
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    # 业务说明：职位所属行业，如"互联网"、"金融"、"制造业"等
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 业务说明：职位描述，存储职位的通用职责和要求说明
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 业务说明：职位记录创建时间，用于数据审计
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<PositionRecord {self.name}>"


class MatchResult(Base):
    """业务说明：技能匹配诊断结果表。

    持久化存储用户的技能匹配诊断结果，包括目标职位、
    个人技能清单、匹配分数、技能缺口分析、学习路径建议等。
    是StarMap核心功能"技能匹配诊断"的数据落点，支持结果分享和历史回溯。
    """

    __tablename__ = "match_results"

    # 业务说明：匹配结果唯一标识
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # 业务说明：匹配结果的业务标识，用于对外分享和查询
    # 技术说明：unique=True确保标识唯一，index加速结果查询
    match_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    # 业务说明：用户选择的目标职位名称
    target_position: Mapped[str] = mapped_column(String(255), nullable=False)
    # 业务说明：用户输入的个人技能列表，JSON数组格式
    # 技术说明：存储原始输入技能，用于结果重现和对比分析
    person_skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # 业务说明：总体匹配分数，0-1之间，越高表示越匹配
    # 技术说明：默认0.0，基于技能覆盖度、重要性加权计算
    match_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 业务说明：已匹配的技能列表，用户已掌握且职位需要的技能
    matched_skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # 业务说明：缺失的必需技能列表，用户未掌握但职位必需的技能
    missing_required: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # 业务说明：缺失的加分技能列表，用户未掌握但职位优先的技能
    missing_bonus: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # 业务说明：技能缺口详细报告，包含每个缺失技能的详细信息
    # 技术说明：JSON格式存储结构化缺口分析数据
    gap_report: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # 业务说明：推荐的学习路径，按优先级排序的技能学习序列
    # 技术说明：JSON数组格式，每个元素包含技能名、学习资源、预计时长
    learning_path: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # 业务说明：CII（Career Investment Index）职业投资指数
    # 技术说明：默认1.0，反映达成目标职位所需投入的综合评估指标
    cii: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    # 业务说明：匹配结果创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    # 业务说明：结果过期时间，过期后结果可能被清理
    # 技术说明：null表示永不过期，支持TTL自动清理策略
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<MatchResult {self.match_id} position={self.target_position} score={self.match_score}>"


class ReviewQueue(Base):
    """业务说明：审核队列表（持久化存储）。

    存储需要人工审核的数据条目，包括技能别名审核、
    新技能发现审核、提取结果异常审核等。
    是人工介入质量控制的入口，确保关键数据变更经过人工确认。
    """

    __tablename__ = "review_queue"

    # 业务说明：审核队列条目自增ID
    # 技术说明：使用自增整数主键，便于队列顺序管理和分页查询
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 业务说明：待审核实体类型，如"skill_alias"、"new_skill"、"extraction"等
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # 业务说明：待审核实体名称，便于快速识别审核内容
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # 业务说明：审核状态，追踪审核流程
    # 技术说明：默认"pending"，状态流转：pending -> approved/rejected
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    # 业务说明：审核相关的附加数据，以JSON格式存储
    # 技术说明：null表示无附加数据，存储审核所需的上下文信息
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 业务说明：审核条目创建时间，用于队列优先级和时效管理
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<ReviewQueue {self.id} {self.entity_type}:{self.entity_name} status={self.status}>"
