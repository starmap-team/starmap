"""SQLAlchemy models for data pipeline monitoring."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from app.models import Base


class PipelineRun(Base):
    """业务说明：数据流水线运行记录表。

    记录ETL数据流水线（crawl -> dedup -> clean -> import -> graph_sync）
    的每次运行状态和结果。是数据运维监控的核心数据表，支持流水线
    执行追踪、性能分析、故障排查和质量评估。
    每个PipelineRun包含多个阶段（stages）的详细执行信息。
    """

    __tablename__ = "pipeline_runs"

    # 业务说明：流水线运行记录唯一标识
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # 业务说明：流水线运行类型，标识数据处理的粒度
    # 技术说明：默认"full"，可选值：
    #   full（全量重跑）| incremental（增量更新）| source_sync（单源同步）
    run_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="full",
        comment="'full' | 'incremental' | 'source_sync'",
    )
    # 业务说明：流水线整体运行状态
    # 技术说明：默认"running"，状态流转：running -> completed/failed/cancelled
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="running",
        comment="'running' | 'completed' | 'failed' | 'cancelled'",
    )
    # 业务说明：流水线启动时间，用于计算总执行时长
    # 技术说明：默认当前UTC时间，精确记录任务调度时间
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )
    # 业务说明：流水线完成时间，null表示尚未完成或仍在运行中
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # 业务说明：各阶段的详细执行信息，包括阶段名称、状态、耗时、处理记录数、错误等
    # 技术说明：JSON数组格式，结构：[{name, status, duration_ms, records_processed, errors}]
    stages: Mapped[dict | list | None] = mapped_column(
        JSON, nullable=True, default=list,
        comment="[{name, status, duration_ms, records_processed, errors}]",
    )
    # 业务说明：本次运行处理的总记录数，包含新增和更新
    # 技术说明：默认0，用于评估数据吞吐量和流水线负载
    total_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 业务说明：本次运行新增的记录数
    # 技术说明：默认0，与total_records对比可计算更新比例
    new_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 业务说明：本次运行更新的记录数
    # 技术说明：默认0，反映数据变化的活跃程度
    updated_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 业务说明：数据质量评分，综合评估本次运行产出数据的质量
    # 技术说明：默认0.0，基于完整性、准确性、一致性等多维度计算
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 业务说明：错误日志，记录流水线运行中的异常和错误详情
    # 技术说明：Text类型支持长文本，null表示无错误或尚未记录
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 业务说明：指定执行的特定阶段列表，用于部分重跑或调试
    # 技术说明：JSON数组格式，null表示执行所有阶段
    selected_stages: Mapped[list | None] = mapped_column(
        JSON, nullable=True,
        comment="List of stage names to execute; null = all stages",
    )

    def __repr__(self) -> (
        str
    ):
        return (
            f"<PipelineRun {self.id} type={self.run_type} "
            f"status={self.status} quality={self.quality_score:.2f}>"
        )


class PipelineSchedule(Base):
    """业务说明：流水线定时调度配置表。

    存储基于Cron表达式的流水线定时调度配置，支持自动化数据更新。
    是数据流水线自动化运维的基础设施，可配置不同调度策略
    （全量、增量）和触发时间，实现无人值守的数据同步。
    """

    __tablename__ = "pipeline_schedules"

    # 业务说明：调度配置唯一标识
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    # 业务说明：调度任务名称，便于识别和管理
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # 业务说明：Cron表达式，定义调度触发时间规则
    # 技术说明：标准Cron格式，例如"0 2 * * *"表示每天凌晨2点执行
    cron_expression: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="cron expression, e.g. '0 2 * * *'",
    )
    # 业务说明：调度触发的流水线运行类型
    # 技术说明：默认"incremental"，增量更新减少资源消耗，适合定时调度
    run_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="incremental",
    )
    # 业务说明：指定调度触发的特定阶段列表
    # 技术说明：JSON数组格式，null表示执行所有阶段
    selected_stages: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # 业务说明：调度任务是否启用，用于临时暂停而不删除配置
    # 技术说明：默认True，设置为False时调度器跳过该任务
    enabled: Mapped[bool] = mapped_column(
        default=True, nullable=False,
    )
    # 业务说明：调度任务最近一次执行时间，null表示尚未执行
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 业务说明：调度任务预计下次执行时间，由调度器计算
    # 技术说明：null表示无法计算或调度已暂停，用于调度状态展示
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 业务说明：调度配置创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )


class DataSourceRecord(Base):
    """业务说明：外部数据源配置与状态表。

    存储各外部数据源的详细配置和运行状态，包括招聘平台、API接口、
    手动导入等数据来源。是数据治理的核心元数据表，支持数据源
    统一管理、质量评估和权限控制。
    每个数据源有独立的权威度评分，影响数据融合时的权重分配。
    """

    __tablename__ = "data_sources"

    # 业务说明：数据源唯一标识
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # 业务说明：数据源名称，如"BOSS直聘"、"拉勾网"、"51Job"、"GitHub"、"ESCO"等
    # 技术说明：unique=True确保名称唯一，index加速数据源查询
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True,
        comment="'BOSS直聘' | '拉勾网' | '51Job' | 'GitHub' | 'ESCO'",
    )
    # 业务说明：数据源接入类型，标识数据获取方式
    # 技术说明：默认"crawler"，可选值：crawler（爬虫）| api（接口）| manual（手动）| import（导入）
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="crawler",
        comment="'crawler' | 'api' | 'manual' | 'import'",
    )
    # 业务说明：数据源权威度评分，影响数据融合权重
    # 技术说明：默认0.5，范围0.0-1.0，权威度越高，该源数据在冲突时权重越大
    authority_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5,
        comment="Source authority weight 0.0-1.0",
    )
    # 业务说明：数据源运行状态，用于监控和告警
    # 技术说明：默认"active"，可选值：active（正常）| paused（暂停）| error（异常）
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active",
        comment="'active' | 'paused' | 'error'",
    )
    # 业务说明：最近一次爬取/同步时间，评估数据新鲜度
    # 技术说明：null表示尚未执行过爬取
    last_crawl_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # 业务说明：该数据源累计爬取的总记录数
    # 技术说明：默认0，用于评估数据源的数据丰富度
    total_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 业务说明：该数据源有效的记录数（经过去重和质量过滤后）
    # 技术说明：默认0，与total_records对比可计算数据有效率
    valid_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 业务说明：该数据源的重复率，评估数据质量
    # 技术说明：默认0.0，计算公式：重复记录数 / total_records，越低越好
    duplicate_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 业务说明：该数据源的平均数据质量评分
    # 技术说明：默认0.0，综合评估数据完整性、准确性、时效性等维度
    avg_quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 业务说明：数据源的详细配置参数，如爬取规则、API密钥、请求频率等
    # 技术说明：JSON格式存储，结构灵活，支持不同类型数据源的配置差异
    config: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=dict,
        comment="Crawler / API configuration parameters",
    )


# ── Phase 7: Graph write outbox (P0-1 fix: prevent PG/Neo4j data drift) ──


class GraphWriteOutbox(Base):
    """Outbox record for pending Neo4j graph writes.

    Before writing extraction results to Neo4j (graph_sync stage), each batch is
    first persisted here. If the Neo4j write succeeds, the record is marked
    'completed'. If it fails, it stays 'pending' and is retried on the next
    pipeline run or via the manual retry endpoint.
    """

    __tablename__ = "graph_write_outbox"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True,
        comment="Owning pipeline run; NULL for ad-hoc extractions (use extraction_ids)",
    )
    extraction_ids: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list,
        comment="List of JDExtractionRecord IDs to write to Neo4j",
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
        comment="'pending' | 'completed' | 'failed'",
    )
    triples_written: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Triples successfully merged into Neo4j",
    )
    error: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Failure reason (if status='failed')",
    )
    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<GraphWriteOutbox id={self.id} status={self.status} "
            f"run_id={self.run_id}>"
        )


def _utcnow() -> datetime:
    """业务说明：获取当前UTC时间的辅助函数。

    用于LoopResultRecord的默认时间值，确保时间一致性。
    """
    return datetime.now(UTC)


class LoopResultRecord(Base):
    """业务说明：闭环流水线运行结果表。

    持久化存储闭环流水线（closed-loop pipeline）的运行结果，
    包括各步骤的执行状态、序列化结果和错误日志。
    是自动化数据处理闭环的数据落点，支持结果回溯、
    故障诊断和流程优化分析。
    """

    __tablename__ = "loop_results"

    # 业务说明：闭环结果记录ID，使用自增整数
    # 技术说明：使用Integer自增主键，便于顺序查询和分页
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 业务说明：闭环运行的业务标识，全局唯一
    # 技术说明：unique=True确保标识唯一，index加速结果查询
    run_id: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False,
    )
    # 业务说明：触发此闭环运行的用户标识 (SEC-04)
    # 技术说明：nullable=True 兼容历史数据，server_default='system' 用于迁移回填
    user_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        server_default="system",
        comment="User who triggered this loop run (null for legacy data)",
    )
    # 业务说明：各步骤的序列化结果，以JSONB格式存储
    # 技术说明：使用JSONB类型支持高效查询和索引，默认空字典
    steps_json: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, default=dict,
        comment="Serialized list of step results",
    )
    # 业务说明：闭环运行整体状态
    # 技术说明：默认"running"，状态流转：running -> completed/failed
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="running",
        comment="'running' | 'completed' | 'failed'",
    )
    # 业务说明：错误日志，记录闭环运行中的异常信息
    # 技术说明：Text类型支持长文本，null表示无错误
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 业务说明：闭环结果记录创建时间
    # 技术说明：使用_utcnow函数确保UTC时间一致性
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )
    # 业务说明：闭环运行完成时间，null表示尚未完成
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    def __repr__(self) -> str:
        return f"<LoopResultRecord {self.run_id} status={self.status}>"
