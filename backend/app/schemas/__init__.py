"""StarMap 集中式 Pydantic Schema 定义。

所有 API 请求/响应模型集中管理于此包中，作为前后端数据模型的单点真相源。
每个模块对应一个业务域，模块内按用途分组：

- *_request:  客户端 → 服务端请求体
- *_response: 服务端 → 客户端响应体
- *_node:     图谱/列表中的子对象

命名约定：
- 所有字段使用 snake_case（项目统一约定）
- 每个 Field 必须有 description + 合理的约束（min_length/max_length/ge/le/pattern）
- 响应模型同时用作 FastAPI response_model
"""

from app.schemas.admin import (
    AdminResetPasswordRequest,
    AuditEventOut,
    AuditItem,
    AuditQueueResponse,
    BatchAuditRequest,
    CreateUserRequest,
    DeleteUserRequest,
    GraphNodeItem,
    GraphNodeListResponse,
    PipelineTriggerResponse,
    ReconcileResult,
    ReviewActionRequest,
    ReviewListResponse,
    UpdateUserRequest,
    HealthMetrics,
    SourceCount,
    TruthReport,
    TruthRow,
)
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    RefreshResponse,
    ResetPasswordRequest,
    TokenUser,
)
from app.schemas.common import (
    ErrorResponse,
    FieldError,
    PaginatedResponse,
    PaginationMeta,
)
from app.schemas.datasource import (
    DataSourceCreateRequest,
    DataSourceResponse,
    DataSourceStatsResponse,
    DatasourcesHealthResponse,
    SyncTriggerResponse,
)
from app.schemas.dashboard import (
    DistributionResponse,
    OverviewResponse,
    RealtimePollResponse,
    TrendPoint,
    TrendsResponse,
)
from app.schemas.evolution import (
    CausalAnalysisResponse,
    CausalAssociation,
    CareerPathNode,
    CareerPathResponse,
    ChangelogEntry,
    EmergingAlert,
    EmergingAlertsResponse,
    EmergingSkill,
    EvolutionKpiResponse,
    EvolutionPathEntry,
    EvolutionTrend,
    EvolutionTrendsResponse,
    PortabilityDetail,
    ReviewQueueItem,
    SnapshotEntry,
    IndustryReportResponse,
    SkillTrendItem,
)
from app.schemas.extract import (
    ExtractionRequest,
    ExtractionResult,
    NormalizedSkill,
    SkillItem,
)
from app.schemas.graph import (
    DomainOverviewItem,
    DomainOverviewResponse,
    GraphEdge,
    GraphNode,
    GraphOverviewResponse,
    GraphPositionNode,
    GraphSkillNode,
    KAPositionsResponse,
    PositionSkillDetailResponse,
)
from app.schemas.import_jd import (
    ImportItem,
    ImportRequest,
    ImportResult,
)
from app.schemas.judge import (
    BatchJudgeRequest,
    BatchJudgeResponse,
    JudgeRequest,
    JudgeSampleResponse,
    PairwiseRequest,
    PairwiseResponse,
)
from app.schemas.learning import (
    AddSkillRequest,
    CreatePlanRequest,
    PhaseInfo,
    PlanResponse,
    RecommendationItem,
    RecommendationsResponse,
    SkillGapInput,
    SkillProgressItem,
    UpdateProgressRequest,
)
from app.schemas.loop import (
    LoopHistoryResponse,
    LoopRunRequest,
    LoopRunResponse,
    LoopStepResponse,
)
from app.schemas.match import (
    BatchMatchItem,
    BatchMatchRequest,
    MatchOptionsInput,
    MatchRequestInput,
    MatchResponse,
    PersonSkillInput,
    PositionRecommendation,
    ReverseMatchRequest,
    ReverseMatchResponse,
    SkillGapDetail,
)
from app.schemas.pipeline import (
    DataQualityResponse,
    PipelineRunResponse,
    PipelineStatusResponse,
    StageInfo,
)
from app.schemas.position import (
    PositionListResponse,
    PositionNode,
    SkillNode,
)
from app.schemas.prompt import (
    ABResultRequest,
    ABTestRequest,
    RegisterVersionRequest,
    SetActiveRequest,
)
from app.schemas.quality import (
    AlertItem,
    QualityAlertsResponse,
    QualityTrendsResponse,
    ComprehensiveReport,
    QualityDashboard,
    QualityDetail,
    QualityReport,
    ResumeEvalResponse,
)
from app.schemas.prompt import (
    ABResultRequest,
    ABTestRequest,
    RegisterVersionRequest,
    SetActiveRequest,
)

__all__ = [
 # common
    "ErrorResponse",
    "FieldError",
    "PaginatedResponse",
    "PaginationMeta",
 # auth
    "ChangePasswordRequest",
    "AdminResetPasswordRequest",
    "AuditEventOut",
    "AuditItem",
    "AuditQueueResponse",
    "BatchAuditRequest",
    "CreateUserRequest",
    "DeleteUserRequest",
    "GraphNodeItem",
    "PipelineTriggerResponse",
    "ReconcileResult",
    "ReviewActionRequest",
    "ReviewListResponse",
    "UpdateUserRequest",
    "GraphNodeListResponse",
    "HealthMetrics",
    "SourceCount",
    "TruthReport",
    "TruthRow",
    "ForgotPasswordRequest",
    "LoginRequest",
    "LoginResponse",
    "LogoutRequest",
    "RefreshRequest",
    "RefreshResponse",
    "ResetPasswordRequest",
    "TokenUser",
 # dashboard
    "DataSourceCreateRequest",
    "DataSourceResponse",
    "DataSourceStatsResponse",
    "DatasourcesHealthResponse",
    "SyncTriggerResponse",
    "DistributionResponse",
    "OverviewResponse",
    "RealtimePollResponse",
    "TrendPoint",
    "TrendsResponse",
 # prompt
    "ABResultRequest",
    "ABTestRequest",
    "RegisterVersionRequest",
    "SetActiveRequest",
 # quality
    "ComprehensiveReport",
    "QualityDashboard",
    "QualityDetail",
    "QualityReport",
    "ResumeEvalResponse",
 # position
    "PositionListResponse",
    "PositionNode",
    "SkillNode",
 # graph
    "DomainOverviewItem",
    "DomainOverviewResponse",
    "GraphEdge",
    "GraphNode",
    "GraphOverviewResponse",
    "GraphPositionNode",
    "GraphSkillNode",
    "KAPositionsResponse",
    "PositionSkillDetailResponse",
    "PipelineRunResponse",
    "PipelineStatusResponse",
    "DataQualityResponse",
    "StageInfo",
 # extract
    "CausalAnalysisResponse",
    "CausalAssociation",
    "CareerPathNode",
    "CareerPathResponse",
    "ChangelogEntry",
    "EmergingAlert",
    "EmergingAlertsResponse",
    "EmergingSkill",
    "EvolutionPathEntry",
    "EvolutionTrend",
    "EvolutionTrendsResponse",
    "PortabilityDetail",
    "ReviewQueueItem",
    "SnapshotEntry",
    "IndustryReportResponse",
    "SkillTrendItem",
    "ExtractionRequest",
    "ExtractionResult",
    "NormalizedSkill",
    "SkillItem",
 # judge
    "BatchJudgeRequest",
    "BatchJudgeResponse",
    "JudgeRequest",
    "JudgeSampleResponse",
    "PairwiseRequest",
    "PairwiseResponse",
 # import_jd
    "ImportItem",
    "ImportRequest",
    "ImportResult",
 # loop
    "LoopHistoryResponse",
    "LoopRunRequest",
    "LoopRunResponse",
    "LoopStepResponse",
 # match
    "BatchMatchItem",
    "BatchMatchRequest",
    "MatchOptionsInput",
    "MatchRequestInput",
    "MatchResponse",
    "PersonSkillInput",
    "PositionRecommendation",
    "ReverseMatchRequest",
    "ReverseMatchResponse",
    "SkillGapDetail",
 # learning
    "AddSkillRequest",
    "CreatePlanRequest",
    "PhaseInfo",
    "PlanResponse",
    "RecommendationItem",
    "RecommendationsResponse",
    "SkillGapInput",
    "SkillProgressItem",
    "UpdateProgressRequest",
]
