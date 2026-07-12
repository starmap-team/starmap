# 服务层 - Services 规范

## 1. 模块概述

Services（服务层）模块是 StarMap 后端的核心业务编排层，负责封装 Neo4j 图查询、业务逻辑编排、外部服务调用等。该模块位于 `backend/app/services/`，包含 12 个核心文件，共约 2332 行代码。

**核心目标**：
- 封装 Neo4j 图数据库查询逻辑
- 编排业务核心层（core/）的调用
- 提供简历解析、匹配诊断、学习路径等业务服务
- 管理应用级资源连接（PG/Neo4j/Redis）

**在系统中的位置**：位于 `backend/app/services/`，被 `api/v1/` 路由层调用，调用 `core/` 层和 `models/` 层。

---

## 2. 文件清单

| 文件路径 | 行数 | 职责 | 主要导出 |
|---------|------|------|---------|
| `backend/app/services/dedup_service.py` | 246 | 去重服务：SimHash 去重、重复检测 | `DedupService`, `find_duplicates` |
| `backend/app/services/graph_overview.py` | 258 | 图谱概览：按级别/技术栈统计 | `fetch_overview_by_level`, `fetch_overview_by_tech_stack` |
| `backend/app/services/graph_serializers.py` | 188 | 图谱序列化器：节点/关系序列化 | `serialize_node`, `serialize_relationship`, `count_positions_neo4j` |
| `backend/app/services/graph_service.py` | 179 | 图谱服务：Neo4j 查询封装（向后兼容包装器） | `fetch_position_graph`, `count_skills_neo4j` |
| `backend/app/services/graph_sync.py` | 265 | 图谱同步：从流水线同步数据到 Neo4j | `sync_from_pipeline`, `sync_positions` |
| `backend/app/services/judge_service.py` | 353 | Judge 服务：LLM-as-Judge 评估 | `JudgeService`, `SampleEvaluation`, `run_judge` |
| `backend/app/services/learning_service.py` | 116 | 学习服务：学习路径生成（向后兼容包装器） | `LearningService`, `generate_learning_path` |
| `backend/app/services/match_service.py` | 293 | 匹配服务：图驱动匹配引擎（向后兼容包装器） | `MatchService`, `run_match` |
| `backend/app/services/neo4j_service.py` | 89 | Neo4j 服务：基础连接封装 | `Neo4jService`, `get_driver` |
| `backend/app/services/recommendation_service.py` | 123 | 推荐服务：基于图的技能推荐 | `RecommendationService`, `recommend_skills` |
| `backend/app/services/resources.py` | 105 | 资源服务：应用级资源连接封装 | `AppResources`, `init_resources`, `healthcheck_resources` |
| `backend/app/services/resume_service.py` | 117 | 简历服务：简历解析、存储、查询 | `ResumeService`, `parse_resume`, `store_resume` |

---

## 3. 架构设计

### 3.1 模块内部结构

```
services/
├── dedup_service.py         ← 去重服务
├── graph_overview.py        ← 图谱概览
├── graph_serializers.py     ← 图谱序列化器
├── graph_service.py          ← 图谱服务（向后兼容）
├── graph_sync.py            ← 图谱同步
├── judge_service.py          ← Judge 服务
├── learning_service.py       ← 学习服务（向后兼容）
├── match_service.py          ← 匹配服务（向后兼容）
├── neo4j_service.py          ← Neo4j 服务
├── recommendation_service.py ← 推荐服务
├── resources.py              ← 资源服务
└── resume_service.py         ← 简历服务
```

### 3.2 依赖关系

```
services/
├── graph_service.py ──► graph_overview.py
│                        graph_serializers.py
│                        neo4j_service.py
│
├── match_service.py ──► core/matching/
│
├── learning_service.py ──► core/learning/
│
├── judge_service.py ──► core/extraction/llm_client.py
│                        core/extraction/prompt.py
│
├── resume_service.py ──► core/extraction/
│
├── graph_sync.py ──► neo4j_service.py
│
├── dedup_service.py ──► core/pipeline/simhash.py
│
├── recommendation_service.py ──► neo4j_service.py
│
└── resources.py ──► db/session.py
```

### 3.3 数据流向

```
HTTP Request
    │
    ▼
┌─────────────────────────┐
│ api/v1/*.py              │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ services/                │
│ ├─ graph_service.py       │  ← Neo4j 查询
│ ├─ match_service.py       │  ← 匹配引擎
│ ├─ judge_service.py       │  ← LLM 评估
│ ├─ resume_service.py      │  ← 简历解析
│ ├─ learning_service.py    │  ← 学习路径
│ └─ resources.py           │  ← 资源管理
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ core/                    │
│ ├─ extraction/           │
│ ├─ matching/             │
│ ├─ learning/             │
│ └─ pipeline/             │
└─────────────────────────┘
```

---

## 4. 接口规范

### 4.1 主要类与函数签名

```python
# graph_service.py
async def fetch_position_graph(driver: Any, position_name: str) -> dict[str, Any]:
    """获取职位的技能图谱。"""

# match_service.py
class MatchService:
    async def run_match(
        self,
        target_position: str,
        person_skills: list[dict[str, Any]],
        threshold: float = 0.6,
        driver: Any = None,
    ) -> dict[str, Any]:
        """运行匹配引擎。"""

# judge_service.py
class JudgeService:
    async def evaluate(
        self,
        raw_jd: str,
        system_output: dict[str, Any],
    ) -> SampleEvaluation:
        """LLM-as-Judge 评估。"""

# resume_service.py
class ResumeService:
    async def parse_resume(self, resume_text: str) -> dict[str, Any]:
        """解析简历。"""

    async def store_resume(self, resume_data: dict[str, Any]) -> str:
        """存储简历。"""

# resources.py
@dataclass
class AppResources:
    pg_engine: AsyncEngine | None = None
    pg_sessionmaker: async_sessionmaker[AsyncSession] | None = None
    neo4j_driver: Any = None
    redis_client: Redis | None = None

async def init_resources() -> AppResources:
    """初始化应用资源。"""

async def healthcheck_resources() -> dict[str, str]:
    """健康检查。"""
```

---

## 5. 编码规范（本模块特有）

### 5.1 图查询封装

```python
# graph_service.py
async def fetch_position_graph(driver: Any, position_name: str) -> dict[str, Any]:
    """获取职位的技能图谱。

    查询逻辑：
    1. 精确匹配职位名称
    2. 查询职位的 required/preferred 技能
    3. 查询技能的前置条件
    4. 返回结构化的图谱数据
    """
```

### 5.2 向后兼容

```python
# match_service.py
# 新代码应直接使用 app.core.matching 中的组件
# 此模块仅作为向后兼容包装器

from app.core.matching.service import MatchService as _MatchService

class MatchService:
    async def run_match(self, ...) -> dict[str, Any]:
        return await _MatchService().run_match(...)
```

### 5.3 反模式

| 反模式 | 说明 | 正确做法 |
|--------|------|---------|
| 在 services/ 中写业务算法 | 职责错位 | 业务算法放在 core/ 中 |
| 直接操作 Neo4j | 绕过封装 | 使用 graph_service.py |
| 跳过 resources.py 创建连接 | 资源泄漏 | 统一使用 init_resources() |
| 硬编码 SQL | 维护困难 | 使用 SQLAlchemy ORM |

---

## 6. 测试规范

### 6.1 对应测试文件

| 被测模块 | 测试文件 | 行数 | 测试类型 |
|---------|---------|------|---------|
| `graph_service.py` | `tests/unit/test_graph_service.py` | 269 | 单元测试 |
| `graph_service.py` (覆盖) | `tests/unit/test_graph_service_coverage.py` | 347 | 单元测试 |
| `graph_service.py` (纯) | `tests/unit/test_graph_service_pure.py` | 101 | 单元测试 |
| `graph_services.py` | `tests/unit/test_graph_services.py` | 896 | 单元测试 |
| `graph_writer.py` | `tests/unit/test_graph_writer_coverage.py` | 510 | 单元测试 |
| `graph_writer.py` (Stage3) | `tests/unit/test_graph_writer_stage3.py` | 187 | 单元测试 |
| `judge_service.py` | `tests/unit/test_judge_service.py` | 560 | 单元测试 |
| `judge_service.py` (辅助) | `tests/unit/test_judge_service_helpers.py` | 266 | 单元测试 |
| `match_service.py` | `tests/unit/test_run_match.py` | 762 | 单元测试 |
| `match_service.py` (辅助) | `tests/unit/test_match_service_helpers.py` | 94 | 单元测试 |
| `resume_service.py` | `tests/unit/test_resume_service.py` | 359 | 单元测试 |
| `dedup_service.py` | `tests/unit/test_dedup_service.py` | 294 | 单元测试 |
| `recommendation.py` | `tests/unit/test_recommendation.py` | 171 | 单元测试 |
| `resources.py` | `tests/unit/test_resources_healthcheck.py` | 40 | 单元测试 |

### 6.2 覆盖率要求

- `graph_service.py`：Neo4j 查询 >= 60%
- `match_service.py`：匹配引擎 >= 60%
- `judge_service.py`：LLM 评估 >= 60%
- `resume_service.py`：简历解析 >= 60%
- `resources.py`：资源管理 >= 60%

### 6.3 Mock 策略

```python
# 测试 graph_service
def test_fetch_position_graph():
    # mock Neo4j driver
    # 验证查询结果格式正确

# 测试 match_service
def test_run_match():
    # mock Neo4j driver
    # mock MatchCache
    # 验证匹配结果
```

---

## 7. 变更管理

### 7.1 修改检查清单

修改 Services 模块时：

- [ ] 是否修改 Neo4j 查询？是 → 确认查询性能
- [ ] 是否修改匹配逻辑？是 → 运行评估套件
- [ ] 是否修改 Judge 评估？是 → 确认评估标准
- [ ] 是否修改资源连接？是 → 确认资源释放

### 7.2 契约影响

| 变更 | 影响 |
|------|------|
| 修改 Neo4j 查询 | 影响图查询结果 |
| 修改匹配逻辑 | 影响匹配结果 |
| 修改 Judge 评估 | 影响评估标准 |
| 修改资源连接 | 影响应用启动 |

### 7.3 迁移要求

- 修改 Neo4j 查询时，必须同步更新 `starmap-contracts/graph_cypher/` 中的 Cypher 查询
- 修改匹配逻辑时，必须运行评估套件确认不降级
- 新增服务时，必须添加对应的测试文件
