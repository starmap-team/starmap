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
    PositionSkillDetailResponse,
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
from app.schemas.position import (
    PositionListResponse,
    PositionNode,
    SkillNode,
)

__all__ = [
    # common
    "ErrorResponse",
    "FieldError",
    "PaginatedResponse",
    "PaginationMeta",
    # auth
    "ChangePasswordRequest",
    "ForgotPasswordRequest",
    "LoginRequest",
    "LoginResponse",
    "LogoutRequest",
    "RefreshRequest",
    "RefreshResponse",
    "ResetPasswordRequest",
    "TokenUser",
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
    "PositionSkillDetailResponse",
    # extract
    "ExtractionRequest",
    "ExtractionResult",
    "NormalizedSkill",
    "SkillItem",
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
