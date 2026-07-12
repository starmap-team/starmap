# 业务核心 - Learning 规范

## 1. 模块概述

Learning（学习中心）模块是 StarMap 的核心业务层之一，负责根据匹配诊断结果生成个性化学习路径，并跟踪学习进度。该模块位于 `backend/app/core/learning/`，包含 3 个核心文件，共约 830 行代码。

**核心目标**：
- 基于技能差距诊断结果构建技能前置条件 DAG
- 拓扑排序技能，确保前置技能优先学习
- 基于当前/目标熟练度估算每个技能的学习时长
- 按可用周学时分配学习路径
- 跟踪学习进度，提供进度聚合查询

**在系统中的位置**：位于 `backend/app/core/learning/`，被 `services/learning_service.py` 和 `api/v1/learning.py` 调用，依赖 `models/learning_models.py` 和 Neo4j。

---

## 2. 文件清单

| 文件路径 | 行数 | 职责 | 主要导出 |
|---------|------|------|---------|
| `backend/app/core/learning/__init__.py` | 5 | 学习中心核心模块声明 | 无（仅 docstring） |
| `backend/app/core/learning/path_engine.py` | 543 | 学习路径生成引擎：DAG 构建、拓扑排序、时长估算 | `generate_learning_path`, `LearningPath`, `SkillNode`, `PathSegment` |
| `backend/app/core/learning/progress_tracker.py` | 282 | 进度跟踪器：学习计划 CRUD、进度更新、聚合查询 | `create_plan`, `update_progress`, `get_plan_progress`, `LearningPlan`, `LearningProgress` |

---

## 3. 架构设计

### 3.1 模块内部结构

```
core/learning/
├── __init__.py        ← 模块声明
├── path_engine.py     ← 学习路径生成引擎
└── progress_tracker.py ← 进度跟踪器
```

### 3.2 数据流向

```
HTTP POST /api/v1/learning/generate-path
    │
    ▼
┌─────────────────────────┐
│ api/v1/learning.py       │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ services/learning_service.py │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ core/learning/path_engine.py │
│ ├─ 构建技能前置条件 DAG      │
│ ├─ 拓扑排序                 │
│ ├─ 估算学习时长              │
│ └─ 按周学时分配路径          │
└─────────────────────────┘
    │
    ▼
PostgreSQL (learning_models)
```

### 3.3 学习路径生成流程

```
1. 输入：匹配诊断结果（技能差距列表）
   └─ 每个技能包含：skill_name, gap_level, current_proficiency, target_proficiency

2. 构建 DAG
   └─ 从 Neo4j 查询技能前置条件（PREREQUISITE 关系）
   └─ 使用 fallback 前置条件（当 Neo4j 不可用时）

3. 拓扑排序
   └─ 确保前置技能在目标技能之前

4. 估算时长
   └─ 基础时长：完全缺失 40h，部分掌握 20h，已掌握 2h
   └─ 根据熟练度差距调整

5. 分配路径
   └─ 按可用周学时（默认 10h/周）分配
   └─ 生成阶段性学习计划
```

---

## 4. 接口规范

### 4.1 主要函数签名

```python
# path_engine.py
@dataclass
class SkillNode:
    name: str
    gap_level: str           # "完全缺失" | "部分掌握" | "已掌握"
    estimated_hours: float
    prerequisites: list[str]
    proficiency_target: str

@dataclass
class PathSegment:
    week: int
    skills: list[SkillNode]
    total_hours: float

def generate_learning_path(
    gap_skills: list[dict[str, Any]],
    weekly_hours: float = 10.0,
    neo4j_driver: Any | None = None,
) -> list[PathSegment]:
    """根据技能差距生成个性化学习路径。"""

# progress_tracker.py
async def create_plan(
    session: AsyncSession,
    *,
    position: str,
    skills: list[dict[str, Any]],
    user_id: str = "anonymous",
    match_score: float = 0.0,
    estimated_hours: float = 0.0,
) -> LearningPlan:
    """创建新的学习计划。"""

async def update_progress(
    session: AsyncSession,
    plan_id: uuid.UUID,
    skill_name: str,
    progress_pct: float,
) -> LearningProgress:
    """更新单个技能的学习进度。"""

async def get_plan_progress(
    session: AsyncSession,
    plan_id: uuid.UUID,
) -> dict[str, Any]:
    """获取学习计划的整体进度。"""
```

### 4.2 Fallback 前置条件

```python
# path_engine.py
_FALLBACK_PREREQUISITES: dict[str, list[str]] = {
    "Pandas": ["Python", "NumPy"],
    "NumPy": ["Python"],
    "数据可视化": ["Python", "Pandas"],
    "Tableau": ["数据可视化"],
    "Machine Learning": ["Python", "统计学"],
    "Kubernetes": ["Docker", "Linux"],
    "Microservices": ["REST API", "Docker"],
    "FastAPI": ["Python", "REST API"],
    "Vue.js": ["HTML5", "CSS3", "JavaScript"],
    "TypeScript": ["JavaScript"],
    "Deep Learning": ["Machine Learning", "Python"],
    # ... 更多
}
```

### 4.3 基础学习时长

```python
_BASE_HOURS: dict[str, float] = {
    "完全缺失": 40.0,
    "部分掌握": 20.0,
    "已掌握": 2.0,
}
```

---

## 5. 编码规范（本模块特有）

### 5.1 DAG 构建规范

```python
# 使用 defaultdict + deque 实现拓扑排序
graph = defaultdict(list)
in_degree = defaultdict(int)
queue = deque([node for node in all_nodes if in_degree[node] == 0])

while queue:
    node = queue.popleft()
    ordered.append(node)
    for neighbor in graph[node]:
        in_degree[neighbor] -= 1
        if in_degree[neighbor] == 0:
            queue.append(neighbor)
```

### 5.2 学习时长估算

```python
# 基于熟练度差距调整时长
def estimate_hours(skill: dict) -> float:
    base = _BASE_HOURS.get(skill["gap_level"], 40.0)
    proficiency_gap = _calculate_gap(skill["current"], skill["target"])
    return base * proficiency_gap
```

### 5.3 反模式

| 反模式 | 说明 | 正确做法 |
|--------|------|---------|
| 跳过前置条件检查 | 学习顺序错误 | 使用 DAG 拓扑排序 |
| 硬编码学习时长 | 无法调整 | 使用 `_BASE_HOURS` 配置 |
| 忽略已掌握技能 | 重复学习 | 识别并跳过已掌握技能 |
| 直接操作数据库 | 绕过服务层 | 通过 `progress_tracker.py` 操作 |

---

## 6. 测试规范

### 6.1 对应测试文件

| 被测模块 | 测试文件 | 行数 | 测试类型 |
|---------|---------|------|---------|
| `path_engine.py` | `tests/unit/test_path_engine.py` | 605 | 单元测试 |
| `progress_tracker.py` | `tests/unit/test_progress_tracker.py` | 472 | 单元测试 |
| `learning.py` API | `tests/unit/test_learning_api.py` | 783 | 单元测试 |

### 6.2 覆盖率要求

- `path_engine.py`：DAG 构建、拓扑排序、时长估算 >= 60%
- `progress_tracker.py`：CRUD 操作、进度聚合 >= 60%

### 6.3 Mock 策略

```python
# 测试 path_engine
def test_generate_learning_path_with_prerequisites():
    gap_skills = [
        {"skill": "Pandas", "gap_level": "完全缺失", "current": "beginner", "target": "advanced"},
    ]
    path = generate_learning_path(gap_skills)
    # 验证 Python 和 NumPy 在 Pandas 之前

# 测试 progress_tracker
def test_create_plan():
    # mock AsyncSession
    # 验证学习计划创建正确
```

---

## 7. 变更管理

### 7.1 修改检查清单

修改 Learning 模块时：

- [ ] 是否修改学习时长估算？是 → 更新 `_BASE_HOURS`
- [ ] 是否修改前置条件？是 → 更新 `_FALLBACK_PREREQUISITES`
- [ ] 是否修改进度跟踪逻辑？是 → 确认数据库模型兼容
- [ ] 是否修改学习路径生成？是 → 评估对现有计划的影响

### 7.2 契约影响

| 变更 | 影响 |
|------|------|
| 修改学习时长 | 影响新计划生成，不影响已有计划 |
| 修改前置条件 | 影响新路径生成，可能导致路径变化 |
| 修改进度跟踪 | 影响前端进度展示 |
| 修改数据库模型 | 需 Alembic 迁移 |

### 7.3 迁移要求

- 修改 `_BASE_HOURS` 时，必须评估对现有学习计划的影响
- 修改 `_FALLBACK_PREREQUISITES` 时，必须验证不会引入循环依赖
- 修改数据库模型时，必须通过 Alembic 迁移
