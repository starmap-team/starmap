# API 路由层规范

## 1. 模块概述

本模块为 StarMap 后端 API 路由层，位于 `backend/app/api/v1/`，包含 22 个路由文件（含 pipeline 子目录），覆盖 14 个功能域，共 5767 行代码。所有路由通过 `router.py` 统一聚合挂载到 `/api/v1` 前缀下。

**核心目标**：
- 提供统一的 HTTP API 接口，处理请求解析、参数校验、调用服务层、返回响应
- 遵循契约优先原则，所有 API 定义与 `starmap-contracts/openapi.yaml` 保持一致
- 实现认证、授权、限流等横切关注点

**在系统中的位置**：位于 `backend/app/api/v1/`，是外部请求进入系统的第一层，依赖 `services/` 层和 `core/` 层。

---

## 2. 文件清单

| 文件路径 | 行数 | 职责 | 主要导出 |
|---------|------|------|---------|
| `backend/app/api/v1/__init__.py` | 1 | API v1 路由包声明 | 无 |
| `backend/app/api/v1/router.py` | 44 | 路由聚合器，统一挂载所有子路由 | `api_router` (APIRouter) |
| `backend/app/api/v1/admin.py` | 278 | 管理后台：数据源评分、系统配置、审核队列 | `router` |
| `backend/app/api/v1/admin_graph_nodes.py` | 246 | 管理后台：图节点管理（CRUD） | `router` |
| `backend/app/api/v1/admin_prompts.py` | 274 | 管理后台：Prompt 模板管理 | `router` |
| `backend/app/api/v1/dashboard.py` | 178 | 数据大屏：实时数据聚合与 SSE 推送 | `router` |
| `backend/app/api/v1/datasource.py` | 335 | 数据源管理：CRUD、健康检查、评分 | `router`, `admin_router` |
| `backend/app/api/v1/evolution.py` | 598 | 演化分析：快照对比、趋势分析、信任度 | `router` |
| `backend/app/api/v1/evolution_career_path.py` | 136 | 演化分析：职业路径推荐 | `router` |
| `backend/app/api/v1/evolution_emerging_alerts.py` | 132 | 演化分析：新兴技能预警 | `router` |
| `backend/app/api/v1/evolution_industry_report.py` | 168 | 演化分析：行业报告生成 | `router` |
| `backend/app/api/v1/extract.py` | 210 | 信息抽取：JD/简历技能抽取 | `router` |
| `backend/app/api/v1/graph.py` | 253 | 图谱查询：节点/关系查询、可视化 | `router` |
| `backend/app/api/v1/judge.py` | 175 | Judge 评估：质量评估、基准测试 | `router` |
| `backend/app/api/v1/learning.py` | 557 | 学习中心：学习路径、进度跟踪 | `router` |
| `backend/app/api/v1/loop.py` | 116 | 闭环验证：验证循环触发与结果 | `router` |
| `backend/app/api/v1/match.py` | 322 | 匹配诊断：技能匹配、差距分析 | `router` |
| `backend/app/api/v1/pipeline/__init__.py` | 4 | Pipeline 路由包声明 | 无 |
| `backend/app/api/v1/pipeline/routes.py` | 576 | 数据流水线：触发、监控、调度 | `router` |
| `backend/app/api/v1/pipeline/schemas.py` | 185 | Pipeline Pydantic Schema 定义 | 多个 Pydantic Model |
| `backend/app/api/v1/pipeline/serializers.py` | 57 | Pipeline 序列化器：DB → Response | `serialize_run`, `serialize_datasource` 等 |
| `backend/app/api/v1/position.py` | 241 | 岗位管理：CRUD、技能关联 | `router` |
| `backend/app/api/v1/quality.py` | 573 | 质量监控：质量评估、趋势分析 | `router` |
| `backend/app/api/v1/quality_trends_alerts.py` | 206 | 质量监控：趋势预警 | `router` |
| `backend/app/api/v1/resume.py` | 99 | 简历解析：上传、解析、存储 | `router` |

---

## 3. 架构设计

### 3.1 路由分组

```
api/v1/
├── router.py              ← 路由聚合器
├── admin.py               ← 管理后台
├── admin_graph_nodes.py   ← 图节点管理
├── admin_prompts.py       ← Prompt 管理
├── dashboard.py           ← 数据大屏
├── datasource.py          ← 数据源管理
├── evolution.py           ← 演化分析（主）
├── evolution_career_path.py      ← 演化：职业路径
├── evolution_emerging_alerts.py  ← 演化：新兴技能
├── evolution_industry_report.py   ← 演化：行业报告
├── extract.py             ← 信息抽取
├── graph.py               ← 图谱查询
├── judge.py               ← Judge 评估
├── learning.py            ← 学习中心
├── loop.py                ← 闭环验证
├── match.py               ← 匹配诊断
├── pipeline/              ← 数据流水线
│   ├── routes.py
│   ├── schemas.py
│   └── serializers.py
├── position.py            ← 岗位管理
├── quality.py             ← 质量监控（主）
├── quality_trends_alerts.py ← 质量：趋势预警
└── resume.py              ← 简历解析
```

### 3.2 依赖关系

```
api/v1/router.py
 ├── admin.py
 ├── admin_graph_nodes.py
 ├── admin_prompts.py
 ├── dashboard.py
 ├── datasource.py (router + admin_router)
 ├── evolution.py
 ├── extract.py
 ├── graph.py
 ├── judge.py
 ├── learning.py
 ├── loop.py
 ├── match.py
 ├── pipeline/routes.py
 ├── position.py
 ├── quality.py
 ├── resume.py
 └── dependencies.py (get_current_user)
```

### 3.3 数据流向

```
HTTP Request
    │
    ▼
┌─────────────────┐
│ FastAPI Router   │  ← 路径匹配、参数解析
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ dependencies.py │  ← 认证/授权/依赖注入
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ services/        │  ← 业务逻辑编排
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ core/            │  ← 领域算法
└─────────────────┘
    │
    ▼
Response (JSON)
```

---

## 4. 接口规范

### 4.1 路由挂载规范

```python
# router.py
api_router = APIRouter(dependencies=[Depends(get_current_user)])
api_router.include_router(graph.router, tags=["图谱查询"])
api_router.include_router(position.router, tags=["岗位管理"])
api_router.include_router(match.router, tags=["匹配诊断"])
# ... 其他路由
```

### 4.2 认证与授权

| 装饰器 | 用途 | 说明 |
|--------|------|------|
| `Depends(get_current_user)` | 默认认证 | 所有路由默认需要认证 |
| `Depends(require_admin)` | Admin 授权 | 管理后台端点额外要求 admin 角色 |

### 4.3 14 个功能域路由清单

| 功能域 | 路由文件 | 主要端点 | Tags |
|--------|---------|---------|------|
| 管理后台 | `admin.py` | `/admin/*` | 管理后台 |
| 图节点管理 | `admin_graph_nodes.py` | `/admin/graph-nodes/*` | 管理后台 |
| Prompt 管理 | `admin_prompts.py` | `/admin/prompts/*` | 管理后台 |
| 数据大屏 | `dashboard.py` | `/dashboard/*` | 数据大屏 |
| 数据源管理 | `datasource.py` | `/datasources/*` | 数据源管理 |
| 演化分析 | `evolution.py` + 子路由 | `/evolution/*` | 演化分析 |
| 信息抽取 | `extract.py` | `/extract/*` | 信息抽取 |
| 图谱查询 | `graph.py` | `/graph/*` | 图谱查询 |
| Judge 评估 | `judge.py` | `/judge/*` | Judge 评估 |
| 学习中心 | `learning.py` | `/learning/*` | 学习中心 |
| 闭环验证 | `loop.py` | `/loop/*` | 闭环验证 |
| 匹配诊断 | `match.py` | `/match/*` | 匹配诊断 |
| 数据流水线 | `pipeline/routes.py` | `/pipeline/*` | 数据流水线 |
| 岗位管理 | `position.py` | `/positions/*` | 岗位管理 |
| 质量监控 | `quality.py` + 子路由 | `/quality/*` | 质量监控 |
| 简历解析 | `resume.py` | `/resumes/*` | 简历解析 |

---

## 5. 编码规范（本模块特有）

### 5.1 路由文件规范

```python
# 每个路由文件的标准结构
from fastapi import APIRouter

router = APIRouter(prefix="/xxx", tags=["xxx"])

@router.get("/")
async def list_items():
    """List all items."""
    ...

@router.post("/")
async def create_item():
    """Create a new item."""
    ...
```

### 5.2 请求/响应模型

- 使用 Pydantic 模型定义请求体和响应体
- Pipeline 模块使用独立的 `schemas.py` 和 `serializers.py`
- 其他模块直接在路由文件中定义 Pydantic 模型

### 5.3 错误处理

- 使用 FastAPI 的 `HTTPException` 返回标准错误响应
- 全局异常处理在 `main.py` 中定义
- 业务异常应在服务层捕获并转换为 HTTP 状态码

### 5.4 反模式

| 反模式 | 说明 | 正确做法 |
|--------|------|---------|
| 在路由层写业务逻辑 | 破坏分层 | 业务逻辑放在 services/ 层 |
| 在路由层直接操作数据库 | 职责错位 | 通过 services/ 层操作 |
| 路由文件过大（>500行） | 难以维护 | 按功能拆分子路由 |
| 缺少请求/响应模型 | 契约不清晰 | 定义 Pydantic 模型 |
| 硬编码状态码 | 不一致 | 使用 `fastapi.status` |

---

## 6. 测试规范

### 6.1 对应测试文件

| 被测路由 | 测试文件 | 行数 | 测试类型 |
|---------|---------|------|---------|
| `admin.py` | `tests/unit/test_admin_endpoints.py` | 853 | 单元测试 |
| `datasource.py` | `tests/unit/test_datasource_api.py` | 527 | 单元测试 |
| `evolution.py` + 子路由 | `tests/unit/test_evolution_api.py` | 320 | 单元测试 |
| `evolution.py` + 子路由 | `tests/unit/test_evolution_sub_api.py` | 569 | 单元测试 |
| `extract.py` | `tests/unit/test_extraction.py` | 126 | 单元测试 |
| `graph.py` | `tests/unit/test_graph_ingest.py` | 170 | 单元测试 |
| `judge.py` | `tests/unit/test_judge_service.py` | 560 | 单元测试 |
| `learning.py` | `tests/unit/test_learning_api.py` | 783 | 单元测试 |
| `loop.py` | `tests/unit/test_loop_api.py` | 57 | 单元测试 |
| `match.py` | `tests/unit/test_run_match.py` | 762 | 单元测试 |
| `pipeline/routes.py` | `tests/unit/test_pipeline_api.py` | 869 | 单元测试 |
| `position.py` | `tests/unit/test_position_repository.py` | 79 | 单元测试 |
| `quality.py` + 子路由 | `tests/unit/test_quality_api.py` | 668 | 单元测试 |
| `resume.py` | `tests/unit/test_resume_service.py` | 359 | 单元测试 |

### 6.2 覆盖率要求

- 每个路由文件 >= 60%
- 重点关注：认证逻辑、参数校验、错误处理

### 6.3 Mock 策略

```python
# 测试路由时 mock 服务层
@pytest.fixture
def mock_match_service():
    return MagicMock()

def test_match_endpoint(mock_match_service):
    # mock services/match_service.py 的返回值
    # 验证路由层正确处理参数和响应
```

---

## 7. 变更管理

### 7.1 修改检查清单

修改 API 路由层时：

- [ ] 是否新增端点？是 → 同步更新 `starmap-contracts/openapi.yaml`
- [ ] 是否修改请求/响应格式？是 → 同步更新 Pydantic Schema
- [ ] 是否修改认证逻辑？是 → 全量回归测试
- [ ] 是否新增路由文件？是 → 在 `router.py` 中注册
- [ ] 是否修改路由前缀？是 → 通知前端团队

### 7.2 契约影响

| 变更 | 影响 |
|------|------|
| 新增端点 | 需更新 openapi.yaml，前端需同步生成 API 客户端 |
| 修改请求体 | 需更新 Pydantic 模型，前端需同步更新类型定义 |
| 修改响应体 | 需更新 openapi.yaml，前端需同步更新类型定义 |
| 修改认证方式 | 影响所有端点，需全量回归测试 |
| 删除端点 | 需评估前端依赖，提供迁移方案 |

### 7.3 迁移要求

- 新增端点时，必须同步更新 `starmap-contracts/openapi.yaml`
- 修改端点时，必须评估对前端的影响
- 删除端点前，必须确认无前端依赖
- 所有变更必须通过 PR Review
