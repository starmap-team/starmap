# 业务核心 - Evolution 规范

## 1. 模块概述

Evolution（演化分析）模块是 StarMap 的核心业务层之一，负责追踪职位技能随时间的变化，检测新兴技能趋势，计算信任度评分，并推荐演化路径。该模块位于 `backend/app/core/evolution/`，包含 9 个核心文件，共约 2395 行代码。

**核心目标**：
- 创建和存储职位技能快照（Snapshot）
- 计算快照间的技能差异（Diff）
- 检测新兴技能趋势（Emergence）
- 三层反幻觉防御（Hallucination Guard）
- 信任度评分与聚合（Trust Integration）
- 演化路径推荐（Path Recommender）
- 8 步流水线编排（Orchestrator）

**在系统中的位置**：位于 `backend/app/core/evolution/`，被 `services/` 层和 `api/v1/evolution.py` 调用，依赖 `models/` 层和 Neo4j/PostgreSQL。

---

## 2. 文件清单

| 文件路径 | 行数 | 职责 | 主要导出 |
|---------|------|------|---------|
| `backend/app/core/evolution/__init__.py` | 70 | 公共 API 聚合 | `EvolutionOrchestrator`, `DiffEngine`, `TrustScorer`, `HallucinationGuard`, `EmergenceFinder`, `PathRecommender`, `SnapshotManager` 等 |
| `backend/app/core/evolution/diff_engine.py` | 297 | 技能差异引擎：计算两个快照间的技能变化 | `DiffEngine`, `DiffResult`, `SkillChange`, `ChangeType` |
| `backend/app/core/evolution/emergence_finder.py` | 548 | 新兴技能检测：Z-score 算法检测新兴/上升/下降趋势 | `EmergenceFinder`, `EmergenceReport`, `EmergenceSignal`, `EmergenceLevel` |
| `backend/app/core/evolution/hallucination_guard.py` | 363 | 反幻觉守卫：三层防御（语义验证、来源验证、时间跨度验证） | `HallucinationGuard`, `GuardResult`, `LLMJudgment`, `VerificationStatus` |
| `backend/app/core/evolution/orchestrator.py` | 382 | 演化分析编排器：8 步流水线协调所有组件 | `EvolutionOrchestrator`, `EvolutionResult` |
| `backend/app/core/evolution/path_recommender.py` | 209 | 演化路径推荐：基于 Jaccard 相似度发现 EVOLVES_TO 关系 | `PathRecommender`, `EvolutionPath`, `PathReport` |
| `backend/app/core/evolution/snapshot_manager.py` | 250 | 快照管理器：创建/存储/检索职位技能快照 | `SnapshotManager`, `SnapshotData`, `SkillProfile` |
| `backend/app/core/evolution/timeseries_loader.py` | 75 | 时间序列加载器：加载技能时间序列数据 | `TimeseriesLoader` |
| `backend/app/core/evolution/trust_integration.py` | 201 | 信任度评分：加权评分 + 指数衰减 | `TrustScorer`, `TrustResult`, `TrustFactors`, `TrustLevel` |

---

## 3. 架构设计

### 3.1 模块内部结构

```
core/evolution/
├── __init__.py           ← 公共 API 聚合
├── diff_engine.py        ← 技能差异引擎
├── emergence_finder.py    ← 新兴技能检测
├── hallucination_guard.py ← 反幻觉守卫
├── orchestrator.py        ← 8 步流水线编排
├── path_recommender.py    ← 演化路径推荐
├── snapshot_manager.py    ← 快照管理器
├── timeseries_loader.py   ← 时间序列加载器
└── trust_integration.py   ← 信任度评分
```

### 3.2 8 步演化流水线

```
1. Load snapshots (SnapshotManager)
   └─ 从 PostgreSQL 加载两个时间点的职位快照

2. Compute diff (DiffEngine)
   └─ 集合差集算法检测六类变化：
      - ADDED_REQUIRED (新增必备)
      - ADDED_PREFERRED (新增优先)
      - REMOVED (删除)
      - PROMOTED (优先 → 必备)
      - DEMOTED (必备 → 优先)
      - RETAINED (保留)

3. Score trust (TrustScorer)
   └─ 加权评分：来源权重 0.35 + 时间权重 0.25 + 交叉验证 0.25 + 人工标注 0.15

4. Check hallucination (HallucinationGuard)
   └─ 三层防御：
      - 语义验证（LLM 二次验证）
      - 来源验证（最少 3 个来源）
      - 时间跨度验证（最少 4 周）

5. Detect emergence (EmergenceFinder)
   └─ Z-score 检测：emerging (z > 2.0), rising (z > 1.5), declining (z < -1.5)

6. Discover paths (PathRecommender)
   └─ Jaccard 相似度发现 EVOLVES_TO 关系

7. Save changelog (PostgreSQL)
   └─ 写入 EvolutionChangelog 表

8. Update graph (Neo4j)
   └─ 更新 EVOLVES_TO 关系
```

### 3.3 数据流向

```
HTTP POST /api/v1/evolution/analyze
    │
    ▼
┌─────────────────────────┐
│ api/v1/evolution.py       │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ EvolutionOrchestrator     │
│ ├─ SnapshotManager.load()   │
│ ├─ DiffEngine.compute()     │
│ ├─ TrustScorer.score()      │
│ ├─ HallucinationGuard.check()│
│ ├─ EmergenceFinder.detect() │
│ ├─ PathRecommender.discover()│
│ ├─ Save changelog           │
│ └─ Update graph             │
└─────────────────────────┘
    │
    ▼
PostgreSQL + Neo4j
```

---

## 4. 接口规范

### 4.1 主要类与函数签名

```python
# snapshot_manager.py
class SnapshotManager:
    async def create_snapshot(self, position_name: str, skills: list[dict]) -> SnapshotData: ...
    async def load_snapshot(self, position_name: str, timestamp: datetime) -> SnapshotData: ...

# diff_engine.py
class DiffEngine:
    def compute(self, old: SnapshotData, new: SnapshotData) -> DiffResult: ...

class ChangeType(StrEnum):
    ADDED_REQUIRED = "added_required"
    ADDED_PREFERRED = "added_preferred"
    REMOVED = "removed"
    PROMOTED = "promoted"
    DEMOTED = "demoted"
    RETAINED = "retained"

# trust_integration.py
class TrustScorer:
    def score(self, skill: str, sources: list[str], timestamp: datetime) -> TrustResult: ...

class TrustFactors:
    w_source: float = 0.35      # 来源权重
    w_temporal: float = 0.25   # 时间权重
    w_cross: float = 0.25      # 交叉验证权重
    w_manual: float = 0.15     # 人工标注权重

# hallucination_guard.py
class HallucinationGuard:
    async def check(self, skill: str, context: dict) -> GuardResult: ...

class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    PENDING = "pending"
    REJECTED = "rejected"

# emergence_finder.py
class EmergenceFinder:
    def detect(self, timeseries: list[dict]) -> EmergenceReport: ...

class EmergenceLevel(StrEnum):
    EMERGING = "emerging"      # z > 2.0
    RISING = "rising"          # z > 1.5
    STABLE = "stable"          # -1.5 <= z <= 1.5
    DECLINING = "declining"    # z < -1.5

# path_recommender.py
class PathRecommender:
    def discover_paths(self, position: str, min_similarity: float = 0.6) -> PathReport: ...

# orchestrator.py
class EvolutionOrchestrator:
    async def analyze(self, position_name: str) -> EvolutionResult: ...
```

---

## 5. 编码规范（本模块特有）

### 5.1 信任度评分权重

```python
# config.py
settings.trust_w_source = 0.35
settings.trust_w_temporal = 0.25
settings.trust_w_cross = 0.25
settings.trust_w_manual = 0.15
settings.trust_decay_rate = 0.15
settings.trust_max_sources = 10
settings.trust_verified_threshold = 0.8
settings.trust_pending_threshold = 0.5
```

### 5.2 新兴技能检测阈值

```python
# config.py
settings.emergence_z_emerging = 2.0
settings.emergence_z_rising = 1.5
settings.emergence_z_declining = -1.5
settings.emergence_min_frequency = 3
settings.emergence_min_sources = 3
```

### 5.3 反幻觉三层防御

```python
# hallucination_guard.py
class HallucinationGuard:
    # 第一层：语义验证
    async def _semantic_verify(self, skill: str, context: dict) -> bool: ...

    # 第二层：来源验证
    async def _source_verify(self, skill: str, min_sources: int = 3) -> bool: ...

    # 第三层：时间跨度验证
    async def _temporal_verify(self, skill: str, min_weeks: int = 4) -> bool: ...
```

### 5.4 反模式

| 反模式 | 说明 | 正确做法 |
|--------|------|---------|
| 跳过信任度评分 | 数据不可靠 | 使用 `TrustScorer.score()` |
| 跳过反幻觉检查 | 幻觉风险 | 使用 `HallucinationGuard.check()` |
| 直接修改快照数据 | 数据不一致 | 通过 `SnapshotManager` 操作 |
| 硬编码阈值 | 无法调整 | 使用 `settings` 配置 |
| 跳过时间序列验证 | 趋势误判 | 使用 `TimeseriesLoader` |

---

## 6. 测试规范

### 6.1 对应测试文件

| 被测模块 | 测试文件 | 行数 | 测试类型 |
|---------|---------|------|---------|
| `diff_engine.py` | `tests/unit/test_evolution_diff_engine.py` | 195 | 单元测试 |
| `emergence_finder.py` | `tests/unit/test_evolution_emergence_path.py` | 182 | 单元测试 |
| `orchestrator.py` | `tests/unit/test_evolution_orchestrator.py` | 197 | 单元测试 |
| `orchestrator.py` (集成) | `tests/unit/test_evolution_integration_pipeline.py` | 163 | 单元测试 |
| `trust_integration.py` + `hallucination_guard.py` | `tests/unit/test_evolution_trust_hallucination.py` | 204 | 单元测试 |
| `evolution.py` API | `tests/unit/test_evolution_api.py` | 320 | 单元测试 |
| `evolution.py` 子 API | `tests/unit/test_evolution_sub_api.py` | 569 | 单元测试 |

### 6.2 覆盖率要求

- `diff_engine.py`：六类变化检测 >= 60%
- `emergence_finder.py`：Z-score 计算 >= 60%
- `hallucination_guard.py`：三层防御 >= 60%
- `trust_integration.py`：加权评分 >= 60%
- `path_recommender.py`：Jaccard 相似度 >= 60%
- `orchestrator.py`：8 步流水线 >= 60%
- `snapshot_manager.py`：CRUD 操作 >= 60%

### 6.3 Mock 策略

```python
# 测试 DiffEngine
def test_diff_engine_detects_added_required():
    old = SnapshotData(skills=[...])
    new = SnapshotData(skills=[...])
    result = DiffEngine().compute(old, new)
    assert any(c.change_type == ChangeType.ADDED_REQUIRED for c in result.changes)

# 测试 TrustScorer
def test_trust_scorer_weights():
    scorer = TrustScorer()
    result = scorer.score("Python", sources=["lagou", "zhaopin"], timestamp=datetime.now())
    assert 0 <= result.score <= 1

# 测试 HallucinationGuard
def test_hallucination_guard_rejects_low_sources():
    guard = HallucinationGuard()
    result = guard.check("Python", {"sources": []})
    assert result.status == VerificationStatus.REJECTED
```

---

## 7. 变更管理

### 7.1 修改检查清单

修改 Evolution 模块时：

- [ ] 是否修改 DiffEngine 逻辑？是 → 确认六类变化检测正确
- [ ] 是否修改 TrustScorer 权重？是 → 更新 config.py 并评估影响
- [ ] 是否修改 HallucinationGuard？是 → 确认三层防御完整性
- [ ] 是否修改 EmergenceFinder 阈值？是 → 更新 config.py
- [ ] 是否修改 PathRecommender？是 → 评估对 EVOLVES_TO 关系的影响
- [ ] 是否修改 Orchestrator 流程？是 → 确认 8 步流水线顺序正确

### 7.2 契约影响

| 变更 | 影响 |
|------|------|
| 修改 DiffEngine | 影响演化分析结果，需更新评估 baseline |
| 修改 TrustScorer 权重 | 影响信任度评分，需重新计算历史数据 |
| 修改 HallucinationGuard | 影响反幻觉效果，需评估误杀率 |
| 修改 EmergenceFinder | 影响新兴技能检测，需更新阈值配置 |
| 修改 PathRecommender | 影响路径推荐结果，需评估准确性 |
| 修改 Orchestrator | 影响整个演化流程，需全量回归测试 |

### 7.3 迁移要求

- 修改信任度评分权重时，必须同步更新 `config.py` 和 `.env.example`
- 修改反幻觉规则时，必须评估对现有数据的影响
- 修改阈值时，必须运行评估套件确认不降级
- 新增演化步骤时，必须更新 `orchestrator.py` 和文档
