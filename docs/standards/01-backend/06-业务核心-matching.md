# 业务核心 - Matching 规范

## 1. 模块概述

Matching（匹配诊断）模块是 StarMap 的核心业务层之一，负责计算求职者技能与岗位要求的匹配度，识别技能差距，并推荐学习路径。该模块位于 `backend/app/core/matching/`，包含 6 个核心文件，共约 814 行代码。

**核心目标**：
- 计算求职者技能与岗位要求的匹配度
- 识别技能差距（完全缺失、部分掌握、已掌握）
- 基于图查询加载技能前置条件
- 提供线程安全的缓存机制
- 生成学习路径建议

**在系统中的位置**：位于 `backend/app/core/matching/`，被 `services/match_service.py` 和 `api/v1/match.py` 调用，依赖 Neo4j 和 `core/extraction/normalize.py`。

---

## 2. 文件清单

| 文件路径 | 行数 | 职责 | 主要导出 |
|---------|------|------|---------|
| `backend/app/core/matching/__init__.py` | 18 | 公共 API 聚合 | `MatchService`, `MatchCache`, `get_match_cache`, `reset_match_cache`, `score_skill_match`, `build_learning_path` |
| `backend/app/core/matching/cache.py` | 145 | 匹配服务缓存：线程安全缓存，支持 TTL | `MatchCache`, `get_match_cache`, `reset_match_cache` |
| `backend/app/core/matching/constants.py` | 19 | 共享常量：熟练度评分、节点标签、高级关键词 | `PROFICIENCY_SCORE`, `ALLOWED_NODE_LABELS`, `SENIOR_KEYWORDS` |
| `backend/app/core/matching/path_builder.py` | 50 | 学习路径构建：基于技能差距生成学习路径 | `build_learning_path` |
| `backend/app/core/matching/scorer.py` | 159 | 技能匹配评分：精确匹配、模糊匹配、向量匹配 | `score_skill_match`, `_semantic_similarity` |
| `backend/app/core/matching/service.py` | 423 | 匹配服务主类：图驱动匹配引擎 | `MatchService` |

---

## 3. 架构设计

### 3.1 模块内部结构

```
core/matching/
├── __init__.py        ← 公共 API 聚合
├── cache.py           ← 线程安全缓存
├── constants.py       ← 共享常量
├── path_builder.py    ← 学习路径构建
├── scorer.py          ← 技能匹配评分
└── service.py         ← 匹配服务主类
```

### 3.2 数据流向

```
HTTP POST /api/v1/match/diagnose
    │
    ▼
┌─────────────────────────┐
│ api/v1/match.py           │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ services/match_service.py │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ core/matching/service.py  │
│ ├─ cache.py              │  ← 缓存技能前置条件
│ ├─ scorer.py             │  ← 计算匹配度
│ ├─ path_builder.py         │  ← 生成学习路径
│ └─ constants.py          │  ← 熟练度评分
└─────────────────────────┘
    │
    ▼
Neo4j (PREREQUISITE 关系)
```

### 3.3 匹配评分算法

```
1. 精确匹配：技能名称完全匹配 → 1.0
2. 模糊匹配：SequenceMatcher >= 0.7 → ratio
3. 向量匹配：ChromaDB 语义相似度 >= 0.85
4. 熟练度覆盖：根据 PROFICIENCY_SCORE 计算

PROFICIENCY_SCORE = {"了解": 0.35, "熟悉": 0.65, "精通": 0.9}
```

---

## 4. 接口规范

### 4.1 主要类与函数签名

```python
# service.py
class MatchService:
    def __init__(self) -> None: ...
    async def diagnose(
        self,
        resume_skills: list[dict[str, Any]],
        position_name: str,
        neo4j_driver: Any,
    ) -> dict[str, Any]:
        """诊断简历技能与岗位的匹配度。"""

# scorer.py
def score_skill_match(
    resume_skill: str,
    position_skill: str,
    resume_proficiency: str | None = None,
    position_proficiency: str | None = None,
) -> dict[str, Any]:
    """计算两个技能的匹配度。"""

# cache.py
class MatchCache:
    def __init__(self, ttl: int = 300, max_size: int = 1000) -> None: ...
    def get_profile(self, target_position: str) -> dict | None: ...
    def set_profile(self, target_position: str, profile: dict) -> None: ...
    def get_prerequisite_map(self) -> dict | None: ...
    def set_prerequisite_map(self, prereq_map: dict) -> None: ...

# path_builder.py
def build_learning_path(
    gap_skills: list[dict[str, Any]],
    prerequisite_map: dict[str, list[str]],
) -> list[dict[str, Any]]:
    """基于技能差距和前置条件生成学习路径。"""
```

### 4.2 缓存策略

```python
# cache.py
class MatchCache:
    # 缓存过期时间（秒）
    ttl = 300  # 5 分钟

    # 最大缓存条目数
    max_size = 1000

    # 缓存内容
    _profile_cache: dict[str, dict]  # 职位技能画像
    _match_results: dict[str, dict]    # 匹配结果
    _prerequisite_map: dict[str, list]  # 技能前置条件
```

---

## 5. 编码规范（本模块特有）

### 5.1 线程安全

```python
# cache.py
class MatchCache:
    def __init__(self, ...) -> None:
        self._lock = threading.Lock()

    def get_profile(self, target_position: str) -> dict | None:
        with self._lock:
            # 线程安全读取
```

### 5.2 熟练度评分

```python
# constants.py
PROFICIENCY_SCORE: dict[str, float] = {
    "了解": 0.35,
    "熟悉": 0.65,
    "精通": 0.9,
}
```

### 5.3 反模式

| 反模式 | 说明 | 正确做法 |
|--------|------|---------|
| 全局可变状态 | 线程不安全 | 使用 `MatchCache` |
| 跳过缓存 | 性能下降 | 使用 `get_match_cache()` |
| 硬编码阈值 | 无法调整 | 使用配置项 |
| 直接查询 Neo4j | 绕过缓存 | 通过 `MatchService` 操作 |

---

## 6. 测试规范

### 6.1 对应测试文件

| 被测模块 | 测试文件 | 行数 | 测试类型 |
|---------|---------|------|---------|
| `matching/` 整体 | `tests/unit/test_run_match.py` | 762 | 单元测试 |
| `matching/` 覆盖率 | `tests/unit/test_match_coverage_gaps.py` | 679 | 单元测试 |
| `matching/` 可靠性 | `tests/unit/test_match_diagnosis_reliability.py` | 393 | 单元测试 |
| `matching/` 黄金集 | `tests/unit/test_match_golden.py` | 177 | 单元测试 |
| `matching/` 辅助函数 | `tests/unit/test_match_service_helpers.py` | 94 | 单元测试 |

### 6.2 覆盖率要求

- `service.py`：匹配诊断流程 >= 60%
- `scorer.py`：评分算法 >= 60%
- `cache.py`：缓存操作 >= 60%
- `path_builder.py`：路径构建 >= 60%

### 6.3 Mock 策略

```python
# 测试 MatchService
def test_diagnose_with_prerequisites():
    # mock Neo4j driver
    # mock MatchCache
    # 验证匹配结果包含技能差距

# 测试 scorer
def test_score_skill_match_exact():
    result = score_skill_match("Python", "Python")
    assert result["score"] == 1.0

def test_score_skill_match_fuzzy():
    result = score_skill_match("Python", "python3")
    assert result["score"] > 0.7
```

---

## 7. 变更管理

### 7.1 修改检查清单

修改 Matching 模块时：

- [ ] 是否修改评分算法？是 → 评估对现有匹配结果的影响
- [ ] 是否修改缓存策略？是 → 确认线程安全
- [ ] 是否修改阈值？是 → 更新配置并评估影响
- [ ] 是否修改 Neo4j 查询？是 → 确认查询性能

### 7.2 契约影响

| 变更 | 影响 |
|------|------|
| 修改评分算法 | 影响匹配结果，需更新评估 baseline |
| 修改缓存策略 | 影响性能，需压力测试 |
| 修改阈值 | 影响匹配灵敏度 |
| 修改 Neo4j 查询 | 影响查询性能 |

### 7.3 迁移要求

- 修改评分算法时，必须运行评估套件确认不降级
- 修改缓存策略时，必须确认线程安全
- 修改阈值时，必须同步更新配置文档
