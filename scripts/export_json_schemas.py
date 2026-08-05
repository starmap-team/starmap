"""将 Pydantic Schema 模型导出为 JSON Schema，供前端运行时校验使用。

运行方式：
    cd backend && poetry run python -m scripts.export_json_schemas

输出位置：
    starmap-contracts/schemas/*.schema.json

前端使用这些 JSON Schema 文件进行运行时请求/响应数据校验。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows GBK 控制台防 UnicodeEncodeError

# 确保 backend/ 在 sys.path 中
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_ROOT = _PROJECT_ROOT / "backend"
sys.path.insert(0, str(_BACKEND_ROOT))

from app.schemas import (  # noqa: E402  (sys.path 引导必须先于 app 导入)
    ChangePasswordRequest,
    DomainOverviewItem,
    DomainOverviewResponse,
    ErrorResponse,
    ExtractionRequest,
    ExtractionResult,
    FieldError,
    ForgotPasswordRequest,
    GraphEdge,
    GraphNode,
    GraphOverviewResponse,
    GraphPositionNode,
    GraphSkillNode,
    KAPositionsResponse,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    ImportItem,
    ImportRequest,
    ImportResult,
    ABResultRequest,
    ABTestRequest,
    RegisterVersionRequest,
    SetActiveRequest,
    BatchJudgeRequest,
    BatchJudgeResponse,
    JudgeRequest,
    JudgeSampleResponse,
    PairwiseRequest,
    PairwiseResponse,
    ComprehensiveReport,
    QualityDashboard,
    QualityDetail,
    QualityReport,
    ResumeEvalResponse,
    LoopHistoryResponse,
    LoopRunRequest,
    LoopRunResponse,
    LoopStepResponse,
    SkillGapInput,
    CreatePlanRequest,
    SkillProgressItem,
    PhaseInfo,
    PlanResponse,
    PipelineRunResponse,
    PipelineStatusResponse,
    DataQualityResponse,
    StageInfo,
    PositionListResponse,
    OverviewResponse,
    RealtimePollResponse,
    PositionNode,
    PositionSkillDetailResponse,
    PersonSkillInput,
    MatchOptionsInput,
    MatchRequestInput,
    BatchMatchItem,
    BatchMatchRequest,
    SkillGapDetail,
    MatchResponse,
    ReverseMatchRequest,
    PositionRecommendation,
    ReverseMatchResponse,
    RefreshRequest,
    RefreshResponse,
    ResetPasswordRequest,
    SkillItem,
    SkillNode,
    TokenUser,
    TrendPoint,
    TrendsResponse,
    DistributionResponse,
)

# 按域分组的 Schema
SCHEMA_GROUPS: dict[str, list[tuple[str, type]]] = {
    "common": [
        ("ErrorResponse", ErrorResponse),
        ("FieldError", FieldError),
    ],
    "auth": [
        ("LoginRequest", LoginRequest),
        ("LoginResponse", LoginResponse),
        ("RefreshRequest", RefreshRequest),
        ("RefreshResponse", RefreshResponse),
        ("LogoutRequest", LogoutRequest),
        ("ChangePasswordRequest", ChangePasswordRequest),
        ("ForgotPasswordRequest", ForgotPasswordRequest),
        ("ResetPasswordRequest", ResetPasswordRequest),
        ("TokenUser", TokenUser),
    ],
    "dashboard": [
        ("OverviewResponse", OverviewResponse),
        ("TrendPoint", TrendPoint),
        ("TrendsResponse", TrendsResponse),
        ("DistributionResponse", DistributionResponse),
        ("RealtimePollResponse", RealtimePollResponse),
    ],
    "pipeline": [
        ("StageInfo", StageInfo),
        ("PipelineRunResponse", PipelineRunResponse),
        ("PipelineStatusResponse", PipelineStatusResponse),
        ("DataQualityResponse", DataQualityResponse),
    ],
    "position": [
        ("PositionNode", PositionNode),
        ("SkillNode", SkillNode),
        ("PositionListResponse", PositionListResponse),
    ],
    "graph": [
        ("GraphNode", GraphNode),
        ("GraphEdge", GraphEdge),
        ("GraphOverviewResponse", GraphOverviewResponse),
        ("DomainOverviewItem", DomainOverviewItem),
        ("DomainOverviewResponse", DomainOverviewResponse),
        ("GraphPositionNode", GraphPositionNode),
        ("GraphSkillNode", GraphSkillNode),
        ("KAPositionsResponse", KAPositionsResponse),
        ("PositionSkillDetailResponse", PositionSkillDetailResponse),
    ],
    "extract": [
        ("ExtractionRequest", ExtractionRequest),
        ("ExtractionResult", ExtractionResult),
        ("SkillItem", SkillItem),
    ],
    "judge": [
        ("JudgeRequest", JudgeRequest),
        ("PairwiseRequest", PairwiseRequest),
        ("BatchJudgeRequest", BatchJudgeRequest),
        ("JudgeSampleResponse", JudgeSampleResponse),
        ("PairwiseResponse", PairwiseResponse),
        ("BatchJudgeResponse", BatchJudgeResponse),
    ],
    "quality": [
        ("QualityDetail", QualityDetail),
        ("QualityReport", QualityReport),
        ("QualityDashboard", QualityDashboard),
        ("ResumeEvalResponse", ResumeEvalResponse),
        ("ComprehensiveReport", ComprehensiveReport),
    ],
    "import_jd": [
        ("ImportItem", ImportItem),
        ("ImportRequest", ImportRequest),
        ("ImportResult", ImportResult),
    ],
    "prompt": [
        ("ABResultRequest", ABResultRequest),
        ("ABTestRequest", ABTestRequest),
        ("RegisterVersionRequest", RegisterVersionRequest),
        ("SetActiveRequest", SetActiveRequest),
    ],
    "learning": [
        ("SkillGapInput", SkillGapInput),
        ("CreatePlanRequest", CreatePlanRequest),
        ("SkillProgressItem", SkillProgressItem),
        ("PhaseInfo", PhaseInfo),
        ("PlanResponse", PlanResponse),
    ],
    "loop": [
        ("LoopRunRequest", LoopRunRequest),
        ("LoopStepResponse", LoopStepResponse),
        ("LoopRunResponse", LoopRunResponse),
        ("LoopHistoryResponse", LoopHistoryResponse),
    ],
    "match": [
        ("PersonSkillInput", PersonSkillInput),
        ("MatchOptionsInput", MatchOptionsInput),
        ("MatchRequestInput", MatchRequestInput),
        ("BatchMatchItem", BatchMatchItem),
        ("BatchMatchRequest", BatchMatchRequest),
        ("SkillGapDetail", SkillGapDetail),
        ("MatchResponse", MatchResponse),
        ("ReverseMatchRequest", ReverseMatchRequest),
        ("PositionRecommendation", PositionRecommendation),
        ("ReverseMatchResponse", ReverseMatchResponse),
    ],
}

OUTPUT_DIR = _PROJECT_ROOT / "starmap-contracts" / "schemas"


def main() -> None:
    """导出所有 Schema 为 JSON Schema 文件。"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total_schemas = 0
    for group_name, models in SCHEMA_GROUPS.items():
        definitions: dict[str, dict] = {}
        root_defs: dict[str, dict] = {}
        for model_name, model_cls in models:
            json_schema = model_cls.model_json_schema()
            # Pydantic v2 的 $ref 指向文档根 "#/$defs/X"；把各模型嵌套的 $defs
            # 提升到根文档，避免 ref 悬空（前端运行时校验按根 $defs 解析）。
            nested_defs = json_schema.pop("$defs", None) or {}
            root_defs.update(nested_defs)
            definitions[model_name] = json_schema

        output: dict[str, object] = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": f"StarMap {group_name} schemas",
            "description": f"Auto-generated from backend/app/schemas/{group_name}.py",
            "definitions": definitions,
        }
        if root_defs:
            output["$defs"] = root_defs

        output_path = OUTPUT_DIR / f"{group_name}.schema.json"
        output_path.write_text(
            json.dumps(output, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        total_schemas += len(models)
        print(f"  ✓ {output_path.name} ({len(models)} models)")

    print(f"\n✓ Exported {total_schemas} models to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
