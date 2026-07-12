# API 契约规范文档

## 1. 模块概述

**职责定位**：StarMap 系统的 API 契约中心，定义前后端共享的数据模型、接口路径、请求/响应格式及验证规则，是前后端协作的唯一真相来源。

**核心目标**：
- 定义完整的 OpenAPI 3.0.3 规范（4496 行，93 路径，102 操作，60 Schema）
- 提供 Pydantic v2 共享模型，确保前后端类型一致性
- 通过 CI 自动校验契约一致性
- 驱动前端 TypeScript 类型自动生成（`openapi-typescript`）

**在系统中的位置**：
- 上游：业务需求、领域模型设计
- 下游：`frontend/src/api/schema.ts`（前端类型）、`backend/`（后端实现）、`crawler/`（数据输出格式）
- 依赖：OpenAPI 3.0.3 规范、Pydantic v2

## 2. 文件清单

| 文件路径 | 行数 | 职责 | 主要导出 |
|---------|------|------|---------|
| `starmap-contracts/openapi.yaml` | ~4496 | OpenAPI 3.0.3 规范：93 路径、102 操作、60 Schema | 无（YAML 文件） |
| `starmap-contracts/models/__init__.py` | ~274 | Pydantic v2 共享模型：ExtractionResult、PositionNode、SkillNode、MatchResult 等 | 多个 Pydantic Model |
| `starmap-contracts/validate.py` | ~179 | CI 契约校验脚本：YAML 语法、模型一致性、operationId 检查 | `main()` |
| `starmap-contracts/CONTRACT_AUDIT.md` | ~200 | 契约审计记录：变更历史、版本说明、兼容性评估 | 无（Markdown） |
| `starmap-contracts/API_INTEGRATION_GUIDE.md` | ~150 | API 集成指南：使用说明、示例代码、常见问题 | 无（Markdown） |
| `starmap-contracts/graph_cypher/` | - | Cypher 查询模板：Neo4j 图数据库查询 | 多个 `.cypher` 文件 |

## 3. 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│  starmap-contracts/                                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ openapi.yaml (4496行)                               │   │
│  │ ├── 系统 (health)                                   │   │
│  │ ├── 信息抽取 (extract/jd, extract/resume)           │   │
│  │ ├── 岗位管理 (positions, positions/{id})              │   │
│  │ ├── 匹配诊断 (match/position)                       │   │
│  │ ├── 演化分析 (evolution/trends, evolution/paths)    │   │
│  │ ├── 质量监控 (quality/dashboard)                    │   │
│  │ ├── 图谱查询 (graph/overview, graph/nodes, edges)   │   │
│  │ ├── 流水线 (pipeline/runs, pipeline/stages)        │   │
│  │ ├── 数据源 (datasources, datasources/{id})         │   │
│  │ ├── 学习路径 (learning/plan, learning/progress)      │   │
│  │ ├── 用户管理 (users, auth)                          │   │
│  │ └── 管理后台 (admin/*)                              │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ models/__init__.py (274行)                          │   │
│  │ ├── ExtractionRequest / ExtractionResult            │   │
│  │ ├── SkillItem / NormalizedSkill / SkillNode         │   │
│  │ ├── PositionNode / GraphNode / GraphEdge           │   │
│  │ ├── MatchRequest / MatchResult / SkillGapDetail     │   │
│  │ ├── QualityReport / QualityDetail                   │   │
│  │ ├── EvolutionTrend / EvolutionAnalyzeRequest        │   │
│  │ ├── Error / AdminStats / SourceConfig               │   │
│  │ ├── AuditItem / AuditQueue                          │   │
│  │ ├── PaginatedPositions / DiscoverRequest            │   │
│  │ └── TaskResponse / EvaluateRequest                │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ validate.py (179行)                                 │   │
│  │ ├── validate_openapi()                              │   │
│  │ ├── validate_models_py()                            │   │
│  │ └── validate_consistency()                          │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Consumers                                                    │
│  ├── frontend/src/api/schema.ts (openapi-typescript 生成)   │
│  ├── backend/ (FastAPI 实现)                                │
│  ├── crawler/ (数据输出格式)                                │
│  └── evaluation/ (评估数据格式)                             │
└─────────────────────────────────────────────────────────────┘
```

## 4. 接口规范

### 4.1 OpenAPI 路径概览

| 路径 | 方法 | 操作 ID | 标签 | 描述 |
|------|------|---------|------|------|
| `/health` | GET | `healthCheck` | 系统 | 健康检查 |
| `/extract/jd` | POST | `extractJd` | 信息抽取 | 职位描述技能抽取 |
| `/extract/resume` | POST | `extractResume` | 信息抽取 | 简历技能抽取 |
| `/positions` | GET | `listPositions` | 岗位管理 | 岗位列表 |
| `/positions/{positionId}` | GET | `getPositionDetail` | 岗位管理 | 岗位详情 |
| `/match/position` | POST | `runMatch` | 匹配诊断 | 岗位-技能匹配诊断 |
| `/evolution/trends` | GET | `getEvolutionTrends` | 演化分析 | 技能演化趋势 |
| `/evolution/paths/{positionId}` | GET | `getEvolutionPaths` | 演化分析 | 岗位演进路径 |
| `/quality/dashboard` | GET | `getQualityDashboard` | 质量监控 | 质量看板数据 |
| `/graph/overview` | GET | `getGraphOverview` | 图谱查询 | 图谱概览 |
| `/pipeline/runs/{runId}` | GET | `getPipelineStatus` | 流水线 | 流水线运行状态 |
| `/datasources` | GET/POST | `listDataSources` / `createDataSource` | 数据源 | 数据源管理 |
| `/learning/plan` | GET/POST | `getLearningPlan` / `createLearningPlan` | 学习路径 | 学习路径管理 |
| `/users/me` | GET | `getCurrentUser` | 用户管理 | 当前用户信息 |
| `/admin/stats` | GET | `getAdminStats` | 管理后台 | 管理统计 |

### 4.2 核心 Schema（models/__init__.py）

```python
# 信息抽取
class ExtractionRequest(BaseModel):
    jd_content: str = Field(min_length=1, description="职位描述文本")
    options: Optional[dict[str, Any]] = Field(default=None, description="抽取选项")

class ExtractionResult(BaseModel):
    position_name: str = Field(default="", description="抽取的岗位名称")
    required_skills: list[SkillItem] = Field(default_factory=list, description="必需技能列表")
    preferred_skills: list[SkillItem] = Field(default_factory=list, description="加分技能列表")
    experience_required: Optional[int] = Field(default=None, description="要求经验年数")
    education_required: Optional[str] = Field(default=None, description="学历要求")
    responsibilities: list[str] = Field(default_factory=list, description="岗位职责描述")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="抽取置信度")
    hallucination_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="幻觉风险评分")
    normalized_skills: list[NormalizedSkill] = Field(default_factory=list, description="归一化后的技能列表")

# 技能节点
class SkillNode(BaseModel):
    skill_id: str = Field(description="技能唯一标识")
    name: str = Field(description="技能展示名称")
    category: SkillCategory = Field(description="技能分类")
    proficiency: Proficiency = Field(description="熟练度等级")
    confidence: float = Field(ge=0.0, le=1.0, description="该技能节点置信度")
    source_count: int = Field(ge=0, description="来源文档计数")

# 岗位节点
class PositionNode(BaseModel):
    position_id: str = Field(description="岗位唯一标识")
    name: str = Field(description="岗位名称")
    industry: str = Field(description="所属行业")
    description: str = Field(description="岗位描述")
    skills_required: list[SkillNode] = Field(description="技能要求列表")
    discovered_at: Optional[datetime] = Field(default=None, description="发现时间")

# 匹配结果
class MatchResult(BaseModel):
    match_id: str = Field(description="匹配结果 ID")
    target_position: str = Field(description="目标岗位")
    match_score: float = Field(ge=0.0, le=1.0, description="总体匹配度")
    matched_skills: list[str] = Field(description="已匹配技能")
    gap_skills: list[str] = Field(description="差距技能")
    recommendations: list[str] = Field(description="学习路径建议")
    missing_required: list[str] = Field(default_factory=list, description="缺失的必备技能")
    missing_bonus: list[str] = Field(default_factory=list, description="缺失的加分技能")
    overall_assessment: str = Field(default="", description="总体评估")
    estimated_learning_time: str = Field(default="", description="预计学习时长")

# 质量报告
class QualityReport(BaseModel):
    precision: float = Field(ge=0.0, le=1.0, description="精度")
    recall: float = Field(ge=0.0, le=1.0, description="召回率")
    f1: float = Field(ge=0.0, le=1.0, description="F1 值")
    warning_level: WarningLevel = Field(description="警戒等级")
    details: list[QualityDetail] = Field(description="详细评估条目")
```

### 4.3 validate.py 校验流程

```python
def main() -> int:
    # 1. 校验 openapi.yaml 是合法 OpenAPI 3.0.3 文档
    validate_openapi()  # 检查 YAML 语法、必填字段、operationId
    
    # 2. 校验 models/__init__.py 是合法 Python
    validate_models_py()  # 编译检查
    
    # 3. 校验 openapi.yaml 与 models 无矛盾
    validate_consistency()  # 字段级快速比对
    
    # 退出码: 0=通过, 1=数据错误, 2=逻辑错误
```

## 5. 编码规范（本模块特有）

### 5.1 OpenAPI 规范约定
- **必须**为每个操作提供 `operationId`（用于生成客户端代码）
- **必须**为每个路径提供 `tags`（用于 API 文档分组）
- **推荐**为每个响应定义完整的 `schema`（包括错误响应）
- 使用 `$ref` 引用共享 schema，避免重复定义

### 5.2 Pydantic 模型约定
- 使用 Pydantic v2 语法（`BaseModel` + `Field()`）
- 字段描述使用中文，便于团队理解
- 数值字段使用 `ge`/`le` 约束范围
- 可选字段使用 `Optional[T]` 或 `T | None`，并提供 `default`
- 列表字段使用 `default_factory=list`

### 5.3 契约变更流程
1. 修改 `openapi.yaml` 或 `models/__init__.py`
2. 运行 `validate.py` 校验一致性
3. 执行 `npm run gen:api` 重新生成 `schema.ts`
4. 更新 `API_INTEGRATION_GUIDE.md`
5. 在 `CONTRACT_AUDIT.md` 中记录变更

### 5.4 反模式
- **禁止**直接修改 `frontend/src/api/schema.ts`（应修改 `openapi.yaml` 后重新生成）
- **禁止**在 `models/__init__.py` 中使用 Pydantic v1 语法
- **禁止**删除已发布的 API 路径（应标记为 deprecated）
- **禁止**在契约中定义前端专有类型（如 Vue 组件 props）

## 6. 测试规范

| 测试文件 | 覆盖范围 | 策略 |
|---------|---------|------|
| `starmap-contracts/validate.py` | YAML 语法、模型一致性、operationId | 命令行执行 |
| `.github/workflows/ci.yml` | CI 自动校验 | GitHub Actions |

**覆盖率要求**：
- `openapi.yaml` 必须通过 YAML 语法校验
- 所有 `paths` 必须有 `operationId`
- `models/__init__.py` 必须能正常编译
- `openapi.yaml` 与 `models/__init__.py` 的 schema 定义无矛盾

**校验命令**：
```bash
cd starmap-contracts
python validate.py
```

## 7. 变更管理

### 修改检查清单

- [ ] 修改 `openapi.yaml` 后是否运行了 `validate.py`？
- [ ] 新增/修改路径是否提供了 `operationId`？
- [ ] 新增/修改 schema 是否在 `models/__init__.py` 中有对应定义？
- [ ] 是否执行了 `npm run gen:api` 重新生成 `schema.ts`？
- [ ] 是否更新了 `API_INTEGRATION_GUIDE.md`？
- [ ] 是否在 `CONTRACT_AUDIT.md` 中记录了变更？
- [ ] 破坏性变更是否通知了前端团队？

### 契约影响
- `openapi.yaml` 变更直接影响 `frontend/src/api/schema.ts` 的生成结果
- `models/__init__.py` 变更直接影响后端 FastAPI 的输入校验
- 字段名变更需同步更新 `crawler/` 的数据输出格式
- API 版本升级需考虑向后兼容性

### 迁移要求
- 新增字段：使用 `Optional` + `default`，保持向后兼容
- 删除字段：标记为 deprecated，至少保留一个版本周期
- 重命名字段：新增别名字段，逐步迁移
- 类型变更：需评估对前后端的影响范围
