# StarMap API 契约审计报告

> 生成时间: 2026-07-10
> 审计范围: 全模块前后端接口一致性

## 一、严重问题 (Critical)


### 1.1 编码问题 - 后端文件乱码

**影响范围**: 所有后端 `.py` 文件
**问题描述**: 后端代码文件存在严重的中文乱码（GBK/UTF-8 混用），导致代码不可读且可能引发运行时编码错误。
**示例**:
```python
# backend/app/api/v1/router.py 中的乱码
"""API v1 璺敤鑱氬悎銆?"""
# backend/app/api/v1/extract.py 中的乱码
"""淇℃伅鎶藉彇 API锛氫粠 JD/绠€鍘嗕腑鎻愬彇鎶€鑳藉苟褰掍竴鍖栥€?"""
```

**修复方案**:
1. 将所有后端 `.py` 文件统一转换为 UTF-8 编码
2. 在 `.gitattributes` 中声明 `*.py text eol=lf encoding=utf-8`
3. 在 CI 中添加编码检查步骤

---

### 1.2 API 路径不一致

**影响范围**: 前后端通信
**问题描述**: 
- 后端路由挂载: `app.include_router(api_router, prefix="/api/v1")`
- 前端 axios baseURL: `/api/v1`
- Vite 代理: `'/api'` → `http://localhost:8000`

**风险**: 请求可能被错误路由到 `/api/api/v1/...` 或 `/api/v1/api/v1/...`

**修复方案**:
```typescript
// frontend/vite.config.ts
proxy: {
  '/api/v1': {
    target: process.env.VITE_API_BASE_URL || 'http://localhost:8000',
    changeOrigin: true,
    // 不需要 rewrite，因为后端路径就是 /api/v1
  },
}
```

---

### 1.3 契约与实现偏差

#### 1.3.1 `/match/position` 响应字段不一致

**契约定义** (openapi.yaml):
```yaml
MatchResult:
  required: [match_id, target_position, match_score, matched_skills, gap_skills, recommendations]
  properties:
    match_id:
      type: string
    match_score:
      type: number
      format: float
      minimum: 0
      maximum: 1
    cii:
      type: number
      nullable: true
```

**后端实现** (backend/app/api/v1/match.py):
```python
class MatchResponse(BaseModel):
    match_id: str
    target_position: str
    match_score: float
    matched_skills: list[str]
    gap_skills: list[str]
    recommendations: list[str]
    missing_required: list[str] = []
    missing_bonus: list[str] = []
    skill_gap_detail: list[SkillGapDetail] = []
    overall_assessment: str = ""
    estimated_learning_time: str = ""
    cii: float | None = None
```

**前端期望** (frontend/src/stores/match.ts):
```typescript
export interface MatchResult {
  match_id?: string          // ❌ 可选，但契约要求必填
  match_score: number
  matched_skills: string[]
  gap_skills: string[]
  recommendations: string[]
  target_position?: string    // ❌ 可选，但契约要求必填
  missing_required?: string[]
  missing_bonus?: string[]
  skill_gap_detail?: SkillGap[]
  overall_assessment?: string
  estimated_learning_time?: string
  cii?: number | null
}
```

**偏差**: 
- 契约中 `match_id` 和 `target_position` 是 required，但前端定义为可选
- 后端 `cii` 字段在契约中 nullable，但前端类型定义为 `number | null`

---

#### 1.3.2 `/extract/jd` 响应字段不一致

**契约定义**:
```yaml
ExtractionResult:
  properties:
    position_name: string
    required_skills: array
    preferred_skills: array
    experience_required: integer|null
    education_required: string|null
    responsibilities: string[]
    confidence: number
    hallucination_score: number|null
    normalized_skills: array
```

**后端实现**:
```python
class ExtractionResult(BaseModel):
    position_name: str
    required_skills: list[dict[str, Any]] = []
    preferred_skills: list[dict[str, Any]] = []
    experience_required: int | None = None
    education_required: str | None = None
    responsibilities: list[str] = []
    confidence: float = 0.0
    hallucination_score: float | None = None
    normalized_skills: list[dict[str, Any]] = []
```

**前端期望** (frontend/src/stores/jd.ts):
```typescript
interface JDExtractResult {
  position_name?: string
  required_skills?: { skill?: string; name?: string; category?: string; proficiency?: string }[]
  preferred_skills?: { skill?: string; name?: string; category?: string; proficiency?: string }[]
  experience_required?: number | null
  education_required?: string | null
  responsibilities?: string[]
  confidence?: number
  hallucination_score?: number | null
  normalized_skills?: { original?: string; normalized?: string; method?: string; confidence?: number }[]
  skills?: { name: string; category: string; confidence: number; is_new: boolean }[]
  position?: string
  [key: string]: unknown
}
```

**偏差**:
- 前端额外期望 `skills` 和 `position` 字段，但契约中未定义
- 前端 `required_skills` 中 `skill` 和 `name` 都可选，但后端只返回 `skill`

---

#### 1.3.3 `/graph/overview` 响应字段不一致

**契约定义**:
```yaml
DomainOverviewResponse:
  required: [domains, connections, total_positions, total_skills]
  properties:
    domains:
      type: array
      items:
        type: object
        required: [id, name, position_count, skill_count, color]
```

**后端实现** (backend/app/api/v1/graph.py):
```python
class DomainOverviewResponse(BaseModel):
    domains: list[DomainOverviewItem] = Field(default_factory=list)
    connections: list[GraphEdge] = Field(default_factory=list)
    total_positions: int = 0
    total_skills: int = 0
```

**前端期望** (frontend/src/stores/graph.ts):
```typescript
// 前端通过 request.get(`/graph/overview?group_by=${mode}`) 获取
// 期望返回: { domains?: DomainOverviewItem[]; connections?: DomainConnection[] }
```

**偏差**:
- 契约中 `domains` 和 `connections` 是 required，但后端给了默认值
- 前端未使用 `total_positions` 和 `total_skills`

---

## 二、中等问题 (Major)

### 2.1 类型定义不同步

**问题**: 前端 `frontend/src/api/schema.ts` 是由 `openapi-typescript` 自动生成的，但生成时间未知，可能存在过期。

**检查方法**:
```bash
cd frontend
npm run gen:api  # 检查是否有变更
```

**建议**: 在 CI 中添加自动检查步骤，如果 schema.ts 与 openapi.yaml 不一致则报错。

---

### 2.2 错误处理不一致

**后端错误格式** (FastAPI 默认):
```json
{ "detail": "错误信息" }
```

**前端错误处理** (frontend/src/api/request.ts):
```typescript
const status = error.response?.status
let message = '未知错误，请稍后重试'
if (!error.response) {
  message = '无法连接到服务器，请稍后重试'
} else if (status) {
  message = ERROR_MESSAGES[status] ?? `请求失败 (${status})`
}
```

**问题**: 前端未使用后端返回的 `detail` 字段，而是根据状态码显示固定错误消息。

**修复方案**:
```typescript
// 在前端错误处理中使用后端返回的 detail
const detail = (error.response?.data as any)?.detail
if (detail) {
  message = detail
}
```

---

### 2.3 Loading 状态管理问题

**问题**: 前端全局 loading 通过简单的计数器实现，如果同时发起多个请求，可能在最后一个请求完成前就隐藏 loading。

**当前实现**:
```typescript
let loadingCount = 0
function showLoading() {
  if (loadingCount === 0) { /* 显示 loading */ }
  loadingCount++
}
function hideLoading() {
  loadingCount = Math.max(0, loadingCount - 1)
  if (loadingCount === 0) { /* 隐藏 loading */ }
}
```

**修复方案**: 使用 request ID 管理
```typescript
const activeRequests = new Set<string>()
function showLoading(requestId: string) {
  activeRequests.add(requestId)
  if (activeRequests.size === 1) { /* 显示 loading */ }
}
function hideLoading(requestId: string) {
  activeRequests.delete(requestId)
  if (activeRequests.size === 0) { /* 隐藏 loading */ }
}
```

---

## 三、低等问题 (Minor)

### 3.1 代码注释乱码

**影响**: 可读性
**修复**: 统一转换为 UTF-8

### 3.2 文件名大小写不一致

**问题**: 部分文件使用 PascalCase，部分使用 camelCase
**建议**: 统一使用项目约定的命名规范

### 3.3 未使用的导入

**示例**:
```python
# backend/app/api/v1/match.py
from app.services.match_service import compute_competitiveness, get_match_result, run_match
# `get_match_result` 未在文件中使用
```

---

## 四、修复优先级

| 优先级 | 问题 | 影响 | 修复工作量 |
|--------|------|------|-----------|
| P0 | 后端编码乱码 | 代码不可读，可能引发运行时错误 | 大 |
| P0 | API 路径不一致 | 请求可能失败 | 小 |
| P1 | 契约与实现字段不一致 | 类型不匹配，运行时错误 | 中 |
| P1 | 类型定义不同步 | 编译时无法发现错误 | 小 |
| P1 | 错误处理不一致 | 用户体验差 | 小 |
| P2 | Loading 状态管理 | 并发请求时 UI 异常 | 小 |
| P2 | 代码注释乱码 | 可读性 | 中 |

---

## 五、修复建议

### 5.1 立即修复 (P0)

1. **统一编码**: 将所有后端 `.py` 文件转换为 UTF-8
2. **修复 API 路径**: 确认 Vite 代理配置与后端路由匹配

### 5.2 短期修复 (P1)

1. **同步契约与实现**: 更新后端 Pydantic 模型或前端 TypeScript 类型
2. **建立自动化流程**: 在 CI 中自动检查契约一致性
3. **统一错误处理**: 前后端统一错误格式

### 5.3 中期优化 (P2)

1. **改进 Loading 管理**: 使用 request ID
2. **清理未使用的导入和代码**
3. **添加契约测试**: 确保前后端一致性
